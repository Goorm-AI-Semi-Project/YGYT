import pandas as pd
import json
import math
import asyncio # 비동기 처리를 위해 asyncio 추가
from typing import List, Dict, Any
import httpx # requests 대신 httpx.AsyncClient를 main.py에서 전달받아 사용

# --- 기획자가 설정하는 가중치 (Weights) ---
# 기획 의도: "뚜벅이 경험이 가장 중요하고, 그다음이 외국인 친화도"
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

async def get_best_travel_score_async(
    restaurant: pd.Series, 
    user_start_location: str, 
    async_http_client: httpx.AsyncClient, 
    graphhopper_url: str
) -> float:
    """
    [비동기 API 호출] main.py에서 전달받은 http 클라이언트를 사용하여
    GraphHopper API를 호출하고 가장 좋은 '이동 마찰 점수'를 반환합니다.
    """
    
    # --- 1. API 호출 준비 ---
    to_coords = f"{restaurant['Y좌표']},{restaurant['X좌표']}"
    
    params = [
        ('point', user_start_location),
        ('point', to_coords),
        ('profile', 'pt'),
        ('pt.earliest_departure_time', '2023-01-01T09:00:00Z'), # 예시 시간 (main.py에서와 동일하게)
        ('algorithm', 'alternative_route'),
        ('alternative_route.max_paths', '3')
    ]

    # --- 2. API 호출 및 경로 데이터 추출 ---
    try:
        # main.py에서 받은 클라이언트로 GraphHopper (localhost:8989) 직접 호출
        response = await async_http_client.get(graphhopper_url, params=params, timeout=10)
        response.raise_for_status() 
        
        data = response.json()
        route_plans = data.get('paths', []) # GraphHopper 원본 응답은 'paths'

    except (httpx.RequestError, json.JSONDecodeError) as e:
        print(f"Error: GraphHopper API 요청 실패 (ID: {restaurant.name}): {e}")
        return 0.0

    # --- 3. 점수 계산 (기존 로직 재사용) ---
    if not route_plans:
        return 0.0

    all_path_scores = []
    for path in route_plans:
        score = calculate_travel_friction_score(path)
        all_path_scores.append(score)
    
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

async def calculate_final_scores_async(
    candidate_df: pd.DataFrame, 
    user_start_location: str, 
    user_price_prefs: List[str],
    async_http_client: httpx.AsyncClient,
    graphhopper_url: str
) -> pd.DataFrame:
    """
    (비동기) 후보 DataFrame을 입력받아,
    150개의 이동 마찰 점수 계산을 '동시에' 실행하고 최종 정렬하여 반환합니다.
    """
    
    print(f"--- 최종 점수 계산 시작 (후보군: {len(candidate_df)}개) ---")
    
    df = candidate_df.copy()
    
    # 가중치
    W = WEIGHTS
    
    # 1. Travel_Friction (이동 마찰 점수) 계산 (비동기 동시 처리)
    print("1/4. 이동 마찰 점수 계산 중 (API 동시 호출)...")
    
    # 150개의 API 호출 작업을 리스트로 만듭니다.
    tasks = []
    for index, row in df.iterrows():
        tasks.append(
            get_best_travel_score_async(
                row, 
                user_start_location, 
                async_http_client, 
                graphhopper_url
            )
        )
    
    # asyncio.gather를 사용해 150개 API 호출을 '동시에' 실행
    travel_scores = await asyncio.gather(*tasks)
    
    df['score_travel'] = travel_scores
    
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


