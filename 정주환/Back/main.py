import asyncio
import httpx
from contextlib import asynccontextmanager
import sys
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, Query, HTTPException
from neo4j import AsyncGraphDatabase # Neo4j 임시 주석 처리
# Pydantic V2에 맞게 RootModel을 추가로 임포트합니다.
from pydantic import BaseModel, Field, RootModel

# --- 📜 1. 설정: GraphHopper 및 Neo4j 정보 ---
NEO4J_URI = "bolt://localhost:7687" # Neo4j 임시 주석 처리
NEO4J_USER = "neo4j" # Neo4j 임시 주석 처리
NEO4J_PASSWORD = "wnghks1278" # Neo4j 임시 주석 처리
GRAPH_HOPPER_API_URL = "http://localhost:8989/route"
GRAPH_HOPPER_HEALTH_CHECK_URL = "http://localhost:8989/info"

# --- ✅ 2. Pydantic 모델 정의 ---
class POI(BaseModel):
    name: str = Field(..., description="The name of the place", json_schema_extra={'example': "Deoksugung Palace"})
    category: str = Field(..., description="The category of the place", json_schema_extra={'example': "Tourist Attraction"})

class ContextualInfo(RootModel[Dict[str, List[POI]]]):
    pass

# 여러 경로를 반환하도록 수정
class TripPlanResponse(BaseModel):
    route_plans: List[Dict[str, Any]] = Field(..., description="Multiple route options provided by GraphHopper")
    contextual_info: ContextualInfo = Field(..., description="Additional contextual information around the route provided by Neo4j")


# --- 🚀 3. 애플리케이션 생명 주기 관리 (GraphHopper 용으로 수정) ---
db_driver = None # Neo4j 임시 주석 처리

@asynccontextmanager
async def lifespan(app: FastAPI):
    # global db_driver # Neo4j 임시 주석 처리
    # # Neo4j 드라이버 연결
    # db_driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) # Neo4j 임시 주석 처리
    # print("✅ Neo4j driver connected.") # Neo4j 임시 주석 처리
    
    # 별도로 실행된 GraphHopper 서버가 준비될 때까지 대기
    print("⏳ Waiting for independently running GraphHopper server to become responsive...")
    is_gh_ready = False
    # 최대 2분 대기 (12 * 10초)
    for attempt in range(12):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(GRAPH_HOPPER_HEALTH_CHECK_URL, timeout=5.0)
                if response.status_code == 200:
                    is_gh_ready = True
                    print(f"✅ GraphHopper server is ready! (took {(attempt + 1) * 10} seconds to respond)")
                    break
        except httpx.RequestError:
            await asyncio.sleep(10)
            
    if not is_gh_ready:
        print("🛑 GraphHopper server did not respond. Please ensure it is running.", file=sys.stderr)
    
    yield
    
    # # 앱 종료 시 Neo4j 드라이버 연결 해제
    # if db_driver: # Neo4j 임시 주석 처리
    #     await db_driver.close() # Neo4j 임시 주석 처리
    #     print("🛑 Neo4j driver closed.") # Neo4j 임시 주석 처리
    print("Application shutdown.")

app = FastAPI(
    lifespan=lifespan,
    title="🧠 Smart Path Planning API (GraphHopper Edition)",
    description="An API that combines GraphHopper and Neo4j to provide real-time route planning with contextual information.",
    version="2.0.0"
)

# --- 4. API 엔드포인트 코드 (GraphHopper 용으로 수정) ---
@app.get("/", tags=["Status"])
async def read_root():
    """Checks if the server is running properly."""
    return {"status": "ok", "message": "Welcome to the Smart Path Planning API (GraphHopper Edition)!"}

@app.get(
    "/plan-trip",
    response_model=TripPlanResponse,
    tags=["Path Planning"],
    summary="대중교통 경로 탐색 API (GraphHopper 기반)"
)
async def plan_trip(
    from_coords: str = Query(..., alias="from", description="출발 좌표 (예: 37.5547,126.9704)"),
    to_coords: str = Query(..., alias="to", description="도착 좌표 (예: 37.4979,127.0276)"),
    date: str = Query(None, description="출발 날짜 (예: 2023-03-02)"),
    time: str = Query(None, description="출발 시각 (예: 09:00am 또는 14:30)")
):
    # --- GraphHopper 요청 파라미터 생성 ---
    now = datetime.now()
    travel_date = date or now.strftime("%Y-%m-%d")
    
    # 'am/pm' 형식 또는 24시간 형식의 시간을 HH:MM:SS로 변환
    try:
        if time:
            if "am" in time.lower() or "pm" in time.lower():
                travel_time_obj = datetime.strptime(time, "%I:%M%p")
            else:
                travel_time_obj = datetime.strptime(time, "%H:%M")
        else: # 기본값
            travel_time_obj = datetime.strptime("09:00", "%H:%M")
        
        travel_time_24hr = travel_time_obj.strftime("%H:%M:%S")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use 'HH:MMam/pm' or 'HH:MM'.")

    # ISO 8601 형식으로 조합 (예: 2023-03-02T09:00:00Z)
    departure_datetime_str = f"{travel_date}T{travel_time_24hr}Z"
    
    # GraphHopper는 동일한 이름의 파라미터를 여러 번 받으므로 리스트로 전달
    params = [
        ('point', from_coords),
        ('point', to_coords),
        ('profile', 'pt'),
        ('pt.earliest_departure_time', departure_datetime_str),
        ('algorithm', 'alternative_route'),
        ('alternative_route.max_paths', '3')
    ]
    
    # --- GraphHopper API 호출 ---
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(GRAPH_HOPPER_API_URL, params=params, timeout=60.0)
            response.raise_for_status()
            gh_data = response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"GraphHopper server request failed: {e}")

    if 'paths' not in gh_data or not gh_data['paths']:
        raise HTTPException(status_code=404, detail="Route not found by GraphHopper.")
    
    paths = gh_data['paths']
    
    # --- Neo4j에서 주변 정보 조회 (임시 주석 처리) ---
    # GraphHopper 응답 구조에 맞게 정류장 이름 추출
    stops_in_path = set()
    
    # paths는 리스트이므로 각 path를 순회
    for path in paths:
        # 각 path에서 legs를 가져옴
        legs = path.get('legs', [])
        for leg in legs:
            # pt(public transport) 타입의 leg만 처리
            if leg.get('type') == 'pt':
                # stops 리스트에서 정류장 이름 추출
                stops = leg.get('stops', [])
                for stop in stops:
                    if 'stop_name' in stop:
                        stops_in_path.add(stop['stop_name'])

    nearby_pois_dict = {}
    # Neo4j 연결이 활성화되어 있다면 아래 주석 해제
    # if stops_in_path and db_driver:
    #     async with db_driver.session() as session:
    #         for stop_name in stops_in_path:
    #             cypher_query = "MATCH (s:Stop {name: $stop_name})-[:NEARBY]->(p:POI) RETURN p.name as name, p.category as category"
    #             result = await session.run(cypher_query, stop_name=stop_name)
    #             pois = [{"name": r["name"], "category": r["category"]} async for r in result]
    #             if pois:
    #                 nearby_pois_dict[stop_name] = pois

    # RootModel을 사용하므로 딕셔너리를 바로 전달
    return TripPlanResponse(
        route_plans=paths,
        contextual_info=nearby_pois_dict
    )

if __name__ == "__main__":
    import uvicorn
    # 포트를 8080으로 변경 (포트 충돌 방지)
    uvicorn.run("graphhopper_server:app", host="127.0.0.1", port=8080, reload=True)