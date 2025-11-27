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
# (final_scorer에서 GraphHopperDownError도 임포트)
from API import final_scorer
from API.final_scorer import GraphHopperDownError

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

# (좌표 변환 헬퍼)
# (실제 서비스에서는 이 부분을 DB나 API로 대체해야 합니다)
LOCATION_COORDS = {
    "명동역": "37.5630,126.9830",
    "홍대입구역": "37.5570,126.9244",
    "강남역": "37.4980,127.0276",
    "서울역": "37.5547,126.9704",
    "서울시청": "37.5665, 126.9780", # (Chloe 프로필 대응)
    "시청역": "37.5658,126.9772",
}

def get_start_location_coords(location_name: str) -> str:
    """간단한 장소 이름을 좌표 문자열로 변환"""
    # (일치하는 역 이름이 없으면 '명동역' 좌표를 기본값으로 사용)
    return LOCATION_COORDS.get(location_name, "37.5630,126.9830") 

# --- Gradio 콜백 ---

def start_chat() -> Tuple[List[Dict], List[Dict], Dict, bool, Dict, gr.update]: 
    """
    (수정됨: 6개 반환)
    채팅방이 처음 로드될 때 실행.
    (ValueError: 6 needed, 5 returned 오류 해결)
    """
    try:
        initial_profile = config.PROFILE_TEMPLATE.copy()
        
        bot_message, updated_profile = llm_utils.call_gpt4o(
            chat_messages=[], 
            current_profile=initial_profile
        )
        
        gradio_history = [{"role": "assistant", "content": bot_message}]
        llm_history = [{"role": "assistant", "content": bot_message}]
        
        # (5번째: user_profile_row_state 초기값)
        initial_user_profile_row = {} # (None 대신 빈 딕셔너리)
        
        # (6번째: recommendation_output 초기값)
        initial_reco_state = gr.update(
            value="...프로필 설문이 완료되면 여기에 추천 결과가 표시됩니다...",
            visible=False 
        )
        
        return gradio_history, llm_history, updated_profile, False, initial_user_profile_row, initial_reco_state 

    except Exception as e:
        print(f"start_chat에서 API 호출 실패: {e}")
        error_msg = f"챗봇 초기화에 실패했습니다. (API 키 오류일 수 있습니다): {e}"
        
        initial_user_profile_row = {}
        error_reco_state = gr.update(
            value="챗봇 초기화 실패...", 
            visible=True
        )
        
        return [{"role": "assistant", "content": error_msg}], [], config.PROFILE_TEMPLATE.copy(), False, initial_user_profile_row, error_reco_state 

async def _run_recommendation_flow(
    profile_data: dict, 
    http_client: httpx.AsyncClient, 
    graphhopper_url: str,
    top_k: int # (★ topk_value를 top_k로 받음)
) -> Tuple[gr.update, Dict]:
    """ 
    (신규 헬퍼 함수)
    1단계 RAG -> 2단계 final_scorer 실행 (Fallback 포함) 
    (user_profile_row도 반환하도록 수정)
    """
    
    final_user_profile_row = {}
    
    try:
        # --- 1단계: RAG + 점수제 후보군 생성 ---
        print("--- 1단계: RAG + 점수제 후보군 생성 시작 ---")
        gr.Info("--- 1단계: 1차 RAG 후보군 생성 중... ---")
        
        profile_summary = llm_utils.generate_profile_summary_text_only(profile_data)
        
        # (AttributeError: 'llm_utils' has no 'create_filter_metadata' 해결)
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
            user_profile_row,
            n_results=config.RAG_REQUEST_N_RESULTS
        )
        
        if not candidate_ids:
            print("[오류] 1단계 RAG 검색 결과, 후보군 0개.")
            gr.Warning("1단계 RAG 검색 결과가 0건입니다. 필터를 완화해보세요.")
            return gr.update(value="1단계 RAG 검색 결과가 0건입니다. 필터를 완화해보세요."), final_user_profile_row

        print(f"--- 1단계 RAG 완료 (후보: {len(candidate_ids)}개) ---")
        user_profile_row["final_candidate_ids"] = candidate_ids 

        # --- [ 2단계 Fallback 로직 시작 ] ---
        try:
            # --- 2단계 (A): final_scorer (뚜벅이 점수) 실행 ---
            print(f"--- 2단계: final_scorer 실행 (후보: {len(candidate_ids)}개) ---")
            gr.Info(f"--- 2단계: {len(candidate_ids)}개 후보 '뚜벅이 점수' 계산 중... (API 호출) ---")
            
            candidate_df = data_loader.get_restaurants_by_ids(candidate_ids)
            
            if candidate_df.empty:
                 print("[오류] 1단계 ID로 2단계 DataFrame 조회 실패.")
                 raise Exception("1단계 ID로 2단계 DataFrame 조회 실패.")

            user_start_coords = get_start_location_coords(profile_data.get('start_location'))
            user_price_prefs = budget_mapper(profile_data.get('budget'))
            
            final_scored_df = await final_scorer.calculate_final_scores_async(
                candidate_df=candidate_df,
                user_start_location=user_start_coords,
                user_price_prefs=user_price_prefs,
                async_http_client=http_client,
                graphhopper_url=graphhopper_url
            )
            
            # (DataFrame은 JSON 직렬화 불가 -> to_dict)
            user_profile_row["final_scored_df"] = final_scored_df.to_dict('records')
            
            print("--- 3단계: 최종 결과 포맷팅 (2단계 기준) ---")
            gr.Info("--- 3단계: '뚜벅이 점수' 포함 최종 추천 생성 중... ---")
            
            top_k_df = final_scored_df.head(top_k) # (★ top_k 사용)
            output_md = "### 🤖 '뚜벅이 점수' 포함 최종 추천!\n\n"
            
            for i, (store_id, row) in enumerate(top_k_df.iterrows()):
                output_md += search_logic.format_restaurant_markdown(
                    store_id_str=store_id, 
                    rank_prefix="최종 추천", 
                    rank_index=i+1
                )
                output_md += (
                    f"*(Debug: Final={row['final_score']:.2f} | "
                    f"Travel={row['score_travel']:.2f} | "
                    f"Friend={row['score_friendliness']:.2f})*\n\n---\n\n"
                )

        except GraphHopperDownError as e:
            # --- 2단계 (B): Fallback (1단계 RAG 결과 사용) ---
            print(f"[경고] 2단계 final_scorer 실패: {e}. 1단계 RAG 결과로 대체합니다.")
            gr.Warning("⚠️ 뚜벅이 점수 서버가 응답하지 않습니다. 1단계 RAG 검색 결과로 대체합니다.")
            
            output_md = (
                "### 🤖 1단계 RAG 검색 결과\n"
                "(뚜벅이 점수 서버가 응답하지 않아, '뚜벅이 점수'가 반영되지 않은 1단계 검색 결과입니다.)\n\n"
            )
            
            top_k_ids = candidate_ids[:top_k] # (★ top_k 사용)
            
            for i, store_id in enumerate(top_k_ids):
                output_md += search_logic.format_restaurant_markdown(
                    store_id_str=store_id, 
                    rank_prefix="RAG 추천", 
                    rank_index=i+1
                )
                output_md += "\n---\n\n"
                
        # --- [ Fallback 로직 종료 ] ---
        
        final_user_profile_row = user_profile_row
        return gr.update(value=output_md, visible=True), final_user_profile_row
        
    except Exception as e:
        print(f"[오류] 식당 추천 흐름 중 예외 발생: {e}")
        gr.Error(f"추천 생성 중 오류 발생: {e}")
        reco_output = gr.update(value=f"[오류] 식당 추천 중 오류가 발생했습니다. (세부정보: {e})", visible=True)
        return reco_output, final_user_profile_row
    
async def chat_survey(
    message: str, 
    gradio_history: List[Dict], 
    llm_history: List[Dict], 
    current_profile: Dict, 
    is_completed: bool,
    topk_value: int,              # (★ app_main.py와 일치시킴)
    user_profile_row_state: Dict, # (★ app_main.py와 일치시킴)
    # (app.state에서 주입되는 자원)
    http_client: httpx.AsyncClient,
    graphhopper_url: str
) -> Tuple[List[Dict], List[Dict], Dict, bool, gr.update, Dict]:
    
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
        return gradio_history, llm_history, current_profile, is_completed, gr.update(), user_profile_row_state

    # 3. 봇 응답 추가 (LLM API용)
    llm_history.append({"role": "assistant", "content": bot_message})

    # --- 4. 완료 여부 확인 및 최종 데이터 생성 ---
    final_bot_message = bot_message
    recommendation_output = gr.update()
    new_user_profile_row_state = user_profile_row_state 
    
    profile_is_complete = all(v is not None for v in updated_profile.values())
    
    if profile_is_complete and not is_completed:
        print("--- 프로필 완성! 1/2단계 추천 로직을 실행합니다. ---")
        gr.Info("프로필이 완성되었습니다! AI가 1/2단계 맞춤 식당 추천을 시작합니다...")
        
        chat_message_html = llm_utils.generate_profile_summary_html(updated_profile)
        
        # (★ 수정) _run_recommendation_flow는 2개의 값을 반환
        recommendation_output, new_user_profile_row_state = await _run_recommendation_flow(
            updated_profile, 
            http_client, 
            graphhopper_url,
            top_k=topk_value # (★ 슬라이더의 topk_value 전달)
        )
        
        final_bot_message = f"{bot_message}\n{chat_message_html}\n\n👇 아래에서 추천 결과를 확인하세요! 👇"
        is_completed = True 
        print(json.dumps(updated_profile, indent=2, ensure_ascii=False))

    # 5. Gradio 챗봇 기록 업데이트 (UI용)
    gradio_history.append({"role": "assistant", "content": final_bot_message})
    
    # 6. (★ 6개 상태 반환)
    return gradio_history, llm_history, updated_profile, is_completed, recommendation_output, new_user_profile_row_state


def update_recommendations_with_topk(topk_value: int, user_profile_row_state: Dict):
    """
    (신규 헬퍼 함수 - 슬라이더용)
    Top-K 값이 바뀔 때마다, 저장된 'user_profile_row_state'를 기반으로
    추천 결과 Markdown만 다시 생성합니다. (API 호출 X)
    """
    
    # (프로필이 아직 없거나, 1단계가 실행된 적 없으면 아무것도 안 함)
    if not user_profile_row_state:
        return gr.update(value="...프로필을 먼저 완성해주세요...", visible=True)
    
    gr.Info(f"--- Top-K 변경: {topk_value}개로 추천 목록을 다시 생성합니다. ---")
    
    try:
        # 1. 2단계 (뚜벅이 점수) 결과가 있는지 확인
        if user_profile_row_state.get("final_scored_df"):
            # (DataFrame이 to_dict('records')로 저장되었으므로 다시 변환)
            final_scored_df = pd.DataFrame(user_profile_row_state["final_scored_df"])
            # (id를 인덱스로 복원 - format_restaurant_markdown이 인덱스(store_id)를 사용함)
            if 'id' in final_scored_df.columns:
                 final_scored_df = final_scored_df.set_index('id')
            
            top_k_df = final_scored_df.head(topk_value)
            output_md = "### 🤖 '뚜벅이 점수' 포함 최종 추천!\n\n"
            
            for i, (store_id, row) in enumerate(top_k_df.iterrows()):
                output_md += search_logic.format_restaurant_markdown(
                    store_id_str=store_id, 
                    rank_prefix="최종 추천", 
                    rank_index=i+1
                )
                output_md += (
                    f"*(Debug: Final={row['final_score']:.2f} | "
                    f"Travel={row['score_travel']:.2f} | "
                    f"Friend={row['score_friendliness']:.2f})*\n\n---\n\n"
                )
        
        # 2. 2단계 결과가 없고, 1단계 (Fallback) 결과만 있는지 확인
        elif user_profile_row_state.get("final_candidate_ids"):
            output_md = (
                "### 🤖 1단계 RAG 검색 결과\n"
                "(뚜벅이 점수 서버가 응답하지 않아, '뚜벅이 점수'가 반영되지 않은 1단계 검색 결과입니다.)\n\n"
            )
            top_k_ids = user_profile_row_state["final_candidate_ids"][:topk_value] 
            
            for i, store_id in enumerate(top_k_ids):
                output_md += search_logic.format_restaurant_markdown(
                    store_id_str=store_id, 
                    rank_prefix="RAG 추천", 
                    rank_index=i+1
                )
                output_md += "\n---\n\n"
        
        # 3. 아무 결과도 저장되지 않은 경우
        else:
            output_md = "...추천 결과가 없습니다. (State 비어있음)..."

        return gr.update(value=output_md, visible=True)

    except Exception as e:
        print(f"[오류] Top-K 슬라이더 변경 중 오류: {e}")
        return gr.update(value=f"[오류] Top-K 슬라이더 변경 중 오류: {e}", visible=True)