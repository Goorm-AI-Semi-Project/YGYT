# gradio_callbacks.py (리셋 함수 추가)
# (2-space indentation)

import gradio as gr 
import json
import pandas as pd
import httpx
from typing import Dict, Any, List, Tuple, Set
import random

# ⬇️ [수정] get_lang_code 임포트
from i18n_texts import get_text, get_lang_code

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

CARD_SEPARATOR = "\n---\n\n"


def _build_reco_md_from_df(
  df: pd.DataFrame, 
  top_k: int = 5, 
  prefix: str = "추천",
  lang_code: str = "KR" 
) -> str:
  """
  final_scorer 결과 DataFrame -> 카드형 markdown으로 변환
  """
  blocks: List[str] = []

  if "id" in df.columns:
    df = df.set_index("id")

  for i, (store_id, row) in enumerate(df.head(top_k).iterrows(), start=1):
    block = search_logic.format_restaurant_markdown(
      store_id_str=str(store_id),
      rank_prefix=prefix,
      rank_index=i,
      lang_code=lang_code, 
    )
    blocks.append(block.strip())
  return CARD_SEPARATOR.join(blocks)


def _build_reco_md_from_ids(
  store_ids, 
  top_k: int = 5, 
  prefix: str = "RAG 추천",
  lang_code: str = "KR"
) -> str:
  """
  1단계 RAG로 뽑은 식당 id 리스트 -> 카드형 markdown으로 변환
  """
  blocks = []
  for i, store_id in enumerate(list(store_ids)[:top_k], start=1):
    block = search_logic.format_restaurant_markdown(
      store_id_str=str(store_id),
      rank_prefix=prefix,
      rank_index=i,
      lang_code=lang_code, 
    )
    blocks.append(block.strip())
  return CARD_SEPARATOR.join(blocks)


# --- (budget_mapper, calculate_evaluation_metrics, LOCATION_COORDS, get_start_location_coords 함수는 변경 없음) ---
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

LOCATION_COORDS = {
    "명동역": "37.5630,126.9830",
    "홍대입구역": "37.5570,126.9244",
    "강남역": "37.4980,127.0276",
    "서울역": "37.5547,126.9704",
    "서울시청": "37.5665, 126.9780",
    "시청역": "37.5658,126.9772",
}

def get_start_location_coords(location_name: str) -> str:
  """간단한 장소 이름을 좌표 문자열로 변환"""
  return LOCATION_COORDS.get(location_name, "37.5630,126.9830")
# ---------------------------------------------------------------------------------


# =========================
# Gradio 콜백
# =========================

def start_chat(request: gr.Request) -> Tuple:
  """
  (페이지 로드용)
  채팅방이 *로드*될 때 실행됩니다.
  URL 파라미터(?lang=...)를 읽어 해당 언어로 챗봇과 UI를 초기화합니다.
  """
  
  # 1. URL에서 언어 코드 읽기 (기본값 KR)
  lang_code = "KR"
  if request:
    lang_code = request.query_params.get("lang", "KR")
  print(f"[start_chat] 로드. (Lang={lang_code})")

  # 2. 챗봇 첫 메시지 생성 (수정된 call_gpt4o 호출)
  try:
    profile_keys = list(config.PROFILE_TEMPLATE.keys())
    random.shuffle(profile_keys)
    initial_profile = {key: config.PROFILE_TEMPLATE[key] for key in profile_keys}
    
    bot_message, updated_profile = llm_utils.call_gpt4o(
      chat_messages=[], 
      current_profile=initial_profile,
      lang_code=lang_code # ⬅️ lang_code 전달
    )

    gradio_history = [{"role": "assistant", "content": bot_message}]
    llm_history = [{"role": "assistant", "content": bot_message}]
    initial_user_profile_row = {}

  except Exception as e:
    print(f"start_chat에서 API 호출 실패: {e}")
    error_msg = get_text("error_chatbot_init", lang_code, e=e)
    gradio_history = [{"role": "assistant", "content": error_msg}]
    llm_history = []
    updated_profile = config.PROFILE_TEMPLATE.copy()
    initial_user_profile_row = {}

  # 3. [중요] app_main.py의 outputs 리스트와 정확히 일치하는 26개 항목 반환
  
  lang_map = {"KR": "한국어 KR", "US": "English US", "JP": "日本語 JP", "CN": "中文 CN"}
  lang_radio_value = lang_map.get(lang_code, "한국어 KR")
  
  return (
    # --- States (6개) ---
    gradio_history,       # 1. chatbot (value)
    llm_history,          # 2. llm_history_state
    updated_profile,      # 3. profile_state
    False,                # 4. is_completed_state
    initial_user_profile_row, # 5. user_profile_row_state
    lang_code,            # 6. lang_code_state
    
    # --- UI Components (20개) ---
    gr.update(value=f"## {get_text('app_title', lang_code)}"),  # 7. title_md
    gr.update(value=get_text('app_description', lang_code)), # 8. desc_md
    
    gr.update(label=get_text('lang_select_label', lang_code), value=lang_radio_value), # 9. lang_radio
    
    gr.update(label=get_text('tab_explore', lang_code)),       # 10. tab_explore
    gr.update(label=get_text('tab_setting', lang_code)),       # 11. tab_setting
    
    gr.update(label=get_text('chatbot_label', lang_code)),     # 12. chatbot (label)
    gr.update(label=get_text('textbox_label', lang_code), placeholder=get_text('textbox_placeholder', lang_code)), # 13. msg_textbox
    gr.update(value=get_text('btn_show_results', lang_code)),  # 14. show_results_btn
    
    gr.update(label=get_text('slider_label', lang_code)),      # 15. topk_slider
    gr.update(value=get_text('btn_refresh', lang_code)),       # 16. refresh_btn
    gr.update(value=get_text('btn_back', lang_code)),          # 17. back_btn
    gr.update(value=None), # 18. profile_html (초기엔 비어있음)
    
    gr.update(value=get_text('setting_header', lang_code)),    # 19. setting_header_md
    gr.update(value=get_text('setting_description', lang_code)), # 20. setting_desc_md
    gr.update(value=get_text('btn_rebuild_db', lang_code)),    # 21. rebuild_btn
    gr.update(label=get_text('checkbox_debug_log', lang_code)), # 22. debug_checkbox
    gr.update(label=get_text('checkbox_debug_panel', lang_code)), # 23. debug_toggle
    
    gr.update(label=get_text('label_debug_profile', lang_code)), # 24. debug_profile_json
    gr.update(label=get_text('label_debug_summary', lang_code)), # 25. debug_summary_text
    gr.update(label=get_text('label_debug_norm', lang_code)), # 26. debug_norm_json
  )


async def _run_recommendation_flow(
  profile_data: dict,
  http_client: httpx.AsyncClient,
  graphhopper_url: str,
  top_k: int,
  lang_code: str 
) -> Tuple[gr.update, Dict]:
  """
  1단계 RAG -> 2단계 final_scorer 실행 (Fallback 포함)
  """
  final_user_profile_row: Dict[str, Any] = {}

  try:
    # --- 1단계: RAG + 필터 메타데이터 생성 ---
    print("--- 1단계: RAG + 점수제 후보군 생성 시작 ---")
    
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

    candidate_results = search_logic.get_rag_candidate_ids(
      user_profile_row, n_results=config.RAG_REQUEST_N_RESULTS
    )
    
    if not candidate_results:
      candidate_ids = []
    else:
      candidate_ids = [item['id'] for item in candidate_results]

    if not candidate_ids:
      print("[오류] 1단계 RAG 검색 결과, 후보군 0개.")
      warn_msg = get_text("warn_rag_empty", lang_code)
      gr.Warning(warn_msg)
      return (
        gr.update(value=warn_msg, visible=True),
        final_user_profile_row,
      )

    print(f"--- 1단계 RAG 완료 (후보: {len(candidate_ids)}개) ---")
    user_profile_row["final_candidate_ids"] = candidate_ids

    # --- 2단계: final_scorer 시도 ---
    try:
      print(f"--- 2단계: final_scorer 실행 (후보: {len(candidate_ids)}개) ---")
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
      
      # ( ... 평가 지표 계산 부분 ... )
      try:
        ground_truth_set = search_logic.get_ground_truth_for_user(
            live_rag_query_text=profile_summary,
            max_similar_users=5 
        )
        live_reco_ids = final_scored_df.index.astype(str).tolist()
        preprocessed_reco_ids = profile_data.get("preprocessed_list", []) 
        if not preprocessed_reco_ids:
          print("[평가] 'preprocessed_list'가 프로필에 없어 평가를 건너뜁니다.")

        evaluation_results = calculate_evaluation_metrics(
            live_reco_ids=live_reco_ids,
            preprocessed_reco_ids=preprocessed_reco_ids,
            ground_truth_set=ground_truth_set,
            k=5
        )
        print("\n--- [추천 성능 평가 결과 (K=5)] ---")
        print(json.dumps(evaluation_results, indent=2, ensure_ascii=False))
        print("----------------------------------\n")
      except Exception as eval_e:
        print(f"[오류] 평가 지표 계산 중 오류 발생: {eval_e}")
      # ( ... 평가 지표 계산 끝 ... )

      user_profile_row["final_scored_df"] = final_scored_df.reset_index().to_dict(
        "records"
      )

      prefix_reco = get_text("rank_prefix_reco", lang_code)
      output_md = _build_reco_md_from_df(
        final_scored_df, 
        top_k=top_k, 
        prefix=prefix_reco, 
        lang_code=lang_code
      )

    except GraphHopperDownError as e:
      # --- 2단계 실패 시: 1단계만 사용 ---
      print(f"[경고] 2단계 final_scorer 실패: {e}. 1단계 RAG 결과로 대체합니다.")
      warn_msg_gh = get_text("warn_graphhopper_down", lang_code)
      gr.Warning(warn_msg_gh)

      prefix_rag = get_text("rank_prefix_rag", lang_code)
      output_md = _build_reco_md_from_ids(
        candidate_ids, 
        top_k=top_k, 
        prefix=prefix_rag, 
        lang_code=lang_code
      )

    # 결과 반환
    final_user_profile_row = user_profile_row
    return gr.update(value=output_md, visible=True), final_user_profile_row

  except Exception as e:
    print(f"[오류] 식당 추천 흐름 중 예외 발생: {e}")
    error_msg_reco = get_text("error_reco_general", lang_code, e=e)
    error_msg_details = get_text("error_reco_general_details", lang_code, e=e)
    gr.Error(error_msg_reco)
    return (
      gr.update(value=error_msg_details, visible=True),
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
  lang_code: str # ⬅️ lang_code 파라미터 추가 (app_main.py에서 전달)
):
  """
  채팅 답변을 처리하고, 프로필이 완성되면 2단계(대기/결과)로 UI를 업데이트합니다.
  """
  # 1) 사용자 메시지 기록
  gradio_history.append({"role": "user", "content": message})
  llm_history.append({"role": "user", "content": message})

  # 2) LLM 호출해서 다음 질문/응답 생성
  try:
    bot_message, updated_profile = llm_utils.call_gpt4o(
      llm_history, 
      current_profile,
      lang_code=lang_code # ⬅️ lang_code 전달
    )
  except Exception as e:
    print(f"chat_survey에서 API 호출 실패: {e}")
    error_msg = get_text("error_api_call", lang_code, e=e)
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

  # LLM 히스토리에 어시턴트 응답 추가
  llm_history.append({"role": "assistant", "content": bot_message})

  # 3) 프로필이 다 모였는지 확인
  profile_is_complete = all(v is not None for v in updated_profile.values())
  # ⬇️ [수정] llm_signals_completion: "완료되었습니다" 외 다국어 메시지 확인
  completion_text_kr = "프로필 수집이 완료되었습니다!" 
  # (참고: i18n_texts.py에 info_profile_complete 키가 있지만, 
  #  LLM은 SYSTEM_PROMPT의 규칙 5번을 따르므로 "완료되었습니다"만 확인해도 됨)
  llm_signals_completion = completion_text_kr in bot_message

  recommendation_output = gr.update()
  new_user_profile_row_state = user_profile_row_state

  if profile_is_complete and llm_signals_completion and not is_completed:
      
    # --- (A) 1차: "대기 메시지" 즉시 반환 ---
    loading_message = get_text("info_profile_complete", lang_code)
    
    gradio_history.append({"role": "assistant", "content": loading_message.strip()})
    
    print("--- 프로필 완성! [1/2] 대기 메시지 전송 (화면 유지) ---")
    
    yield (
      gradio_history,
      llm_history,
      updated_profile,
      False, # (화면 유지)
      gr.update(), 
      user_profile_row_state
    )

    # --- (B) 2차: 오래 걸리는 추천 로직 실행 ---
    print("--- 프로필 완성! [2/2] 추천 로직 실행 ---")
    recommendation_output, new_user_profile_row_state = await _run_recommendation_flow(
      updated_profile,
      http_client,
      graphhopper_url,
      top_k=topk_value,
      lang_code=lang_code # ⬇️ lang_code 전달
    )
    
    is_completed = True # (이제 상태를 True로 변경)

    # --- (C) 3차: "최종 결과" 반환 ---
    print("--- 프로필 완성! [2/2] 최종 결과 전송 (화면 전환) ---")
    
    yield (
      gradio_history, 
      llm_history,
      updated_profile,
      True, # (화면 전환)
      recommendation_output, # (실제 식당 HTML)
      new_user_profile_row_state
    )
      
  else:
    # --- (프로필 미완성) ---
    gradio_history.append({"role": "assistant", "content": bot_message})
    yield (
      gradio_history,
      llm_history,
      updated_profile,
      is_completed, # (False)
      recommendation_output, # (gr.update())
      new_user_profile_row_state
    )


def update_recommendations_with_topk(
  topk_value: int, 
  user_profile_row_state: Dict,
  lang_code: str # ⬇️ lang_code 파라미터 추가 (app_main.py에서 전달)
):
  """
  Top-K 슬라이더 변경 시 호출.
  """
  if not user_profile_row_state:
    return gr.update(value=get_text("info_complete_profile_first", lang_code), visible=True)

  try:
    # 1) 2단계 결과가 있는 경우
    if user_profile_row_state.get("final_scored_df"):
      df = pd.DataFrame(user_profile_row_state["final_scored_df"])
      prefix_reco = get_text("rank_prefix_reco", lang_code)
      md = _build_reco_md_from_df(
        df, 
        top_k=topk_value, 
        prefix=prefix_reco, 
        lang_code=lang_code
      )
      return gr.update(value=md, visible=True)

    # 2) 1단계 후보만 있는 경우
    if user_profile_row_state.get("final_candidate_ids"):
      ids = user_profile_row_state["final_candidate_ids"]
      prefix_rag = get_text("rank_prefix_rag", lang_code)
      md = _build_reco_md_from_ids(
        ids, 
        top_k=topk_value, 
        prefix=prefix_rag, 
        lang_code=lang_code
      )
      return gr.update(value=md, visible=True)

    # 3) 아무것도 없을 때
    return gr.update(value=get_text("error_no_recos_state", lang_code), visible=True)

  except Exception as e:
    print(f"[오류] Top-K 슬라이더 변경 중 오류: {e}")
    return gr.update(
      value=get_text("error_slider_update", lang_code, e=e), visible=True
    )

# ⬇️ [신규] 언어 변경 시 챗봇과 UI를 리셋하는 함수
def reset_chat_for_language(lang_str: str) -> Tuple:
  """
  (언어 변경용)
  lang_radio.change() 시 호출됩니다.
  start_chat과 거의 동일하나, 입력을 lang_str (예: "English US")로 받습니다.
  """
  
  # 1. 'English US' -> 'US'
  lang_code = get_lang_code(lang_str)
  print(f"[reset_chat_for_language] 시작. (Lang={lang_code})")

  # 2. 챗봇 첫 메시지 생성
  try:
    profile_keys = list(config.PROFILE_TEMPLATE.keys())
    random.shuffle(profile_keys)
    initial_profile = {key: config.PROFILE_TEMPLATE[key] for key in profile_keys}
    
    bot_message, updated_profile = llm_utils.call_gpt4o(
      chat_messages=[], 
      current_profile=initial_profile,
      lang_code=lang_code # ⬅️ 새 lang_code 전달
    )

    gradio_history = [{"role": "assistant", "content": bot_message}]
    llm_history = [{"role": "assistant", "content": bot_message}]
    initial_user_profile_row = {}

  except Exception as e:
    print(f"reset_chat_for_language에서 API 호출 실패: {e}")
    error_msg = get_text("error_chatbot_init", lang_code, e=e)
    gradio_history = [{"role": "assistant", "content": error_msg}]
    llm_history = []
    updated_profile = config.PROFILE_TEMPLATE.copy()
    initial_user_profile_row = {}

  # 3. app_main.py의 outputs 리스트와 정확히 일치하는 26개 항목 반환
  
  # ⬇️ lang_code가 아닌 lang_str (예: "English US")을 Radio의 value로 설정
  lang_radio_value = lang_str 
  
  return (
    # --- States (6개) ---
    gradio_history,       # 1. chatbot (value)
    llm_history,          # 2. llm_history_state
    updated_profile,      # 3. profile_state
    False,                # 4. is_completed_state
    initial_user_profile_row, # 5. user_profile_row_state
    lang_code,            # 6. lang_code_state
    
    # --- UI Components (20개) ---
    gr.update(value=f"## {get_text('app_title', lang_code)}"),  # 7. title_md
    gr.update(value=get_text('app_description', lang_code)), # 8. desc_md
    
    gr.update(label=get_text('lang_select_label', lang_code), value=lang_radio_value), # 9. lang_radio
    
    gr.update(label=get_text('tab_explore', lang_code)),       # 10. tab_explore
    gr.update(label=get_text('tab_setting', lang_code)),       # 11. tab_setting
    
    gr.update(label=get_text('chatbot_label', lang_code)),     # 12. chatbot (label)
    gr.update(label=get_text('textbox_label', lang_code), placeholder=get_text('textbox_placeholder', lang_code)), # 13. msg_textbox
    gr.update(value=get_text('btn_show_results', lang_code)),  # 14. show_results_btn
    
    gr.update(label=get_text('slider_label', lang_code)),      # 15. topk_slider
    gr.update(value=get_text('btn_refresh', lang_code)),       # 16. refresh_btn
    gr.update(value=get_text('btn_back', lang_code)),          # 17. back_btn
    gr.update(value=None), # 18. profile_html (리셋)
    
    gr.update(value=get_text('setting_header', lang_code)),    # 19. setting_header_md
    gr.update(value=get_text('setting_description', lang_code)), # 20. setting_desc_md
    gr.update(value=get_text('btn_rebuild_db', lang_code)),    # 21. rebuild_btn
    gr.update(label=get_text('checkbox_debug_log', lang_code)), # 22. debug_checkbox
    gr.update(label=get_text('checkbox_debug_panel', lang_code)), # 23. debug_toggle
    
    gr.update(label=get_text('label_debug_profile', lang_code)), # 24. debug_profile_json
    gr.update(label=get_text('label_debug_summary', lang_code)), # 25. debug_summary_text
    gr.update(label=get_text('label_debug_norm', lang_code)), # 26. debug_norm_json
  )
