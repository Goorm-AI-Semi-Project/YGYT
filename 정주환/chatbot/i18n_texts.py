# i18n_texts.py
# (2-space indentation)

I18N_TEXTS = {
  # App Header
  "app_title": {"KR": "거긴어때", "US": "How About There", "JP": "あそこはどう？", "CN": "那里怎么样?"},
  "app_description": {
    "KR": "AI가 14가지 프로필 정보를 수집하고, 완료되면 맞춤 식당을 추천합니다.",
    "US": "AI collects 14 profile items, then recommends tailored restaurants.",
    "JP": "AIが14のプロファイル情報を収集し、完了後にカスタムレストランを推薦します。",
    "CN": "AI收集14个个人资料项，完成后推荐定制餐厅。"
  },

  # Language/Chat Tab
  "lang_select_label": {"KR": "🌐 사용 언어 선택", "US": "🌐 Select Language", "JP": "🌐 使用言語を選択", "CN": "🌐 选择语言"},
  "btn_lang_kr": {"KR": "한국어", "US": "Korean", "JP": "韓国語", "CN": "韩语"},
  "btn_lang_us": {"KR": "English", "US": "English", "JP": "英語", "CN": "英语"},
  "btn_lang_jp": {"KR": "日本語", "US": "Japanese", "JP": "日本語", "CN": "日语"},
  "btn_lang_cn": {"KR": "中文", "US": "Chinese", "JP": "中国語", "CN": "中文"},   
  "tab_explore": {"KR": "🍽 음식 탐색", "US": "🍽 Explore Food", "JP": "🍽 料理を探索", "CN": "🍽 探索美食"},
  "chatbot_label": {"KR": "한국 여행 도우미 챗봇", "US": "Korea Travel Helper Chatbot", "JP": "韓国旅行アシスタントチャットボット", "CN": "韩国旅行助手聊天机器人"},
  "textbox_label": {"KR": "답변 입력", "US": "Your Answer", "JP": "回答を入力", "CN": "您的回答"},
  "textbox_placeholder": {
    "KR": "여기에 답변을 입력하고 Enter를 누르세요...",
    "US": "Enter your answer here and press Enter...",
    "JP": "ここに回答を入力してEnterを押してください...",
    "CN": "在此输入您的回答并按 Enter..."
  },
  "btn_show_results": {"KR": "✅ 결과 보기", "US": "✅ Show Results", "JP": "✅ 結果を見る", "CN": "✅ 查看结果"},
  
  # Result Tab (Controls)
  "slider_label": {"KR": "표시 개수 (Top-K)", "US": "Display Count (Top-K)", "JP": "表示件数 (Top-K)", "CN": "显示数量 (Top-K)"},
  "btn_refresh": {"KR": "🔮 추천 새로고침", "US": "🔮 Refresh Recommendation", "JP": "🔮 おすすめを更新", "CN": "🔮 刷新推荐"},
  "btn_back": {"KR": "✏️ 프로필 수정", "US": "✏️ Edit Profile", "JP": "✏️ プロフィール修正", "CN": "✏️ 编辑资料"},

  # Setting Tab
  "tab_setting": {"KR": "⚙️ 설정", "US": "⚙️ Settings", "JP": "⚙️ 設定", "CN": "⚙️ 设置"},
  "setting_header": {"KR": "### ⚙️ 앱 설정 (예시)", "US": "### ⚙️ App Settings (Example)", "JP": "### ⚙️ アプリ設定 (例)", "CN": "### ⚙️ 应用设置 (示例)"},
  "setting_description": {
    "KR": "- 나중에 벡터 DB 리셋, 디버그 옵션, 모델 선택 등을 넣을 수 있습니다.\n- 현재는 UI 틀만 만들어 둔 상태입니다.",
    "US": "- Options like vector DB reset, debug options, model selection can be added later.\n- Currently, only the UI frame is set up.",
    "JP": "- ベクターDBリセット、デバッグオプション、モデル選択などを後で追加できます。\n- 現在はUIの枠組みのみ作成されています。",
    "CN": "- 稍后可以添加矢量数据库重置、调试选项、模型选择等。\n- 目前仅设置了UI框架。"
  },
  "btn_rebuild_db": {"KR": "🔁 벡터 DB 다시 빌드 (예시)", "US": "🔁 Rebuild Vector DB (Example)", "JP": "🔁 ベクターDB再構築 (例)", "CN": "🔁 重建矢量数据库 (示例)"},
  "checkbox_debug_log": {"KR": "디버그 로그 출력 (예시)", "US": "Output Debug Logs (Example)", "JP": "デバッグログ出力 (例)", "CN": "输出调试日志 (示例)"},
  "checkbox_debug_panel": {"KR": "🔎 디버그 패널 보기", "US": "🔎 Show Debug Panel", "JP": "🔎 デバッグパネルを表示", "CN": "🔎 显示调试面板"},
  "label_debug_profile": {"KR": "profile_state(raw)", "US": "profile_state(raw)", "JP": "プロファイル_状態(生)", "CN": "profile_state(原始)"},
  "label_debug_summary": {"KR": "inferred summary text", "US": "inferred summary text", "JP": "推論された要約テキスト", "CN": "推断摘要文本"},
  "label_debug_norm": {"KR": "normalized for card", "US": "normalized for card", "JP": "カード用に正規化済み", "CN": "已为卡片规范化"},
  
  # --- search_logic.py 텍스트 ---
  "similar_user_reco_header": {
    "KR": "### 🤖 Charlie님과 비슷한 사용자가 추천한 식당",
    "US": "### 🤖 Restaurants Recommended by Users Similar to Charlie",
    "JP": "### 🤖 Charlie様と似たユーザーがお勧めするレストラン",
    "CN": "### 🤖 与Charlie相似用户推荐的餐厅"
  },
  "pc_tags_label": {
    "KR": "주요 태그",
    "US": "Tags",
    "JP": "主なタグ",
    "CN": "主要标签"
  },
  "pc_red_ribbon_title": {
    "KR": "레드 리본 선정",
    "US": "Red Ribbon Selection",
    "JP": "レッドリボン選定",
    "CN": "红丝带入选"
  },
  "pc_seoul_2025_title": {
    "KR": "서울 2025 선정",
    "US": "Seoul 2025 Selection",
    "JP": "ソウル2025選定",
    "CN": "首尔 2025 入选"
  },  
  
  "rank_prefix_reco": {"KR": "추천", "US": "Reco", "JP": "おすすめ", "CN": "推荐"},
  "rank_prefix_similar": {"KR": "유사 추천", "US": "Similar", "JP": "類似おすすめ", "CN": "相似推荐"},
  "detail_link_text": {"KR": "가게 상세정보", "US": "Store Details", "JP": "店舗詳細情報", "CN": "店铺详细信息"},
  "map_link_text": {"KR": "카카오맵 길찾기", "US": "KakaoMap Directions", "JP": "カカオマップ道案内", "CN": "KakaoMap 路线"},
  "store_not_loaded": {"KR": "ID: {store_id_str} (DB 미로드)", "US": "ID: {store_id_str} (DB not loaded)", "JP": "ID: {store_id_str} (DB未ロード)", "CN": "ID: {store_id_str} (DB未加载)"},
  "store_not_found": {"KR": "ID: {store_id_str} (상세 정보 조회 실패)", "US": "ID: {store_id_str} (Details lookup failed)", "JP": "ID: {store_id_str} (詳細情報検索失敗)", "CN": "ID: {store_id_str} (详细信息查询失败)"},
  "info_address": {"KR": "📍 {store_address}{social_proof_html}", "US": "📍 {store_address}{social_proof_html}", "JP": "📍 {store_address}{social_proof_html}", "CN": "📍 {store_address}{social_proof_html}"},
  "menu_summary": {"KR": "주요 메뉴 보기", "US": "View Main Menu", "JP": "主なメニューを見る", "CN": "查看主菜单"},
  "menu_not_found": {"KR": "(메뉴 정보 없음)", "US": "(Menu info not found)", "JP": "(メニュー情報なし)", "CN": "(无菜单信息)"},
  
# --- gradio_callbacks.py 텍스트 ---
  "rank_prefix_rag": {"KR": "RAG 추천", "US": "RAG Reco", "JP": "RAGおすすめ", "CN": "RAG 推荐"},
  "initial_reco_placeholder": {
    "KR": "...프로필 설문이 완료되면 여기에 추천 결과가 표시됩니다...",
    "US": "...Recommendation results will be displayed here once the profile is complete...",
    "JP": "...プロフィールアンケートが完了すると、ここに推薦結果が表示されます...",
    "CN": "...个人资料调查完成后，推荐结果将显示在此处..."
  },
  "error_chatbot_init": {
    "KR": "챗봇 초기화에 실패했습니다. (API 키 오류일 수 있습니다): {e}",
    "US": "Failed to initialize chatbot. (May be an API key error): {e}",
    "JP": "チャットボットの初期化に失敗しました。 (APIキーのエラーかもしれません): {e}",
    "CN": "聊天机器人初始化失败。 (可能是API密钥错误): {e}"
  },
  "error_chatbot_init_short": {
    "KR": "챗봇 초기화 실패...",
    "US": "Chatbot init failed...",
    "JP": "チャットボット初期化失敗...",
    "CN": "聊天机器人初始化失败..."
  },
  "warn_rag_empty": {
    "KR": "1단계 RAG 검색 결과가 0건입니다. 필터를 완화해보세요.",
    "US": "Stage 1 RAG search returned 0 results. Try relaxing your filters.",
    "JP": "第1段階のRAG検索結果が0件です。フィルターを緩和してみてください。",
    "CN": "第1阶段RAG搜索结果为0。请尝试放宽筛选条件。"
  },
  "warn_graphhopper_down": {
    "KR": "⚠️ 뚜벅이 점수 서버가 응답하지 않습니다. 1단계 RAG 검색 결과로 대체합니다.",
    "US": "⚠️ Walking score server is not responding. Falling back to Stage 1 RAG results.",
    "JP": "⚠️ 徒歩スコアサーバーが応答しません。第1段階のRAG検索結果で代替します。",
    "CN": "⚠️ 步行得分服务器无响应。将回退到第1阶段RAG搜索结果。"
  },
  "error_reco_general": {
    "KR": "추천 생성 중 오류 발생: {e}",
    "US": "Error during recommendation generation: {e}",
    "JP": "推薦生成中にエラーが発生しました: {e}",
    "CN": "生成推荐时出错: {e}"
  },
  "error_reco_general_details": {
    "KR": "[오류] 식당 추천 중 오류가 발생했습니다. (세부정보: {e})",
    "US": "[Error] An error occurred while recommending restaurants. (Details: {e})",
    "JP": "[エラー] レストラン推薦中にエラーが発生しました。 (詳細: {e})",
    "CN": "[错误] 推荐餐厅时发生错误。 (详情: {e})"
  },
  "error_api_call": {
    "KR": "API 호출 중 오류가 발생했습니다: {e}",
    "US": "An error occurred during API call: {e}",
    "JP": "API呼び出し中にエラーが発生しました: {e}",
    "CN": "API调用期间发生错误: {e}"
  },
  "info_profile_complete": {
    "KR": "🤖 프로필 수집이 완료되었습니다! 잠시만 기다려주시면, 수집된 프로필을 기반으로 멋진 음식점을 찾아드릴게요.",
    "US": "🤖 Profile collection is complete! Please wait a moment while I find great restaurants based on your profile.",
    "JP": "🤖 プロフィールの収集が完了しました！ただいま、収集したプロフィールに基づいて素敵なお店をお探ししますので、少々お待ちください。",
    "CN": "🤖 个人资料收集完毕！请稍候，我将根据收集的资料为您寻找合适的餐厅。"
  },
  "info_complete_profile_first": {
    "KR": "...프로필을 먼저 완성해주세요...",
    "US": "...Please complete your profile first...",
    "JP": "...まずプロフィールを完成させてください...",
    "CN": "...请先完成您的个人资料..."
  },
  "error_no_recos_state": {
    "KR": "추천 결과가 없습니다. (State 비어있음)",
    "US": "No recommendation results found. (State is empty)",
    "JP": "推薦結果がありません。 (Stateが空です)",
    "CN": "没有推荐结果。 (状态为空)"
  },
  "error_slider_update": {
    "KR": "[오류] Top-K 슬라이더 변경 중 오류: {e}",
    "US": "[Error] Error updating Top-K slider: {e}",
    "JP": "[エラー] Top-Kスライダーの更新中にエラーが発生しました: {e}",
    "CN": "[错误] 更新Top-K滑块时出错: {e}"
  },
  # --- profile_view.py 텍스트 ---
  "profile_card_title": {
    "KR": "🤖 AI가 파악한 프로필",
    "US": "🤖 AI Profile Analysis",
    "JP": "🤖 AIによるプロフィール分析",
    "CN": "🤖 AI分析的个人资料"
  },
  "pc_chip_origin": {"KR": "출발", "US": "From", "JP": "出発", "CN": "出发"},
  "pc_chip_budget": {"KR": "예산", "US": "Budget", "JP": "予算", "CN": "预算"},
  "pc_grid_likes": {"KR": "선호", "US": "Likes", "JP": "好み", "CN": "偏好"},
  "pc_grid_limits": {"KR": "제한", "US": "Limits", "JP": "制限", "CN": "限制"},
  "pc_grid_age_gender": {"KR": "연령/성별", "US": "Age/Gender", "JP": "年齢/性別", "CN": "年龄/性别"},
  "pc_grid_spice": {"KR": "매운맛", "US": "Spice", "JP": "辛さ", "CN": "辣度"}
}

# --- Helper Functions ---

def get_lang_code(lang_str: str) -> str:
  """Gradio의 언어 문자열을 코드(KR, US, JP, CN)로 변환"""
  if "한국어" in lang_str: return "KR"
  if "English" in lang_str: return "US"
  if "日本語" in lang_str: return "JP"
  if "中文" in lang_str: return "CN"
  return "KR" # 기본값

def get_text(key: str, lang_code: str = "KR", **kwargs) -> str:
  """I18N_TEXTS 딕셔너리에서 텍스트를 가져와 kwargs로 포맷팅합니다."""
  # 만약 lang_code가 없으면 KR을 기본값으로 사용
  text_dict = I18N_TEXTS.get(key, {})
  text = text_dict.get(lang_code, text_dict.get("KR", f"!!MISSING TEXT for {key}!!"))
  
  # kwargs를 사용하여 f-string 포맷팅을 수행합니다.
  try:
    return text.format(**kwargs)
  except KeyError:
    # 포맷팅 인수가 필요했지만 제공되지 않은 경우 (예: {store_id_str})
    return text 
  except Exception:
    return text
