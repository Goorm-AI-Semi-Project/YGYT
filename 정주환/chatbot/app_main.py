# app_main.py (CSS 추가)

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

# 다국어
from i18n_texts import I18N_TEXTS, get_lang_code, get_text

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
      config.RESTAURANT_DB_FILE_ALL, 
      config.MENU_DB_FILE,
    )
    data_loader.load_user_ratings()
    
    data_loader.build_vector_db(
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

/* (★★★ 2. gr.HTML 내부에서 버튼 스타일을 적용하기 위한 CSS 추가 ★★★) */
/* Gradio의 .gr-button-primary, .gr-button-secondary, .gr-button-sm 스타일을 복제 */

.html-button {
  text-decoration: none; /* 링크 밑줄 제거 */
  display: inline-block;
  padding: 0.25rem 0.5rem; /* sm: py-1 px-2 */
  font-size: 0.875rem; /* sm: text-sm */
  font-weight: 500; /* medium */
  border-radius: 0.375rem; /* rounded-md */
  border: 1px solid transparent;
  transition: all 0.2s;
  white-space: nowrap;
}

/* Primary Button (상세 보기) */
.html-button-primary {
  background-color: #ff7600; /* gradio-orange-600 */
  color: white;
  border-color: #ff7600;
}
.html-button-primary:hover {
  background-color: #f06e00; /* hover 어둡게 */
  border-color: #f06e00;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

/* Secondary Button (카카오맵) -> Kakao Yellow */
.html-button-secondary {
  background-color: #FEE500; /* Kakao Yellow */
  color: #374151; /* Dark Text (gray-700) */
  border-color: #FEE500; 
}
.html-button-secondary:hover {
  background-color: #F0D900; /* Darker Yellow */
  border-color: #F0D900;
  color: #374151; /* Keep Dark Text */
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

/* ⬇️ [신규] 뱃지/태그 CSS (3개 추가) ⬇️ */
.badge-ribbon {
  display: inline-block;
  font-size: 1.1rem; /* 이모지 크기 */
  margin-left: 6px;
  vertical-align: middle;
  line-height: 1;
}
.badge-seoul2025 {
  display: inline-block;
  background-color: #007bff; /* 서울시 파란색 (예시) */
  color: white;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 3px 6px;
  border-radius: 4px;
  margin-left: 6px;
  vertical-align: middle;
  line-height: 1;
}
.tags-container {
  margin-bottom: 12px;
}
/* (★★★ 신규 CSS 끝 ★★★) */
"""

# ⬇️ 초기 언어 설정 (이제 load 이벤트가 덮어씀)
INITIAL_LANG_CODE = "KR"

with gr.Blocks(title=get_text("app_title", INITIAL_LANG_CODE), theme=gr.themes.Soft(), css=GRADIO_CSS) as gradio_app:
    # ⬇️ [수정] 컴포넌트 변수만 정의. (값 설정은 load 이벤트에서)
    title_md = gr.Markdown("## ...")
    desc_md = gr.Markdown("...")

    # ⬇️ [삭제] js_loader 삭제
    # js_loader = gr.HTML(visible=False)

    with gr.Group():
        #gr.Markdown("### 🌐 언어 설정")
        with gr.Row():
            # ⬇️ [수정] 4개 버튼 -> 1개 Radio로 복귀
            lang_radio = gr.Radio(
                ["한국어 KR", "English US", "日本語 JP", "中文 CN"],
                label="...", # (load에서 설정)
                value="한국어 KR",
                interactive=True,
            )

    # States
    llm_history_state = gr.State(value=[])
    profile_state = gr.State(value=config.PROFILE_TEMPLATE.copy())
    is_completed_state = gr.State(value=False)
    user_profile_row_state = gr.State(value=None)
    lang_code_state = gr.State(value=INITIAL_LANG_CODE)

    with gr.Tabs():
        # ⬇️ [수정] 컴포넌트 변수만 정의
        with gr.TabItem("...") as tab_explore:
            # ---- 채팅 영역 ----
            with gr.Group() as chat_group:
                with gr.Column():
                    chatbot = gr.Chatbot(
                        label="...", # (load에서 설정)
                        height=700,
                        show_copy_button=True,
                        type="messages",
                    )
                    msg_textbox = gr.Textbox(
                        label="...", # (load에서 설정)
                        placeholder="...", # (load에서 설정)
                    )
                    # ✅ 결과 보기 버튼 (채팅 → 결과 화면 이동)
                    show_results_btn = gr.Button("...", variant="primary") # (load에서 설정)

            # ---- 결과 영역 ----
            with gr.Group(visible=False) as result_group:
                profile_html = gr.HTML(label=None, value="")

                gr.HTML("<div class='controls-bar'><div id='ctrl-left' class='controls-left'></div><div id='ctrl-right' class='controls-right'></div></div>")
                with gr.Group(elem_id="ctrl-left"):
                    topk_slider = gr.Slider(
                        minimum=1, maximum=30, value=5, step=1, label="..." # (load에서 설정)
                    )
                with gr.Group(elem_id="ctrl-right"):
                    with gr.Row():
                        refresh_btn = gr.Button("...", variant="secondary") # (load에서 설정)
                        back_btn    = gr.Button("...",  variant="secondary") # (load에서 설정)

                recommendation_output = gr.HTML(label=None, value="") # (수정)
                
        with gr.TabItem("...") as tab_setting:
            with gr.Column():
                # ⬇️ 설정 탭 텍스트 변수에 할당 및 get_text() 사용
                setting_header_md = gr.Markdown("...") # (load에서 설정)
                setting_desc_md = gr.Markdown("...") # (load에서 설정)
                
                rebuild_btn = gr.Button("...") # (load에서 설정)
                debug_checkbox = gr.Checkbox(label="...", value=False) # (load에서 설정)

                # 🔎 디버그 패널
                debug_toggle = gr.Checkbox(label="...", value=False) # (load에서 설정)
                debug_profile_json = gr.JSON(label="...", visible=False) # (load에서 설정)
                debug_summary_text = gr.Textbox(label="...", visible=False) # (load에서 설정)
                debug_norm_json    = gr.JSON(label="...", visible=False) # (load에서 설정)

    # ---- 이벤트 바인딩 ----

    # ⬇️ [수정] (A) 페이지 로드
    # start_chat이 26개의 State/UI 초기값을 반환
    # (Radio로 복귀했으므로 29개 -> 26개로 다시 변경)
    gradio_app.load(
        fn=gradio_callbacks.start_chat,  
        inputs=None, # (fn 시그니처에 request: gr.Request가 있으면 자동 주입됨)
        outputs=[
            # --- States (6개) ---
            chatbot,                  # 1. (Welcome 메시지)
            llm_history_state,        # 2
            profile_state,            # 3
            is_completed_state,       # 4
            user_profile_row_state,   # 5
            lang_code_state,          # 6
            
            # --- UI Components (20개) ---
            title_md,                 # 7
            desc_md,                  # 8
            
            lang_radio,               # 9. (Radio로 복귀)
            
            tab_explore,              # 10
            tab_setting,              # 11
            chatbot,                  # 12 (chatbot label 업데이트용 - 중복 아님)
            msg_textbox,              # 13
            show_results_btn,         # 14
            topk_slider,              # 15
            refresh_btn,              # 16
            back_btn,                 # 17
            profile_html,             # 18 (value=None으로 초기화)
            setting_header_md,        # 19
            setting_desc_md,          # 20
            rebuild_btn,              # 21
            debug_checkbox,           # 22
            debug_toggle,             # 23
            debug_profile_json,       # 24
            debug_summary_text,       # 25
            debug_norm_json           # 26
        ],
    )

    # ⬇️ [수정] (B) 언어 변경 (챗봇 초기화 + UI 새로고침)
    lang_radio.change(
        fn=gradio_callbacks.reset_chat_for_language, # ⬅️ [신규] 콜백 함수
        inputs=[lang_radio],
        outputs=[
            # ⬇️ load 이벤트의 outputs와 동일한 26개 컴포넌트
            # --- States (6개) ---
            chatbot,                  # (Welcome 메시지)
            llm_history_state,
            profile_state,
            is_completed_state,
            user_profile_row_state,
            lang_code_state,
            
            # --- UI Components (20개) ---
            title_md,
            desc_md,
            lang_radio,
            tab_explore,
            tab_setting,
            chatbot,                  # (chatbot label 업데이트용 - 중복 아님)
            msg_textbox,
            show_results_btn,
            topk_slider,
            refresh_btn,
            back_btn,
            profile_html,
            setting_header_md,
            setting_desc_md,
            rebuild_btn,
            debug_checkbox,
            debug_toggle,
            debug_profile_json,
            debug_summary_text,
            debug_norm_json,
            
            # ⬇️ [신규] 27, 28번째 output으로 추가
            chat_group,               # 27. 채팅 화면
            result_group,             # 28. 결과 화면
        ],
        queue=True # (LLM API를 호출하므로 큐 사용)
    )
    
    # --- (이하 나머지 이벤트 핸들러는 수정 없이 그대로 사용) ---

    async def chat_survey_handler(
        message: str,
        gradio_history: List[Dict],
        llm_history: List[Dict],
        current_profile: Dict,
        is_completed: bool,
        topk_value: int,
        user_profile_row: Dict,
        debug_on: bool,
        lang_code: str,
    ):
        """
        (수정됨: 이 함수는 이제 제너레이터입니다)
        chat_survey 콜백이 yield하는 값들을 스트리밍으로 받아 UI를 업데이트합니다.
        """
        
        # 1. (수정) `await` 대신 `async for`를 사용합니다.
        #    gradio_callbacks.chat_survey가 (A)대기, (B)결과 2개를 yield합니다.
        async for (
            chatbot_out,
            llm_out,
            profile_out,
            is_completed_out,
            rec_md_out,
            upr_out,
        ) in gradio_callbacks.chat_survey( # ⬅️ (await 제거)
            message=message,
            gradio_history=gradio_history,
            llm_history=llm_history,
            current_profile=current_profile,
            is_completed=is_completed,
            topk_value=topk_value,
            user_profile_row_state=user_profile_row,
            http_client=app.state.http_client,
            graphhopper_url=config.GRAPH_HOPPER_API_URL,
            lang_code=lang_code,
        ):
            # --- (이하 로직은 yield되는 값들로 UI를 업데이트합니다) ---
            
            # ★ 요약문 강제 주입 (fallback)
            summary_text = _extract_summary_text(profile_out, chatbot_out, llm_out)
            profile_for_view = dict(profile_out or {})
            if summary_text and "summary" not in profile_for_view:
                profile_for_view["summary"] = summary_text
    
            # 화면 전환/카드 렌더
            chat_group_vis   = gr.update(visible=not is_completed_out)
            result_group_vis = gr.update(visible=is_completed_out)
            profile_html_out = gr.update(value=render_profile_card(profile_for_view, lang_code))
    
            # 디버그 패널 값
            norm_preview = normalize_profile(profile_for_view)
            vis = gr.update(visible=bool(debug_on))
            
            # 2. (수정) `return` 대신 `yield`를 사용합니다.
            #    (Gradio에 12개 출력값을 스트리밍으로 전달)
            yield ( 
                chatbot_out, llm_out, profile_out, is_completed_out,
                rec_md_out, upr_out,
                chat_group_vis, result_group_vis, profile_html_out,
                gr.update(value=profile_out, visible=bool(debug_on)),
                gr.update(value=summary_text, visible=bool(debug_on)),
                gr.update(value=norm_preview,  visible=bool(debug_on)),
            )

    msg_textbox.submit(
        fn=chat_survey_handler, # (이 함수는 이제 제너레이터입니다)
        inputs=[msg_textbox, chatbot, llm_history_state, profile_state, is_completed_state, topk_slider, user_profile_row_state, debug_toggle, lang_code_state],
        outputs=[chatbot, llm_history_state, profile_state, is_completed_state, recommendation_output, user_profile_row_state, chat_group, result_group, profile_html, debug_profile_json, debug_summary_text, debug_norm_json],
    )
    msg_textbox.submit(lambda: "", inputs=None, outputs=msg_textbox)
    
    
    # (C) Top-K 변경 시 추천만 갱신
    def update_recommendations_with_topk_handler(topk_value: int, user_profile_row: Dict, lang_code: str):
        return gradio_callbacks.update_recommendations_with_topk(
            topk_value=topk_value,
            user_profile_row_state=user_profile_row,
            lang_code=lang_code, 
        )

    topk_slider.change(
        fn=update_recommendations_with_topk_handler,
        inputs=[topk_slider, user_profile_row_state, lang_code_state], 
        outputs=recommendation_output,
    )

    refresh_btn.click(
        fn=update_recommendations_with_topk_handler,
        inputs=[topk_slider, user_profile_row_state, lang_code_state], 
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
    def show_results_from_chat_handler(current_profile: Dict, user_profile_row: Dict, topk_value: int, chatbot_hist: List[Dict], llm_hist: List[Dict], lang_code: str):
        rec_md = update_recommendations_with_topk_handler(topk_value, user_profile_row, lang_code)
        # 요약 주입
        summary_text = _extract_summary_text(current_profile, chatbot_hist, llm_hist)
        profile_for_view = dict(current_profile or {})
        if summary_text and "summary" not in profile_for_view:
            profile_for_view["summary"] = summary_text
        return (
            gr.update(visible=False),                                   # chat_group 숨김
            gr.update(visible=True),                                    # result_group 표시
            gr.update(value=render_profile_card(profile_for_view, lang_code)),  # 프로필 카드
            rec_md,                                                     # 추천 결과
            True                                                        # is_completed_state = True
        )

    show_results_btn.click(
        fn=show_results_from_chat_handler,
        inputs=[profile_state, user_profile_row_state, topk_slider, chatbot, llm_history_state, 
            lang_code_state],
        outputs=[chat_group, result_group, profile_html, recommendation_output, is_completed_state],
    )


# ========= 5) 마운트 =========
app = gr.mount_gradio_app(
    app,
    gradio_app,
    path="/chatbot", # ⬅️ JS 새로고침 경로와 일치
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
