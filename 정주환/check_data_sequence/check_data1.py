import pandas as pd
import zipfile
import io
import os

def validate_gtfs(gtfs_path):
    required_files = [
        "agency.txt",
        "stops.txt",
        "routes.txt",
        "trips.txt",
        "stop_times.txt",
        "calendar.txt"
    ]

    print("🔍 GTFS 파일 검증 시작:", gtfs_path)
    if not os.path.exists(gtfs_path):
        print("❌ GTFS 파일이 존재하지 않습니다.")
        return

    # ZIP 파일 열기
    with zipfile.ZipFile(gtfs_path, 'r') as z:
        gtfs_files = z.namelist()
        print(f"📁 포함된 파일: {gtfs_files}\n")

        # 필수 파일 존재 여부
        for f in required_files:
            if f not in gtfs_files:
                print(f"❌ 누락된 파일: {f}")
            else:
                print(f"✅ 포함된 파일: {f}")

        # 주요 파일 내용 검증
        for f in required_files:
            if f in gtfs_files:
                df = pd.read_csv(io.BytesIO(z.read(f)))
                if df.empty:
                    print(f"⚠️ {f}: 비어 있습니다.")
                else:
                    print(f"📄 {f}: {len(df)}행 {len(df.columns)}열 로드 완료")

        # 참조 관계 기본 검증
        try:
            stops = pd.read_csv(z.open('stops.txt'))
            routes = pd.read_csv(z.open('routes.txt'))
            trips = pd.read_csv(z.open('trips.txt'))
            stop_times = pd.read_csv(z.open('stop_times.txt'))
            calendar = pd.read_csv(z.open('calendar.txt'))

            # stops와 stop_times 연결 확인
            invalid_stops = set(stop_times['stop_id']) - set(stops['stop_id'])
            if invalid_stops:
                print(f"⚠️ stop_times.txt에 존재하지만 stops.txt에 없는 stop_id: {list(invalid_stops)[:5]}")

            # routes와 trips 연결 확인
            invalid_routes = set(trips['route_id']) - set(routes['route_id'])
            if invalid_routes:
                print(f"⚠️ trips.txt에 존재하지만 routes.txt에 없는 route_id: {list(invalid_routes)[:5]}")

            # calendar와 trips 연결 확인
            invalid_service = set(trips['service_id']) - set(calendar['service_id'])
            if invalid_service:
                print(f"⚠️ trips.txt에 존재하지만 calendar.txt에 없는 service_id: {list(invalid_service)[:5]}")

            print("\n✅ 기본 참조 무결성 검증 완료")

        except Exception as e:
            print("❌ 검증 중 오류 발생:", e)

# 실행 예시
if __name__ == "__main__":
    # GTFS ZIP 경로 수정
    validate_gtfs("./otp_server/202303_GTFS_DataSet.zip")
