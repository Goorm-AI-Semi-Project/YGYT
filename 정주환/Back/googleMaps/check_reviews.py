import pandas as pd
import os
import glob # 파일 경로를 쉽게 찾기 위해 glob을 사용합니다.

# --- 1. 설정: 이 부분을 사용자의 환경에 맞게 수정하세요. ---

# 1-1. 원본 가게 이름 목록 파일
# 이전에 생성한 .txt 파일의 경로입니다.
ORIGINAL_LIST_FILE = 'restaurant_list.txt'

# 1-2. 리뷰 CSV 파일이 저장된 폴더
# '다이닝마-detailed-reviews.csv'와 같은 파일들이 모여있는 폴더 경로를 지정하세요.
# 예: 'C:/Users/YourName/Documents/reviews' 또는 './collected_reviews'
REVIEWS_DIRECTORY = './'  # <--- !!! 이 경로를 꼭 수정해주세요 !!!

# 1-3. 리뷰 CSV 파일 내의 가게 이름 컬럼
# 업로드해주신 '다이닝마-detailed-reviews.csv' 파일을 기준으로 'place_name'으로 설정했습니다.
# 만약 컬럼 이름이 다르다면 이 값을 수정하세요.
RESTAURANT_NAME_COLUMN = 'place_name'

# 1-4. 리뷰 CSV 파일을 찾는 패턴
# 폴더 내의 모든 .csv 파일을 찾습니다.
REVIEW_FILE_PATTERN = '*.csv'

# --- 2. 스크립트 본체: 이 아래는 수정할 필요 없습니다. ---

def read_original_list(filepath):
    """원본 .txt 파일에서 가게 이름 목록을 읽어 Set으로 반환합니다."""
    print(f"'{filepath}' 파일에서 원본 가게 목록을 읽는 중...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # 공백/줄바꿈 제거 후 비어있지 않은 이름만 추가
            names = set(line.strip() for line in f if line.strip())
        print(f"✅ 원본 목록 로드 완료. 총 {len(names)}개의 고유한 가게 이름을 찾았습니다.")
        return names
    except FileNotFoundError:
        print(f"❌ 오류: 원본 파일 '{filepath}'를 찾을 수 없습니다.")
        print("ORIGINAL_LIST_FILE 변수의 경로를 확인하세요.")
        return None
    except Exception as e:
        print(f"❌ '{filepath}' 파일 읽기 중 오류 발생: {e}")
        return None

def find_scraped_names(directory, pattern, column_name):
    """지정된 디렉토리에서 CSV 파일들을 읽어 가게 이름 Set을 반환합니다."""
    scraped_names_set = set()
    
    # 디렉토리와 패턴을 결합하여 파일 경로 목록을 찾습니다.
    search_path = os.path.join(directory, pattern)
    csv_files = glob.glob(search_path)
    
    if not csv_files:
        print(f"❌ 경고: '{search_path}' 경로에서 '{pattern}' 패턴과 일치하는 CSV 파일을 찾을 수 없습니다.")
        print("REVIEWS_DIRECTORY 경로와 REVIEW_FILE_PATTERN을 확인하세요.")
        return scraped_names_set

    print(f"총 {len(csv_files)}개의 CSV 파일에서 리뷰 추출 현황을 확인합니다...")
    
    for i, csv_file in enumerate(csv_files):
        # 업로드된 파일 이름('다이닝마-detailed-reviews.csv')은 무시합니다.
        if os.path.basename(csv_file) == '다이닝마-detailed-reviews.csv' and len(csv_files) > 1:
            continue

        try:
            # CSV 파일 읽기 (인코딩 자동 감지 시도)
            try:
                df = pd.read_csv(csv_file, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(csv_file, encoding='cp949')
            
            # 가게 이름 컬럼 확인
            if column_name in df.columns:
                # 해당 컬럼에서 고유한 가게 이름 추출 (NaN 값 제외)
                names_in_file = set(df[column_name].dropna().astype(str).unique())
                if names_in_file:
                    scraped_names_set.update(names_in_file)
                # else:
                #     print(f"  ℹ️ '{csv_file}' 파일은 비어있거나 '{column_name}'에 유효한 값이 없습니다.")
            
            # else:
            #     print(f"  ⚠️ 경고: '{csv_file}' 파일에 '{column_name}' 컬럼이 없습니다.")

        except pd.errors.EmptyDataError:
            print(f"  ℹ️ '{csv_file}' 파일이 비어있습니다. (리뷰 0개)")
        except Exception as e:
            print(f"  ❌ '{csv_file}' 파일 처리 중 오류 발생: {e}")
            
        if (i + 1) % 100 == 0 or (i + 1) == len(csv_files):
            print(f"  ... {i + 1}/{len(csv_files)} 파일 처리 완료.")

    print(f"✅ CSV 파일 분석 완료. 총 {len(scraped_names_set)}개의 고유한 가게 이름을 찾았습니다.")
    return scraped_names_set

def main():
    """메인 실행 함수"""
    print("--- 리뷰 누락 가게 확인 스크립트 시작 ---")
    
    # 1. 원본 목록 읽기
    original_names = read_original_list(ORIGINAL_LIST_FILE)
    
    if original_names is None:
        print("스크립트를 종료합니다.")
        return

    # 2. 스크랩된 목록 읽기
    scraped_names = find_scraped_names(REVIEWS_DIRECTORY, REVIEW_FILE_PATTERN, RESTAURANT_NAME_COLUMN)
    
    if not scraped_names:
        print(f"❌ '{REVIEWS_DIRECTORY}'에서 스크랩된 가게 이름을 찾을 수 없습니다. 스크립트를 종료합니다.")
        return

    print("\n--- 📊 상세 비교 시작 (이름 불일치 확인 중...) ---")
    print(f"(원본 {len(original_names)}개 vs 스크랩 {len(scraped_names)}개 비교. 잠시만 기다려주세요...)")
    
    exact_matches = set()
    partial_matches = {} # Dict to store {original_name: [list_of_partial_matches]}
    truly_missing = set()

    # Set은 'in' 연산 (정확한 일치)에 매우 빠릅니다.
    # List는 'contains' 연산 (부분 일치)을 위해 필요합니다.
    scraped_names_list = list(scraped_names) 

    for i, name in enumerate(original_names):
        # 500개마다 진행 상황 출력
        if (i + 1) % 500 == 0 or (i + 1) == len(original_names):
            print(f"  ... {i+1}/{len(original_names)} 원본 목록 비교 완료.")

        # 1. 정확한 일치 확인 (가장 빠름)
        if name in scraped_names:
            exact_matches.add(name)
        else:
            # 2. 부분 일치 확인 (스크랩된 이름이 원본 이름을 포함하는지)
            # 예: 원본="ABC", 스크랩="ABC (본점)" -> "ABC (본점)" in "ABC" (X)
            #     "ABC" in "ABC (본점)" (O)
            found_partials = []
            # 이 부분은 느릴 수 있습니다. (O(N*M))
            for scraped_name in scraped_names_list: 
                if name in scraped_name: # 원본 이름이 스크랩된 이름에 포함되는가?
                    found_partials.append(scraped_name)
            
            if found_partials:
                partial_matches[name] = found_partials
            else:
                # 3. 그래도 없으면 완전 누락
                truly_missing.add(name)

    
    # --- 4. 결과 출력 ---
    print("\n" + "="*30)
    print("--- 📊 최종 비교 결과 ---")
    print(f"✅ 1. 정확히 일치: {len(exact_matches)}개")
    print(f"⚠️ 2. 부분 일치 (이름은 다르지만 스크랩 추정): {len(partial_matches)}개")
    print(f"🚨 3. 완전 누락 (스크랩 실패 추정): {len(truly_missing)}개")
    print("="*30)
    print(f"(참고: 원본 목록 총 {len(original_names)}개 ≈ {len(exact_matches)} + {len(partial_matches)} + {len(truly_missing)})")

    # 완전 누락 목록 저장
    if truly_missing:
        print(f"\n--- 🚨 {len(truly_missing)}개의 '완전 누락' 목록 ---")
        sorted_missing = sorted(list(truly_missing))
        
        # 처음 20개만 터미널에 출력
        for j, name in enumerate(sorted_missing):
            if j >= 20:
                print(f"  ... 외 {len(sorted_missing) - 20}개")
                break
            print(f"  - {name}")
        
        missing_filename = 'missing_restaurants.txt'
        try:
            with open(missing_filename, 'w', encoding='utf-8') as f:
                f.write(f"--- 총 {len(sorted_missing)}개의 완전 누락 목록 ---\n")
                f.write("\n".join(sorted_missing))
            print(f"\n✅ '{missing_filename}' 파일에 '완전 누락' 목록 전체를 저장했습니다.")
        except Exception as e:
            print(f"\n❌ 누락 목록 저장 중 오류: {e}")
    else:
        print("\n🎉 '완전 누락'된 가게가 없습니다!")

    # 부분 일치 목록 저장
    if partial_matches:
        print(f"\n--- ⚠️ {len(partial_matches)}개의 '부분 일치' 상세 (최대 20개) ---")
        print("(원본 이름 -> [CSV에서 찾은 이름])")
        count = 0
        sorted_partials = sorted(partial_matches.items())
        
        for original, found_list in sorted_partials:
            if count >= 20:
                print(f"  ... 외 {len(partial_matches) - 20}개")
                break
            print(f"  - {original} -> {found_list}")
            count += 1
        
        partial_filename = 'partial_match_details.txt'
        try:
            with open(partial_filename, 'w', encoding='utf-8') as f:
                f.write(f"--- 총 {len(partial_matches)}개의 부분 일치 상세 내역 ---\n")
                f.write("(원본 이름 -> [CSV에서 찾은 이름])\n")
                f.write("="*30 + "\n")
                for original, found_list in sorted_partials:
                    f.write(f"{original} -> {str(found_list)}\n")
            print(f"\n✅ '{partial_filename}' 파일에 '부분 일치' 상세 내역 전체를 저장했습니다.")
        except Exception as e:
            print(f"\n❌ 부분 일치 파일 저장 중 오류: {e}")

    print("\n--- 스크립트 종료 ---")

if __name__ == "__main__":
    main()

