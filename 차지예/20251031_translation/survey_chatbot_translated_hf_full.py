
# survey_chatbot_translated_hf_full.py
import os, json
import gradio as gr

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from openai import OpenAI
    _env_key = os.getenv("OPENAI_API_KEY")
    if _env_key:
        client = OpenAI(api_key=_env_key)
        API_ERROR = None
    else:
        client = None
        API_ERROR = "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다."
except Exception as e:
    client = None
    API_ERROR = str(e)

from huggingface_translate import HFTranslator
from glossary import enforce_glossary_en
from polite_post_edit import PolitePostEditor
from quality_checks import profile_completeness, enforce_keywords_in_summary

TRANS = HFTranslator("Helsinki-NLP/opus-mt-ko-en")
POST_EDITOR = PolitePostEditor(use_llm=False)

SYSTEM_PROMPT = """
당신은 매우 친절하고 지능적인 한국 여행 도우미 챗봇입니다.
당신의 유일한 임무는 사용자와 자연스러운 대화를 나누며, 12가지 필수 정보를 수집하여 JSON 프로필을 완성하는 것입니다.

[수집해야 할 12개 항목 스키마]
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

[대화 규칙]
1.  대화는 당신이 먼저 시작합니다. 환영 인사와 함께 첫 질문(예: 연령대)을 하세요.
2.  항상 한 번에 하나씩만 질문하세요.
3.  사용자의 답변을 분석하여 [현재 프로필]을 업데이트합니다. (한 번에 여러 정보가 들어오면 모두 업데이트)
4.  업데이트된 프로필을 확인하고, 아직 'null'이거나 수집되지 않은 항목 중 하나를 골라 자연스럽게 다음 질문을 합니다.
5.  모든 12개 항목이 수집되면, "설문이 완료되었습니다! 감사합니다."라는 메시지를 보내고 더 이상 질문하지 마세요.
6.  매우 친절하고 공감하는 톤을 유지하세요.

[필수 출력 포맷]
당신은 *반드시* 다음 JSON 형식으로만 응답해야 합니다.
{
  "updated_profile": {
    "age": "20대",
    "gender": "남",
    "nationality": null,
    "travel_type": null,
    "party_size": null,
    "can_wait": null,
    "budget": null,
    "spicy_ok": null,
    "is_vegetarian": null,
    "avoid_ingredients": null,
    "like_ingredients": null,
    "food_category": null
  },
  "bot_response": "아, 20대 남성이시군요! 반갑습니다. 혹시 국적이 어떻게 되시나요?"
}
"""

PROFILE_TEMPLATE = {
  "age": None, "gender": None, "nationality": None, "travel_type": None,
  "party_size": None, "can_wait": None, "budget": None, "spicy_ok": None,
  "is_vegetarian": None, "avoid_ingredients": None, "like_ingredients": None,
  "food_category": None
}

def _translate_ko_to_en(text: str) -> str:
    en = TRANS.translate(text)
    en = enforce_glossary_en(en)
    en = POST_EDITOR.rewrite(en)
    return en

def _no_key_banner():
    tip = (
        "OpenAI key not set. Add a .env file with\n"
        "OPENAI_API_KEY=sk-...\n"
        "or export it in your shell before running."
    )
    return f"⚠️ {_translate_ko_to_en('시스템 설정 오류: OPENAI_API_KEY가 필요합니다.')}\n{tip}"

def generate_profile_summary(profile_data):
  if client is None:
    return "\n\n(" + _translate_ko_to_en("프로필 요약 생성에 실패했습니다. (LLM 미설정)") + ")"
  profile_str = json.dumps(profile_data, indent=2, ensure_ascii=False)
  summary_system_prompt = """
  당신은 JSON 프로필 데이터를 받아서, 그 사람의 입장에서 자신을 소개하는 '구어체' 텍스트로 변환하는 글쓰기 전문가입니다.
  데이터를 기반으로 매우 자연스럽고 친근한 톤으로 "안녕하세요! 저는..." 하고 시작하는 1인칭 자기소개 글을 작성해주세요.
  [규칙]
  1. 1인칭 시점("저는", "제가")를 사용하세요.
  2. 딱딱한 리스트가 아닌, 하나의 연결된 문단으로 만드세요.
  3. 모든 정보를 포함하되, 자연스럽게 문장에 녹여내세요.
  4. 'party_size'와 'travel_type'을 묶어서 표현하세요.
  5. 'budget'은 "가성비 있는", "적당한", "고급스러운" 등으로 표현하세요.
  6. 'can_wait'는 "맛집이라면 줄 서는 것도 괜찮아요" 등으로 표현하세요.
  """
  user_prompt = f"""
  [사용자 프로필 JSON]
  {profile_str}
  위 프로필을 바탕으로 규칙에 맞게 자기소개 글을 작성해주세요.
  """
  try:
    resp = client.chat.completions.create(
      model="gpt-4o",
      messages=[
        {"role": "system", "content": summary_system_prompt},
        {"role": "user", "content": user_prompt}
      ],
      temperature=0.7
    )
    summary_ko = resp.choices[0].message.content
    summary_en = _translate_ko_to_en(summary_ko)
    summary_en = enforce_keywords_in_summary(summary_en, profile_data)
    return f"\n\n---\n\n### 🤖 " + _translate_ko_to_en("AI가 파악한 Charlie님의 프로필") + f"\n\n{summary_en}"
  except Exception as e:
    return "\n\n(" + _translate_ko_to_en("프로필 요약 생성에 실패했습니다.") + f" {e}" + ")"

def call_gpt4o(chat_messages, current_profile):
  if client is None:
    return _no_key_banner(), current_profile
  system_message_with_profile = f"""
  {SYSTEM_PROMPT}

  [현재까지 수집된 프로필]
  {json.dumps(current_profile, indent=2, ensure_ascii=False)}

  [대화 기록]
  (대화 기록은 아래 메시지 리스트에 포함되어 있습니다)
  """
  messages = [{"role": "system", "content": system_message_with_profile}]
  messages.extend(chat_messages)
  try:
    response = client.chat.completions.create(
      model="gpt-4o",
      messages=messages,
      response_format={"type": "json_object"},
      temperature=0.7
    )
    data = json.loads(response.choices[0].message.content)
    bot_message_ko = data.get("bot_response", "오류가 발생했습니다.")
    updated_profile = data.get("updated_profile", current_profile)
    bot_message_en = _translate_ko_to_en(bot_message_ko)
    return bot_message_en, updated_profile
  except Exception as e:
    return _translate_ko_to_en("죄송합니다. 챗봇 응답 생성 중 오류가 발생했습니다:") + f" {e}", current_profile

def start_chat():
  initial_profile = PROFILE_TEMPLATE.copy()
  bot_message_en, updated_profile = call_gpt4o([], initial_profile)
  gradio_history = [(None, bot_message_en)]
  llm_history = [{"role": "assistant", "content": bot_message_en}]
  return gradio_history, llm_history, updated_profile, False

def chat_survey(message, gradio_history, llm_history, current_profile, is_completed):
  llm_history.append({"role": "user", "content": message})
  bot_message_en, updated_profile = call_gpt4o(llm_history, current_profile)
  llm_history.append({"role": "assistant", "content": bot_message_en})

  final_bot_message = bot_message_en
  profile_is_complete = all(v is not None for v in updated_profile.values())
  if profile_is_complete and not is_completed:
    gr.Info("Profile complete! Generating a friendly summary...")
    summary_text = generate_profile_summary(updated_profile)
    final_bot_message = f"{bot_message_en}\n{summary_text}"
    is_completed = True

  gradio_history.append((message, final_bot_message))
  return gradio_history, llm_history, updated_profile, is_completed

with gr.Blocks(theme=gr.themes.Soft()) as demo:
  title = "🤖 " + _translate_ko_to_en("GPT-4o 기반 자연어 서베이 챗봇 (요약 기능)")
  subtitle = _translate_ko_to_en("AI가 12가지 프로필 정보를 수집하고, 완료되면 구어체로 요약합니다.")

  if API_ERROR:
    gr.Markdown(f"> {_translate_ko_to_en('주의: ')}{_translate_ko_to_en(API_ERROR)}")

  gr.Markdown(f"# {title}")
  gr.Markdown(subtitle)

  llm_history_state = gr.State(value=[])
  profile_state = gr.State(value=PROFILE_TEMPLATE.copy())
  is_completed_state = gr.State(value=False)

  chatbot = gr.Chatbot(label=_translate_ko_to_en("서베이 챗봇"), height=600, show_copy_button=True)
  msg_textbox = gr.Textbox(label=_translate_ko_to_en("답변 입력"), placeholder=_translate_ko_to_en("여기에 답변을 입력하고 Enter를 누르세요..."))

  demo.load(fn=start_chat, inputs=None, outputs=[chatbot, llm_history_state, profile_state, is_completed_state])

  msg_textbox.submit(
    fn=chat_survey,
    inputs=[msg_textbox, chatbot, llm_history_state, profile_state, is_completed_state],
    outputs=[chatbot, llm_history_state, profile_state, is_completed_state]
  )
  msg_textbox.submit(lambda: "", inputs=None, outputs=msg_textbox)

if __name__ == "__main__":
  if API_ERROR:
    print(f"!!! Warning: {API_ERROR}")
    print("!!! Check .env or export OPENAI_API_KEY=sk-... before running.")
  demo.launch()
