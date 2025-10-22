import pandas as pd
import os

def check_gtfs_quality(gtfs_path='.'):
    """
    GTFS 데이터의 NegativeHopTime과 TripDegenerate 문제를 검사합니다.

    Args:
        gtfs_path (str): GTFS 파일들(stop_times.txt, trips.txt)이 있는 폴더 경로.
    """
    print(f"🔍 GTFS 데이터 품질 검사를 시작합니다. (경로: {gtfs_path})")

    # --- 1. 필요한 파일 로드 ---
    try:
        stop_times_df = pd.read_csv(os.path.join(gtfs_path, 'stop_times.txt'))
        trips_df = pd.read_csv(os.path.join(gtfs_path, 'trips.txt'))
        print("✅ stop_times.txt, trips.txt 파일 로딩 성공!")
    except FileNotFoundError as e:
        print(f"🚨 오류: 필수 파일({e.filename})을 찾을 수 없습니다. 경로를 확인해주세요.")
        return

    # --- 2. TripDegenerate (퇴화된 운행) 검사 ---
    # 각 trip_id 별로 정류장(stop) 수를 계산
    stops_per_trip = stop_times_df.groupby('trip_id').size()
    
    # 정류장 수가 2개 미만인 trip_id (운행이 성립되지 않음)
    degenerate_trips = stops_per_trip[stops_per_trip < 2].index.tolist()
    
    # trips.txt에 있지만 stop_times.txt에 아예 없는 trip_id
    trips_in_trips_file = set(trips_df['trip_id'])
    trips_in_stoptimes_file = set(stop_times_df['trip_id'])
    no_stops_trips = list(trips_in_trips_file - trips_in_stoptimes_file)

    all_degenerate_trips = set(degenerate_trips + no_stops_trips)

    print("\n--- 텅 빈 버스: TripDegenerate 검사 ---")
    if not all_degenerate_trips:
        print("🟢 훌륭합니다! 정류장 수가 부족한 비정상 운행(Trip)이 없습니다.")
    else:
        print(f"🟡 경고: 총 {len(all_degenerate_trips)}개의 비정상 운행(Trip)을 발견했습니다.")
        print("   (원인: 운행에 포함된 정류장이 1개 이하인 경우)")
        if len(all_degenerate_trips) > 5:
            print("   - 일부 예시:", list(all_degenerate_trips)[:5])
        else:
            print("   - 목록:", list(all_degenerate_trips))


    # --- 3. NegativeHopTime (음수 운행 시간) 검사 ---
    print("\n--- 시간 여행자: NegativeHopTime 검사 ---")
    
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # 수정된 부분: to_timedelta가 24시 이상 시간을 잘 처리하므로 로직을 단순화합니다.
    # errors='coerce'는 혹시 모를 비정상적인 시간 포맷이 있어도 에러 없이 NaT(Not a Time)로 처리합니다.
    stop_times_df['arrival_td'] = pd.to_timedelta(stop_times_df['arrival_time'], errors='coerce')
    stop_times_df['departure_td'] = pd.to_timedelta(stop_times_df['departure_time'], errors='coerce')
    # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
    
    # 변환에 실패한 행(NaT)이 있다면 미리 제거
    stop_times_df.dropna(subset=['arrival_td', 'departure_td'], inplace=True)
    
    # trip_id와 stop_sequence로 정렬
    stop_times_df = stop_times_df.sort_values(['trip_id', 'stop_sequence'])
    
    # 각 운행(trip) 내에서 이전 정류장의 출발 시간을 다음 행으로 가져옴
    stop_times_df['prev_departure_td'] = stop_times_df.groupby('trip_id')['departure_td'].shift(1)
    
    # 현재 정류장 도착 시간 < 이전 정류장 출발 시간인 경우를 필터링
    negative_hop_times = stop_times_df[stop_times_df['arrival_td'] < stop_times_df['prev_departure_td']]

    if negative_hop_times.empty:
        print("🟢 훌륭합니다! 도착 시간이 출발 시간보다 빠른 비정상 데이터가 없습니다.")
    else:
        # 문제가 되는 trip_id만 추출
        problematic_trips = negative_hop_times['trip_id'].unique()
        print(f"🔴 문제 발견: 총 {len(problematic_trips)}개 운행(Trip)에서 {len(negative_hop_times)}개의 시간 역전 구간을 발견했습니다.")
        print("   (원인: 다음 정류장 도착 시간이 이전 정류장 출발 시간보다 빠름)")
        
        # 상세 예시 출력
        print("\n--- 상세 문제 데이터 예시 (최대 5개) ---")
        for trip_id in problematic_trips[:5]:
            print(f"\n[운행 ID: {trip_id}]")
            # 문제 구간을 더 명확히 보여주기 위해 이전 정류장 정보도 함께 출력
            problem_indices = negative_hop_times[negative_hop_times['trip_id'] == trip_id].index
            for idx in problem_indices:
                # 현재 행과 이전 행을 함께 보여줌
                print(stop_times_df.loc[idx-1:idx][['stop_sequence', 'arrival_time', 'departure_time']].to_string(index=False))
                print("   ^--- 이 구간에서 시간 역전 발생")

    print("\n✅ 검사가 완료되었습니다.")


# --- 코드 실행 ---
if __name__ == '__main__':
    gtfs_folder_path = '.' 
    check_gtfs_quality(gtfs_folder_path)