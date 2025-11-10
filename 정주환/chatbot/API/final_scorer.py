import pandas as pd
import json
import math
import asyncio # 비동기 처리를 위해 asyncio 추가
from typing import List, Dict, Any
import httpx # requests 대신 httpx.AsyncClient를 main.py에서 전달받아 사용

class GraphHopperDownError(Exception):
    """GraphHopper 서버가 다운되었거나 모든 요청이 실패했을 때 발생하는 전용 오류"""
    pass

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
    """ (수정) GraphHopper API를 비동기로 호출 (try-except 제거) """
    
    from_coords = user_start_location
    to_coords = f"{restaurant['Y좌표']},{restaurant['X좌표']}"
    
    params = [
        ('point', from_coords),
        ('point', to_coords),
        ('profile', 'pt'),
        ('pt.earliest_departure_time', "2024-01-01T09:00:00Z"), # (고정된 표준시)
        ('algorithm', 'alternative_route'),
        ('alternative_route.max_paths', '3')
    ]
    
    # try-except 블록 삭제
    # (httpx.RequestError 등이 발생하면 asyncio.gather가 잡도록 둡니다)
    response = await async_http_client.get(graphhopper_url, params=params, timeout=10.0)
    response.raise_for_status() # (4xx, 5xx 오류 시 예외 발생)
    data = response.json()
    route_plans = data.get('paths', [])
    
    if not route_plans:
        return 0.0 # (경로 없음)

    all_path_scores = [calculate_travel_friction_score(path) for path in route_plans]
    best_score = max(all_path_scores) if all_path_scores else 0.0
    
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
    (대폭 수정) 
    1. 후보군 DF에 4가지 점수를 계산 (비동기 GraphHopper 호출 포함)
    2. 모든 GraphHopper 호출 실패 시 GraphHopperDownError 발생
    """
    
    # --- 1/4. 이동 마찰 점수 (비동기) ---
    print(f"1/4. 이동 마찰 점수 계산 중 (API 동시 호출)...")
    
    tasks = [
        get_best_travel_score_async(
            restaurant, 
            user_start_location, 
            async_http_client, 
            graphhopper_url
        ) 
        for _, restaurant in candidate_df.iterrows()
    ]
    
    # [ ★★★ 3. asyncio.gather 수정 (예외 처리) ★★★ ]
    # return_exceptions=True : 개별 작업이 실패해도 중단하지 않고, 결과 리스트에 Exception 객체를 포함
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    travel_scores = []
    any_failures = False
    
    for i, res in enumerate(results):
        if isinstance(res, float):
            travel_scores.append(res)
        else:
            # (res는 Exception 객체)
            restaurant_id = candidate_df.index[i] # (ID는 .index에 있음)
            print(f"Error: GraphHopper API 요청 실패 (ID: {restaurant_id}): {res}")
            travel_scores.append(0.0)
            any_failures = True
            
    # [ ★★★ 4. 서버 다운 감지 로직 추가 ★★★ ]
    # (모든 점수가 0점이고, 그 중 하나라도 실패(Exception)가 있었다면 -> 서버 다운으로 간주)
    if any_failures and all(s == 0.0 for s in travel_scores) and not candidate_df.empty:
        print("[치명적 오류] GraphHopper 서버가 다운되었거나 모든 요청이 실패했습니다. Fallback을 위해 오류를 발생시킵니다.")
        raise GraphHopperDownError("GraphHopper server is unreachable or all requests failed.")
        
    candidate_df['score_travel'] = travel_scores
    
    # ... (이하 2, 3, 4번 점수 계산 및 final_score 계산 로직은 기존과 동일) ...
    
    # --- 2/4. 외국인 친화도 점수 (미리 계산됨) ---
    print("2/4. 외국인 친화도 점수 계산 중...")
    candidate_df['score_friendliness'] = candidate_df['avg_friendliness']
    
    # --- 3/4. 품질 점수 (미리 계산됨) ---
    print("3/4. 품질 점수 계산 중...")
    candidate_df['score_quality'] = candidate_df['avg_quality']
    
    # --- 4/4. 가격 일치도 ---
    print("4/4. 가격 일치도 계산 중...")
    if not user_price_prefs:
        candidate_df['score_price'] = 0.0
    else:
        # 'price' 컬럼이 없거나, NaN인 경우를 대비하여 .get(col, default) 사용 안 함
        def get_price_score(row):
            if 'price' not in row or pd.isna(row['price']):
                return 0.0
            # (참고) 'price' 컬럼은 '$' 또는 '$$' 형태여야 함
            if row['price'] in user_price_prefs:
                return 1.0
            return 0.0
            
        candidate_df['score_price'] = candidate_df.apply(get_price_score, axis=1)

    # --- 최종 점수 합산 ---
    print("--- 최종 점수 합산 및 정렬 중 ---")
    weights = WEIGHTS
    
    candidate_df['final_score'] = (
        (candidate_df['score_travel'] * weights['travel']) +
        (candidate_df['score_friendliness'] * weights['friendliness']) +
        (candidate_df['score_quality'] * weights['quality']) +
        (candidate_df['score_price'] * weights['price'])
    )
    
    final_scored_df = candidate_df.sort_values(by='final_score', ascending=False)
    
    return final_scored_df