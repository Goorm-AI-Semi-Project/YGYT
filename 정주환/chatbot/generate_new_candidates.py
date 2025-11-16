# 01_generate_candidates.py (최종본: 'profile' 캐시 무조건 생성 로직)

import pandas as pd
import numpy as np
import asyncio
import httpx
import json
import os
import random
from typing import List, Set, Dict, Any

# --- 제공된 소스 모듈 임포트 ---
try:
  import config
  import data_loader
  import search_logic
  import llm_utils
  from llm_utils import extract_profile_from_summary 
  import gradio_callbacks
  from API import final_scorer
  from API.final_scorer import GraphHopperDownError
except ImportError as e:
  print(f"오류: 필수 모듈 임포트 실패. '{e.name}' 모듈이 없거나 경로가 잘못되었습니다.")
  exit()

# (캐시 디렉토리)
CACHE_DIR = "evaluation_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ==================================================================
# 1. 평가 지표 계산 함수 (변경 없음)
# ==================================================================

def calculate_precision_k(recommendations: List[str], ground_truth: Set[str], k: int) -> float:
  """ Precision@K (정밀도) 계산 """
  if not ground_truth: 
    return 0.0 
  
  # (k값보다 추천 개수가 적을 수 있으므로 min() 사용 안함)
  top_k_recs = recommendations[:k]
  if not top_k_recs: 
    return 0.0 # (추천이 0개면 0점)
  
  relevant_set = ground_truth
  hits = sum(1 for item in top_k_recs if item in relevant_set)
  
  # (P@K의 분모는 항상 K)
  return hits / k

def calculate_recall_k(recommendations: List[str], ground_truth: Set[str], k: int) -> float:
  """ Recall@K (재현율) 계산 """
  if not ground_truth or len(ground_truth) == 0: 
    return 0.0 
    
  top_k_recs = recommendations[:k]
  relevant_set = ground_truth
  hits = sum(1 for item in top_k_recs if item in relevant_set)
  
  # (R@K의 분모는 전체 정답 개수)
  return hits / len(relevant_set)


# ==================================================================
# [!!! 신규 함수 1 !!!]
# LLM 프로필 추출 및 캐시 확인/생성 (동기 함수)
# ==================================================================
def get_or_create_profile_cache(user_row: pd.Series) -> Dict[str, Any]:
  """
  _profile.json 캐시를 확인하고, 없으면 생성합니다.
  (LLM 호출은 동기(sync)로 처리됩니다.)
  """
  user_id = str(user_row['id'])
  summary_text = user_row['summary_text']
  profile_cache_file = os.path.join(CACHE_DIR, f"{user_id}_profile.json")
  
  profile_data = None

  if os.path.exists(profile_cache_file):
    try:
      with open(profile_cache_file, 'r', encoding='utf-8') as f:
        profile_data = json.load(f)
    except Exception as e:
      print(f"  > [경고] User {user_id}: _profile.json 캐시가 깨져 다시 생성합니다. (오류: {e})")
      profile_data = None # (캐시 깨졌으면 다시 생성)
      
  if not profile_data:
    # (캐시가 없거나 깨졌으면 LLM 호출)
    try:
      profile_data = extract_profile_from_summary(summary_text)
      
      if profile_data:
        try:
          # (LLM 프로필 추출 결과 캐시 저장)
          with open(profile_cache_file, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
          print(f"  > [정보] User {user_id}: _profile.json 캐시 생성 완료.")
        except Exception as e:
          print(f"  > [경고] User {user_id}: _profile.json 캐시 저장 실패 (무시하고 진행). (오류: {e})")
      
    except Exception as e:
      print(f"  > [실패] User {user_id}: LLM 프로필 추출 실패. (오류: {e})")
      return None # (LLM 추출 실패 시 None 반환)
    
  if not profile_data or not profile_data.get("start_location"):
    print(f"  > [실패] User {user_id}: LLM 프로필이 비어있거나 'start_location'이 없습니다.")
    return None # (유효하지 않은 프로필)

  return profile_data


# ==================================================================
# [!!! 신규 함수 2 (기존 run_single_user_generation 변경) !!!]
# RAG + Scorer 파이프라인 (비동기 함수)
# ==================================================================
async def run_rag_and_scorer_pipeline(
    user_row: pd.Series,
    profile_data: Dict[str, Any], # (프로필 데이터를 인자로 받음)
    http_client: httpx.AsyncClient,
    k: int
) -> List[Dict[str, Any]]:
  """
  [!!! 수정본: LLM 프로필 추출 로직 제거 !!!]
  (RAG + Scorer만 실행하여 최종 8컬럼 리스트를 반환합니다.)
  """
  
  user_id = str(user_row['id'])
  user_name = str(user_row['name'])
  summary_text = user_row['summary_text'] # (RAG 쿼리 생성용)
  
  final_recommendations = []
  
  # (try...except를 이 함수를 호출한 limited_task로 이동)
  
  # --- [B] 1단계: RAG + 점수제 ---
  filter_dict = search_logic.create_filter_metadata(profile_data)
  user_profile_row = {
    "rag_query_text": summary_text,
    "filter_metadata_json": json.dumps(filter_dict, ensure_ascii=False)
  }
  
  candidate_results = search_logic.get_rag_candidate_ids(
      user_profile_row, 
      n_results=config.RAG_REQUEST_N_RESULTS
  )
  
  if not candidate_results:
    return [] # (추천 0건도 '성공'이므로 빈 리스트 반환)

  candidate_ids = [item['id'] for item in candidate_results]
  scores_map = {item['id']: {
    'rag_distance': item.get('rag_distance', 0.0),
    'filter_score': item.get('filter_score', 0)
  } for item in candidate_results}

  live_recs_ids = []
  
  # --- [C] 2단계: final_scorer ---
  try:
    candidate_df = data_loader.get_restaurants_by_ids(candidate_ids)
    user_start_location_name = profile_data.get("start_location")
    user_budget_pref_str = profile_data.get("budget")
    user_start_coords = gradio_callbacks.get_start_location_coords(user_start_location_name)
    user_price_prefs = gradio_callbacks.budget_mapper(user_budget_pref_str)

    final_scored_df = await final_scorer.calculate_final_scores_async(
        candidate_df=candidate_df,
        user_start_location=user_start_coords,
        user_price_prefs=user_price_prefs,
        async_http_client=http_client,
        graphhopper_url=config.GRAPH_HOPPER_API_URL,
    )
    live_recs_ids = final_scored_df.index.astype(str).tolist()

  except Exception as e:
    print(f"  > [경고] User {user_id}: 2단계 Scorer 실패 ({e}). 1단계 RAG로 대체.")
    live_recs_ids = candidate_ids

  # --- [D] Gradio 호환 8컬럼 포맷팅 (및 70/30 자동 평가) ---
  
  num_visited = k 
  num_recommended = round(num_visited * 0.7) # 7개
  num_not_recommended = num_visited - num_recommended # 3개
  
  evaluations_list = (
      ['추천'] * num_recommended +
      ['미추천'] * num_not_recommended
  )
  random.shuffle(evaluations_list)

  for i, res_id in enumerate(live_recs_ids[:k]): # (k=10)
    rank = i + 1
    try:
      store_name = data_loader.df_restaurants.loc[res_id]['가게']
    except:
      store_name = "(알 수 없음)"
    
    original_scores = scores_map.get(res_id, {
        'rag_distance': 0.0, 'filter_score': 0
    })
      
    final_recommendations.append({
      'user_id': user_id, 
      'user_name': user_name, 
      'rank': rank, 
      'restaurant_id': res_id, 
      'store_name': store_name, 
      'rag_distance': original_scores['rag_distance'],
      'filter_score': original_scores['filter_score'], 
      '사용자평가': evaluations_list[i] 
    })
  
  # (최종 성공 결과 반환)
  return final_recommendations


# ==================================================================
# [!!! main_generation 함수 수정 !!!]
# ==================================================================
async def main_generation():
  
  # --- [ 1. 설정 변수 ] ---
  PROFILES_CSV_PATH = './data/user_profiles_combined.csv'
  OUTPUT_CSV_PATH = 'recommendation_results_with_ratings.csv'
  
  # (테스트 시 5, 전체 실행 시 None)
  MAX_USERS_TO_TEST = None
  
  K_VALUE = 10            
  CONCURRENT_LIMIT = 2   
  
  # --- [ 2. 데이터 로드 ] ---
  print("--- [1/4] 서버 데이터 로드 시작 ---")
  try:
    data_loader.load_app_data(config.RESTAURANT_DB_FILE, config.MENU_DB_FILE)
    if not config.client or not config.client.api_key:
      print("[치명적 오류] OpenAI API 키가 로드되지 않았습니다.")
      return
    data_loader.build_vector_db(
        config.RESTAURANT_DB_FILE, config.PROFILE_DB_FILE, config.CLEAR_DB_AND_REBUILD
    )
    data_loader.load_scoring_data(config.RESTAURANT_DB_SCORING_FILE)
    print("--- [1/4] 모든 데이터 로드 완료 ---")
  except Exception as e:
    print(f"[치명적 오류] 데이터 로드 실패: {e}")
    return

  print(f"\n--- [2/4] '{PROFILES_CSV_PATH}' 로드 중 ---")
  try:
    profiles_df_all = pd.read_csv(PROFILES_CSV_PATH, dtype={'id': str})
    
    if MAX_USERS_TO_TEST is not None:
      print(f"  > [테스트 모드] {MAX_USERS_TO_TEST}명만 테스트합니다.")
      profiles_df = profiles_df_all.head(MAX_USERS_TO_TEST).copy()
    else:
      print(f"  > [전체 실행 모드] {len(profiles_df_all)}명 전체를 테스트합니다.")
      profiles_df = profiles_df_all
      
  except FileNotFoundError:
    print(f"[치명적 오류] '{PROFILES_CSV_PATH}' 파일을 찾을 수 없습니다.")
    return
  
  # --- [ 3. 캐시 확인 및 작업 목록 생성 (!!! 수정된 로직 !!!) ] ---
  # (이제 'profile' 캐시 생성은 비동기 작업(limited_task) 내부에서 처리)
  print(f"\n--- [3/4] 작업 목록 생성 ---")
  print(f"  > 총 {len(profiles_df)}명의 사용자에 대해 2단계 캐시(Profile -> Generation)를 확인/생성합니다.")


  # --- [ 4. 비동기 평가 실행 (!!! 수정된 로직 !!!) ] ---
  print(f"\n--- [4/4] {len(profiles_df)}명 추천 생성 시작 (동시성={CONCURRENT_LIMIT}) ---")

  all_success_results_lists = [] # (최종 결과를 담을 리스트)
  
  async with httpx.AsyncClient(timeout=20.0) as http_client:
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    
    # [!!! limited_task 로직 수정 !!!]
    async def limited_task(user_row, index):
      user_id = user_row['id']
      print(f"  > 시작 ( {index + 1} / {len(profiles_df)} ) : User {user_id}")
      
      generation_list = None
      
      try:
        # --- 1. 프로필 캐시 확인/생성 ---
        # (이 함수는 동기 함수임)
        profile_data = get_or_create_profile_cache(user_row)
        
        if not profile_data:
          raise Exception("프로필 생성/로드 실패") # (실패 시 아래 except로 이동)
          
        # --- 2. 생성(Generation) 캐시 확인 ---
        generation_cache_file = os.path.join(CACHE_DIR, f"{user_id}_generation.json")
        
        if os.path.exists(generation_cache_file):
          try:
            with open(generation_cache_file, 'r', encoding='utf-8') as f:
              generation_list = json.load(f)
            print(f"  > 완료/캐시 ( {index + 1} / {len(profiles_df)} ) : User {user_id} (Generation 캐시 로드)")
          except:
            generation_list = None # (캐시 깨졌으면 다시 생성)
        
        if generation_list is None:
          # --- 3. (캐시 없을 시) RAG + Scorer 실행 ---
          # (세마포어는 이 비동기 함수에만 적용)
          async with semaphore:
            generation_list = await run_rag_and_scorer_pipeline(
              user_row, profile_data, http_client, K_VALUE
            )
          
          # (성공 시 캐시 파일 저장)
          try:
            with open(generation_cache_file, 'w', encoding='utf-8') as f:
              json.dump(generation_list, f, ensure_ascii=False, indent=2)
            print(f"  > 완료/저장 ( {index + 1} / {len(profiles_df)} ) : User {user_id} ({len(generation_list)}건)")
          except Exception as e:
            print(f"  > 완료/저장실패 ( {index + 1} ) : User {user_id} (이유: {e})")
        
        return generation_list # (성공 결과 반환)
        
      except Exception as e:
        # (프로필 생성 실패 또는 RAG/Scorer 파이프라인 실패 시)
        print(f"  > 실패 ( {index + 1} / {len(profiles_df)} ) : User {user_id} (이유: {e})")
        return None # (실패 시 None 반환)

    tasks = [limited_task(row, i) for i, (idx, row) in enumerate(profiles_df.iterrows())]
    results_raw = await asyncio.gather(*tasks)

    # (신규) 새로 실행된 결과만 분리 (None이 아닌 것)
    for item in results_raw:
      if isinstance(item, list): # (성공 시 [..] 리스트)
        all_success_results_lists.append(item)
      # (실패(None)는 위에서 이미 로깅됨)

  # --- [ 5. CSV 저장 ] ---
  
  # (2D 리스트를 1D 리스트로 평탄화)
  all_results_flat = []
  for user_list in all_success_results_lists:
    all_results_flat.extend(user_list)

  if not all_results_flat:
    print("\n[오류] 생성된 추천 후보가 없습니다. 스크립트를 종료합니다.")
    return

  print(f"\n[성공] 총 {len(all_success_results_lists)}명({len(all_results_flat)}건)의 추천 후보 생성 완료.")
  df_final_candidates = pd.DataFrame(all_results_flat)
  
  try:
    FINAL_COLUMNS_ORDER = [
      'user_id', 'user_name', 'rank', 'restaurant_id', 'store_name', 
      'rag_distance', 'filter_score', '사용자평가'
    ]
    if not df_final_candidates.empty:
      df_final_candidates = df_final_candidates[FINAL_COLUMNS_ORDER]
    
    df_final_candidates.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
    print(f"  > 최종 후보 파일이 '{OUTPUT_CSV_PATH}'에 저장되었습니다.")
  except Exception as e:
    print(f"  > [오류] CSV 파일 저장 실패: {e}")


# ==================================================================
# 6. 스크립트 실행
# ==================================================================
if __name__ == "__main__":
  print("--- 1단계: 'Live' 파이프라인 Top-10 추천 후보 생성 시작 ---")
  if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
  asyncio.run(main_generation())