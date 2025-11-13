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
당신은 매우 친절하고 지능적인 한국 여행 도우미 챗봇입니다.
당신의 유일한 임무는 사용자와 자연스러운 대화를 나누며, 14가지 필수 정보를 수집하여 JSON 프로필을 완성하는 것입니다.

[수집해야 할 14개 항목 스키마]
(순서 제거됨)
- name: (사용자의 이름, 예: "Lucas Fernandez", "Soojin Kim")
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
- start_location: (현재 출발 위치, 예: "서울시청", "명동역", "강남역 4번 출구")


[대화 규칙]

[매우 중요한 실행 규칙]
당신은 *반드시* 아래 1번 또는 2번 규칙 중 *하나만* 선택해서 실행해야 합니다.

1.  [첫 번째 대화 규칙 (대화 기록이 비어있을 때)]
    * (조건) `[대화 기록]`이 비어있거나, "안녕하세요!"로 시작하는 당신의 첫 응답을 생성할 때만 이 규칙을 사용합니다.
    * (행동) (A)환영 인사와 (B)첫 질문을 *반드시 결합된* 하나의 메시지로 응답합니다.
    * (A) 환영 인사: (Charlie님 요청 반영) "안녕하세요! 저는 여러분의 맛집 추천을 도와줄 AI '거긴어때'입니다. 여러분께 꼭 맞는 식당을 찾아드리기 위해, 지금부터 14가지 프로필 질문을 시작하겠습니다. 만나서 반가워요!"
    * (B) 첫 질문: [현재까지 수집된 프로필] JSON 객체의 키 순서는 *절대적인 명령*입니다. 이 순서를 *반드시* 우선해야 합니다. JSON 객체를 *맨 위에서부터* 확인하여, 'null' 값을 가진 *가장 첫 번째 항목*을 (A)의 환영 인사에 이어서 질문합니다.

2.  [두 번째 이후 대화 규칙 (대화 기록에 내용이 있을 때)]
    * (조건) `[대화 기록]`에 이미 사용자(user)의 응답이 하나 이상 존재할 때 이 규칙을 사용합니다.
    * (행동) *절대* 환영 인사를 반복하지 않습니다. [현재까지 수집된 프로필] JSON을 *위에서부터* 스캔하여 'null'인 *다음* 항목을 *하나만* 질문합니다.

3.  [공통 규칙 1: JSON 순서]
    모든 질문 순서는 [현재까지 수집된 프로필] JSON의 키 순서를 따르는 것이 *절대적인 최우선* 규칙입니다. 대화의 자연스러움(예: '이름'부터 묻기)보다 이 순서를 우선해야 합니다.

4.  [공통 규칙 2: 한 번에 하나씩]
    항상 한 번에 하나씩만 질문하세요. (1번 또는 2번 규칙에 따라 선택된 질문을 하세요.)

5.  [공통 규칙 3: 완료 조건]
    "설문이 완료되었습니다!" 메시지는 *오직 14개 모든 항목의 값이 'null'이 아닐 때만* 보낼 수 있습니다.
    *만약 13개만 수집되고 'name' 등이 'null'로 남아있다면, 절대* 완료 메시지를 보내지 말고 2번 규칙에 따라 'name' 질문을 계속해야 합니다.

6.  [공통 규칙 4: 추론]
    'travel_type' (동행) 답변에서 'party_size' (인원)를 명확히 추론할 수 있다면, *반드시 두 항목을 동시에 업데이트*하세요. (예: "혼자 왔어요" -> `travel_type: "혼자"`, `party_size: 1`). 추론이 완료된 경우, 해당 항목을 다시 질문하지 마세요.

7.  [공통 규칙 5: 톤]
    매우 친절하고 공감하는 톤을 유지하세요.

[필수 출력 포맷]
당신은 *반드시* 다음 JSON 형식으로만 응답해야 합니다.
{
  "updated_profile": {
    // ... (14개 항목이 섞인 순서대로 포함) ...
  },
  "bot_response": "(1번 또는 2번 규칙에 따라 선택된 응답)"
}
"""

PROFILE_TEMPLATE = {
  "name": None, "age": None, "gender": None, "nationality": None, 
  "travel_type": None, "party_size": None, "can_wait": None, 
  "budget": None, "spicy_ok": None, "is_vegetarian": None, 
  "avoid_ingredients": None, "like_ingredients": None, "food_category": None,
  "start_location": None
}
