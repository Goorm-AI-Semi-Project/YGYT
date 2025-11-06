import pandas as pd
# (수정) 필요한 라이브러리 추가
from transformers import AutoModelForSequenceClassification, AutoTokenizer, AutoConfig
import numpy as np
from scipy.special import softmax
import re
import json
import warnings
from collections import Counter
from tqdm import tqdm

# -----------------------------------------------------------------
# 0. 설정: 파일 이름 및 NLP 모델 (Full classification 방식으로 수정)
# -----------------------------------------------------------------
INPUT_REVIEWS_FILE = 'all_reviews.csv'
OUTPUT_PROCESSED_FILE = 'all_reviews_processed.csv'
MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

print(f"Loading model '{MODEL_NAME}' (Full classification)...")
# (수정) pipeline 대신 Tokenizer와 Model을 직접 로드
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
config = AutoConfig.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
print("✅ NLP Model loaded.")

# -----------------------------------------------------------------
# 1. NLP 분석 함수 (가중 평균 방식으로 수정)
# -----------------------------------------------------------------
# (수정) '외국인 친화도' 키워드는 폭넓은 버전 유지
FOREIGNER_KEYWORDS = [
    # 1. 언어 & 메뉴
    'menu', 'english', 'speaks', 'language', 'translation',
    '영어', '메뉴', '메뉴판', '외국어', '번역',
    '英語', 'メニュー', '日本語', '外国語', '翻訳',
    '英语', '菜单', '中文', '外语', '翻译',
    # 2. 주문 편의성
    'order', 'ordering', 'easy', 'kiosk', 'tablet', 'picture menu', 'vending machine',
    '주문', '키오스크', '태블릿', '그림 메뉴', '사진 메뉴', '쉽게', '편하게',
    '注文', '券売機', 'タブレット', '簡単', 'やすい',
    '点餐', '自助点餐机', '平板', '方便', '图片菜单',
    # 3. 직원 태도
    'staff', 'friendly', 'kind', 'helpful', 'welcoming', 'rude', 'unhelpful', 'patient',
    '직원', '친절', '불친절', '도움', '설명', '환대',
    '店員', '親切', '丁寧', '不親切', '助かり',
    '服务员', '友好', '热情', '不友好', '耐心', '态度',
    # 4. 대상
    'foreigner', 'tourist', 'traveler',
    '외국인', '관광객', '여행객',
    '外国人', '観光客',
    '外国人', '游客'
]
keyword_pattern = re.compile("|".join(FOREIGNER_KEYWORDS), re.IGNORECASE)

# (수정) 모델 config에서 라벨 순서 확인 후 가중치(-1, 0, 1) 설정
# config.id2label -> {0: 'Negative', 1: 'Neutral', 2: 'Positive'}
# 따라서 점수 순서는 [Negative, Neutral, Positive]
WEIGHTS = np.array([-1, 0, 1]) # Negative(-1), Neutral(0), Positive(1) 가중치

def process_review_text(text: str):
    """
    (수정됨) 리뷰 텍스트 1개를 받아 3개 확률의 '가중 평균'으로 점수를 계산합니다.
    """
    quality_score = None
    friendliness_score = None
    
    if pd.isna(text):
        return pd.Series([None, None], index=['quality_score', 'friendliness_score'])

    try:
        # 1. 토크나이징 및 모델 추론
        encoded_input = tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
        output = model(**encoded_input)
        
        # 2. 3가지 0~1 확률 추출
        scores = output[0][0].detach().numpy()
        scores = softmax(scores) # [Neg_prob, Neu_prob, Pos_prob]

        # 3. '전반적 품질' 점수 (넓은 필터): 가중 평균 계산
        # (Neg_prob * -1) + (Neu_prob * 0) + (Pos_prob * 1)
        score = np.dot(scores, WEIGHTS)
        quality_score = score
        
        # 4. '외국인 친화도' 점수 (좁은 필터) - 키워드 검사
        if keyword_pattern.search(text):
            friendliness_score = score # 이미 계산된 점수 재사용
            
    except Exception as e:
        pass # 오류 시 None 반환

    return pd.Series([quality_score, friendliness_score], index=['quality_score', 'friendliness_score'])

# -----------------------------------------------------------------
# 2. '하드 필터' 태그 추출 함수 (이전과 동일)
# -----------------------------------------------------------------
# (!!! 경고 !!!)
# 이 맵핑은 '추측'입니다. 'all_reviews.csv'를 열어보고
# 실제 스크래핑된 태그 'name'과 'value'에 맞게 반드시 수정해야 합니다.
TAG_MAPPING = {
    # 예산 (1인당 가격)
    '₩10,000 미만': '$',
    '₩10,000–20,000': '$',
    '₩20,000–30,000': '$$',
    '₩30,000–40,000': '$$',
    '₩40,000-50,000': '$$',
    '₩50,000–100,000': '$$$',
    '₩100,000 이상': '$$$',
    
    # 채식
    '채식주의자 옵션': 'is_vegetarian',
    
    # 서비스 옵션
    '그룹 이용에 적합': 'good_for_groups',
    '가족 단위에 적합': 'good_for_family',
}

def extract_hard_filter_tags(details_str: str):
    """
    리뷰 1개의 'experience_details' 문자열을 파싱하여
    '하드 필터' 태그를 추출합니다.
    """
    tags = {
        'price_range': None,
        'is_vegetarian': False
    }
    
    if pd.isna(details_str):
        return pd.Series(tags)

    try:
        details_list = json.loads(details_str)
        for item in details_list:
            tag_name = item.get('name')
            tag_value = item.get('value')
            
            if tag_name == '1인당 가격':
                mapped_price = TAG_MAPPING.get(tag_value)
                if mapped_price:
                    tags['price_range'] = mapped_price
            
            mapped_tag = TAG_MAPPING.get(tag_name) or TAG_MAPPING.get(tag_value)
            if mapped_tag == 'is_vegetarian':
                tags['is_vegetarian'] = True

    except:
        pass 

    return pd.Series(tags)

# -----------------------------------------------------------------
# 3. 메인 실행 함수 (처리) - (이전과 동일)
# -----------------------------------------------------------------
def main():
    warnings.filterwarnings('ignore')
    tqdm.pandas(desc="Processing Reviews") # pandas.apply() 진행률 표시
    
    print(f"Loading all reviews from '{INPUT_REVIEWS_FILE}'...")
    try:
        df = pd.read_csv(
            INPUT_REVIEWS_FILE, 
            usecols=['place_id', 'place_name', 'review_text', 'experience_details'],
            encoding='utf-8'
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            INPUT_REVIEWS_FILE,
            usecols=['place_id', 'place_name', 'review_text', 'experience_details'],
            encoding='cp437'
        )
    except FileNotFoundError:
        print(f"❌ Error: '{INPUT_REVIEWS_FILE}'을(를) 찾을 수 없습니다.")
        return
    except ValueError:
        print(f"❌ Error: '{INPUT_REVIEWS_FILE}'에 필요한 컬럼이 없습니다.")
        return

    print(f"Loaded {len(df)} reviews.")
    
    print("Running NLP analysis for all reviews...")
    nlp_scores = df['review_text'].progress_apply(process_review_text)
    df = pd.concat([df, nlp_scores], axis=1)
    
    print("Extracting hard filter tags from 'experience_details'...")
    tags = df['experience_details'].progress_apply(extract_hard_filter_tags)
    df = pd.concat([df, tags], axis=1)

    df.to_csv(OUTPUT_PROCESSED_FILE, index=False, encoding='utf-8-sig')
    
    print(f"\n🎉 Success! '데이터당 작업' 완료.")
    print(f"'{OUTPUT_PROCESSED_FILE}' 파일이 저장되었습니다.")
    print("\n--- Processed File (Head) ---")
    print(df.head())

# -----------------------------------------------------------------
# 4. 스크립트 실행
# -----------------------------------------------------------------
if __name__ == "__main__":
    main()