
import gradio as gr
import json
import pandas as pd
import httpx
from typing import Dict, Any, List, Tuple

# 내부 모듈 임포트
import config
import llm_utils
import search_logic
import data_loader
from API import final_scorer
from API.final_scorer import GraphHopperDownError

# 🔹 번역 / i18n 모듈
import translator
from i18n_texts import t


# =========================
# 공통 헬퍼
# =========================

CARD_SEPARATOR = "\n---\n\n"  # 카드 구분용 세퍼레이터


def _build_reco_md_from_df(df: pd.DataFrame, top_k: int = 5, prefix: str = "최종 추천") -> str:
    """final_scorer 결과 DataFrame -> 카드형 markdown으로 변환"""
    blocks: List[str] = []
    if "id" in df.columns:
        df = df.set_index("id")
    for i, (store_id, row) in enumerate(df.head(top_k).iterrows(), start=1):
        block = search_logic.format_restaurant_markdown(
            store_id_str=str(store_id),
            rank_prefix=prefix,
            rank_index=i,
        )
        blocks.append(block.strip())
    return CARD_SEPARATOR.join(blocks)


def _build_reco_md_from_ids(store_ids, top_k: int = 5, prefix: str = "RAG 추천") -> str:
    """1단계 RAG로 뽑은 식당 id 리스트 -> 카드형 markdown으로 변환"""
    blocks = []
    for i, store_id in enumerate(list(store_ids)[:top_k], start=1):
        block = search_logic.format_restaurant_markdown(
            store_id_str=str(store_id),
            rank_prefix=prefix,
            rank_index=i,
        )
        blocks.append(block.strip())
    return CARD_SEPARATOR.join(blocks)


def budget_mapper(budget_str: str) -> List[str]:
    """'저', '중', '고'를 최종 스코어러가 알아듣는 가격대 리스트로 변환"""
    if budget_str == "저":
        return ["$", "$$"]
    elif budget_str == "중":
        return ["$$", "$$$"]
    elif budget_str == "고":
        return ["$$$", "$$$$"]
    else:
        return ["$", "$$", "$$$", "$$$$"]


LOCATION_COORDS = {  # 좌표 변환 헬퍼 (데모용)
    "명동역": "37.5630,126.9830",
    "홍대입구역": "37.5570,126.9244",
    "강남역": "37.4980,127.0276",
    "서울역": "37.5547,126.9704",
    "서울시청": "37.5665, 126.9780",
    "시청역": "37.5658,126.9772",
}


def get_start_location_coords(location_name: str) -> str:
    return LOCATION_COORDS.get(location_name, "37.5630,126.9830")


# =========================
# Gradio 콜백
# =========================

def start_chat(selected_lang: str = "ko") -> Tuple[List[Dict], List[Dict], Dict, bool, Dict, gr.update]:
    """
    채팅방이 처음 로드될 때 실행.
    - GPT에게 첫 질문을 시키지 않고, i18n 고정 문구(first_question) 사용
    - 화면에는 selected_lang으로, LLM 내부는 ko로 저장
    """
    user_lang = selected_lang or "ko"

    try:
        initial_profile = config.PROFILE_TEMPLATE.copy()

        # 1) 첫 질문(한국어 고정) - i18n 사전 사용
        first_msg_ko = t("first_question", "ko")

        # 2) 화면엔 선택 언어로
        first_msg_display = t("first_question", user_lang)

        # 3) UI 히스토리(사용자 언어) / LLM 히스토리(한국어)
        gradio_history = [{"role": "assistant", "content": first_msg_display}]
        llm_history = [{"role": "assistant", "content": first_msg_ko}]

        # 4) 추천 영역 placeholder도 언어별
        initial_user_profile_row: Dict[str, Any] = {}
        initial_reco_state = gr.update(
            value=t("initial_reco_placeholder", user_lang),
            visible=False,
        )

        return (
            gradio_history,
            llm_history,
            initial_profile,
            False,
            initial_user_profile_row,
            initial_reco_state,
        )

    except Exception as e:
        print(f"start_chat에서 초기화 실패: {e}")
        error_msg = f"챗봇 초기화에 실패했습니다. (환경 설정 문제일 수 있습니다): {e}"

        initial_user_profile_row = {}
        error_reco_state = gr.update(value="챗봇 초기화 실패...", visible=True)

        return (
            [{"role": "assistant", "content": error_msg}],
            [],
            config.PROFILE_TEMPLATE.copy(),
            False,
            initial_user_profile_row,
            error_reco_state,
        )


async def _run_recommendation_flow(
    profile_data: dict,
    http_client: httpx.AsyncClient,
    graphhopper_url: str,
    top_k: int,
    user_lang: str = "ko",
) -> Tuple[gr.update, Dict]:
    """
    1단계 RAG -> 2단계 final_scorer 실행 (Fallback 포함)
    결과 마크다운은 마지막에 user_lang에 맞게 번역한다.
    """
    final_user_profile_row: Dict[str, Any] = {}

    try:
        # --- 1단계: RAG + 필터 메타데이터 생성 ---
        profile_summary = llm_utils.generate_profile_summary_text_only(profile_data)

        filter_dict = search_logic.create_filter_metadata(profile_data)
        filter_metadata_json = json.dumps(filter_dict, ensure_ascii=False)

        user_profile_row = {
            "name": profile_data.get("name", "N/A"),
            "user_id": "live_user",
            "rag_query_text": profile_summary,
            "filter_metadata_json": filter_metadata_json,
            "final_candidate_ids": [],
            "final_scored_df": None,
        }

        candidate_ids = search_logic.get_rag_candidate_ids(
            user_profile_row, n_results=config.RAG_REQUEST_N_RESULTS
        )

        if not candidate_ids:
            warn_ko = "1단계 RAG 검색 결과가 0건입니다. 필터를 완화해보세요."
            warn = translator.translate_text(warn_ko, "ko", user_lang) if user_lang != "ko" else warn_ko
            gr.Warning(warn)
            return (
                gr.update(value=warn, visible=True),
                final_user_profile_row,
            )

        user_profile_row["final_candidate_ids"] = candidate_ids

        # --- 2단계: final_scorer 시도 ---
        try:
            candidate_df = data_loader.get_restaurants_by_ids(candidate_ids)
            if candidate_df.empty:
                raise Exception("1단계 ID로 2단계 DataFrame 조회 실패.")

            user_start_coords = get_start_location_coords(
                profile_data.get("start_location")
            )
            user_price_prefs = budget_mapper(profile_data.get("budget"))

            final_scored_df = await final_scorer.calculate_final_scores_async(
                candidate_df=candidate_df,
                user_start_location=user_start_coords,
                user_price_prefs=user_price_prefs,
                async_http_client=http_client,
                graphhopper_url=graphhopper_url,
            )

            user_profile_row["final_scored_df"] = final_scored_df.reset_index().to_dict("records")
            output_md_ko = _build_reco_md_from_df(final_scored_df, top_k=top_k, prefix="최종 추천")

        except GraphHopperDownError as e:
            warn_ko = "⚠️ 뚜벅이 점수 서버가 응답하지 않습니다. 1단계 RAG 검색 결과로 대체합니다."
            warn = translator.translate_text(warn_ko, "ko", user_lang) if user_lang != "ko" else warn_ko
            gr.Warning(warn)
            output_md_ko = _build_reco_md_from_ids(candidate_ids, top_k=top_k, prefix="RAG 추천")

        final_user_profile_row = user_profile_row

        output_md = translator.translate_text(output_md_ko, "ko", user_lang) if user_lang != "ko" else output_md_ko
        return gr.update(value=output_md, visible=True), final_user_profile_row

    except Exception as e:
        err_ko = f"[오류] 식당 추천 중 오류가 발생했습니다. (세부정보: {e})"
        err = translator.translate_text(err_ko, "ko", user_lang) if user_lang != "ko" else err_ko
        gr.Error(err)
        return (gr.update(value=err, visible=True), final_user_profile_row)


async def chat_survey(
    message: str,
    gradio_history: List[Dict],
    llm_history: List[Dict],
    current_profile: Dict,
    is_completed: bool,
    topk_value: int,
    user_profile_row_state: Dict,
    http_client: httpx.AsyncClient,
    graphhopper_url: str,
    selected_lang: str,
) -> Tuple[List[Dict], List[Dict], Dict, bool, gr.update, Dict]:
    """
    사용자 입력마다 호출.
    - GPT는 한국어로만 대화
    - 화면에는 선택 언어로 번역된 답변 표시
    """
    user_lang = selected_lang or "ko"

    # 1) UI 기록: 사용자 원문 그대로
    gradio_history.append({"role": "user", "content": message})

    # 2) GPT 기록: 한국어 버전으로
    internal_user_text = message if user_lang == "ko" else translator.translate_text(message, user_lang, "ko")
    llm_history.append({"role": "user", "content": internal_user_text})

    # 3) GPT 호출
    try:
        bot_internal_message, updated_profile = llm_utils.call_gpt4o(
            llm_history,
            current_profile,
        )
    except Exception as e:
        error_msg = f"API 호출 중 오류가 발생했습니다: {e}"
        gradio_history.append({"role": "assistant", "content": error_msg})
        return (
            gradio_history,
            llm_history,
            current_profile,
            is_completed,
            gr.update(),
            user_profile_row_state,
        )

    # 4) 사용자 언어로 번역
    bot_message_for_user = bot_internal_message if user_lang == "ko" else translator.translate_text(
        bot_internal_message, "ko", user_lang
    )

    # LLM 히스토리(한국어) 업데이트
    llm_history.append({"role": "assistant", "content": bot_internal_message})

    # 5) 프로필 완성 여부
    profile_is_complete = all(v is not None for v in updated_profile.values())

    final_bot_message_for_user = bot_message_for_user
    recommendation_output = gr.update()
    new_user_profile_row_state = user_profile_row_state

    # 6) 프로필이 완성되면 추천 실행
    if profile_is_complete and not is_completed:
        profile_html = llm_utils.generate_profile_summary_html(updated_profile)

        recommendation_output, new_user_profile_row_state = await _run_recommendation_flow(
            updated_profile,
            http_client,
            graphhopper_url,
            top_k=topk_value,
            user_lang=user_lang,
        )

        suffix = t("profile_complete_suffix", user_lang)
        final_bot_message_for_user = f"{bot_message_for_user}\n{profile_html}{suffix}"
        is_completed = True

    # 7) UI에 어시스턴트 응답 기록
    gradio_history.append({"role": "assistant", "content": final_bot_message_for_user})

    return (
        gradio_history,
        llm_history,
        updated_profile,
        is_completed,
        recommendation_output,
        new_user_profile_row_state,
    )


def update_recommendations_with_topk(
    topk_value: int,
    user_profile_row_state: Dict,
    user_lang: str = "ko",
):
    """
    Top-K 변경 때 state만으로 마크다운 재생성.
    최종 출력은 user_lang에 맞게 번역.
    """
    if not user_profile_row_state:
        msg_ko = "...프로필을 먼저 완성해주세요..."
        msg = translator.translate_text(msg_ko, "ko", user_lang) if user_lang != "ko" else msg_ko
        return gr.update(value=msg, visible=True)

    try:
        if user_profile_row_state.get("final_scored_df"):
            df = pd.DataFrame(user_profile_row_state["final_scored_df"])
            md_ko = _build_reco_md_from_df(df, top_k=topk_value, prefix="최종 추천")
        elif user_profile_row_state.get("final_candidate_ids"):
            ids = user_profile_row_state["final_candidate_ids"]
            md_ko = _build_reco_md_from_ids(ids, top_k=topk_value, prefix="RAG 추천")
        else:
            md_ko = "추천 결과가 없습니다. (State 비어있음)"

        md = translator.translate_text(md_ko, "ko", user_lang) if user_lang != "ko" else md_ko
        return gr.update(value=md, visible=True)

    except Exception as e:
        err_ko = f"[오류] Top-K 슬라이더 변경 중 오류: {e}"
        err = translator.translate_text(err_ko, "ko", user_lang) if user_lang != "ko" else err_ko
        return gr.update(value=err, visible=True)
