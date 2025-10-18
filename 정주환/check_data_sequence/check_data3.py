import pandas as pd
import zipfile
import io

# --- 설정 ---
GTFS_ZIP_PATH = '202303_GTFS_DataSet.zip'
STOP_TIMES_FILENAME = 'stop_times.txt'

def find_degenerate_trips(gtfs_zip_path):
    """
    GTFS zip 파일 내의 stop_times.txt를 읽어
    정류장이 하나뿐인 'Degenerate Trip' 오류를 찾습니다.
    """
    print(f"'{gtfs_zip_path}' 파일에서 '{STOP_TIMES_FILENAME}' 파일을 읽는 중입니다...")

    try:
        with zipfile.ZipFile(gtfs_zip_path, 'r') as zf:
            if STOP_TIMES_FILENAME not in zf.namelist():
                print(f"오류: Zip 파일 안에 '{STOP_TIMES_FILENAME}'이 없습니다.")
                return
            
            with zf.open(STOP_TIMES_FILENAME) as f:
                # trip_id 열만 읽어서 메모리를 절약합니다.
                df = pd.read_csv(io.TextIOWrapper(f, 'utf-8-sig'), usecols=['trip_id'])
                print("파일 로딩 완료. 데이터 분석을 시작합니다...")

    except FileNotFoundError:
        print(f"오류: '{gtfs_zip_path}' 파일을 찾을 수 없습니다.")
        return
    except Exception as e:
        print(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        return

    print("각 trip_id별 정류장 개수를 계산 중입니다...")
    # value_counts()는 각 trip_id가 몇 번 등장하는지 계산합니다.
    trip_counts = df['trip_id'].value_counts()

    # 정류장 개수가 1개인 트립만 필터링합니다.
    degenerate_trips = trip_counts[trip_counts == 1]

    # 결과 출력
    if not degenerate_trips.empty:
        print("\n" + "="*50)
        print(f"🚨 총 {len(degenerate_trips)}건의 'Degenerate Trip' (정류장 1개) 오류를 발견했습니다!")
        print("="*50)
        print("오류가 발생한 trip_id 샘플 (상위 10개):\n")
        print(degenerate_trips.head(10).to_string())
        print("\n\n분석 완료: 데이터에 경로 계획에 사용할 수 없는 '미완성 노선'이 대량 포함되어 있습니다.")
        print("이것이 OTP가 대중교통 경로를 생성하지 못하는 진짜 원인입니다.")
    else:
        print("\n✅ 'Degenerate Trip' 오류가 발견되지 않았습니다.")

# --- 스크립트 실행 ---
if __name__ == "__main__":
    find_degenerate_trips(GTFS_ZIP_PATH)