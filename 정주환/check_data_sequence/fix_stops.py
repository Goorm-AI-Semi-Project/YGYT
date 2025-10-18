import pandas as pd
import os

# --- 설정 ---
INPUT_FILE = '202303_GTFS_DataSet/stop_times.txt'      # 원본 GTFS 파일 이름
OUTPUT_FILE = '202303_GTFS_DataSet/stop_times_fixed.txt' # 새로 저장할 파일 이름
CHUNK_SIZE = 500000                # 한 번에 처리할 줄 수 (메모리에 맞게 조절)
# -----------

# 처리된 헤더(첫 번째 줄)를 저장했는지 확인하기 위한 플래그
header_saved = False

# 임시 출력 파일이 있다면 삭제 (이전 실행 찌꺼기 제거)
if os.path.exists(OUTPUT_FILE):
    os.remove(OUTPUT_FILE)

print(f"'{INPUT_FILE}' 파일 처리를 시작합니다. 잠시 기다려주세요...")

try:
    # 파일을 CHUNK_SIZE만큼 나눠서 읽어옵니다. (메모리 절약)
    # low_memory=False로 설정하여 DtypeWarning을 방지합니다.
    for chunk_df in pd.read_csv(INPUT_FILE, chunksize=CHUNK_SIZE, low_memory=False):

        # 'stop_sequence' 열이 있는지 확인
        if 'stop_sequence' not in chunk_df.columns:
            print(f"오류: '{INPUT_FILE}' 파일에 'stop_sequence' 열이 없습니다.")
            break
        
        # --- 핵심 로직 ---
        # 1. pd.to_numeric: 'stop_sequence' 열을 숫자로 변환합니다.
        #    '123.0' 같은 소수점은 숫자로, 'NA'나 'abc' 같은 문자열은 NaN(빈 값)으로 바꿉니다.
        # 2. .fillna(0): 변환에 실패한 NaN(빈 값)들을 0으로 채웁니다.
        # 3. .astype(int): 모든 값을 정수(integer)로 변환합니다. (예: 123.0 -> 123)
        chunk_df['stop_sequence'] = pd.to_numeric(
            chunk_df['stop_sequence'], errors='coerce'
        ).fillna(0).astype(int)
        
        # --- 파일 저장 ---
        if not header_saved:
            # 첫 번째 청크(chunk)는 헤더(열 이름)와 함께 저장
            chunk_df.to_csv(OUTPUT_FILE, index=False, mode='w', header=True)
            header_saved = True
        else:
            # 두 번째부터는 헤더 없이 데이터만 추가
            chunk_df.to_csv(OUTPUT_FILE, index=False, mode='a', header=False)

    print(f"\n✨ 작업 완료! '{OUTPUT_FILE}' 파일이 생성되었습니다.")
    print("이 파일로 다시 OTP 빌드를 시도해 보세요.")

except FileNotFoundError:
    print(f"오류: '{INPUT_FILE}' 파일을 찾을 수 없습니다. 파일 이름을 확인해 주세요.")
except Exception as e:
    print(f"처리 중 예기치 않은 오류가 발생했습니다: {e}")