# 04. Source File Description - React Version

## 🏗️ Architecture Overview
React 버전은 **Frontend (React)** + **Backend (FastAPI)** 분리 아키텍처로 구성되어 있습니다.
- **Frontend**: React로 구현된 SPA (Single Page Application)
- **Backend**: FastAPI 기반 REST API 서버

---

## 📁 Backend (APIserver)

### Entry & Config

| Structure | File Name | Description |
|-----------|-----------|-------------|
| **Entry & Config** | app.py | • FastAPI 서버의 진입점입니다. REST API 엔드포인트를 정의하고, 서버 시작 시 데이터(CSV, VectorDB)를 로드(Lifespan)합니다.<br>• 핵심: `/api/chat/init`, `/api/chat/message`, `/api/recommendations/generate` 등의 API를 제공합니다.<br>• CORS 설정: React 개발 서버(`localhost:3000`)와 통신을 허용합니다. |
| | config.py | • 환경 변수 로드 (.env 파일), OpenAI API 키, GraphHopper API URL, 파일 경로 등을 관리합니다.<br>• 챗봇 시스템 프롬프트(`SYSTEM_PROMPT`)와 프로필 템플릿(`PROFILE_TEMPLATE`) 정의 |
| | models.py | • FastAPI 엔드포인트에서 사용하는 요청(Request) 및 응답(Response) Pydantic 모델을 정의합니다.<br>• 예: `RecommendationRequest`, `RecommendationResponse` |

### Logic & Data

| Structure | File Name | Description |
|-----------|-----------|-------------|
| **Logic & Data** | search_logic.py | • 실제 맛집 검색 알고리즘을 담당합니다.<br>• `get_rag_candidate_ids`: 사용자 쿼리로 ChromaDB에서 1차 후보군 검색 후 점수제(Scoring)를 적용합니다.<br>• `format_restaurant_markdown`: 추천된 식당 정보를 Markdown 문자열로 변환 (Gradio용, React에서는 사용 안 함)<br>• `_run_recommendation_flow`: 1단계 RAG 검색 후 2단계 Score를 실행 |
| | data_loader.py | • CSV 데이터 로드: 식당 DB, 메뉴 DB를 전처리하여 DataFrame으로 로딩합니다.<br>• `load_and_merge_translations`: 한/영/일/중 데이터를 통합 관리<br>• VectorDB 구축/로드: ChromaDB를 사용하여 식당 및 사용자 프로필 벡터 DB를 생성하거나 기존 DB를 로드합니다. |
| | llm_utils.py | • OpenAI API와 통신합니다.<br>• 대화 생성(`call_gpt4o`), 프로필 요약 생성(`generate_profile_summary_text_only`), RAG 쿼리 추출 등의 기능을 수행합니다.<br>• 다국어 지원: 4개 국어(KR, US, JP, CN) 텍스트 처리 로직 포함 |

### API & Scoring

| Structure | File Name | Description |
|-----------|-----------|-------------|
| **Utils & View** | API/final_scorer.py | • 2단계 정밀 스코어링: 1단계 RAG 후보군을 받아 GraphHopper API를 통해 뚜벅이 점수(도보 시간), 가격 매칭, 품질 점수 등을 계산합니다.<br>• `calculate_final_scores_async`: 비동기 병렬 처리로 최대 속도 향상 |

---

## 🎨 Frontend (frontfinal)

### Entry

| Structure | File Name | Description |
|-----------|-----------|-------------|
| **Entry** | src/index.js | • React 앱의 진입점입니다. ReactDOM을 사용하여 `App` 컴포넌트를 렌더링합니다. |
| | src/App.js | • 메인 애플리케이션 컴포넌트로, 전체 화면 흐름을 관리합니다.<br>• 화면 단계: 'survey' (설문) → 'loading' (추천 생성 중) → 'recommendations' (결과 표시)<br>• 상태 관리: 사용자 프로필, 추천 식당 목록, Top-K 개수, 가중치(weights) 등을 관리<br>• 언어 선택: 4개 국어(한국어, English, 日本語, 中文) UI 제공 |

### Components

| Structure | File Name | Description |
|-----------|-----------|-------------|
| **Components** | src/components/SurveyChat.js | • AI 챗봇 설문 UI 컴포넌트입니다.<br>• 사용자와 대화하며 13가지 프로필 정보(이름, 나이, 국적, 여행 타입, 예산, 맵기, 채식 등)를 수집합니다.<br>• 프로필 진행률 표시: 13개 항목 중 몇 개가 수집되었는지 % 로 표시<br>• 다국어 지원: 언어 선택 시 챗봇이 해당 언어로 대화 |
| | src/components/RestaurantList.js | • 추천된 식당 목록을 그리드 형태로 표시합니다.<br>• 배치 번역: `batchTranslateText` API를 사용하여 모든 식당 이름/주소/음식 종류를 동시 번역 (병렬 처리로 5-10배 속도 향상)<br>• 로딩/에러/빈 상태 처리 |
| | src/components/RestaurantCard.js | • 개별 식당 카드 UI입니다. 이미지, 이름, 음식 종류, 평점, 주소 등을 표시합니다.<br>• 클릭 시 모달로 상세 정보 표시 |
| | src/components/RestaurantModal.js | • 식당 상세 정보를 보여주는 모달 컴포넌트입니다.<br>• 메뉴 정보, 가격, 카카오맵 길찾기 링크, 식당 상세 페이지 링크 등을 표시 |
| | src/components/WeightsControl.js | • 추천 알고리즘의 가중치를 사용자가 직접 조절할 수 있는 슬라이더 UI입니다.<br>• 4가지 요소: 뚜벅이 점수(travel), 친절도(friendliness), 품질(quality), 가격(price)<br>• 가중치 변경 시 실시간으로 추천 재계산 |
| | src/components/SearchBar.js | • 키워드 검색바 컴포넌트 (현재 프로젝트에서 사용 여부 확인 필요) |

### Services & API

| Structure | File Name | Description |
|-----------|-----------|-------------|
| **Services** | src/services/api.js | • Backend FastAPI와 통신하는 API 클라이언트입니다.<br>• Axios를 사용하여 HTTP 요청 처리<br>• 주요 함수:<br>&nbsp;&nbsp;- `initChat`: 채팅 초기화<br>&nbsp;&nbsp;- `sendChatMessage`: 사용자 메시지 전송<br>&nbsp;&nbsp;- `generateRecommendations`: 프로필 기반 추천 생성<br>&nbsp;&nbsp;- `getRestaurantDetail`: 식당 상세 정보 조회<br>&nbsp;&nbsp;- `batchTranslateText`: 배치 번역 (병렬 처리) |

---

## 🔄 Data Flow

```
1. 사용자가 React 앱 시작
   ↓
2. SurveyChat 컴포넌트: AI 챗봇과 대화 (13개 프로필 항목 수집)
   ↓ API: /api/chat/init, /api/chat/message
3. Backend: GPT-4를 호출하여 자연스러운 대화 생성
   ↓
4. 프로필 완성 시 → App.js에서 추천 생성 요청
   ↓ API: /api/recommendations/generate
5. Backend: 1단계 RAG 검색 (ChromaDB) + 2단계 정밀 스코어링 (GraphHopper)
   ↓
6. 추천 결과 반환 → RestaurantList 표시
   ↓
7. 사용자가 언어 변경 시 → 배치 번역 API 호출 (병렬 처리)
   ↓ API: /api/translate/batch
8. 번역된 식당 정보 표시
```

---

## 🆚 Gradio vs React 주요 차이점

| 구분 | Gradio 버전 | React 버전 |
|------|-------------|-----------|
| **아키텍처** | 단일 서버 (Gradio UI + FastAPI) | 분리 아키텍처 (React Frontend + FastAPI Backend) |
| **UI 렌더링** | Gradio 라이브러리 (Python) | React 컴포넌트 (JavaScript/JSX) |
| **통신 방식** | Gradio 콜백 함수 (`gradio_callbacks.py`) | REST API (`/api/*` 엔드포인트) |
| **다국어 지원** | 서버 사이드에서 텍스트 번역 후 반환 | 클라이언트 사이드에서 배치 번역 API 호출 (병렬 처리) |
| **상태 관리** | Gradio State 객체 | React useState, useEffect Hooks |
| **사용자 경험** | 웹 기반 간단한 폼 UI | SPA 기반 매끄러운 UX, 애니메이션, 실시간 번역 |

---

## 📌 주요 특징

### Backend (FastAPI)
- ✅ RESTful API 설계로 Frontend/Backend 완전 분리
- ✅ CORS 설정으로 React 개발 서버와 통신
- ✅ Lifespan 이벤트로 서버 시작 시 모든 데이터 미리 로딩
- ✅ 비동기 처리 (`async/await`)로 성능 최적화

### Frontend (React)
- ✅ 컴포넌트 기반 구조로 재사용성 극대화
- ✅ 4개 국어 UI 지원 (실시간 언어 전환)
- ✅ 배치 번역 API로 5-10배 속도 향상 (병렬 처리)
- ✅ 반응형 디자인 (모바일/태블릿/데스크톱 대응)
- ✅ 사용자 경험 최적화: 로딩 상태, 에러 핸들링, 진행률 표시

---

## 🚀 실행 방법

### Backend 실행
```bash
cd 정주환/APIserver
python app.py
# 서버 주소: http://127.0.0.1:8000
```

### Frontend 실행
```bash
cd 정주환/frontfinal
npm install
npm start
# 개발 서버 주소: http://localhost:3000
```

---

## 📝 Notes
- React 버전은 Gradio 버전의 모든 기능을 포함하면서도, 더 나은 UX와 확장성을 제공합니다.
- `gradio_callbacks.py`는 React 버전에서 사용되지 않습니다 (Gradio 전용).
- Frontend는 Node.js 환경에서 실행되며, Backend는 Python 환경에서 실행됩니다.
