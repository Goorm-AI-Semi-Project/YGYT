import uvicorn
import httpx
import sys
import os
import json
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import pandas as pd
from deep_translator import GoogleTranslator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# APIserver 디렉토리를 Python 경로에 추가
api_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'APIserver'))
sys.path.insert(0, api_server_path)

# 모듈 임포트
import config
import data_loader
import llm_utils
import search_logic
from API import final_scorer
from models import RecommendationRequest, RecommendationResponse

# --- Pydantic Models ---

class ChatInitRequest(BaseModel):
    """채팅 초기화 요청"""
    language: str = "ko"

class ChatInitResponse(BaseModel):
    """채팅 초기화 응답"""
    bot_message: str
    profile: Dict[str, Any]
    is_completed: bool

class ChatMessageRequest(BaseModel):
    """채팅 메시지 요청"""
    message: str
    llm_history: List[Dict[str, str]] = []
    profile: Dict[str, Any] = {}
    language: str = "ko"

class ChatMessageResponse(BaseModel):
    """채팅 메시지 응답"""
    bot_message: str
    profile: Dict[str, Any]
    is_completed: bool

class RecommendationGenerateRequest(BaseModel):
    """추천 생성 요청 (프로필 기반)"""
    profile: Dict[str, Any]
    top_k: int = 10
    weights: Optional[Dict[str, float]] = None

class RecommendationGenerateResponse(BaseModel):
    """추천 생성 응답"""
    restaurants: List[Dict[str, Any]]
    total_count: int
    user_profile_summary: str

class TranslateRequest(BaseModel):
    """번역 요청"""
    text: str
    target_language: str  # 'en', 'ja', 'zh'

class TranslateResponse(BaseModel):
    """번역 응답"""
    translated_text: str
    original_text: str
    target_language: str

# --- 헬퍼 함수 ---

def translate_text(text: str, target_lang: str) -> str:
    """텍스트 번역 함수"""
    if not text or target_lang == 'ko':
        return text

    try:
        # deep-translator 사용
        lang_map = {
            'en': 'english',
            'ja': 'japanese',
            'zh': 'chinese (simplified)'
        }

        target_language = lang_map.get(target_lang, 'english')
        translated = GoogleTranslator(source='korean', target=target_language).translate(text)
        return translated
    except Exception as e:
        print(f"번역 오류: {e}")
        return text  # 번역 실패 시 원본 반환

# --- 헬퍼 함수 ---

def budget_mapper(budget_str: str) -> List[str]:
    """'저', '중', '고'를 'final_scorer'가 알아듣는 ['$', '$$']로 변환"""
    if budget_str == '저':
        return ['$', '$$']
    elif budget_str == '중':
        return ['$$', '$$$']
    elif budget_str == '고':
        return ['$$$', '$$$$']
    else:
        return ['$', '$$', '$$$', '$$$$']

LOCATION_COORDS = {
    "명동역": "37.5630,126.9830",
    "홍대입구역": "37.5570,126.9244",
    "강남역": "37.4980,127.0276",
    "서울역": "37.5547,126.9704",
    "서울시청": "37.5665,126.9780",
    "시청역": "37.5658,126.9772",
}

def get_start_location_coords(location_name: str) -> str:
    """장소 이름을 좌표 문자열로 변환"""
    return LOCATION_COORDS.get(location_name, "37.5630,126.9830")

# --- FastAPI 앱 및 Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 1회 실행"""
    print("--- 서버 시작: Lifespan 시작 ---")

    # 1. API 키 로드 확인
    if not config.client or not config.client.api_key:
        print("[치명적 오류] OPENAI_API_KEY가 로드되지 않았습니다.")
    else:
        print("  > OpenAI API 키 로드 완료.")

    # 2. GraphHopper 연결용 HTTP 클라이언트 생성
    app.state.http_client = httpx.AsyncClient()
    print("  > HTTPX AsyncClient 생성 완료.")

    # 3. 모든 CSV 및 VectorDB 로드
    try:
        data_loader.load_app_data(
            config.RESTAURANT_DB_FILE,
            config.MENU_DB_FILE
        )
        data_loader.load_user_ratings()
        data_loader.build_vector_db(
            config.RESTAURANT_DB_FILE,
            config.PROFILE_DB_FILE,
            config.CLEAR_DB_AND_REBUILD
        )

        # 4. /recommendations API용 스코어링 DB 로드
        app.state.all_restaurants_df_scoring = data_loader.load_scoring_data(
            config.RESTAURANT_DB_SCORING_FILE
        )

        print("  > 모든 데이터 로드 완료.")

    except Exception as e:
        print(f"[치명적 오류] 데이터 로드 실패: {e}")

    print("--- 서버 시작 완료 ---")

    yield

    # 서버 종료 시
    print("--- 서버 종료: Lifespan 종료 ---")
    await app.state.http_client.aclose()
    print("  > HTTPX AsyncClient 종료.")

# FastAPI 앱 생성
app = FastAPI(
    title="길따라 맛따라 API",
    description="식당 추천 서비스 REST API",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API 엔드포인트 ---

@app.get("/", tags=["Root"])
async def root():
    """루트 엔드포인트"""
    return {
        "message": "길따라 맛따라 API 서버",
        "version": "2.0.0",
        "endpoints": [
            "/api/chat/init",
            "/api/chat/message",
            "/api/recommendations/generate",
            "/api/restaurants/{restaurant_id}",
        ]
    }

@app.post("/api/chat/init", response_model=ChatInitResponse, tags=["Chat Survey"])
async def init_chat(request: ChatInitRequest):
    """
    채팅 세션 초기화 - AI가 첫 인사 및 설문 시작
    """
    try:
        initial_profile = config.PROFILE_TEMPLATE.copy()

        # GPT-4에게 첫 인사 요청 (언어 파라미터 전달)
        bot_message, updated_profile = llm_utils.call_gpt4o(
            chat_messages=[],
            current_profile=initial_profile,
            language=request.language
        )

        return ChatInitResponse(
            bot_message=bot_message,
            profile=updated_profile,
            is_completed=False
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 초기화 실패: {str(e)}")

@app.post("/api/chat/message", response_model=ChatMessageResponse, tags=["Chat Survey"])
async def send_chat_message(request: ChatMessageRequest):
    """
    사용자 메시지 전송 및 AI 응답 받기
    AI가 13가지 프로필 정보를 수집합니다
    """
    try:
        # LLM 히스토리에 사용자 메시지 추가
        updated_llm_history = request.llm_history + [
            {"role": "user", "content": request.message}
        ]

        # GPT-4에게 응답 요청 (언어 파라미터 전달)
        bot_message, updated_profile = llm_utils.call_gpt4o(
            chat_messages=updated_llm_history,
            current_profile=request.profile,
            language=request.language
        )

        # LLM 히스토리에 봇 응답 추가
        updated_llm_history.append({"role": "assistant", "content": bot_message})

        # 프로필 완성 여부 확인 (13개 항목 모두 채워짐)
        is_completed = all(v is not None for v in updated_profile.values())

        return ChatMessageResponse(
            bot_message=bot_message,
            profile=updated_profile,
            is_completed=is_completed
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메시지 처리 실패: {str(e)}")

@app.post("/api/recommendations/generate", response_model=RecommendationGenerateResponse, tags=["Recommendations"])
async def generate_recommendations(request: RecommendationGenerateRequest):
    """
    프로필 기반 맞춤 추천
    1단계: RAG 검색으로 후보군 생성
    2단계: final_scorer로 정밀 스코어링 (사용자 위치 기반)
    """
    try:
        profile = request.profile

        # 1단계: RAG + 협업 필터링
        print("--- 1단계: RAG 후보군 생성 시작 ---")

        profile_summary = llm_utils.generate_profile_summary_text_only(profile)
        filter_dict = search_logic.create_filter_metadata(profile)
        filter_metadata_json = json.dumps(filter_dict, ensure_ascii=False)

        user_profile_row = {
            "name": profile.get("name", "N/A"),
            "user_id": "live_user",
            "rag_query_text": profile_summary,
            "filter_metadata_json": filter_metadata_json,
        }

        candidate_ids = search_logic.get_rag_candidate_ids(
            user_profile_row,
            n_results=config.RAG_REQUEST_N_RESULTS
        )

        if not candidate_ids:
            raise HTTPException(status_code=404, detail="검색 결과가 없습니다. 필터를 완화해보세요.")

        print(f"--- 1단계 완료: {len(candidate_ids)}개 후보 ---")

        # 2단계: final_scorer (뚜벅이 점수 계산)
        print("--- 2단계: final_scorer 실행 ---")

        candidate_df = data_loader.get_restaurants_by_ids(candidate_ids)

        if candidate_df.empty:
            raise HTTPException(status_code=404, detail="후보군 DataFrame 조회 실패")

        user_start_coords = get_start_location_coords(profile.get('start_location'))
        user_price_prefs = budget_mapper(profile.get('budget'))

        try:
            final_scored_df = await final_scorer.calculate_final_scores_async(
                candidate_df=candidate_df,
                user_start_location=user_start_coords,
                user_price_prefs=user_price_prefs,
                async_http_client=app.state.http_client,
                graphhopper_url=config.GRAPH_HOPPER_API_URL,
                weights=request.weights
            )

            print(f"--- 2단계 완료: {len(final_scored_df)}개 스코어링 ---")
            # Top-K 추출
            result_df = final_scored_df.head(request.top_k)

        except Exception as scorer_error:
            print(f"[경고] final_scorer 실패, RAG 1단계 결과만 반환: {scorer_error}")
            # Fallback: RAG 1단계 결과만 반환 (GraphHopper 없어도 추천 가능)
            result_df = candidate_df.head(request.top_k)
            print(f"--- Fallback: RAG 1단계 결과 {len(result_df)}개 반환 ---")

        # 결과를 딕셔너리로 변환 (인덱스를 id 컬럼으로 포함)
        result_df_reset = result_df.reset_index()

        # NaN, Infinity 등을 None으로 변환 (JSON 직렬화 가능하게)
        result_df_reset = result_df_reset.replace([float('inf'), float('-inf')], None)
        result_df_reset = result_df_reset.where(pd.notnull(result_df_reset), None)

        restaurants = result_df_reset.to_dict('records')

        return RecommendationGenerateResponse(
            restaurants=restaurants,
            total_count=len(restaurants),
            user_profile_summary=profile_summary
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"추천 생성 실패: {str(e)}")

@app.get("/api/restaurants/{restaurant_id}", tags=["Restaurants"])
async def get_restaurant_detail(restaurant_id: str):
    """
    특정 식당의 상세 정보 조회
    """
    try:
        if data_loader.df_restaurants is None:
            raise HTTPException(status_code=503, detail="서버 준비 중")

        # df_restaurants는 id가 인덱스로 설정되어 있음
        if restaurant_id not in data_loader.df_restaurants.index:
            raise HTTPException(status_code=404, detail="식당을 찾을 수 없습니다")

        # 인덱스로 직접 접근
        restaurant = data_loader.df_restaurants.loc[restaurant_id]

        # 메뉴 정보 추가
        menus = []
        if data_loader.df_menus is not None:
            restaurant_menus = data_loader.df_menus[
                data_loader.df_menus['식당ID'] == restaurant_id
            ]
            # 메뉴 데이터를 딕셔너리로 변환하고 필드명을 영어로 매핑
            menus_data = restaurant_menus.to_dict('records')
            for menu in menus_data:
                menus.append({
                    'name': menu.get('메뉴', ''),
                    'price': menu.get('가격원문', '').replace('원', ''),  # '원' 제거
                    'is_representative': menu.get('대표여부', ''),
                    'price_range': menu.get('가격범위', ''),
                    'theme': menu.get('테마', ''),
                    'temperature': menu.get('온도', ''),
                    'category': menu.get('카테고리', ''),
                    'main_ingredient': menu.get('주재료', ''),
                    'is_spicy': menu.get('맵기(O/X)', '')
                })

        # Series를 dict로 변환
        restaurant_data = restaurant.to_dict()
        restaurant_data['id'] = restaurant_id  # id 명시적 추가

        # 한글 컬럼명을 영문으로 매핑
        column_mapping = {
            '가게': 'name',
            '주소': 'address',
            '카테고리': 'cuisine_type',
            '이미지URL': 'image_url',
            'LLM요약': 'summary',
            '평점': 'rating',
            '소개': 'description'
        }

        # 영문 필드 추가
        for kor_col, eng_col in column_mapping.items():
            if kor_col in restaurant_data and eng_col not in restaurant_data:
                restaurant_data[eng_col] = restaurant_data[kor_col]

        # NaN, Infinity 등을 None으로 변환 (JSON 직렬화 가능하게)
        restaurant_data = {
            k: None if (isinstance(v, float) and (pd.isna(v) or v == float('inf') or v == float('-inf')))
            else v
            for k, v in restaurant_data.items()
        }

        restaurant_data['menus'] = menus

        return restaurant_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"식당 정보 조회 실패: {str(e)}")

@app.post("/api/translate", response_model=TranslateResponse, tags=["Translation"])
async def translate_api(request: TranslateRequest):
    """
    텍스트 번역 API
    한국어 -> 영어/일본어/중국어
    """
    try:
        translated = translate_text(request.text, request.target_language)
        return TranslateResponse(
            translated_text=translated,
            original_text=request.text,
            target_language=request.target_language
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"번역 실패: {str(e)}")

# --- 서버 실행 ---
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
