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
from API import final_scorer # (사장님 로직 임포트)
from config import PROFILE_TEMPLATE

# --- 헬퍼 ---

def budget_mapper(budget_str: str) -> List[str]:
    """'저', '중', '고'를 'final_scorer'가 알아듣는 ['$', '$$']로 변환"""
    if budget_str == '저':
        return ['$', '$$']
    elif budget_str == '중':
        return ['$$', '$$$']
    elif budget_str == '고':
        return ['$$$', '$$$$']
    else:
        return ['$', '$$', '$$$', '$$$$'] # (N/A의 경우 전체)

# --- Gradio 콜백 ---

def start_chat():
    try:
        initial_profile = PROFILE_TEMPLATE.copy()

        bot_message = "안녕하세요! 저는 길따라 맛따라 AI입니다 😊\n먼저 성함을 알려주실 수 있을까요?"
        # 또는 call_gpt4o(...) 사용 버전 쓰고 싶으면 그 코드

        gradio_history = [{"role": "assistant", "content": bot_message}]
        llm_history = [{"role": "assistant", "content": bot_message}]

        return gradio_history, llm_history, initial_profile, False, None

    except Exception as e:
        print(f"start_chat에서 API 호출 실패: {e}")
        error_msg = f"챗봇 초기화에 실패했습니다. (API 키 또는 네트워크 오류일 수 있습니다): {e}"

        gradio_history = [{"role": "assistant", "content": error_msg}]
        llm_history = []

        return gradio_history, llm_history, PROFILE_TEMPLATE.copy(), False, None


async def chat_survey(
    message: str, 
    gradio_history: List[Dict], 
    llm_history: List[Dict], 
    current_profile: Dict, 
    is_completed: bool,
    topk_value,                 # ✅ Top-K 슬라이더 값 추가
    user_profile_row_state,     # ✅ 프로필 row state 추가
    http_client: httpx.AsyncClient,
    graphhopper_url: str
) -> Tuple[List[Dict], List[Dict], Dict, bool, gr.update, Dict]:
    """
    사용자가 메시지를 입력할 때마다 실행되는 메인 함수
    (★ 2단계 추천 로직 + Top-K 반영 버전 ★)
    """
    
    # 1. 사용자 메시지 추가
    gradio_history.append({"role": "user", "content": message})
    llm_history.append({"role": "user", "content": message})
    
    # 2. gpt-4.1-mini API 호출 (정보 수집)
    try:
        bot_message, updated_profile = llm_utils.call_gpt4o(llm_history, current_profile)
    except Exception as e:
        print(f"chat_survey에서 API 호출 실패: {e}")
        error_msg = f"API 호출 중 오류가 발생했습니다: {e}"
        gradio_history.append({"role": "assistant", "content": error_msg})
        # ✅ 항상 6개 리턴
        return gradio_history, llm_history, current_profile, is_completed, gr.update(), user_profile_row_state

    # 3. 봇 응답 추가 (LLM API용)
    llm_history.append({"role": "assistant", "content": bot_message})

    # --- 4. 완료 여부 확인 및 ★ 2단계 추천 실행 ★ ---
    final_bot_message = bot_message
    recommendation_string = gr.update() 
    
    # 프로필의 모든 값이 None이 아닌지 확인
    profile_is_complete = all(v is not None for v in updated_profile.values())
    
    if profile_is_complete and not is_completed:
        print("--- 프로필 완성! 1단계, 2단계 추천을 순차 실행합니다. ---")
        gr.Info("프로필이 완성되었습니다! AI가 요약 및 식당 추천을 생성 중입니다...")

        # (A) 구어체 요약 (RAG 텍스트) 생성
        chat_message_html, raw_summary_text = llm_utils.generate_profile_summary(updated_profile)
        
        # (B) 필터 메타데이터 생성
        filter_dict = search_logic.create_filter_metadata(updated_profile)
        filter_metadata_json = json.dumps(filter_dict, ensure_ascii=False)
        
        # (C) 1단계 검색용 'user_profile_row' 생성
        user_profile_row = {
            "name": updated_profile.get("name", "N/A"),
            "user_id": "live_user",
            "rag_query_text": raw_summary_text,
            "filter_metadata_json": filter_metadata_json
        }

        try:
            # --- (★ 1단계: 챗봇 RAG 검색) ---
            candidate_ids = search_logic.get_rag_candidate_ids(
                user_profile_row,
                n_results=50  # (챗봇이 50개 후보군 생성)
            )
            
            if not candidate_ids:
                raise Exception("1단계 RAG 검색 결과, 후보군 0개.")

            # --- (★ 2단계: final_scorer 호출) ---
            print(f"\n--- 2단계: final_scorer 실행 (후보: {len(candidate_ids)}개) ---")
            
            candidate_df = data_loader.get_restaurants_by_ids(candidate_ids)
            if candidate_df.empty:
                raise Exception("1단계 ID로 2단계 DataFrame 조회 실패.")

            # 시작 위치
            user_start_location = updated_profile.get('start_location', '명동역')
            if user_start_location == '명동역':
                user_start_coords = "37.5630,126.9830"
            elif user_start_location == '홍대입구역':
                user_start_coords = "37.5570,126.9244"
            elif user_start_location == '강남역':
                user_start_coords = "37.4980,127.0276"
            else:
                user_start_coords = "37.5630,126.9830"  # 기본값 명동역
            
            user_price_prefs = budget_mapper(updated_profile.get('budget'))

            # 2단계 점수 계산
            final_scored_df = await final_scorer.calculate_final_scores_async(
                candidate_df=candidate_df,
                user_start_location=user_start_coords,
                user_price_prefs=user_price_prefs,
                async_http_client=http_client,
                graphhopper_url=graphhopper_url
            )

            # --- (★ 3단계: Top-K 반영해서 최종 결과 포맷팅) ---
            k = int(topk_value) if topk_value is not None else 10  # ✅ 슬라이더 값 반영
            top_results = final_scored_df.head(k)
            
            output_string = f"\n\n---\n\n### 🤖 {updated_profile['name']}님을 위한 최종 추천 (뚜벅이 점수 포함!)\n\n"
            
            for i, (store_id, row) in enumerate(top_results.iterrows()):
                output_string += search_logic.format_restaurant_markdown(
                    store_id_str=str(store_id),
                    rank_prefix="최종 추천",
                    rank_index=i + 1
                )
                # (디버깅용 점수 출력)
                output_string += (
                    f"  - (Debug: Final={row['final_score']:.2f} | "
                    f"Travel={row['score_travel']:.2f} | "
                    f"Friend={row['score_friendliness']:.2f})\n\n---\n\n"
                )

            recommendation_string = gr.update(value=output_string, visible=True)
            # ✅ state에 저장
            user_profile_row_state = user_profile_row
            
        except Exception as e:
            print(f"[오류] 2단계 추천 실행 중 오류: {e}")
            reco_error_msg = (
                f"\n\n[오류] 식당 추천 중 오류가 발생했습니다.\n"
                f"(세부정보: {e})\n"
                f"1단계 후보군 생성 또는 2단계 점수 계산에 실패했습니다."
            )
            recommendation_string = gr.update(value=reco_error_msg, visible=True)

        # (최종 봇 메시지 조합)
        final_bot_message = f"{bot_message}\n{chat_message_html}\n\n👇 아래에서 최종 추천 결과를 확인하세요! 👇"
        is_completed = True 
        print(json.dumps(updated_profile, indent=2, ensure_ascii=False))

    # 5. Gradio 챗봇 기록 업데이트 (UI용)
    gradio_history.append({"role": "assistant", "content": final_bot_message})
    
    # 6. (6개 상태 반환: chatbot, llm, profile, is_completed, 추천, user_profile_row_state)
    return gradio_history, llm_history, updated_profile, is_completed, recommendation_string, user_profile_row_state
