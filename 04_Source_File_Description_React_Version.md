# Source File Description - React Version

## Backend (APIserver)

| Structure | File Name | Description |
|-----------|-----------|-------------|
| Entry<br>&<br>Config | app.py | • FastAPI 서버의 진입점입니다. REST API 엔드포인트를 정의하고, 서버 시작 시 데이터(Lifespan)를 로딩합니다.<br>• 핵심: `/api/chat/init`, `/api/chat/message`, `/api/recommendations/generate` 등의 REST API를 제공합니다.<br>• CORS 설정: React 개발 서버(`localhost:3000`)와 통신을 허용합니다. |
| | config.py | • 환경 변수 로드 (.env 파일), OpenAI API 키, GraphHopper API URL, 파일 경로 등을 관리합니다.<br>• 챗봇 시스템 프롬프트(`SYSTEM_PROMPT`)와 프로필 템플릿(`PROFILE_TEMPLATE`) 정의 |
| | models.py | • FastAPI 엔드포인트에서 사용하는 요청(Recommendation Request) 및 응답(Recommendation Response) 데이터의 Pydantic 모델을 정의합니다. |
| Logic<br>&<br>Data | search_logic.py | • 실제 맛집 검색 알고리즘을 담당합니다.<br>• get_rag_candidate_ids: 사용자 쿼리로 ChromaDB에서 1차 후보군(RAG)을 검색하고 필터링합니다.<br>• create_filter_metadata: 사용자 프로필에서 검색 필터를 생성합니다.<br>• format_restaurant_markdown: 추천 결과 포맷 변환 (Gradio 전용, React에서는 JSON으로 전달) |
| | data_loader.py | • CSV 데이터 로드: 식당 DB, 메뉴 DB를 전처리하여 DataFrame으로 로딩합니다.<br>• load_app_data: 앱 실행에 필요한 CSV 파일 로드<br>• build_vector_db: ChromaDB를 사용하여 식당 및 사용자 프로필 벡터 DB를 생성하거나 로드<br>• get_restaurants_by_ids: ID 리스트로 식당 정보 조회 |
| | llm_utils.py | • OpenAI API와 통신합니다.<br>• call_gpt4o: 챗봇 대화 생성 (13가지 프로필 정보 수집)<br>• generate_profile_summary_text_only: 프로필 요약문 생성 (RAG 쿼리용)<br>• generate_rag_query: 사용자 프로필을 RAG 검색용 쿼리로 최적화<br>• 다국어 지원: 4개 국어(한국어, English, 日本語, 中文) 프롬프트 처리 |
| Utils<br>&<br>View | API/final_scorer.py | • 2단계 정밀 스코어링: 1단계 RAG 후보군에 뚜벅이 점수를 적용합니다.<br>• calculate_final_scores_async: 비동기 병렬 처리로 GraphHopper API 호출<br>• 사용자 출발지~식당 간 도보 시간, 가격 매칭, 품질 점수를 종합하여 최종 순위 계산<br>• 가중치 조절 가능: travel, friendliness, quality, price 4가지 요소 |

---

## Frontend (frontfinal)

| Structure | File Name | Description |
|-----------|-----------|-------------|
| Entry<br>&<br>Config | src/index.js | • React 앱의 진입점입니다. ReactDOM을 사용하여 App 컴포넌트를 렌더링합니다. |
| | src/App.js | • 메인 애플리케이션 컴포넌트로, 전체 화면 흐름을 관리합니다 (survey → loading → recommendations).<br>• 상태 관리: 사용자 프로필, 추천 식당 목록, Top-K 개수, 가중치(weights) 등을 useState로 관리합니다.<br>• 언어 선택: 4개 국어(한국어, English, 日本語, 中文) UI 제공 |
| Components | src/components/SurveyChat.js | • AI 챗봇 설문 UI 컴포넌트입니다. 사용자와 대화하며 13가지 프로필 정보를 수집합니다.<br>• 프로필 진행률 표시 (13개 항목 중 몇 개 수집되었는지 %로 표시)<br>• 다국어 지원: 언어 선택 시 챗봇이 해당 언어로 대화 시작 |
| | src/components/RestaurantList.js | • 추천된 식당 목록을 그리드 형태로 표시합니다.<br>• 배치 번역: batchTranslateText API를 사용하여 모든 식당 이름/주소/음식종류를 동시에 번역 (병렬 처리로 5-10배 속도 향상)<br>• 로딩/에러/빈 상태 처리 |
| | src/components/RestaurantCard.js | • 개별 식당 카드 UI입니다. 이미지, 이름, 음식 종류, 평점, 주소 등을 표시합니다.<br>• 클릭 시 RestaurantModal로 상세 정보 표시 |
| | src/components/RestaurantModal.js | • 식당 상세 정보를 보여주는 모달 컴포넌트입니다.<br>• 메뉴 정보, 가격, 카카오맵 길찾기 링크, 식당 상세 페이지 링크 등을 표시 |
| | src/components/WeightsControl.js | • 추천 알고리즘의 가중치를 사용자가 직접 조절할 수 있는 슬라이더 UI입니다.<br>• 4가지 요소: 뚜벅이 점수(travel), 친절도(friendliness), 품질(quality), 가격(price)<br>• 가중치 변경 시 실시간으로 추천 재계산 |
| | src/components/SearchBar.js | • 키워드 검색바 컴포넌트 |
| Services<br>&<br>API | src/services/api.js | • Backend FastAPI와 통신하는 API 클라이언트입니다. Axios를 사용하여 HTTP 요청을 처리합니다.<br>• 주요 함수: initChat (채팅 초기화), sendChatMessage (사용자 메시지 전송), generateRecommendations (프로필 기반 추천 생성), getRestaurantDetail (식당 상세 조회), batchTranslateText (배치 번역) |
