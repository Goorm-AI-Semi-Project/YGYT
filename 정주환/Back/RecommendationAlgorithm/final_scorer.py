import pandas as pd
import json
import math
import random # API 호출 시뮬레이션을 위한 임시 모듈
from typing import List, Dict, Any

# --- 기획자가 설정하는 가중치 (Weights) ---
# 기획 의도: "뚜벅이 경험이 가장 중요하고, 그다음이 외국인 친화도!"
WEIGHTS = {
    'travel': 0.4,      # w_1: Travel_Friction (이동 마찰)
    'friendliness': 0.3, # w_2: Foreigner_Friendliness (외국인 친화도)
    'quality': 0.2,      # w_3: Quality_Score (품질 점수)
    'price': 0.1,        # w_4: Price_Match (가격 일치도)
}
# -------------------------------------------


# [from move.py] 
# move.py의 이동 마찰 점수 계산 함수를 그대로 가져옵니다.
def calculate_travel_friction_score(path_data: dict) -> float:
    """
    GraphHopper의 단일 경로(path) 데이터를 기반으로
    '이동 마찰 점수'(0~1)를 계산합니다. (1점이 가장 좋음)
    """
    
    # 1. 핵심 지표 추출
    total_time_minutes = path_data.get('time', 0) / 1000 / 60
    num_transfers = path_data.get('transfers', 0)
    total_walk_meters = path_data.get('distance', 0)
    
    # 2. 각 지표를 0~1 사이 점수로 정규화
    
    # (A) 시간 점수: 20분 이하는 1점, 50분 이상은 0점
    max_time = 50
    min_time = 20
    time_score = 1 - min(1, max(0, (total_time_minutes - min_time) / (max_time - min_time)))
    
    # (B) 도보 점수: 500m 이하는 1점, 1.2km 이상은 0점
    max_walk = 1200
    min_walk = 500
    walk_score = 1 - min(1, max(0, (total_walk_meters - min_walk) / (max_walk - min_walk)))
    
    # (C) 환승 점수: 0회 = 1점, 1회 = 0.4점, 2회 이상 = 0점
    if num_transfers == 0:
        transfer_score = 1.0
    elif num_transfers == 1:
        transfer_score = 0.4
    else:
        transfer_score = 0.0
        
    # 3. 최종 점수 (가중 평균)
    weights = {'walk': 0.4, 'transfers': 0.4, 'time': 0.2}
    final_score = (
        (time_score * weights['time']) +
        (walk_score * weights['walk']) +
        (transfer_score * weights['transfers'])
    )
    
    return final_score

# --- 점수 계산 헬퍼 함수 ---

def get_best_travel_score(restaurant: pd.Series, user_start_location: str) -> float:
    """
    [API 호출] 사용자의 현재 위치에서 특정 식당까지의 경로를 API로 조회하고,
    가장 좋은 '이동 마찰 점수'를 반환합니다.
    
    TODO: 이 함수는 실제 API 호출 로직으로 대체되어야 합니다.
    """
    # API 호출 시 '가게' 컬럼 사용
    print(f"-> API 호출: '{user_start_location}'에서 '{restaurant['가게']}'(id:{restaurant['id']})까지 경로 조회...")
    
    # --- 시뮬레이션 로직 ---
    # 실제로는 이 부분에 GraphHopper (또는 다른 경로 API)를 호출하는 코드가 들어갑니다.
    # Y좌표(위도), X좌표(경도) 순서로 API에 전달
    # response = call_graphhopper_api(user_start_location, restaurant['Y좌표'], restaurant['X좌표'])
    # route_plans = response.get('route_plans', [])
    
    # (시뮬레이션) API 응답이 왔다고 가정하고, move.py의 테스트 JSON처럼 가짜 경로 3개를 생성합니다.
    simulated_route_plans = [
        {'time': 1200000, 'transfers': 0, 'distance': 300}, # 20분, 0환승, 300m 도보
        {'time': 900000, 'transfers': 1, 'distance': 800},  # 15분, 1환승, 800m 도보
        {'time': 2100000, 'transfers': 2, 'distance': 100}, # 35분, 2환승, 100m 도보
    ]
    # 실제 API 응답을 사용할 때는 이 부분을 삭제하세요.
    random.shuffle(simulated_route_plans)
    route_plans = simulated_route_plans[:random.randint(1,3)] # 1~3개의 경로가 왔다고 가정
    
    # --- / 시뮬레이션 로직 끝 ---

    if not route_plans:
        # 경로가 없는 경우 (예: 제주도 -> 서울) 0점 처리
        return 0.0

    all_path_scores = []
    for path in route_plans:
        # move.py의 함수를 사용해 각 경로의 점수 계산
        score = calculate_travel_friction_score(path)
        all_path_scores.append(score)
    
    # 사용자는 가장 편한 경로를 선택할 것이므로, 가장 높은 점수를 해당 식당의 점수로 사용
    best_score = max(all_path_scores)
    return best_score

def get_price_match_score(restaurant_price: str, user_price_prefs: List[str]) -> int:
    """
    사용자가 선택한 예산과 식당의 가격대가 일치하는지 확인합니다.
    예: user_price_prefs = ['$$', '$$$']
    """
    if not restaurant_price or not isinstance(restaurant_price, str):
        return 0
        
    # 예: '$$'가 ['$$', '$$$'] 안에 포함되면 1점
    if restaurant_price.strip() in user_price_prefs:
        return 1
    else:
        return 0

# --- 메인 스코어링 함수 ---

def calculate_final_scores(candidate_df: pd.DataFrame, user_start_location: str, user_price_prefs: List[str]) -> pd.DataFrame:
    """
    후보 식당 DataFrame을 입력받아,
    사용자 위치/예산에 맞춰 모든 점수를 계산하고 'final_score'로 정렬하여 반환합니다.
    """
    
    print(f"--- 최종 점수 계산 시작 (후보군: {len(candidate_df)}개) ---")
    
    df = candidate_df.copy()
    
    # 가중치
    W = WEIGHTS
    
    # 1. Travel_Friction (이동 마찰 점수) 계산
    # df.apply는 각 행(row)을 순회하며 함수를 적용합니다.
    # (API 호출이 필요하므로 시간이 다소 걸릴 수 있습니다)
    print("1/4. 이동 마찰 점수 계산 중 (API 호출 시뮬레이션)...")
    df['score_travel'] = df.apply(
        lambda row: get_best_travel_score(row, user_start_location), 
        axis=1
    )
    
    # 2. Foreigner_Friendliness (외국인 친화도)
    # (이미 계산된 'avg_friendliness' 값을 그대로 사용)
    print("2/4. 외국인 친화도 점수 할당 중...")
    df['score_friendliness'] = df['avg_friendliness']
    
    # 3. Quality_Score (품질 점수)
    # (이미 계산된 'avg_quality' 값을 그대로 사용)
    print("3/4. 품질 점수 할당 중...")
    df['score_quality'] = df['avg_quality']
    
    # 4. Price_Match (가격 일치도)
    print("4/4. 가격 일치도 점수 계산 중...")
    # 'price' 컬럼이 원본 CSV에 있다고 가정합니다.
    # 만약 컬럼명이 다르면 'price_col_name'을 수정해주세요.
    # (제공해주신 헤더에 'price'가 없으므로, 경고가 출력되고 0점으로 처리될 것입니다)
    price_col_name = 'price' 
    if price_col_name not in df.columns:
        print(f"  [경고] '{price_col_name}' 컬럼을 찾을 수 없습니다. 가격 일치도 점수를 0으로 처리합니다.")
        df['score_price'] = 0
    else:
        df['score_price'] = df[price_col_name].apply(
            lambda price_str: get_price_match_score(price_str, user_price_prefs)
        )
    
    # --- 최종 점수 (Final_Score) 계산 ---
    print("--- 모든 점수 집계 완료. Final_Score 계산 중... ---")
    
    df['final_score'] = (
        df['score_travel'] * W['travel'] +
        df['score_friendliness'] * W['friendliness'] +
        df['score_quality'] * W['quality'] +
        df['score_price'] * W['price']
    )
    
    # 점수가 높은 순서대로 정렬
    df_sorted = df.sort_values(by='final_score', ascending=False)
    
    print("--- 최종 점수 계산 및 정렬 완료 ---")
    
    # 로그 기록을 위해 모든 피처가 포함된 DataFrame을 반환
    return df_sorted

# --- 스크립트 실행 테스트 (예제) ---
if __name__ == "__main__":
    
    # 0. (사전) '음식점별 점수 집계 및 통합.py'가 생성한 파일을 로드합니다.
    INPUT_SCORES_FILE = 'blueribbon_scores_only_reviewed.csv'
    try:
        all_restaurants_df = pd.read_csv(INPUT_SCORES_FILE)
    except FileNotFoundError:
        print(f"[오류] {INPUT_SCORES_FILE} 파일을 찾을 수 없습니다.")
        print("먼저 '음식점별 점수 집계 및 통합.py'를 실행해야 합니다.")
        exit()

    # (가정) 원본 데이터에 'price' 컬럼이 없어서 시뮬레이션을 위해 임의로 추가 <-- 삭제
    # if 'price' not in all_restaurants_df.columns:
    #     print("[알림] 'price' 컬럼이 없어 임의로 생성합니다. (테스트용)")
    #     all_restaurants_df['price'] = ['$'] * (len(all_restaurants_df) // 2) + ['$$'] * (len(all_restaurants_df) - len(all_restaurants_df) // 2)

    # 1. (시뮬레이션) 1단계: 후보군 150개 생성
    # (실제로는 1단계 추천 모델이 반환한 ID 목록을 기반으로 필터링)
    if len(all_restaurants_df) > 150:
        candidate_list_df = all_restaurants_df.sample(n=150, random_state=42)
    else:
        candidate_list_df = all_restaurants_df.copy()

    # 2. (시뮬레이션) 사용자 입력값 (웹사이트에서 받아옴)
    USER_START_LOCATION = "37.5665, 126.9780" # (예: 서울시청)
    USER_PRICE_PREFS = ['$$', '$$$']         # (예: "조금 비싸도 괜찮아요")

    # 3. (실행) 2단계: 가중치 기반 최종 점수 계산
    scored_results_df = calculate_final_scores(
        candidate_df=candidate_list_df,
        user_start_location=USER_START_LOCATION,
        user_price_prefs=USER_PRICE_PREFS
    )
    
    # 4. (결과 확인) 최종 추천 목록 (상위 10개)
    print("\n========= [ 최종 추천 목록 (Top 10) ] ==========")
    
    # 로그 기록에 필요한 모든 컬럼을 포함하여 출력
    result_columns = [
        'id', '가게', 'final_score', 
        'score_travel', 'score_friendliness', 'score_quality', 'score_price'
    ]
    # '가게' 컬럼이 있는지 확인 (없을 경우 sh_name으로 대체 시도)
    if '가게' not in scored_results_df.columns and 'sh_name' in scored_results_df.columns:
        result_columns[1] = 'sh_name'
    elif '가게' not in scored_results_df.columns and 'sh_name' not in scored_results_df.columns:
        result_columns.pop(1) # 이름 컬럼이 없으면 제외
        
    print(scored_results_df[result_columns].head(10).to_string())
    
    print("\n=================================================")
    print("'final_score'가 높은 순서대로 정렬되었습니다.")
    print("이 'scored_results_df' DataFrame을 DB에 로그로 기록하면 됩니다.")

