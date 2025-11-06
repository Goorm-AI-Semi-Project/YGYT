import pandas as pd
from rapidfuzz import process, fuzz
import sys
import re

# tqdm 라이브러리 설정
try:
    from tqdm import tqdm
    tqdm.pandas(desc="실패 원인 분석 중")
    USE_TQDM = True
except ImportError:
    USE_TQDM = False

# --- 사용자 설정 ---
# 1. 분석할 실패 파일 (v10 코드에서 생성된 파일)
FAILED_FILE = 'final_result_v15_failed.csv'
# 2. 원본 블루리본 파일 (비교 대상)
BLUERIBBON_FILE = '20251016_서울시_음식점_목록_GPS.csv'
# 3. 컬럼명 설정
REVIEW_NAME_COL = 'place_name'
BLUERIBBON_NAME_COL = '가게'
# -------------------

def clean_name(name):
    if pd.isna(name): return None
    return re.sub(r'\s+', ' ', str(name)).strip().lower()

print("매핑 실패 원인 심층 분석을 시작합니다...")

# 1. 데이터 로드
try:
    df_failed = pd.read_csv(FAILED_FILE)
    df_blueribbon = pd.read_csv(BLUERIBBON_FILE)
except FileNotFoundError as e:
    print(f"[오류] 파일을 찾을 수 없습니다: {e}")
    print("매핑 코드(v10)를 먼저 실행하여 결과 파일을 만들어주세요.")
    sys.exit()

# 2. 블루리본 참조 데이터 준비
df_blueribbon['clean_name'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(clean_name)
blueribbon_names = list(df_blueribbon['clean_name'].dropna().unique())

# 3. 실패한 고유 가게 목록 추출
unique_failed_shops = df_failed[REVIEW_NAME_COL].unique()
print(f"총 {len(unique_failed_shops)}개의 고유한 실패 가게를 분석합니다.")

# 4. 심층 분석 함수 (제한 없이 가장 비슷한 것 찾기)
def analyze_failure(target_name):
    clean_target = clean_name(target_name)
    if not clean_target: return None, 0
    
    # 임계값(score_cutoff) 없이 무조건 가장 비슷한 1개를 찾음
    match = process.extractOne(
        clean_target, 
        blueribbon_names, 
        scorer=fuzz.token_set_ratio
    )
    if match:
        return match[0], match[1] # (가장 비슷한 이름, 그 점수)
    return None, 0

# 5. 분석 실행
df_analysis = pd.DataFrame({'failed_name': unique_failed_shops})

print("모든 실패 가게에 대해 블루리본 데이터와 재대조 중...")
if USE_TQDM:
    results = df_analysis['failed_name'].progress_apply(analyze_failure)
else:
    results = df_analysis['failed_name'].apply(analyze_failure)

df_analysis[['best_match_clean', 'best_score']] = pd.DataFrame(results.tolist(), index=df_analysis.index)

# 6. 원본 블루리본 이름 복원 (보기 편하게)
# clean_name을 기반으로 원본 이름을 찾아 붙임
clean_to_original = df_blueribbon.set_index('clean_name')[BLUERIBBON_NAME_COL].to_dict()
df_analysis['best_match_original'] = df_analysis['best_match_clean'].map(clean_to_original)

# 7. 유형 분류
def categorize_failure(score):
    if score >= 90: return "1. 미스터리 (90점 이상인데 왜 실패?)"
    elif score >= 80: return "2. 아까운 불일치 (80~89점)"
    elif score >= 60: return "3. 애매한 불일치 (60~79점)"
    else: return "4. 블루리본에 없음 (60점 미만)"

df_analysis['failure_type'] = df_analysis['best_score'].apply(categorize_failure)

# 8. 결과 리포트 출력
print("\n========== [매핑 실패 원인 분석 리포트] ==========")
summary = df_analysis['failure_type'].value_counts().sort_index()
for category, count in summary.items():
    ratio = (count / len(unique_failed_shops)) * 100
    print(f"\n{category}: {count}개 ({ratio:.1f}%)")
    
    # 각 유형별 예시 출력 (상위 5개)
    examples = df_analysis[df_analysis['failure_type'] == category].sort_values('best_score', ascending=False).head(5)
    for _, row in examples.iterrows():
        print(f"   - [리뷰] '{row['failed_name']}' vs [블루리본] '{row['best_match_original']}' (점수: {row['best_score']:.1f})")

# 9. 상세 분석 결과 저장
df_analysis.to_csv('failed_reasons_detailed.csv', index=False, encoding='utf-8-sig')
print("\n==================================================")
print("상세 분석 결과가 'failed_reasons_detailed.csv'에 저장되었습니다.")
print("이 파일을 열어서 '2. 아까운 불일치' 유형을 우선적으로 검토해보세요.")