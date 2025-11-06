import json
from config import client, GPT_API_NAME, SYSTEM_PROMPT, PROFILE_TEMPLATE

# --- (함수 4/9) ---
def call_gpt4o(chat_messages, current_profile):
  """(메인) gpt-4.1-mini API를 호출하고 JSON 응답을 파싱하는 함수"""
  
  if client is None:
      return "죄송합니다. OpenAI API 키가 설정되지 않았습니다.", current_profile
      
  system_message_with_profile = f"""
  {SYSTEM_PROMPT}
  [현재까지 수집된 프로필]
  {json.dumps(current_profile, indent=2, ensure_ascii=False)}
  [대화 기록]
  (대화 기록은 아래 메시지 리스트에 포함되어 있습니다)
  """
  
  messages_for_api = [
    {"role": "system", "content": system_message_with_profile}
  ]
  messages_for_api.extend(chat_messages)

  try:
    response = client.chat.completions.create(
      model=GPT_API_NAME,
      messages=messages_for_api,
      response_format={"type": "json_object"}, 
      temperature=0.7
    )
    
    response_content = response.choices[0].message.content
    response_data = json.loads(response_content)
    
    bot_message = response_data.get("bot_response", "오류가 발생했습니다.")
    updated_profile = response_data.get("updated_profile", current_profile)
    
    return bot_message, updated_profile
    
  except Exception as e:
    print(f"API 호출 또는 JSON 파싱 오류: {e}")
    error_message = f"죄송합니다. 챗봇 응답 생성 중 오류가 발생했습니다: {e}"
    return error_message, current_profile

# --- (함수 6/9) ---
def generate_profile_summary(profile_data):
  """
  완성된 프로필(JSON)을 받아, gpt-4.1-mini를 호출하여
  (1) Gradio 채팅용 메시지, (2) CSV 저장용 원본 요약문 텍스트 
  2가지를 반환합니다.
  """
  if client is None:
      return "(오류: API 키 미설정)", "(오류: API 키 미설정)"

  profile_str = json.dumps(profile_data, indent=2, ensure_ascii=False)
  
  summary_system_prompt = """
  당신은 JSON 프로필 데이터를 받아서, 그 사람의 입장에서 자신을 소개하는 '구어체' 텍스트로 변환하는 글쓰기 전문가입니다.
  [규칙]
  1. (필수) JSON의 'name' 필드를 사용하여 "안녕하세요! 저는 [name]입니다."로 문장을 시작하세요.
  2. 딱딱한 리스트가 아닌, 하나의 연결된 문단으로 만드세요.
  3. 모든 정보를 포함하되, 자연스럽게 문장에 녹여내세요.
  4. 'party_size'와 'travel_type'을 묶어서 표현하세요.
  5. 'budget'은 "가성비 있는(저렴한)", "적당한", "고급스러운" 등으로 표현하세요.
  """
  
  user_prompt = f"""
  [사용자 프로필 JSON]
  {profile_str}
  위 프로필을 바탕으로 규칙에 맞게 자기소개 글을 작성해주세요.
  """
  
  try:
    response = client.chat.completions.create(
      model=GPT_API_NAME,
      messages=[
        {"role": "system", "content": summary_system_prompt},
        {"role": "user", "content": user_prompt}
      ],
      temperature=0.7
    )
    
    raw_summary_text = response.choices[0].message.content
    name = profile_data.get('name', '사용자')
    chat_message_html = f"\n\n---\n\n### 🤖 AI가 파악한 {name}님의 프로필\n\n{raw_summary_text}"
    
    return chat_message_html, raw_summary_text
  
  except Exception as e:
    print(f"요약 생성 오류: {e}")
    error_html = "\n\n(프로필 요약 생성에 실패했습니다.)"
    error_text = "(프로필 요약 생성에 실패했습니다.)"
    return error_html, error_text

# --- (함수 8/9 중 하나) ---
def generate_rag_query(user_profile_summary):
  """
  LLM을 호출하여 긴 자기소개(요약문)를
  가게 RAG 텍스트와 매칭하기 좋은 '짧은 핵심 쿼리'로 변환합니다.
  """
  if client is None:
      return user_profile_summary[:150] # API 키 없으면 원본 반환
      
  print("  > [RAG] LLM을 호출하여 '분위기/성향' 쿼리를 재작성합니다...")
  
  system_prompt = """
  당신은 사용자의 긴 자기소개 텍스트를, 레스토랑 벡터 DB에서 검색하기 위한
  '짧고 핵심적인 쿼리 문장'으로 재작성(Re-writing)하는 전문가입니다.
  
  [규칙]
  1.  '안녕하세요', '저는 OOO입니다', '30대', '캐나다' 등 개인 신상 정보는 *모두 제거*합니다.
  2.  '예산(저/중/고)', '맵기(O/X)', '선호 재료(소고기)' 등 '사실(Fact)' 정보는 *모두 제거*합니다.
  3.  오직 사용자가 원하는 *분위기*, *상황*, *경험*, *성향* (예: '조용한', '혼자', '연인과 함께', '새로운 도전', '인기 맛집', '가족적인')만 추출하여 하나의 문장으로 만듭니다.
  4.  결과는 오직 '재작성된 쿼리 문장' 하나만 반환합니다.
  """
  
  user_prompt = f"""
  [사용자 자기소개]
  {user_profile_summary}
  
  [재작성된 쿼리]
  """

  try:
    response = client.chat.completions.create(
      model=GPT_API_NAME,
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
      ],
      temperature=0.2
    )
    rewritten_query = response.choices[0].message.content.strip().replace('"', '')
    return rewritten_query
  except Exception as e:
    print(f"  > [오류] 쿼리 재작성 실패: {e}")
    return user_profile_summary[:150]