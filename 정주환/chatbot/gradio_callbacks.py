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

# =========================
# 공통 헬퍼
# =========================

# 카드 구분용 공통 세퍼레이터 (test.py에서 쓰는 것과 맞추기)
CARD_SEPARATOR = "\n---\n\n"


def _build_reco_md_from_df(df: pd.DataFrame, top_k: int = 5, prefix: str = "최종 추천") -> str:
    """
    final_scorer 결과 DataFrame -> 카드형 markdown으로 변환
    (디버그/설명 줄은 절대 넣지 않는다.)
    """
    blocks: List[str] = []

    # final_scored_df를 reset_index().to_dict(...)로 저장했다가 다시 DataFrame으로 읽으면
    # 'id' 컬럼이 생겨있을 수 있으니 복원해준다.
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
    """
    1단계 RAG로 뽑은 식당 id 리스트 -> 카드형 markdown으로 변환
    """
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
    """'저', '중', '고'를 'final_scorer'가 알아듣는 ['$', '$$']로 변환"""
    if budget_str == "저":
        return ["$", "$$"]
    elif budget_str == "중":
        return ["$$", "$$$"]
    elif budget_str == "고":
        return ["$$$", "$$$$"]
    else:
        # (N/A의 경우 전체)
        return ["$", "$$", "$$$", "$$$$"]


# (좌표 변환 헬퍼)
# (실제 서비스에서는 이 부분을 DB나 API로 대체해야 합니다)
LOCATION_COORDS = {
    "명동역": "37.5630,126.9830",
    "홍대입구역": "37.5570,126.9244",
    "강남역": "37.4980,127.0276",
    "서울역": "37.5547,126.9704",
    "서울시청": "37.5665, 126.9780",  # (Chloe 프로필 대응)
    "시청역": "37.5658,126.9772",
}


def get_start_location_coords(location_name: str) -> str:
    """간단한 장소 이름을 좌표 문자열로 변환"""
    # (일치하는 역 이름이 없으면 '명동역' 좌표를 기본값으로 사용)
    return LOCATION_COORDS.get(location_name, "37.5630,126.9830")


# =========================
# Gradio 콜백
# =========================

def start_chat() -> Tuple[List[Dict], List[Dict], Dict, bool, Dict, gr.update]:
    """
    채팅방이 처음 로드될 때 실행.
    app_main.py에서 6개를 받아가므로 6개를 반환한다.
    """
    try:
        initial_profile = config.PROFILE_TEMPLATE.copy()

        bot_message, updated_profile = llm_utils.call_gpt4o(
            chat_messages=[], current_profile=initial_profile
        )

        gradio_history = [{"role": "assistant", "content": bot_message}]
        llm_history = [{"role": "assistant", "content": bot_message}]

        # user_profile_row_state 초기값
        initial_user_profile_row = {}

        # 추천 출력 영역 초기값
        initial_reco_state = gr.update(
            value="...프로필 설문이 완료되면 여기에 추천 결과가 표시됩니다...", visible=False
        )

        return (
            gradio_history,
            llm_history,
            updated_profile,
            False,
            initial_user_profile_row,
            initial_reco_state,
        )

    except Exception as e:
        print(f"start_chat에서 API 호출 실패: {e}")
        error_msg = (
            f"챗봇 초기화에 실패했습니다. (API 키 오류일 수 있습니다): {e}"
        )

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
) -> Tuple[gr.update, Dict]:
    """
    1단계 RAG -> 2단계 final_scorer 실행 (Fallback 포함)
    여기서는 '카드로 변환하기 좋은 markdown'만 만들어서 리턴한다.
    """
    final_user_profile_row: Dict[str, Any] = {}

    try:
        # --- 1단계: RAG + 필터 메타데이터 생성 ---
        print("--- 1단계: RAG + 점수제 후보군 생성 시작 ---")
        #gr.Info("--- 1단계: 1차 RAG 후보군 생성 중... ---")

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
            print("[오류] 1단계 RAG 검색 결과, 후보군 0개.")
            gr.Warning("1단계 RAG 검색 결과가 0건입니다. 필터를 완화해보세요.")
            return (
                gr.update(
                    value="1단계 RAG 검색 결과가 0건입니다. 필터를 완화해보세요.",
                    visible=True,
                ),
                final_user_profile_row,
            )

        print(f"--- 1단계 RAG 완료 (후보: {len(candidate_ids)}개) ---")
        user_profile_row["final_candidate_ids"] = candidate_ids

        # --- 2단계: final_scorer 시도 ---
        try:
            print(f"--- 2단계: final_scorer 실행 (후보: {len(candidate_ids)}개) ---")
            #gr.Info(f"--- 2단계: {len(candidate_ids)}개 후보 '뚜벅이 점수' 계산 중... (API 호출) ---")

            candidate_df = data_loader.get_restaurants_by_ids(candidate_ids)
            if candidate_df.empty:
                print("[오류] 1단계 ID로 2단계 DataFrame 조회 실패.")
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

            # 슬라이더에서 다시 쓸 수 있도록 state에 저장
            user_profile_row["final_scored_df"] = final_scored_df.reset_index().to_dict(
                "records"
            )

            # ✅ 여기! 깔끔한 카드용 마크다운으로만 만든다
            output_md = _build_reco_md_from_df(
                final_scored_df, top_k=top_k, prefix="최종 추천"
            )

        except GraphHopperDownError as e:
            # --- 2단계 실패 시: 1단계만 사용 ---
            print(
                f"[경고] 2단계 final_scorer 실패: {e}. 1단계 RAG 결과로 대체합니다."
            )
            gr.Warning(
                "⚠️ 뚜벅이 점수 서버가 응답하지 않습니다. 1단계 RAG 검색 결과로 대체합니다."
            )

            output_md = _build_reco_md_from_ids(
                candidate_ids, top_k=top_k, prefix="RAG 추천"
            )

        # 결과 반환
        final_user_profile_row = user_profile_row
        return gr.update(value=output_md, visible=True), final_user_profile_row

    except Exception as e:
        print(f"[오류] 식당 추천 흐름 중 예외 발생: {e}")
        gr.Error(f"추천 생성 중 오류 발생: {e}")
        return (
            gr.update(
                value=f"[오류] 식당 추천 중 오류가 발생했습니다. (세부정보: {e})",
                visible=True,
            ),
            final_user_profile_row,
        )


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
) -> Tuple[List[Dict], List[Dict], Dict, bool, gr.update, Dict]:
    """
    실제로 사용자가 채팅창에 답변을 넣을 때마다 호출되는 함수.
    프로필이 완성되는 순간 추천 흐름을 돌리고, 그 외에는 대화만 이어간다.
    """
    # 1) 사용자 메시지 기록
    gradio_history.append({"role": "user", "content": message})
    llm_history.append({"role": "user", "content": message})

    # 2) LLM 호출해서 다음 질문/응답 생성
    try:
        bot_message, updated_profile = llm_utils.call_gpt4o(
            llm_history, current_profile
        )
    except Exception as e:
        print(f"chat_survey에서 API 호출 실패: {e}")
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

    # LLM 히스토리에 어시스턴트 응답 추가
    llm_history.append({"role": "assistant", "content": bot_message})

    # 3) 프로필이 다 모였는지 확인
    profile_is_complete = all(v is not None for v in updated_profile.values())

    final_bot_message = bot_message
    recommendation_output = gr.update()
    new_user_profile_row_state = user_profile_row_state

    if profile_is_complete and not is_completed:
        print("--- 프로필 완성! 추천 로직 실행 ---")
        #gr.Info("프로필이 완성되었습니다! AI가 맞춤 식당을 추천합니다...")

        profile_html = llm_utils.generate_profile_summary_html(updated_profile)

        recommendation_output, new_user_profile_row_state = await _run_recommendation_flow(
            updated_profile,
            http_client,
            graphhopper_url,
            top_k=topk_value,
        )

        final_bot_message = (
            f"{bot_message}\n{profile_html}\n\n👇 아래에서 추천 결과를 확인하세요! 👇"
        )
        is_completed = True
        print(json.dumps(updated_profile, indent=2, ensure_ascii=False))

    # 4) UI에 보여줄 대화 기록에 어시스턴트 응답 추가
    gradio_history.append({"role": "assistant", "content": final_bot_message})

    # 5) 6개 상태 반환 (app_main.py와 맞춤)
    return (
        gradio_history,
        llm_history,
        updated_profile,
        is_completed,
        recommendation_output,
        new_user_profile_row_state,
    )


def update_recommendations_with_topk(topk_value: int, user_profile_row_state: Dict):
    """
    Top-K 슬라이더 변경 시 호출.
    이미 state에 저장된 결과만으로 '카드 변환하기 좋은 markdown'을 다시 만든다.
    """
    if not user_profile_row_state:
        return gr.update(value="...프로필을 먼저 완성해주세요...", visible=True)

    try:
        # 1) 2단계 결과가 있는 경우
        if user_profile_row_state.get("final_scored_df"):
            df = pd.DataFrame(user_profile_row_state["final_scored_df"])
            md = _build_reco_md_from_df(df, top_k=topk_value, prefix="최종 추천")
            return gr.update(value=md, visible=True)

        # 2) 1단계 후보만 있는 경우
        if user_profile_row_state.get("final_candidate_ids"):
            ids = user_profile_row_state["final_candidate_ids"]
            md = _build_reco_md_from_ids(ids, top_k=topk_value, prefix="RAG 추천")
            return gr.update(value=md, visible=True)

        # 3) 아무것도 없을 때
        return gr.update(value="추천 결과가 없습니다. (State 비어있음)", visible=True)

    except Exception as e:
        print(f"[오류] Top-K 슬라이더 변경 중 오류: {e}")
        return gr.update(
            value=f"[오류] Top-K 슬라이더 변경 중 오류: {e}", visible=True
        )
