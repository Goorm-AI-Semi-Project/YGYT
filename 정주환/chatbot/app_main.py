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
    gr.Markdown("# 길따라 맛따라")
    gr.Markdown("AI가 13가지 프로필 정보를 수집하고, 완료되면 맞춤 식당을 추천합니다.")

    # 🌐 언어 설정 (UI만, 아직 로직은 사용 X)
    with gr.Group():
        gr.Markdown("### 🌐 언어 설정")
        with gr.Row():
            lang_radio = gr.Radio(
                ["한국어 KR", "English US", "日本語 JP", "中文 CN"],
                label="사용 언어 선택",
                value="한국어 KR",
                interactive=True
            )

    # ── Gradio State 변수들 ─────────────────────────────
    llm_history_state = gr.State(value=[])
    profile_state = gr.State(value=config.PROFILE_TEMPLATE.copy())
    is_completed_state = gr.State(value=False)
    # 하이브리드 검색용 프로필 Row (네가 만든 user_profile_row_state)
    user_profile_row_state = gr.State(value=None)

    with gr.Tabs():
        # [탭 1] 음식 탐색
        with gr.TabItem("🍽 음식 탐색"):
            with gr.Column():
                chatbot = gr.Chatbot(
                    label="서베이 챗봇",
                    height=700,
                    show_copy_button=True,
                    type="messages",
                )

                msg_textbox = gr.Textbox(
                    label="답변 입력",
                    placeholder="여기에 답변을 입력하고 Enter를 누르세요...",
                )

                # 챗봇 아래 맞춤 추천 결과 탭
                with gr.Tabs():
                    with gr.TabItem("🌟 맞춤 추천 결과"):
                        topk_slider = gr.Slider(
                            minimum=1,
                            maximum=30,
                            value=5,
                            step=1,
                            label="표시 개수 (Top-K)",
                        )
                        recommendation_output = gr.Markdown(
                            label="추천 결과",
                            value="...프로필 설문이 완료되면 여기에 추천 결과가 표시됩니다...",
                            visible=False,
                        )

        # [탭 2] 설정
        with gr.TabItem("⚙️ 설정"):
            with gr.Column():
                gr.Markdown("### ⚙️ 앱 설정 (예시)")
                gr.Markdown(
                    "- 이 탭에는 나중에 벡터 DB 리셋, 디버그 옵션, 모델 선택 등을 넣을 수 있습니다.\n"
                    "- 현재는 UI 틀만 만들어 둔 상태입니다."
                )
                rebuild_btn = gr.Button("🔁 벡터 DB 다시 빌드 (예시)")
                debug_checkbox = gr.Checkbox(label="디버그 로그 출력 (예시)", value=False)

    # --- 4.  Gradio 이벤트 핸들러 연결 ---

    # (A) 앱이 처음 로드될 때
    gradio_app.load(
        fn=gradio_callbacks.start_chat,  # 반드시 5개 값 리턴하도록 구현
        inputs=None,
        outputs=[
            chatbot,
            llm_history_state,
            profile_state,
            is_completed_state,
            user_profile_row_state, 
        ],
    )

    # (B) 사용자가 Enter(submit)를 누를 때
    async def chat_survey_handler(
        message: str,
        gradio_history: List[Dict],
        llm_history: List[Dict],
        current_profile: Dict,
        is_completed: bool,
        topk_value: int,
        user_profile_row: Dict,
    ) -> Tuple[
        List[Dict],  # chatbot history
        List[Dict],  # llm_history_state
        Dict,        # profile_state
        bool,        # is_completed_state
        gr.update,   # recommendation_output
        Dict,        # user_profile_row_state
    ]:
        """
        Gradio에서 넘어온 입력 + 상태 + Top-K 값을
        gradio_callbacks.chat_survey에 넘겨주는 핸들러.
        (app.state의 http_client, GRAPH_HOPPER_URL도 같이 주입)
        """
        return await gradio_callbacks.chat_survey(
            message=message,
            gradio_history=gradio_history,
            llm_history=llm_history,
            current_profile=current_profile,
            is_completed=is_completed,
            topk_value=topk_value,
            user_profile_row_state=user_profile_row,
            http_client=app.state.http_client,
            graphhopper_url=config.GRAPH_HOPPER_API_URL,
        )

    msg_textbox.submit(
        fn=chat_survey_handler,
        inputs=[
            msg_textbox,
            chatbot,
            llm_history_state,
            profile_state,
            is_completed_state,
            topk_slider,
            user_profile_row_state,
        ],
        outputs=[
            chatbot,
            llm_history_state,
            profile_state,
            is_completed_state,
            recommendation_output,
            user_profile_row_state,
        ],
    )

    # (C) Enter 누른 후 텍스트박스 비우기
    msg_textbox.submit(lambda: "", inputs=None, outputs=msg_textbox)

    # (D) Top-K 슬라이더 변경 시 추천 재계산
    def update_recommendations_with_topk_handler(topk_value: int, user_profile_row: Dict):
        """
        Top-K 값이 바뀔 때마다, 현재 user_profile_row_state를 기반으로
        추천 결과만 다시 계산해서 Markdown을 업데이트.
        (실제 로직은 gradio_callbacks.update_recommendations_with_topk 에 구현)
        """
        return gradio_callbacks.update_recommendations_with_topk(
            topk_value=topk_value,
            user_profile_row_state=user_profile_row,
        )

    topk_slider.change(
        fn=update_recommendations_with_topk_handler,
        inputs=[topk_slider, user_profile_row_state],
        outputs=recommendation_output,
    )

# --- 5. FastAPI 앱에 Gradio UI 마운트 --- 
app = gr.mount_gradio_app(
    app,
    gradio_app,
    path="/chatbot",
    app_kwargs={
        "title": "Gradio App on FastAPI",
        "description": "Gradio app is mounted at /chatbot",
    },
)

# --- 6. 서버 실행 --- 
if __name__ == "__main__":
    uvicorn.run(
        "app_main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
    )