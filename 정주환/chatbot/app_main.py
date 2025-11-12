import uvicorn
import httpx
from contextlib import asynccontextmanager
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
import gradio as gr

# 프로젝트 모듈
import config
import data_loader
import llm_utils
import gradio_callbacks
import search_logic
from API import final_scorer
from models import RecommendationRequest, RecommendationResponse

# ⬇️ 프로필 뷰 모듈
from profile_view import normalize_profile, render_profile_card, PROFILE_VIEW_CSS


# ========= 0) 요약문 Fallback 추출 유틸 =========
def _extract_summary_text(profile: Dict, chatbot_hist: List[Dict], llm_hist: List[Dict]) -> str:
    """profile/llm_history/chatbot 히스토리에서 요약문 비슷한 텍스트 추출"""
    # 1) profile 내부
    for k in ["summary","profile_summary","llm_summary","final_summary","요약","프로필요약"]:
        v = (profile or {}).get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # 2) llm_history 최근
    if isinstance(llm_hist, list):
        for msg in reversed(llm_hist[-10:]):
            if not isinstance(msg, dict):
                continue
            txt = str(msg.get("content","")).strip()
            if len(txt) > 40 and any(key in txt for key in ["요약","프로필","summary","안녕하세요"]):
                return txt
    # 3) chatbot 히스토리 (type="messages" 포맷 or (u,a) tuple)
    if isinstance(chatbot_hist, list):
        for turn in reversed(chatbot_hist[-6:]):
            if isinstance(turn, dict) and turn.get("role") == "assistant":
                txt = str(turn.get("content","")).strip()
                if len(txt) > 40 and any(key in txt for key in ["요약","프로필","summary","안녕하세요"]):
                    return txt
            if isinstance(turn, (list, tuple)) and len(turn) == 2:
                txt = str(turn[1]).strip()
                if len(txt) > 40 and any(key in txt for key in ["요약","프로필","summary","안녕하세요"]):
                    return txt
    return ""


# ========= 1) Lifespan =========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- 서버 시작: Lifespan 시작 ---")
    if not getattr(config, "client", None) or not getattr(config.client, "api_key", None):
        print("[치명적 오류] OPENAI_API_KEY가 로드되지 않았습니다.")
    else:
        print("  > OpenAI API 키 로드 완료.")

    app.state.http_client = httpx.AsyncClient()
    print("  > HTTPX AsyncClient 생성 완료.")

    try:
        data_loader.load_app_data(
            config.RESTAURANT_DB_FILE,
            config.MENU_DB_FILE,
        )
        data_loader.load_user_ratings()
        data_loader.build_vector_db(
            config.RESTAURANT_DB_FILE,
            config.PROFILE_DB_FILE,
            config.CLEAR_DB_AND_REBUILD,
        )
        app.state.all_restaurants_df_scoring = data_loader.load_scoring_data(
            config.RESTAURANT_DB_SCORING_FILE
        )
        print("  > 모든 데이터 로드 완료.")
    except Exception as e:
        print(f"[치명적 오류] 데이터 로드 실패: {e}")

    print("--- 서버 시작 완료 ---")
    yield
    print("--- 서버 종료: Lifespan 종료 ---")
    await app.state.http_client.aclose()
    print("  > HTTPX AsyncClient 종료.")


# ========= 2) FastAPI =========
app = FastAPI(
    title="FastAPI + Gradio 통합 추천 서버",
    description="챗봇 서베이와 2단계 '뚜벅이' 스코어링 시스템 통합",
    lifespan=lifespan,
)


# ========= 3) /recommendations =========
@app.post(
    "/recommendations",
    response_model=RecommendationResponse,
    tags=["2-Stage Scorer (final_scorer)"],
)
async def get_recommendations(request: RecommendationRequest):
    if app.state.all_restaurants_df_scoring is None:
        raise HTTPException(status_code=503, detail="서버 준비 중 (스코어링 DB 로드 실패)")

    try:
        candidate_df = app.state.all_restaurants_df_scoring.sample(n=request.n_results)
    except ValueError:
        candidate_df = app.state.all_restaurants_df_scoring.copy()

    try:
        final_scored_df = await final_scorer.calculate_final_scores_async(
            candidate_df=candidate_df,
            user_start_location=request.user_start_location,
            user_price_prefs=request.user_price_prefs,
            async_http_client=app.state.http_client,
            graphhopper_url=config.GRAPH_HOPPER_API_URL,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"2단계 스코어링 실패: {e}")

    results = final_scored_df.reset_index().to_dict("records")
    return RecommendationResponse(recommendations=results, total_count=len(results))


# ========= 4) Gradio UI =========
GRADIO_CSS = PROFILE_VIEW_CSS + """
/* (★★★ 앱 메인 CSS ★★★) */
.controls-bar{display:flex;align-items:center;gap:12px;margin:8px 0}
.controls-left{flex:1;min-width:280px}
.controls-right{display:flex;gap:8px}

/* (★★★ 1. Charlie님이 요청한 신규 CSS 추가 ★★★) */
/* Custom CSS for visual fidelity */
.border-container {
  border: 1px solid #e5e7eb;
  border-radius: 8px; /* rounded-lg */
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); /* shadow-sm */
  padding: 1rem; /* p-4 */
  margin-bottom: 1rem; /* space-y-4 */
}

/* 음식 추천 아이템 내부의 테두리 스타일 */
.border-item {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.75rem; /* p-3 */
  margin-bottom: 0.75rem; /* space-y-3 */
}

/* 작은 텍스트 + 배경 (음식 탐색 탭의 태그) */
.text-xs-bg {
  font-size: 0.75rem; /* text-xs */
  background-color: #f3f4f6; /* bg-gray-100 */
  border-radius: 4px;
  padding: 2px 8px;
  margin-right: 4px; /* (태그 간 간격) */
  margin-bottom: 4px; /* (태그 줄바꿈 시 간격) */
  white-space: nowrap;
  display: inline-block;
}
/* (★★★ 신규 CSS 끝 ★★★) */
"""

with gr.Blocks(title="거긴어때", theme=gr.themes.Soft(), css=GRADIO_CSS) as gradio_app:
    gr.Markdown("## 거긴어때")
    gr.Markdown("AI가 13가지 프로필 정보를 수집하고, 완료되면 맞춤 식당을 추천합니다.")

    with gr.Group():
        #gr.Markdown("### 🌐 언어 설정")
        with gr.Row():
            lang_radio = gr.Radio(
                ["한국어 KR", "English US", "日本語 JP", "中文 CN"],
                label="🌐 사용 언어 선택",
                value="한국어 KR",
                interactive=True,
            )

    # States
    llm_history_state = gr.State(value=[])
    profile_state = gr.State(value=config.PROFILE_TEMPLATE.copy())
    is_completed_state = gr.State(value=False)
    user_profile_row_state = gr.State(value=None)

    with gr.Tabs():
        with gr.TabItem("🍽 음식 탐색"):
            # ---- 채팅 영역 ----
            with gr.Group() as chat_group:
                with gr.Column():
                    chatbot = gr.Chatbot(
                        label="한국 여행 도우미 챗봇",
                        height=700,
                        show_copy_button=True,
                        type="messages",
                    )
                    msg_textbox = gr.Textbox(
                        label="답변 입력",
                        placeholder="여기에 답변을 입력하고 Enter를 누르세요...",
                    )
                    # ✅ 결과 보기 버튼 (채팅 → 결과 화면 이동)
                    show_results_btn = gr.Button("✅ 결과 보기", variant="primary")

            # ---- 결과 영역 ----
            with gr.Group(visible=False) as result_group:
                profile_html = gr.HTML(label=None, value="")

                gr.HTML("<div class='controls-bar'><div id='ctrl-left' class='controls-left'></div><div id='ctrl-right' class='controls-right'></div></div>")
                with gr.Group(elem_id="ctrl-left"):
                    topk_slider = gr.Slider(
                        minimum=1, maximum=30, value=5, step=1, label="표시 개수 (Top-K)"
                    )
                with gr.Group(elem_id="ctrl-right"):
                    with gr.Row():
                        refresh_btn = gr.Button("🔮 추천 새로고침", variant="secondary")
                        back_btn    = gr.Button("✏️ 프로필 수정",  variant="secondary")

                recommendation_output = gr.HTML(label=None, value="") # (수정)
                
        with gr.TabItem("⚙️ 설정"):
            with gr.Column():
                gr.Markdown("### ⚙️ 앱 설정 (예시)")
                gr.Markdown(
                    "- 나중에 벡터 DB 리셋, 디버그 옵션, 모델 선택 등을 넣을 수 있습니다.\n"
                    "- 현재는 UI 틀만 만들어 둔 상태입니다."
                )
                rebuild_btn = gr.Button("🔁 벡터 DB 다시 빌드 (예시)")
                debug_checkbox = gr.Checkbox(label="디버그 로그 출력 (예시)", value=False)

                # 🔎 디버그 패널
                debug_toggle = gr.Checkbox(label="🔎 디버그 패널 보기", value=False)
                debug_profile_json = gr.JSON(label="profile_state(raw)", visible=False)
                debug_summary_text = gr.Textbox(label="inferred summary text", visible=False)
                debug_norm_json    = gr.JSON(label="normalized for card", visible=False)

    # ---- 이벤트 바인딩 ----

    # (A) 페이지 로드
    gradio_app.load(
        fn=gradio_callbacks.start_chat,  # 5개 값 반환
        inputs=None,
        outputs=[chatbot, llm_history_state, profile_state, is_completed_state, user_profile_row_state],
    )

    # (B) 설문/채팅 진행
    async def chat_survey_handler(
        message: str,
        gradio_history: List[Dict],
        llm_history: List[Dict],
        current_profile: Dict,
        is_completed: bool,
        topk_value: int,
        user_profile_row: Dict,
        debug_on: bool
    ):
        (
            chatbot_out,
            llm_out,
            profile_out,
            is_completed_out,
            rec_md_out,
            upr_out,
        ) = await gradio_callbacks.chat_survey(
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

        # ★ 요약문 강제 주입 (fallback)
        summary_text = _extract_summary_text(profile_out, chatbot_out, llm_out)
        profile_for_view = dict(profile_out or {})
        if summary_text and "summary" not in profile_for_view:
            profile_for_view["summary"] = summary_text

        # 화면 전환/카드 렌더
        chat_group_vis   = gr.update(visible=not is_completed_out)
        result_group_vis = gr.update(visible=is_completed_out)
        profile_html_out = gr.update(value=render_profile_card(profile_for_view))

        # 디버그 패널 값
        norm_preview = normalize_profile(profile_for_view)
        vis = gr.update(visible=bool(debug_on))
        return (
            chatbot_out, llm_out, profile_out, is_completed_out,
            rec_md_out, upr_out,
            chat_group_vis, result_group_vis, profile_html_out,
            gr.update(value=profile_out, visible=bool(debug_on)),
            gr.update(value=summary_text, visible=bool(debug_on)),
            gr.update(value=norm_preview,  visible=bool(debug_on)),
        )

    msg_textbox.submit(
        fn=chat_survey_handler,
        inputs=[msg_textbox, chatbot, llm_history_state, profile_state, is_completed_state, topk_slider, user_profile_row_state, debug_toggle],
        outputs=[chatbot, llm_history_state, profile_state, is_completed_state, recommendation_output, user_profile_row_state, chat_group, result_group, profile_html, debug_profile_json, debug_summary_text, debug_norm_json],
    )
    msg_textbox.submit(lambda: "", inputs=None, outputs=msg_textbox)

    # (C) Top-K 변경 시 추천만 갱신
    def update_recommendations_with_topk_handler(topk_value: int, user_profile_row: Dict):
        return gradio_callbacks.update_recommendations_with_topk(
            topk_value=topk_value,
            user_profile_row_state=user_profile_row,
        )

    topk_slider.change(
        fn=update_recommendations_with_topk_handler,
        inputs=[topk_slider, user_profile_row_state],
        outputs=recommendation_output,
    )

    refresh_btn.click(
        fn=update_recommendations_with_topk_handler,
        inputs=[topk_slider, user_profile_row_state],
        outputs=recommendation_output,
    )

    # (D) 디버그 토글: 표시만 토글
    def _toggle_debug(v: bool):
        return gr.update(visible=v), gr.update(visible=v), gr.update(visible=v)
    debug_toggle.change(_toggle_debug, inputs=[debug_toggle], outputs=[debug_profile_json, debug_summary_text, debug_norm_json])

    # (E) 뒤로가기(프로필 수정): 결과→채팅
    def back_to_chat():
        return gr.update(visible=True), gr.update(visible=False), False
    back_btn.click(fn=back_to_chat, inputs=None, outputs=[chat_group, result_group, is_completed_state])

    # (F) ✅ 결과 보기: 채팅→결과 (요약 주입 + 카드 갱신 포함)
    def show_results_from_chat_handler(current_profile: Dict, user_profile_row: Dict, topk_value: int, chatbot_hist: List[Dict], llm_hist: List[Dict]):
        rec_md = update_recommendations_with_topk_handler(topk_value, user_profile_row)
        # 요약 주입
        summary_text = _extract_summary_text(current_profile, chatbot_hist, llm_hist)
        profile_for_view = dict(current_profile or {})
        if summary_text and "summary" not in profile_for_view:
            profile_for_view["summary"] = summary_text
        return (
            gr.update(visible=False),                                   # chat_group 숨김
            gr.update(visible=True),                                    # result_group 표시
            gr.update(value=render_profile_card(profile_for_view)),     # 프로필 카드
            rec_md,                                                     # 추천 결과
            True                                                        # is_completed_state = True
        )

    show_results_btn.click(
        fn=show_results_from_chat_handler,
        inputs=[profile_state, user_profile_row_state, topk_slider, chatbot, llm_history_state],
        outputs=[chat_group, result_group, profile_html, recommendation_output, is_completed_state],
    )


# ========= 5) 마운트 =========
app = gr.mount_gradio_app(
    app,
    gradio_app,
    path="/chatbot",
    app_kwargs={
        "title": "Gradio App on FastAPI",
        "description": "Gradio app is mounted at /chatbot",
    },
)


# ========= 6) 실행 =========
if __name__ == "__main__":
    uvicorn.run(
        "app_main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
    )
