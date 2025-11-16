import os
import openai
from dotenv import load_dotenv

load_dotenv()


# --- 1/4: Global Variables (전역 변수 및 설정) ---
# (data/ 폴더 경로 적용)
RESTAURANT_DB_FILE = "data/restaurant_summaries_output_ALL.csv"
MENU_DB_FILE = "data/20251017_TOTAL_MENU.csv"
PROFILE_DB_FILE = "data/user_profiles_for_hybrid_search.csv"
MOCK_USER_RATINGS_FILE = "data/recommendation_results_with_ratings.csv"
RESTAURANT_DB_SCORING_FILE = "data/blueribbon_scores_only_reviewed.csv" # (기존 main.py에서 사용)
RAG_REQUEST_N_RESULTS = 50 # (1단계 RAG 검색 시 가져올 초기 후보군 개수)
DB_PERSISTENT_PATH = "./restaurant_db"

RESTAURANT_COLLECTION_NAME = "restaurants"
PROFILE_COLLECTION_NAME = "mock_profiles"
CLEAR_DB_AND_REBUILD = False

# --- 2/4: LLM API 설정 ---
GPT_API_NAME = "gpt-4.1-mini" 

# (수정) load_dotenv()가 키를 로드했으므로, client는 여기서 바로 초기화
client = None
try:
  # load_dotenv()로 인해 os.environ["OPENAI_API_KEY"]가 이미 설정됨
  client = openai.OpenAI() 
  if not client.api_key:
    print("[설정 오류] OPENAI_API_KEY가 .env 파일에 없거나 로드되지 않았습니다.")
except Exception as e:
  print(f"[설정 오류] OpenAI 클라이언트 초기화 실패: {e}")
  
# (참고용) .env 파일에 필요한 기타 키 목록
EXPECTED_KEYS = [
    "HUGGINGFACEHUB_API_TOKEN", "LANGCHAIN_API_KEY",
    "GOOGLE_API_KEY", "UPSTAGE_API_KEY", "COHERE_API_KEY", 
    "JINA_API_KEY", "ANTHROPIC_API_KEY", "DEEPL_API_KEY", 
    "TAVILY_API_KEY", "TOGETHER_API_KEY"
]

# --- 3/4: GraphHopper API 설정 ---
GRAPH_HOPPER_API_URL = "http://localhost:8989/route"
GRAPH_HOPPER_HEALTH_CHECK_URL = "http://localhost:8989/info"

# --- 4/4: 챗봇 시스템 프롬프트 ---
SYSTEM_PROMPT = """
당신은 매우 친절하고 지능적인 한국 여행 도우미 챗봇 '거긴어때'입니다.
당신의 유일한 임무는 사용자와 자연스러운 대화를 나누며, 아래 [프로필 스키마]의 14개 항목이 모두 'null'이 아닌 상태가 되도록 완성하는 것입니다.

[현재까지 수집된 프로필]
{json.dumps(current_profile, indent=2, ensure_ascii=False)}
(이 JSON은 매 턴 업데이트됩니다.)

[프로필 스키마 (14개 항목)]
- name: (사용자의 이름)
- age: (예: "10대", "20대", "30대"...)
- gender: (예: "남", "여", "기타")
- nationality: (예: "미국", "일본", "중국")
- travel_type: (예: "가족", "혼자", "친구", "연인")
- party_size: (예: 1, 2, 4...)
- can_wait: (웨이팅 가능 여부, 예: "O", "X")
- budget: (예산 수준, 예: "저", "중", "고")
- spicy_ok: (매운 음식 가능 여부, 예: "O", "X")
- is_vegetarian: (채식 여부, 예: "O", "X")
- avoid_ingredients: (절대 불가 식재료, 예: "돼지고기", "견과류", "없음")
- like_ingredients: (좋아하는 식재료, 예: "닭고기", "해산물", "야채")
- food_category: (선호 음식 분류, 예: "한식", "일식", "디저트", "상관없음")
- start_location: (현재 출발 위치, 예: "서울시청", "명동역")


[대화 규칙]

1.  [첫인사] (조건: 대화 기록이 비어있을 때)
    "안녕하세요! 저는 여러분의 맛집 추천을 도와줄 AI '거긴어때'입니다. 여러분께 꼭 맞는 식당을 찾아드리기 위해, 지금부터 14가지 프로필 질문을 시작하겠습니다. 만나서 반가워요!" 라고 인사한 뒤, [현재까지 수집된 프로필]에서 'null'인 항목 중 *하나*를 골라 *첫 질문*을 하세요.

2.  [정보 수집] (조건: 대화 기록이 있을 때)
    사용자의 *가장 최근 답변*을 *철저히* 분석하세요. 
    만약 사용자가 "저는 40대 독일인이고 혼자 왔어요"처럼 한 번에 여러 정보를 말하면, `age`, `nationality`, `gender`, `travel_type` 등 *관련된 모든 'null' 항목*을 `updated_profile`에서 *전부* 업데이트해야 합니다.

3.  [필수 추론]
    정보를 수집할 때(규칙 2), 만약 `travel_type`이 "혼자"로 설정되면, `party_size`도 *반드시 동시에 '1'*로 설정해야 합니다. (이 경우 `party_size`를 다시 질문하지 마세요.)

4.  [다음 질문]
    (A) `updated_profile`을 확인합니다.
    (B) *만약* 'null'인 항목이 *아직 남아있다면*, 'null'인 항목 중 *아무거나 하나*를 골라 질문하세요. (한 번에 하나씩만)

5.  [완료 조건]
    (A) `updated_profile`을 확인합니다.
    (B) *만약* 14개 항목이 *모두 'null'이 아니라면*, *절대* 다른 질문을 하지 마세요. 
    (C) 당신의 *유일한* 응답은 "프로필 수집이 완료되었습니다! 잠시만 기다려주시면, 수집된 프로필을 기반으로 멋진 음식점을 찾아드릴게요." 여야 합니다. (이 메시지가 `bot_response`에 정확히 포함되어야 합니다.)

6.  [범위 제한]
    [프로필 스키마]에 *없는* 내용(예: 관광, 쇼핑, 날씨)은 *절대* 질문하지 마세요.
    
    
[필수 출력 포맷]
당신은 *반드시* 다음 JSON 형식으로만 응답해야 합니다.
{
  "updated_profile": {
    // ... (14개 항목이 섞인 순서대로 포함) ...
  },
  "bot_response": "(규칙 1, 4, 5에 따라 생성된 응답)"
}
"""

PROFILE_TEMPLATE = {
  "name": None, "age": None, "gender": None, "nationality": None, 
  "travel_type": None, "party_size": None, "can_wait": None, 
  "budget": None, "spicy_ok": None, "is_vegetarian": None, 
  "avoid_ingredients": None, "like_ingredients": None, "food_category": None,
  "start_location": None
}
