# run_evaluation.py (최종 수정본: P@K/R@K 함수 추가 및 [Dict] 오류 수정)

import pandas as pd
import numpy as np
import asyncio
import httpx
import json
import os
from typing import List, Set, Dict, Any

# --- Plotly 시각화 모듈 임포트 ---
try:
  import plotly.graph_objects as go
  import plotly.io as pio
  pio.templates.default = "plotly_white"
except ImportError:
  print("[경고] Plotly가 설치되지 않았습니다. 시각화(이미지 저장)가 비활성화됩니다.")
  print("pip install plotly kaleido")
  go, pio = None, None

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
  
# [!!!] 이 한 줄을 여기에 추가하세요 [!!!]
os.environ["TOKENIZERS_PARALLELISM"] = "false"  
  
# (캐시 디렉토리)
CACHE_DIR = "evaluation_cache"
os.makedirs(CACHE_DIR, exist_ok=True)


# ==================================================================
# [!!! 수정 1: 누락된 평가 함수 2개 추가 !!!]
# ==================================================================

def calculate_precision_k(recommendations: List[str], ground_truth: Set[str], k: int) -> float:
  """ Precision@K (정밀도) 계산 """
  if not ground_truth: 
    return 0.0 
  
  top_k_recs = recommendations[:k]
  if not top_k_recs: 
    return 0.0 # (추천이 0개면 0점)
  
  relevant_set = ground_truth
  hits = sum(1 for item in top_k_recs if item in relevant_set)
  
  # [!!! 로직 수정 !!!] (P@K의 분모는 항상 K)
  return hits / k

def calculate_recall_k(recommendations: List[str], ground_truth: Set[str], k: int) -> float:
  """ Recall@K (재현율) 계산 """
  if not ground_truth or len(ground_truth) == 0: 
    return 0.0 
    
  top_k_recs = recommendations[:k]
  relevant_set = ground_truth
  hits = sum(1 for item in top_k_recs if item in relevant_set)
  
  # [!!! 로직 수정 !!!] (R@K의 분모는 전체 정답 개수)
  return hits / len(relevant_set)

# ==================================================================
# 2. Ground Truth 로드 함수 (변경 없음)
# ==================================================================

def load_ground_truth(csv_path: str) -> Dict[str, Set[str]]:
  print(f"\n--- [Ground Truth] '{csv_path}' 로드 중 ---")
  try:
    df = pd.read_csv(csv_path)
    df_truth = df[df['사용자평가'] == '추천']
    ground_truth_map = df_truth.groupby('user_id')['restaurant_id'].apply(
      lambda x: set(x.astype(str))
    )
    print(f"[Ground Truth] 정답 셋 로드 완료 (총 {len(ground_truth_map)}명)")
    return ground_truth_map.to_dict()
  except Exception as e:
    print(f"[오류] Ground Truth 로드 실패: {e}")
    return {}

# ==================================================================
# [!!! 수정 3: '[Dict]' 오류 해결 !!!]
# ==================================================================
async def run_single_user_recommendation(
    user_row: pd.Series,
    ground_truth_map: Dict[str, Set[str]],
    http_client: httpx.AsyncClient,
    k: int
) -> Dict[str, Any]:
  
  user_id = str(user_row['id'])
  summary_text = user_row['summary_text']
  ground_truth_set = ground_truth_map.get(user_id, set())
  
  try:
    # --- [A] LLM 프로필 역추출 ---
    profile_data = extract_profile_from_summary(summary_text)
    
    if not profile_data or not profile_data.get("start_location"):
      return {
        "user_id": user_id, f"precision_at_{k}": 0.0, f"recall_at_{k}": 0.0,
        "ground_truth_size": len(ground_truth_set), "live_recs_count": 0,
        "error": "LLM profile extraction failed"
      }

    # --- [B] 1단계: RAG + 점수제 ---
    filter_dict = search_logic.create_filter_metadata(profile_data)
    user_profile_row = {
      "rag_query_text": summary_text,
      "filter_metadata_json": json.dumps(filter_dict, ensure_ascii=False)
    }
    
    # [!!! 1. 딕셔너리 리스트로 받기 !!!]
    candidate_results = search_logic.get_rag_candidate_ids(
        user_profile_row, 
        n_results=config.RAG_REQUEST_N_RESULTS
    )
    
    live_recs_ids = []
    if not candidate_results:
      live_recs_ids = [] # (결과 0건)
    else:
      # [!!! 2. ID 리스트와 점수 맵 분리 !!!]
      candidate_ids = [item['id'] for item in candidate_results]
      # (run_evaluation.py는 1단계 점수를 사용하지 않으므로 scores_map은 필요 없음)
      
      # --- [C] 2단계: final_scorer ---
      try:
        # [!!! 3. 올바른 ID 리스트 전달 !!!]
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

      except GraphHopperDownError as e:
        print(f"  > [경고] User {user_id}: 2단계 Scorer 실패 ({e}). 1단계 RAG로 대체.")
        live_recs_ids = candidate_ids # (1단계 Fallback)
      except Exception as e:
        print(f"  > [경고] User {user_id}: 2단계 Scorer 알 수 없는 오류 ({e}). 1단계 RAG로 대체.")
        live_recs_ids = candidate_ids # (1단계 Fallback)

    # (디버깅 로그 - 기존 코드)
    print(f"\n  > [디버그: {user_id}]")
    print(f"  > 1. 정답 (Ground Truth): {ground_truth_set}")
    print(f"  > 2. 실시간 추천 (Live Top {k}): {live_recs_ids[:k]}")
    
    # (P@K, R@K 함수 호출 - 이제 NameError 안 남)
    precision = calculate_precision_k(live_recs_ids, ground_truth_set, k)
    recall = calculate_recall_k(live_recs_ids, ground_truth_set, k)
    
    print(f"  > 3. 결과: P@{k}={precision:.2f}, R@{k}={recall:.2f}")

    return {
      "user_id": user_id,
      f"precision_at_{k}": precision,
      f"recall_at_{k}": recall,
      "ground_truth_size": len(ground_truth_set),
      "live_recs_count": len(live_recs_ids),
      "error": None
    }
    
  except Exception as e:
    return { "user_id": user_id, "error": str(e) }

# ==================================================================
# 4. Plotly 시각화 저장 함수 (변경 없음)
# ==================================================================
def save_result_visualizations(df: pd.DataFrame, p_col: str, r_col: str, k: int):
  if go is None:
    print("\n[시각화] Plotly가 설치되지 않아 차트 생성을 건너뜁니다.")
    return
  print(f"\n[시각화] Plotly 차트를 생성하고 .png 파일로 저장합니다...")
  try:
    fig_p = go.Figure(data=[go.Histogram(x=df[p_col], nbinsx=20, marker_color='#FF7600')])
    fig_p.update_layout(title_text=f'<b>Precision@{k} 분포 (N={len(df)})</b>', xaxis_title_text='Precision@K', yaxis_title_text='사용자 수 (Count)')
    fig_p.write_image(f"evaluation_precision_at_{k}_histogram.png", width=800, height=500)
    print(f"  > 'evaluation_precision_at_{k}_histogram.png' 저장 완료")
    
    fig_r = go.Figure(data=[go.Histogram(x=df[r_col], nbinsx=20, marker_color='#007BFF')])
    fig_r.update_layout(title_text=f'<b>Recall@{k} 분포 (N={len(df)})</b>', xaxis_title_text='Recall@K', yaxis_title_text='사용자 수 (Count)')
    fig_r.write_image(f"evaluation_recall_at_{k}_histogram.png", width=800, height=500)
    print(f"  > 'evaluation_recall_at_{k}_histogram.png' 저장 완료")
    
    fig_box = go.Figure()
    fig_box.add_trace(go.Box(y=df[p_col], name=f'Precision@{k}', marker_color='#FF7600'))
    fig_box.add_trace(go.Box(y=df[r_col], name=f'Recall@{k}', marker_color='#007BFF'))
    fig_box.update_layout(title_text=f'<b>평가 지표 Box Plot (N={len(df)})</b>')
    fig_box.write_image(f"evaluation_metrics_boxplot.png", width=800, height=600)
    print(f"  > 'evaluation_metrics_boxplot.png' 저장 완료")
  except Exception as e:
    print(f"[오류] Plotly 차트 생성/저장 중 오류 발생: {e}")
    print("      (Kaleido가 제대로 설치되었는지 확인하세요)")

# ==================================================================
# 5. 메인 실행 함수 (Charlie님이 주신 '이전' 캐시 로직)
# ==================================================================
async def main_evaluation():
  
  # --- [ 1. 설정 변수 ] ---
  MAX_USERS_TO_TEST = None
  K_VALUE = 10
  CONCURRENT_LIMIT = 1 
  
  PROFILES_CSV_PATH = './data/user_profiles_combined.csv'
  GROUND_TRUTH_CSV_PATH = './data/recommendation_results_with_ratings.csv'
  
  CACHE_DIR = "evaluation_cache"
  FINAL_CSV_OUTPUT = "final_evaluation_metrics_all.csv"
  
  os.makedirs(CACHE_DIR, exist_ok=True)
  
  # --- [ 2. 데이터 로드 ] ---
  print("--- [1/5] 서버 데이터 로드 시작 ---")
  try:
    data_loader.load_app_data(config.RESTAURANT_DB_FILE_ALL, config.MENU_DB_FILE)
    if not config.client or not config.client.api_key:
      print("[치명적 오류] OpenAI API 키가 로드되지 않았습니다.")
      return
    print("  > OpenAI API 키 로드 완료.")
    data_loader.build_vector_db(
        config.RESTAURANT_DB_FILE_ALL, config.PROFILE_DB_FILE, config.CLEAR_DB_AND_REBUILD
    )
    data_loader.load_scoring_data(config.RESTAURANT_DB_SCORING_FILE)
    print("--- [1/5] 모든 데이터 로드 완료 ---")
  except Exception as e:
    print(f"[치명적 오류] 데이터 로드 실패: {e}")
    return

  ground_truth_map = load_ground_truth(GROUND_TRUTH_CSV_PATH)
  if not ground_truth_map:
    print("[치명적 오류] Ground Truth가 없습니다.")
    return

  print(f"\n--- [2/5] '{PROFILES_CSV_PATH}' 로드 중 ---")
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
  
  # --- [ 3. 캐시 확인 (이전 방식) ] ---
  print(f"\n--- [3/5] 캐시 확인 및 실행 목록 생성 ---")
  
  tasks = []
  cached_results = []
  users_to_run_rows = [] 

  for _, user_row in profiles_df.iterrows():
    user_id = str(user_row['id'])
    
    # (이전 캐시 파일 이름: {user_id}.json)
    cache_file = os.path.join(CACHE_DIR, f"{user_id}.json")
    
    if os.path.exists(cache_file):
      try:
        with open(cache_file, 'r', encoding='utf-8') as f:
          cached_results.append(json.load(f))
      except:
        users_to_run_rows.append(user_row)
    else:
      users_to_run_rows.append(user_row)

  print(f"  > 총 {len(profiles_df)}명 중 {len(cached_results)}명 캐시 로드, {len(users_to_run_rows)}명 새로 실행.")

  # --- [ 4. 비동기 평가 실행 (이전 방식) ] ---
  newly_completed_results = []
  
  if users_to_run_rows:
    print(f"\n--- [4/5] {len(users_to_run_rows)}명 평가 시작 (동시성={CONCURRENT_LIMIT}) ---")
    
    async with httpx.AsyncClient(timeout=10.0) as http_client:
      semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
      
      async def limited_task(user_row, index):
        user_id = user_row['id']
        print(f"  > 시작 ( {index + 1} / {len(users_to_run_rows)} ) : User {user_id}")
        
        async with semaphore:
          # (수정된 run_single_user_recommendation 호출)
          result = await run_single_user_recommendation(
            user_row, ground_truth_map, http_client, K_VALUE
          )
        
        if isinstance(result, dict) and result.get("error") is None:
          # (이전 캐시 파일 이름: {user_id}.json)
          cache_file = os.path.join(CACHE_DIR, f"{user_id}.json")
          try:
            with open(cache_file, 'w', encoding='utf-8') as f:
              json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  > 완료/저장 ( {index + 1} / {len(users_to_run_rows)} ) : User {user_id}")
          except Exception as e:
            print(f"  > 완료/저장실패 ( {index + 1} ) : User {user_id} (이유: {e})")
        else:
          error_msg = result.get("error", "알 수 없는 오류") if isinstance(result, dict) else str(result)
          print(f"  > 실패 ( {index + 1} / {len(users_to_run_rows)} ) : User {user_id} (이유: {error_msg})")
          
        return result

      tasks = [limited_task(row, i) for i, row in enumerate(users_to_run_rows)]
      new_results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    for r in new_results_raw:
      if isinstance(r, dict) and r.get("error") is None:
        newly_completed_results.append(r)

  else:
    print("\n--- [4/5] 새로 실행할 작업이 없습니다. (모두 캐시됨) ---")

  # --- [ 5. 최종 결과 취합 및 통계 (변경 없음) ] ---
  print("\n--- [5/5] 평가 완료. 최종 통계 계산 중 ---")

  all_success_results = cached_results + newly_completed_results

  if not all_success_results:
    print("[오류] 성공한 결과가 0건입니다. 통계를 계산할 수 없습니다.")
    return

  df_metrics = pd.DataFrame(all_success_results)
  try:
    df_metrics.to_csv(FINAL_CSV_OUTPUT, index=False, encoding='utf-8-sig')
    print(f"\n[성공] 최종 평가 결과가 '{FINAL_CSV_OUTPUT}' 파일로 저장되었습니다.")
  except Exception as e:
    print(f"\n[오류] 최종 CSV 파일 저장 실패: {e}")

  p_col = f'precision_at_{K_VALUE}'
  r_col = f'recall_at_{K_VALUE}'
  
  p_stats = df_metrics[p_col].describe()
  p_var = df_metrics[p_col].var()
  r_stats = df_metrics[r_col].describe()
  r_var = df_metrics[r_col].var()
  
  print("\n" + "="*50)
  print(f"📊 'Live' 추천 파이프라인 전체 평가 통계 (K={K_VALUE})")
  print(f"(총 {len(all_success_results)}명 성공 / {len(profiles_df) - len(all_success_results)}명 실패 또는 누락)")
  print("="*50)
  
  stats_df = pd.DataFrame({ p_col: p_stats, r_col: r_stats })
  stats_df.loc['variance'] = [p_var, r_var]
  stats_df = stats_df.rename(index={
      'count': '개수 (count)', 'mean': '평균 (mean)', 'std': '표준편차 (std)',
      '50%': '중위값 (median)', 'min': '최소값 (min)', '25%': '25% (Q1)',
      '75%': '75% (Q3)', 'max': '최대값 (max)', 'variance': '분산 (variance)'
  })
  
  final_order = [
      '개수 (count)', '평균 (mean)', '분산 (variance)', '표준편차 (std)', 
      '중위값 (median)', '최소값 (min)', '25% (Q1)', '75% (Q3)', '최대값 (max)'
  ]
  
  printable_order = [idx for idx in final_order if idx in stats_df.index]
  print(stats_df.loc[printable_order])
  print("-" * 50)
  print(f"참고: 사용자당 평균 정답('추천') 개수: {df_metrics['ground_truth_size'].mean():.2f} 개")
  
  save_result_visualizations(df_metrics, p_col, r_col, K_VALUE)


# ==================================================================
# 6. 스크립트 실행
# ==================================================================
if __name__ == "__main__":
  print("평가 스크립트를 시작합니다 (캐시 기능 포함)...")
  
  if os.name == 'nt':
    try:
      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except:
      print("[정보] WindowsSelectorEventLoopPolicy 설정 실패 (무시하고 진행)")
      
  asyncio.run(main_evaluation())
  
  
  
"""
==================================================
📊 'Live' 추천 파이프라인 전체 평가 통계 (K=10)
(총 500명 성공 / 0명 실패 또는 누락)
==================================================
               precision_at_10  recall_at_10
개수 (count)        500.000000    500.000000
평균 (mean)           0.447400      0.639143
분산 (variance)       0.064542      0.131719
표준편차 (std)         0.254052      0.362931
중위값 (median)       0.500000      0.714286
최소값 (min)          0.000000      0.000000
25% (Q1)            0.200000      0.285714
75% (Q3)            0.700000      1.000000
최대값 (max)          0.700000      1.000000
--------------------------------------------------
참고: 사용자당 평균 정답('추천') 개수: 6.52 개
"""
