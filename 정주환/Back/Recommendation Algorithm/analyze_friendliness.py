import pandas as pd
from transformers import pipeline
import re
import warnings

# -----------------------------------------------------------------
# 1. 설정: 모델, 키워드, 점수 매핑
# -----------------------------------------------------------------

# "transformers" 라이브러리가 필요합니다.
# 이 모델은 영어, 한국어, 일본어, 중국어 등 다양한 언어를
# 번역 없이 바로 이해하고 감성을 분석할 수 있습니다.
MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

# 분석할 '외국인 친화도' 관련 키워드
# (다국어)
FOREIGNER_KEYWORDS = [
    # English
    'menu', 'staff', 'order', 'english', 'communication', 'friendly', 'speaks', 'foreigner',
    # Korean
    '메뉴', '영어', '직원', '주문', '친절', '불친절', '외국인',
    # Japanese
    'メニュー', '英語', '店員', '注文', '親切',
    # Chinese (Simplified)
    '菜单', '英语', '服务员', '点餐', '友好'
]
# 효율적인 검색을 위해 하나의 regex 패턴으로 컴파일 (대소문자 무시)
keyword_pattern = re.compile("|".join(FOREIGNER_KEYWORDS), re.IGNORECASE)

# 모델이 출력하는 감성 레이블을 점수로 변환
SENTIMENT_SCORE_MAP = {
    'Positive': 1,
    'Neutral': 0,
    'Negative': -1
}

# -----------------------------------------------------------------
# 2. 메인 분석 함수
# -----------------------------------------------------------------
def analyze_restaurant_friendliness(csv_path: str):
    """
    주어진 CSV 파일의 리뷰를 분석하여 '외국인 친화도 점수'를 계산합니다.
    """
    
    # --- A. 모델 로드 ---
    print(f"Loading multilingual sentiment model '{MODEL_NAME}'...")
    try:
        sentiment_pipeline = pipeline("sentiment-analysis", model=MODEL_NAME)
        print("✅ Model loaded successfully.")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        print("HuggingFace Hub에서 모델을 다운로드하려면 인터넷 연결이 필요합니다.")
        return

    # --- B. 데이터 로드 및 전처리 ---
    print(f"\nLoading reviews from '{csv_path}'...")
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding='cp949') # 윈도우용 fallback

    # 'review_text' 컬럼(원본 리뷰)에 NaN(빈 값)이 있는 행 제거
    original_count = len(df)
    df.dropna(subset=['review_text'], inplace=True)
    print(f"Loaded {original_count} reviews. Processing {len(df)} non-empty reviews.")

    # --- C. 분석 파이프라인 함수 ---
    def get_friendliness_score(review_text: str):
        """
        리뷰 1개를 분석하여 관련 키워드가 있으면 감성 점수를 반환합니다.
        """
        if not isinstance(review_text, str):
            return None
        
        # 1. 키워드가 포함되어 있는지 확인
        if keyword_pattern.search(review_text):
            try:
                # 2. 키워드가 있다면, 다국어 감성 모델 실행
                result = sentiment_pipeline(review_text, max_length=512, truncation=True)
                label = result[0]['label']
                # 3. 레이블을 점수(1, 0, -1)로 변환
                return SENTIMENT_SCORE_MAP.get(label, 0)
            except Exception as e:
                print(f"Error during sentiment analysis: {e}")
                return None
        else:
            # 관련 키워드가 없으면 점수 계산에서 제외 (None)
            return None

    # --- D. 파이프라인 실행 ---
    print("\nRunning NLP pipeline on relevant reviews (this may take a a few minutes)...")
    # 'review_text' 컬럼의 모든 리뷰에 함수 적용
    df['friendliness_score'] = df['review_text'].apply(get_friendliness_score)

    # --- E. 결과 집계 ---
    # 키워드가 있어서 점수가 매겨진 리뷰만 필터링
    scored_reviews_df = df.dropna(subset=['friendliness_score'])

    print(f"\n--- Analysis Complete ---")
    print(f"Found {len(scored_reviews_df)} reviews containing relevant keywords.")

    if scored_reviews_df.empty:
        print("\n=======================================================")
        print(f"⚠️ '{csv_path}'의 리뷰 중 관련 키워드를 포함한 리뷰가 없습니다.")
        print("=======================================================")
        return

    # 점수가 매겨진 리뷰와 원본 텍스트 출력
    print("\n--- Scored Reviews ---")
    for _, row in scored_reviews_df.iterrows():
        score_text = {1: 'Positive', -1: 'Negative', 0: 'Neutral'}.get(row['friendliness_score'])
        print(f"  [{score_text:8}] : \"{row['review_text'][:80]}...\"")

    # 이 식당의 최종 '외국인 친화도 점수' (평균값)
    final_score = scored_reviews_df['friendliness_score'].mean()
    
    print("\n=======================================================")
    print(f"🏆 최종 '외국인 친화도 점수': {final_score:.4f}")
    print("=======================================================")


# -----------------------------------------------------------------
# 3. 스크립트 실행
# -----------------------------------------------------------------
if __name__ == "__main__":
    # 분석할 CSV 파일 지정
    warnings.filterwarnings('ignore')
    analyze_restaurant_friendliness(csv_path="다이닝마-detailed-reviews.csv")