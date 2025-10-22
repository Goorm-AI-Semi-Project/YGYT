import pandas as pd
import zipfile
import io

# --- 설정 ---
# 사용 중인 GTFS 압축 파일의 이름을 정확하게 입력해주세요.
GTFS_ZIP_PATH = '202303_GTFS_DataSet.zip'
STOP_TIMES_FILENAME = 'stop_times.txt'

def convert_gtfs_time_to_seconds(time_str):
    """GTFS 시간('HH:MM:SS')을 초 단위로 변환합니다. (예: '25:10:00' -> 90600)"""
    try:
        parts = time_str.split(':')
        seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return seconds
    except (ValueError, IndexError):
        # 시간 형식이 잘못된 경우 None을 반환하여 오류 처리
        return None

def find_negative_hop_times(gtfs_zip_path):
    """
    GTFS zip 파일 내의 stop_times.txt를 읽어 NegativeHopTime 오류를 찾습니다.
    """
    print(f"'{gtfs_zip_path}' 파일에서 '{STOP_TIMES_FILENAME}' 파일을 읽는 중입니다...")

    try:
        with zipfile.ZipFile(gtfs_zip_path, 'r') as zf:
            if STOP_TIMES_FILENAME not in zf.namelist():
                print(f"오류: Zip 파일 안에 '{STOP_TIMES_FILENAME}'이 없습니다.")
                return

            # 압축 파일에서 직접 데이터를 읽어 메모리에 로드
            with zf.open(STOP_TIMES_FILENAME) as f:
                # UTF-8-sig는 파일 시작 부분의 BOM(Byte Order Mark)을 처리합니다.
                # low_memory=False는 대용량 파일의 열 타입을 한번에 추론하여 메모리를 절약합니다.
                df = pd.read_csv(io.TextIOWrapper(f, 'utf-8-sig'), low_memory=False)
                print("파일 로딩 완료. 데이터 분석을 시작합니다...")

    except FileNotFoundError:
        print(f"오류: '{gtfs_zip_path}' 파일을 찾을 수 없습니다. 파일 이름과 위치를 확인해주세요.")
        return
    except Exception as e:
        print(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        return

    # 1. 필요한 열만 선택하고 stop_sequence를 숫자로 변환
    df = df[['trip_id', 'arrival_time', 'departure_time', 'stop_sequence']]
    df['stop_sequence'] = pd.to_numeric(df['stop_sequence'], errors='coerce')

    # 2. 시간을 초 단위로 변환
    print("시간 데이터를 초 단위로 변환 중입니다...")
    df['arrival_seconds'] = df['arrival_time'].apply(convert_gtfs_time_to_seconds)
    df['departure_seconds'] = df['departure_time'].apply(convert_gtfs_time_to_seconds)
    
    # 변환 실패한 데이터 제거
    df.dropna(subset=['stop_sequence', 'arrival_seconds', 'departure_seconds'], inplace=True)
    
    # 3. trip_id와 stop_sequence 순서로 정렬
    print("데이터 정렬 중...")
    df.sort_values(['trip_id', 'stop_sequence'], inplace=True)

    # 4. 이전 정류장의 출발 시간을 다음 행에 추가
    # shift()는 데이터를 한 칸씩 밀어주는 함수입니다.
    df['prev_departure_seconds'] = df.groupby('trip_id')['departure_seconds'].shift(1)
    df['prev_trip_id'] = df.groupby('trip_id')['trip_id'].shift(1)
    
    # 5. 오류 검사
    print("NegativeHopTime 오류를 검사합니다...")
    # 조건:
    # - trip_id가 이전 행과 동일해야 함 (같은 운행 내에서 비교)
    # - 현재 정류장 도착 시간이 이전 정류장 출발 시간보다 작아야 함
    error_df = df[
        (df['trip_id'] == df['prev_trip_id']) &
        (df['arrival_seconds'] < df['prev_departure_seconds'])
    ].copy()

    # 결과 출력
    if not error_df.empty:
        print("\n" + "="*50)
        print(f"🚨 총 {len(error_df)}건의 'NegativeHopTime' 오류를 발견했습니다!")
        print("="*50)
        print("오류가 발생한 데이터 샘플 (상위 10개):\n")
        
        # 이전 정류장 정보도 함께 보기 위해 원본 데이터에서 인덱스로 조회
        original_indices = error_df.index
        # 오류가 발생한 행과 그 바로 이전 행을 함께 출력
        sample_indices = sorted(list(set(original_indices) | set(original_indices - 1)))
        
        print(df.loc[sample_indices].head(20).to_string())
        print("\n\n분석 완료: stop_times.txt 파일에 심각한 시간 오류가 포함되어 있습니다.")

    else:
        print("\n✅ 'NegativeHopTime' 오류가 발견되지 않았습니다. 데이터가 정상입니다.")

# --- 스크립트 실행 ---
if __name__ == "__main__":
    find_negative_hop_times(GTFS_ZIP_PATH)