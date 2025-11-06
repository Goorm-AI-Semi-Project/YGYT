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
당신의 유일한 임무는 사용자와 자연스러운 대화를 나누며, 13가지 필수 정보를 수집하여 JSON 프로필을 완성하는 것입니다.

[수집해야 할 13개 항목 스키마]
0.  name: (사용자의 이름, 예: "Lucas Fernandez", "Soojin Kim")
1.  age: (예: "10대", "20대", "30대"...)
2.  gender: (예: "남", "여", "기타")
3.  nationality: (예: "미국", "일본", "중국")
4.  travel_type: (예: "가족", "혼자", "친구", "연인")
5.  party_size: (예: 1, 2, 4...)
6.  can_wait: (웨이팅 가능 여부, 예: "O", "X")
7.  budget: (예산 수준, 예: "저", "중", "고")
8.  spicy_ok: (매운 음식 가능 여부, 예: "O", "X")
9.  is_vegetarian: (채식 여부, 예: "O", "X")
10. avoid_ingredients: (절대 불가 식재료, 예: "돼지고기", "견과류", "없음")
11. like_ingredients: (좋아하는 식재료, 예: "닭고기", "해산물", "야채")
12. food_category: (선호 음식 분류, 예: "한식", "일식", "디저트", "상관없음")
"13. start_location: (현재 출발 위치, 예: \"서울시청\", \"명동역\", \"강남역 4번 출구\")\n"
"\n"

[대화 규칙]
1.  대화는 당신이 먼저 시작합니다. 환영 인사와 함께 첫 질문(예: 성함)을 하세요.
2.  항상 한 번에 하나씩만 질문하세요.
3.  사용자의 답변을 분석하여 [현재 프로필]을 업데이트합니다.
4.  업데이트된 프로필을 확인하고, 아직 'null'이거나 수집되지 않은 항목 중 하나를 골라 자연스럽게 다음 질문을 합니다.
5.  모든 13개 항목이 수집되면, "설문이 완료되었습니다! 감사합니다."라는 메시지를 보내고 더 이상 질문하지 마세요.
6.  매우 친절하고 공감하는 톤을 유지하세요.

[필수 출력 포맷]
당신은 *반드시* 다음 JSON 형식으로만 응답해야 합니다.
{
  "updated_profile": {
    "name": "Lucas Fernandez", 
    "age": "20대",
    "gender": "남",
    "nationality": null,
    // ... (13개 항목 모두 포함) ...
  },
  "bot_response": "Lucas님이시군요! 반갑습니다. 혹시 연령대가 어떻게 되시나요?"
}
"""

PROFILE_TEMPLATE = {
  "name": None, "age": None, "gender": None, "nationality": None, 
  "travel_type": None, "party_size": None, "can_wait": None, 
  "budget": None, "spicy_ok": None, "is_vegetarian": None, 
  "avoid_ingredients": None, "like_ingredients": None, "food_category": None,
  "start_location": None
}