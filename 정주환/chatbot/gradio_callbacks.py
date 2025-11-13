import gradio as gr
import json
import pandas as pd
import httpx
from typing import Dict, Any, List, Tuple, Set
import random

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


def calculate_evaluation_metrics(
    live_reco_ids: List[str],
    preprocessed_reco_ids: List[str],
    ground_truth_set: Set[str],
    k: int
) -> Dict[str, Any]:
  """
  두 개의 추천 목록과 정답(Ground Truth) Set을 받아
  Precision@k, Recall@k를 계산합니다.
  """
  
  if not ground_truth_set:
    print("[평가] Ground Truth가 비어있어 평가를 건너뜁니다.")
    return {"error": "Ground Truth set is empty."}
  
  k_live = min(k, len(live_reco_ids))
  k_preprocessed = min(k, len(preprocessed_reco_ids))

  # 1. 추천 목록을 Set으로 변환 (K개만큼 자름)
  live_reco_set_at_k = set(live_reco_ids[:k_live])
  preprocessed_reco_set_at_k = set(preprocessed_reco_ids[:k_preprocessed])
  
  # 2. 교집합 (Hits) 계산
  hits_live = live_reco_set_at_k.intersection(ground_truth_set)
  hits_preprocessed = preprocessed_reco_set_at_k.intersection(ground_truth_set)

  # 3. 지표 계산
  precision_live = len(hits_live) / k_live if k_live > 0 else 0.0
  recall_live = len(hits_live) / len(ground_truth_set)
  
  precision_preprocessed = len(hits_preprocessed) / k_preprocessed if k_preprocessed > 0 else 0.0
  recall_preprocessed = len(hits_preprocessed) / len(ground_truth_set)

  # 4. 결과 포맷팅
  results = {
    "ground_truth_size": len(ground_truth_set),
    "k_value": k,
    "live_recommendation": {
      "k": k_live,
      "hits": len(hits_live),
      "precision_at_k": precision_live,
      "recall_at_k": recall_live
    },
    "preprocessed_recommendation": {
      "k": k_preprocessed,
      "hits": len(hits_preprocessed),
      "precision_at_k": precision_preprocessed,
      "recall_at_k": recall_preprocessed
    }
  }
  return results


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

def start_chat() -> Tuple[List[Dict], List[Dict], Dict, bool, Dict]:
    """
    채팅방이 처음 로드될 때 실행.
    app_main.py에서 6개를 받아가므로 6개를 반환한다.
    """
    try:
        # 순서대로 질문함
        # (기존) initial_profile = config.PROFILE_TEMPLATE.copy()

        # (수정) 템플릿의 키(key) 순서를 섞어서 새로운 초기 프로필을 생성합니다.
        profile_keys = list(config.PROFILE_TEMPLATE.keys())
        random.shuffle(profile_keys)
        initial_profile = {key: config.PROFILE_TEMPLATE[key] for key in profile_keys}
        
        print(f"[start_chat] 섞인 프로필 키 순서: {list(initial_profile.keys())}")

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
            #initial_reco_state,
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
            #error_reco_state,
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
            
            
            try:
              # 1. Ground Truth 가져오기
              ground_truth_set = search_logic.get_ground_truth_for_user(
                  live_rag_query_text=profile_summary,
                  max_similar_users=5 
              )
              
              # 2. 추천 목록 ID 가져오기
              live_reco_ids = final_scored_df.index.astype(str).tolist()
              
              # (⭐️ 중요: Charlie님이 이 데이터를 profile_data에 넣어두었다고 가정)
              preprocessed_reco_ids = profile_data.get("preprocessed_list", []) 
              if not preprocessed_reco_ids:
                print("[평가] 'preprocessed_list'가 프로필에 없어 평가를 건너뜁니다.")

              # 3. 평가 수행 (K=5 기준)
              evaluation_results = calculate_evaluation_metrics(
                  live_reco_ids=live_reco_ids,
                  preprocessed_reco_ids=preprocessed_reco_ids,
                  ground_truth_set=ground_truth_set,
                  k=5 # (K=5 기준으로 평가)
              )
              
              # 4. 결과 출력
              print("\n--- [추천 성능 평가 결과 (K=5)] ---")
              print(json.dumps(evaluation_results, indent=2, ensure_ascii=False))
              print("----------------------------------\n")

            except Exception as eval_e:
              print(f"[오류] 평가 지표 계산 중 오류 발생: {eval_e}")
            

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
):
    """
    (수정됨: 이 함수는 이제 제너레이터(generator)입니다)
    채팅 답변을 처리하고, 프로필이 완성되면 2단계(대기/결과)로 UI를 업데이트합니다.
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
        yield ( # (오류 상태 반환)
            gradio_history,
            llm_history,
            current_profile,
            is_completed,
            gr.update(),
            user_profile_row_state,
        )
        return # (제너레이터 종료)

    # LLM 히스토리에 어시스턴트 응답 추가
    llm_history.append({"role": "assistant", "content": bot_message})

    # 3) 프로필이 다 모였는지 확인
    profile_is_complete = all(v is not None for v in updated_profile.values())

    final_bot_message = bot_message
    recommendation_output = gr.update()
    new_user_profile_row_state = user_profile_row_state

    if profile_is_complete and not is_completed:
        
        # --- (A) 1차: "대기 메시지" 즉시 반환 ---
        loading_message = "\n\n🤖 프로필 수집이 완료되었습니다! 잠시만 기다려주시면, 수집된 프로필을 기반으로 멋진 음식점을 찾아드릴게요."
        
        # (봇의 마지막 응답 + 로딩 메시지를 채팅창에 추가)
        gradio_history.append({"role": "assistant", "content": f"{bot_message}{loading_message}"})
        
        print("--- 프로필 완성! [1/2] 대기 메시지 전송 (화면 유지) ---")
        
        # (★수정★) is_completed=False를 반환하여 화면을 채팅창에 머무르게 함
        yield (
            gradio_history,
            llm_history,
            updated_profile,
            False, # ⬅️ [핵심 수정] 아직 is_completed=False 입니다.
            gr.update(), # ⬅️ 추천창은 아직 업데이트하지 않습니다.
            user_profile_row_state
        )

        # --- (B) 2차: 오래 걸리는 추천 로직 실행 ---
        print("--- 프로필 완성! [2/2] 추천 로직 실행 ---")
        recommendation_output, new_user_profile_row_state = await _run_recommendation_flow(
            updated_profile,
            http_client,
            graphhopper_url,
            top_k=topk_value,
        )
        
        is_completed = True # (이제 상태를 True로 변경)

        # --- (C) 3차: "최종 결과" 반환 ---
        print("--- 프로필 완성! [2/2] 최종 결과 전송 (화면 전환) ---")
        
        # (★수정★) is_completed=True와 최종 결과를 반환하여 화면을 전환시킴
        yield (
            gradio_history, 
            llm_history,
            updated_profile,
            True, # ⬅️ [핵심 수정] 이제 is_completed=True 입니다.
            recommendation_output, # ⬅️ 실제 식당 HTML이 담김
            new_user_profile_row_state
        )
        
    else:
        # --- (프로필 미완성) ---
        # 평소처럼 챗봇 메시지만 반환
        gradio_history.append({"role": "assistant", "content": bot_message})
        yield (
            gradio_history,
            llm_history,
            updated_profile,
            is_completed, # (False)
            recommendation_output, # (gr.update())
            new_user_profile_row_state
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
