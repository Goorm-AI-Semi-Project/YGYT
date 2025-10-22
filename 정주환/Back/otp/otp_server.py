import asyncio
import httpx
from contextlib import asynccontextmanager
import sys
from typing import List, Dict, Any

from fastapi import FastAPI, Query, HTTPException
from neo4j import AsyncGraphDatabase
# 💡 Pydantic V2에 맞게 RootModel을 추가로 임포트합니다.
from pydantic import BaseModel, Field, RootModel

# --- 📜 1. 설정: 경로 및 기본 정보 ---
# OTP 서버는 이제 별도로 실행되므로, Python 코드에서는 경로 설정이 필요 없습니다.
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "wnghks1278"
OTP_API_URL = "http://localhost:8080/otp/routers/default/plan"
OTP_HEALTH_CHECK_URL = "http://localhost:8080/otp"

# --- ✅ 2. 수정된 Pydantic 모델 정의 ---
class POI(BaseModel):
    # 💡 Field의 'example'을 'json_schema_extra' 안으로 이동했습니다.
    name: str = Field(..., description="The name of the place", json_schema_extra={'example': "Deoksugung Palace"})
    category: str = Field(..., description="The category of the place", json_schema_extra={'example': "Tourist Attraction"})

# 💡 '__root__'를 사용하는 대신 RootModel을 상속받도록 수정했습니다.
class ContextualInfo(RootModel[Dict[str, List[POI]]]):
    pass

class TripPlanResponse(BaseModel):
    route_plan: Dict[str, Any] = Field(..., description="Detailed route information provided by OTP (Itinerary)")
    contextual_info: ContextualInfo = Field(..., description="Additional contextual information around the route provided by Neo4j")


# --- 🚀 3. 애플리케이션 생명 주기 관리 (수정됨) ---
# OTP 서버 실행/종료 로직을 제거하고, Neo4j 연결 및 OTP 서버 준비 상태 확인만 남깁니다.
db_driver = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_driver
    # Neo4j 드라이버 연결
    db_driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    print("✅ Neo4j driver connected.")
    
    # 별도로 실행된 OTP 서버가 준비될 때까지 대기
    print("⏳ Waiting for independently running OTP server to become responsive...")
    is_otp_ready = False
    for attempt in range(120): # 최대 20분 대기
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(OTP_HEALTH_CHECK_URL, timeout=5.0)
                if response.status_code == 200:
                    is_otp_ready = True
                    print(f"✅ OTP server is ready! (took {(attempt + 1) * 10} seconds to respond)")
                    break
        except httpx.RequestError:
            await asyncio.sleep(10)
            
    if not is_otp_ready:
        print("🛑 OTP server did not respond. Please ensure it is running in a separate terminal.", file=sys.stderr)
        # 앱 실행을 중단하지는 않고, 오류 메시지만 출력
    
    yield
    
    # 앱 종료 시 Neo4j 드라이버 연결 해제
    if db_driver:
        await db_driver.close()
        print("🛑 Neo4j driver closed.")

app = FastAPI(
    lifespan=lifespan,
    title="🧠 Smart Path Planning API",
    description="An API that combines OTP and Neo4j to provide real-time route planning with contextual information.",
    version="1.0.0"
)

# --- 4. API 엔드포인트 코드 ---
@app.get("/", tags=["Status"])
async def read_root():
    """Checks if the server is running properly."""
    return {"status": "ok", "message": "Welcome to the Smart Path Planning API!"}

@app.get(
    "/plan-trip",
    response_model=TripPlanResponse,
    tags=["Path Planning"],
    summary="대중교통 경로 탐색 API"
)
async def plan_trip(
    from_coords: str = Query(..., alias="from", description="출발 좌표 (예: 37.5665,126.9780)"),
    to_coords: str = Query(..., alias="to", description="도착 좌표 (예: 37.5172,127.0473)"),
    date: str = Query(None, description="출발 날짜 (예: 2025-10-17)"),
    time: str = Query(None, description="출발 시각 (예: 08:00am)")
):
    # 기본값 없으면 현재 날짜/시간 적용
    from datetime import datetime
    from urllib.parse import quote

    now = datetime.now()
    travel_date = date or now.strftime("%Y-%m-%d")
    travel_time = quote(time or "08:00am")  # OTP는 time 인코딩 필요

    params = {
        "fromPlace": from_coords,
        "toPlace": to_coords,
        "mode": "TRANSIT,WALK",
        "date": travel_date,
        "time": travel_time,
        "maxWalkDistance": 1000
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(OTP_API_URL, params=params, timeout=60.0)
            response.raise_for_status()
            otp_data = response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"OTP server request failed: {e}")

    if 'plan' not in otp_data or not otp_data['plan']['itineraries']:
        raise HTTPException(status_code=404, detail="Route not found by OTP.")
    
    itinerary = otp_data['plan']['itineraries'][0]
    
    stops_in_path = {leg[pos]['name'] for leg in itinerary['legs'] if leg['mode'] in ['BUS', 'SUBWAY', 'TRAM'] for pos in ['from', 'to']}

    nearby_pois_dict = {}
    async with db_driver.session() as session:
        for stop_name in stops_in_path:
            cypher_query = "MATCH (s:Stop {name: $stop_name})-[:NEARBY]->(p:POI) RETURN p.name as name, p.category as category"
            result = await session.run(cypher_query, stop_name=stop_name)
            pois = [{"name": r["name"], "category": r["category"]} async for r in result]
            if pois:
                nearby_pois_dict[stop_name] = pois
    
    # 💡 RootModel을 사용함에 따라 __root__ 키워드 없이 딕셔너리를 바로 전달하도록 수정했습니다.
    return TripPlanResponse(
        route_plan=itinerary,
        contextual_info=nearby_pois_dict
    )

if __name__ == "__main__":
    import uvicorn
    # 파일 이름이 otp_server.py라고 가정합니다. 만약 app.py라면 "app:app"으로 변경하세요.
    uvicorn.run("otp_server:app", host="127.0.0.1", port=5000, reload=True)