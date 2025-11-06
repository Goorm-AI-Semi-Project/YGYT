import asyncio
import httpx
from contextlib import asynccontextmanager
import sys
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd # pandas 임포트
import random # 150개 샘플링을 위한 random 임포트

from fastapi import FastAPI, Query, HTTPException, Body
# Pydantic V2에 맞게 RootModel을 추가로 임포트합니다.
from pydantic import BaseModel, Field

# final_scorer.py에서 로직 함수들을 임포트합니다.
import RecommendationAlgorithm.final_scorer as final_scorer

import json

# --- 1. 설정: GraphHopper 및 Neo4j 정보 ---
GRAPH_HOPPER_API_URL = "http://localhost:8989/route"
GRAPH_HOPPER_HEALTH_CHECK_URL = "http://localhost:8989/info"
RESTAURANT_DATA_FILE = "RecommendationAlgorithm/blueribbon_scores_only_reviewed.csv" # 0단계에서 생성된 파일

# --- 2. Pydantic 모델 정의 ---
# (새로 추가) 추천 요청 모델
class RecommendationRequest(BaseModel):
    user_start_location: str = Field(..., 
                                     description="사용자 출발 좌표 (예: 37.5665,126.9780)", 
                                     json_schema_extra={'example': "37.5665,126.9780"})
    user_price_prefs: List[str] = Field(default_factory=list, 
                                        description="사용자 선호 가격대 (예: ['$$', '$$$'])", 
                                        json_schema_extra={'example': ['$$', '$$$']})
    candidate_count: int = Field(default=150, 
                                 description="1단계 후보군 수", 
                                 json_schema_extra={'example': 150})

# (새로 추가) 추천 응답 모델 (결과는 JSON으로 변환된 리스트)
class RecommendationResponse(BaseModel):
    recommendations: List[Dict[str, Any]] = Field(..., description="최종 점수로 정렬된 추천 식당 목록")
    log_info: Dict[str, Any] = Field(..., description="로그 기록용 메타데이터")


# --- 3. 애플리케이션 생명 주기 관리 ---
all_restaurants_df = None # 식당 데이터를 메모리에 로드할 전역 변수

@asynccontextmanager
async def lifespan(app: FastAPI):
    global all_restaurants_df
    
    # 0단계: 서버 시작 시 식당 데이터를 메모리에 로드
    try:
        all_restaurants_df = pd.read_csv(RESTAURANT_DATA_FILE)
        # (가정) 원본 데이터에 'price' 컬럼이 없어서 시뮬레이션을 위해 임의로 추가
        if 'price' not in all_restaurants_df.columns:
            print("Info: 'price' 컬럼이 없어 임의로 생성합니다. (테스트용)")
            all_restaurants_df['price'] = ['$'] * (len(all_restaurants_df) // 2) + ['$$'] * (len(all_restaurants_df) - len(all_restaurants_df) // 2)
        
        print(f"Success: {RESTAURANT_DATA_FILE} 로드 성공. (총 {len(all_restaurants_df)}개 식당)")
    except FileNotFoundError:
        print(f"Error: {RESTAURANT_DATA_FILE} 파일을 찾을 수 없습니다. 서버가 시작되지 않습니다.", file=sys.stderr)
        all_restaurants_df = pd.DataFrame() # 임시로 빈 DataFrame 생성
    
    # 별도로 실행된 GraphHopper 서버가 준비될 때까지 대기
    print("Waiting for independently running GraphHopper server to become responsive...")
    is_gh_ready = False
    # 최대 2분 대기 (12 * 10초)
    for attempt in range(12):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(GRAPH_HOPPER_HEALTH_CHECK_URL, timeout=5.0)
                if response.status_code == 200:
                    is_gh_ready = True
                    print(f"Success: GraphHopper server is ready! (took {(attempt + 1) * 10} seconds to respond)")
                    break
        except httpx.RequestError:
            await asyncio.sleep(10)
            
    if not is_gh_ready:
        print("Error: GraphHopper server did not respond. Please ensure it is running.", file=sys.stderr)
    
    yield
    
    print("Application shutdown.")

app = FastAPI(
    lifespan=lifespan,
    title="Smart Path Planning API",
    description="An API that provides real-time route-aware recommendations.",
    version="2.0.0"
)

# --- 4. API 엔드포인트 코드 ---
@app.get("/", tags=["Status"])
async def read_root():
    """Checks if the server is running properly."""
    return {"status": "ok", "message": "Welcome to the Smart Path Planning API!"}


# --- 5. 최종 추천 엔드포인트 ---
@app.post(
    "/recommendations",
    response_model=RecommendationResponse,
    tags=["Recommendations"],
    summary="가중치 기반 최종 식당 추천 API"
)
async def get_recommendations(
    request: RecommendationRequest = Body(...)
):
    global all_restaurants_df
    if all_restaurants_df is None or all_restaurants_df.empty:
        raise HTTPException(status_code=503, detail="Restaurant data is not loaded. Server is not ready.")

    # 1. 1단계: 후보군 생성 (현재는 랜덤 샘플링으로 대체)
    # TODO: 실제 1단계 모델(CF 등)의 ID 목록을 기반으로 필터링해야 함
    if len(all_restaurants_df) > request.candidate_count:
        candidate_df = all_restaurants_df.sample(n=request.candidate_count, random_state=42)
    else:
        candidate_df = all_restaurants_df.copy()

    # 2. 2단계: 가중치 기반 최종 점수 계산 (final_scorer.py 호출)
    # httpx.AsyncClient를 생성하여 final_scorer로 전달
    async with httpx.AsyncClient() as client:
        try:
            sorted_df = await final_scorer.calculate_final_scores_async(
                candidate_df=candidate_df,
                user_start_location=request.user_start_location,
                user_price_prefs=request.user_price_prefs,
                async_http_client=client,
                graphhopper_url=GRAPH_HOPPER_API_URL # 설정에서 URL 전달
            )
        except Exception as e:
            print(f"Error: 최종 점수 계산 중 오류 발생: {e}")
            raise HTTPException(status_code=500, detail=f"Error during score calculation: {e}")

    # 3. 결과 포맷팅 및 로그 정보 생성
    # DataFrame을 JSON으로 변환 (NaN -> None)
    results_json = json.loads(sorted_df.to_json(orient='records'))

    log_info = {
        "timestamp": datetime.now().isoformat(),
        "user_location": request.user_start_location,
        "user_price": request.user_price_prefs,
        "candidate_count": len(candidate_df),
        "weights": final_scorer.WEIGHTS # final_scorer의 가중치 정보 로깅
    }

    # 최종 응답 반환
    return RecommendationResponse(
        recommendations=results_json,
        log_info=log_info
    )


if __name__ == "__main__":
    import uvicorn
    # 포트를 8080으로 변경 (포트 충돌 방지)
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)

