import pandas as pd
import zipfile
import io
from datetime import datetime

# --- 설정 ---
GTFS_ZIP_PATH = '202303_GTFS_DataSet.zip'
CHECK_DATE = datetime.now().strftime('%Y%m%d') # 오늘 날짜를 YYYYMMDD 형식으로

def final_validation(gtfs_zip_path, check_date_str):
    """
    GTFS 데이터의 모든 파일을 교차 검증하여, 특정 날짜에
    유효한 trip이 몇 개인지 확인합니다.
    """
    print(f"'{gtfs_zip_path}' 파일에서 데이터 로딩을 시작합니다...")

    try:
        with zipfile.ZipFile(gtfs_zip_path, 'r') as zf:
            # trips.txt 로딩
            with zf.open('trips.txt') as f:
                trips_df = pd.read_csv(io.TextIOWrapper(f, 'utf-8-sig'), usecols=['trip_id', 'service_id'])
            
            # calendar.txt 로딩
            with zf.open('calendar.txt') as f:
                calendar_df = pd.read_csv(io.TextIOWrapper(f, 'utf-8-sig'))

            # calendar_dates.txt 로딩 (없을 수도 있음)
            calendar_dates_df = None
            if 'calendar_dates.txt' in zf.namelist():
                with zf.open('calendar_dates.txt') as f:
                    calendar_dates_df = pd.read_csv(io.TextIOWrapper(f, 'utf-8-sig'))

        print("파일 로딩 완료. 데이터 분석을 시작합니다...")
        
        # 날짜 형식 통일 (YYYYMMDD)
        check_date = int(check_date_str)
        day_of_week = datetime.strptime(check_date_str, '%Y%m%d').strftime('%A').lower()

        # 1. calendar.txt 기준으로 유효한 service_id 찾기
        valid_calendar_services = calendar_df[
            (calendar_df['start_date'] <= check_date) &
            (calendar_df['end_date'] >= check_date) &
            (calendar_df[day_of_week] == 1)
        ]['service_id']

        # 2. calendar_dates.txt 기준으로 유효한 service_id 찾기
        valid_date_services = set()
        excluded_date_services = set()
        if calendar_dates_df is not None:
            # 운행 날짜로 추가된 서비스
            added_services = calendar_dates_df[
                (calendar_dates_df['date'] == check_date) &
                (calendar_dates_df['exception_type'] == 1)
            ]['service_id']
            valid_date_services.update(added_services)

            # 운행 예외(휴무)로 지정된 서비스
            excluded_services = calendar_dates_df[
                (calendar_dates_df['date'] == check_date) &
                (calendar_dates_df['exception_type'] == 2)
            ]['service_id']
            excluded_date_services.update(excluded_services)

        # 3. 모든 유효한 service_id 집합 생성
        valid_service_ids = set(valid_calendar_services)
        valid_service_ids.update(valid_date_services)
        valid_service_ids.difference_update(excluded_date_services)
        
        # 4. 전체 trip과 유효한 service_id 비교
        total_trips = len(trips_df)
        valid_trips_df = trips_df[trips_df['service_id'].isin(valid_service_ids)]
        valid_trips_count = len(valid_trips_df)
        invalid_trips_count = total_trips - valid_trips_count

        # 결과 출력
        print("\n" + "="*60)
        print(f"🗓️  검증 기준 날짜: {check_date_str} ({day_of_week.capitalize()})")
        print("="*60)
        print(f"총 노선(Trip) 수: {total_trips:,} 개")
        print(f"✅ 오늘 운행하는 유효 노선 수: {valid_trips_count:,} 개")
        print(f"❌ 오늘 운행하지 않는 만료/휴무 노선 수: {invalid_trips_count:,} 개")
        print("-"*60)
        
        if invalid_trips_count > total_trips * 0.9:
             print("\n🚨 분석 결과: 전체 노선의 대부분이 오늘 날짜에 유효하지 않습니다.")
             print("이것이 OTP가 'TripDegenerate' 오류를 대량으로 보고하고,")
             print("대중교통 경로를 생성하지 못하는 최종 원인입니다.")
        else:
            print("\n✅ 데이터가 정상입니다.")


    except FileNotFoundError:
        print(f"오류: '{gtfs_zip_path}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"분석 중 오류 발생: {e}")

# --- 스크립트 실행 ---
if __name__ == "__main__":
    final_validation(GTFS_ZIP_PATH, CHECK_DATE)