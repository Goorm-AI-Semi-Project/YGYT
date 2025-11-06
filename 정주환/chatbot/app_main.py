import uvicorn
import httpx
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Tuple
import pandas as pd

from fastapi import FastAPI, HTTPException
import gradio as gr

# 모듈 임포트
import config
import data_loader
import llm_utils
import gradio_callbacks # (Gradio 콜백 함수)
import search_logic
from API import final_scorer # (사장님 로직)
from models import RecommendationRequest, RecommendationResponse

# --- 1. FastAPI 앱 및 Lifespan (서버 시작/종료) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 1회 실행"""
    print("--- 서버 시작: Lifespan 시작 ---")
    
    # 1. (필수) API 키 로드 확인
    if not config.client or not config.client.api_key:
        print("[치명적 오류] OPENAI_API_KEY가 로드되지 않았습니다.")
        # (실제 배포 시에는 여기서 exit() 또는 raise)
    else:
        print("  > OpenAI API 키 로드 완료.")

    # 2. (필수) GraphHopper 연결용 HTTP 클라이언트 생성
    # (final_scorer가 API 호출 시 이 클라이언트를 재사용)
    app.state.http_client = httpx.AsyncClient()
    print("  > HTTPX AsyncClient 생성 완료.")

    # 3. (필수) 모든 CSV 및 VectorDB 로드
    # (data_loader.py의 전역 변수들이 채워짐)
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
        
        # 4. (필수) /recommendations API용 스코어링 DB 로드
        # (이 데이터를 app.state에 저장 -> /recommendations가 사용)
        app.state.all_restaurants_df_scoring = data_loader.load_scoring_data(
            config.RESTAURANT_DB_SCORING_FILE
        )
        
        print("  > 모든 데이터 로드 완료.")
        
    except Exception as e:
        print(f"[치명적 오류] 데이터 로드 실패: {e}")
        # (실제 배포 시에는 여기서 exit() 또는 raise)

    print("--- 서버 시작 완료 ---")
    
    yield # (서버 실행)
    
    # --- 서버 종료 시 ---
    print("--- 서버 종료: Lifespan 종료 ---")
    await app.state.http_client.aclose()
    print("  > HTTPX AsyncClient 종료.")

# FastAPI 앱 생성
app = FastAPI(
    title="FastAPI + Gradio 통합 추천 서버",
    description="챗봇 서베이와 2단계 '뚜벅이' 스코어링 시스템 통합",
    lifespan=lifespan
)

# --- 2. (기존) /recommendations 엔드포인트 ---
# (이 엔드포인트는 챗봇과 '독립적'으로 작동합니다)

@app.post(
    "/recommendations", 
    response_model=RecommendationResponse,
    tags=["2-Stage Scorer (final_scorer)"]
)
async def get_recommendations(request: RecommendationRequest):
    """
    (챗봇과 무관) 1단계 후보군 150개를 '랜덤'으로 생성하고
    'final_scorer' 로직을 실행하여 최종 점수를 반환합니다.
    """
    if app.state.all_restaurants_df_scoring is None:
        raise HTTPException(status_code=503, detail="서버 준비 중 (스코어링 DB 로드 실패)")

    # 1. 1단계 후보군 생성 (랜덤 샘플링)
    try:
        candidate_df = app.state.all_restaurants_df_scoring.sample(n=request.n_results)
    except ValueError:
        # (DB가 150개보다 적을 경우)
        candidate_df = app.state.all_restaurants_df_scoring.copy()

    # 2. 2단계 스코어링 실행 (final_scorer.py 호출)
    try:
        final_scored_df = await final_scorer.calculate_final_scores_async(
            candidate_df=candidate_df,
            user_start_location=request.user_start_location,
            user_price_prefs=request.user_price_prefs,
            async_http_client=app.state.http_client, # (Lifespan에서 생성한 클라이언트 주입)
            graphhopper_url=config.GRAPH_HOPPER_API_URL
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"2단계 스코어링 실패: {e}")
        
    # 3. Pydantic 모델에 맞춰 결과 반환
    results = final_scored_df.reset_index().to_dict('records')
    return RecommendationResponse(
        recommendations=results,
        total_count=len(results)
    )

# --- 3. (신규) Gradio 챗봇 UI ---

with gr.Blocks(theme=gr.themes.Soft()) as gradio_app:
    gr.Markdown("# 🤖 뚜벅이 여행자를 위한 챗봇 (v2)")
    gr.Markdown("AI가 14가지 프로필(출발 위치 포함)을 수집하고, '이동 마찰 점수'가 포함된 맞춤 식당을 추천합니다.")
    
    with gr.Row():
        with gr.Column(scale=2):
            # 1. (Gradio용) 보이지 않는 상태(State) 변수
            llm_history_state = gr.State(value=[]) 
            profile_state = gr.State(value=config.PROFILE_TEMPLATE.copy())
            is_completed_state = gr.State(value=False)

            # 2. 채팅창
            chatbot = gr.Chatbot(
                label="서베이 챗봇", 
                height=700, 
                show_copy_button=True,
                type='messages'
            )
            
            # 3. 사용자 입력
            msg_textbox = gr.Textbox(
                label="답변 입력", 
                placeholder="여기에 답변을 입력하고 Enter를 누르세요..."
            )
        
        with gr.Column(scale=1):
            gr.Markdown("### 🌟 맞춤 추천 결과")
            # (결과가 표시될 영역)
            recommendation_output = gr.Markdown(
                label="추천 결과",
                value="...프로필 설문이 완료되면 여기에 추천 결과가 표시됩니다...",
                visible=True # (항상 보이도록 수정)
            )

    # --- 4. (★핵심★) Gradio 이벤트 핸들러 연결 ---
    
    # (A) 앱이 처음 로드될 때
    gradio_app.load(
        fn=gradio_callbacks.start_chat, # (일반 함수)
        inputs=None,
        outputs=[chatbot, llm_history_state, profile_state, is_completed_state]
    )
    
    # (B) 사용자가 Enter(submit)를 누를 때
    
    async def chat_survey_handler(
        message: str, 
        gradio_history: List[Dict], 
        llm_history: List[Dict], 
        current_profile: Dict, 
        is_completed: bool
    ) -> Tuple[List[Dict], List[Dict], Dict, bool, gr.update]:
        """
        app_main.py에 정의된 로컬 핸들러.
        Gradio의 입력을 받아, 'app.state'의 자원을
        gradio_callbacks.chat_survey 함수에 '주입(inject)'합니다.
        """
        return await gradio_callbacks.chat_survey(
            message=message,
            gradio_history=gradio_history,
            llm_history=llm_history,
            current_profile=current_profile,
            is_completed=is_completed,
            # --- (★) app.state의 자원 주입 (★) ---
            http_client=app.state.http_client,
            graphhopper_url=config.GRAPH_HOPPER_API_URL
        )

    msg_textbox.submit(
        fn=chat_survey_handler, # (★) (비동기 로컬 핸들러)
        inputs=[
            msg_textbox, chatbot, llm_history_state, 
            profile_state, is_completed_state
        ],
        outputs=[
            chatbot, llm_history_state, profile_state, 
            is_completed_state, recommendation_output
        ]
    )
    
    # (C) Enter 누른 후 텍스트박스 비우기
    msg_textbox.submit(lambda: "", inputs=None, outputs=msg_textbox)

# --- 5. FastAPI 앱에 Gradio UI 마운트 ---
app = gr.mount_gradio_app(
    app, 
    gradio_app, 
    path="/chatbot",
    # (Gradio의 정적 파일(CSS/JS)을 FastAPI가 올바르게 서빙하도록 수정)
    # (Gradio 4.x 이상 및 FastAPI 0.100+ 이상에서 권장)
    app_kwargs={
        "title": "Gradio App on FastAPI",
        "description": "Gradio app is mounted at /chatbot",
    }
)

# --- 6. 서버 실행 ---
if __name__ == "__main__":
    # (GraphHopper가 8989, FastAPI/Gradio가 8080을 사용)
    uvicorn.run(
        "app_main:app", 
        host="127.0.0.1", 
        port=8080, 
        reload=True
    )