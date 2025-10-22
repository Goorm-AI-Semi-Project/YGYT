import pandas as pd
import zipfile
import io

# --- 설정 ---
GTFS_ZIP_PATH = '202303_GTFS_DataSet.zip'

def find_orphan_trips(gtfs_zip_path):
    """
    trips.txt의 route_id가 routes.txt에 존재하는지 검사하여
    '고아'가 된 trip(유령 분반)이 몇 개인지 확인합니다.
    """
    print(f"'{gtfs_zip_path}' 파일에서 데이터 로딩을 시작합니다...")

    try:
        with zipfile.ZipFile(gtfs_zip_path, 'r') as zf:
            # routes.txt에서 모든 route_id를 집합(set)으로 로딩 (검색 속도가 빠름)
            with zf.open('routes.txt') as f:
                routes_df = pd.read_csv(io.TextIOWrapper(f, 'utf-8-sig'), usecols=['route_id'])
                valid_route_ids = set(routes_df['route_id'])
            
            # trips.txt 로딩
            with zf.open('trips.txt') as f:
                trips_df = pd.read_csv(io.TextIOWrapper(f, 'utf-8-sig'), usecols=['trip_id', 'route_id'])
        
        print("파일 로딩 완료. 데이터 교차 검증을 시작합니다...")

        # isin() 함수로 trips_df의 route_id가 valid_route_ids 집합에 포함되는지 확인
        orphan_trips_df = trips_df[~trips_df['route_id'].isin(valid_route_ids)]

        total_trips = len(trips_df)
        orphan_count = len(orphan_trips_df)
        valid_count = total_trips - orphan_count

        # 결과 출력
        print("\n" + "="*60)
        print("🔬 `trips.txt`와 `routes.txt` 연결 관계 검증 결과")
        print("="*60)
        print(f"총 운행(Trip) 수: {total_trips:,} 개")
        print(f"✅ `routes.txt`에 정상적으로 연결된 운행 수: {valid_count:,} 개")
        print(f"❌ `routes.txt`에 없는 유령 노선에 연결된 운행 수: {orphan_count:,} 개")
        print("-"*60)
        
        if orphan_count > 0:
             print("\n🚨 분석 결과: 존재하지 않는 노선(route)에 연결된 운행(trip)이 대량 발견되었습니다.")
             print("이것이 OTP가 데이터를 폐기하는 최종 원인입니다.")
             print("\n유령 노선에 연결된 trip 샘플 (상위 5개):")
             print(orphan_trips_df.head().to_string())
        else:
            print("\n✅ 모든 운행이 정상적인 노선에 연결되어 있습니다.")


    except FileNotFoundError:
        print(f"오류: '{gtfs_zip_path}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"분석 중 오류 발생: {e}")

# --- 스크립트 실행 ---
if __name__ == "__main__":
    find_orphan_trips(GTFS_ZIP_PATH)