import pandas as pd

# 1. 파일 및 컬럼 설정
input_csv_path = '20251016_서울시_음식점_목록_GPS.csv'  # 실제 파일 경로로 수정하세요.
output_txt_path = 'restaurant_list.txt'       # 저장될 텍스트 파일 이름
column_name = '가게'                            # 추출할 가게 이름 컬럼 (C열)

try:
    # 2. CSV 파일 읽기 (인코딩 자동 감지 시도)
    try:
        df = pd.read_csv(input_csv_path, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(input_csv_path, encoding='cp949') # 윈도우 환경에서 저장한 경우

    # 3. '상호' 컬럼이 있는지 확인
    if column_name in df.columns:
        # 4. '상호' 컬럼의 모든 값을 리스트로 추출
        store_names = df[column_name].dropna().astype(str).tolist() # 빈 값(NaN) 제거 및 문자열 변환

        # 5. 줄바꿈(Newline-separated) 형식으로 텍스트 파일 저장
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(store_names))

        print(f"✅ 완료! '{output_txt_path}' 파일에 총 {len(store_names)}개의 가게 이름이 저장되었습니다.")
        print("이 파일의 내용을 복사해서 스크래핑 도구에 붙여넣으세요.")

    else:
        print(f"❌ 오류: CSV 파일에서 '{column_name}' 컬럼을 찾을 수 없습니다.")
        print(f"사용 가능한 컬럼 목록: {df.columns.tolist()}")

except FileNotFoundError:
    print(f"❌ 오류: '{input_csv_path}' 파일을 찾을 수 없습니다. 파일 이름이나 경로를 확인하세요.")
except Exception as e:
    print(f"❌ 알 수 없는 오류가 발생했습니다: {e}")