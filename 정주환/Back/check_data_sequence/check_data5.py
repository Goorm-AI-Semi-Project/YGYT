import zipfile
import io
import csv
import codecs

# --- 설정 ---
GTFS_ZIP_PATH = '202303_GTFS_DataSet.zip'

def inspect_file_format(file_name, byte_content):
    """파일의 바이트 내용을 분석하여 포맷 문제를 진단합니다."""
    print(f"--- 파일: {file_name} 검사 시작 ---")
    
    # 1. 인코딩 및 BOM(Byte Order Mark) 검사
    try:
        # UTF-8 BOM은 파일 시작 부분에 b'\xef\xbb\xbf' 시그니처를 가집니다.
        if byte_content.startswith(codecs.BOM_UTF8):
            print("  [🚨] 인코딩: UTF-8-BOM 발견! (Java 호환성 문제의 주된 원인일 수 있습니다)")
        else:
            # BOM이 없으면 일단 UTF-8로 디코딩 시도
            byte_content.decode('utf-8')
            print("  [✅] 인코딩: UTF-8 (정상)")
    except UnicodeDecodeError:
        print("  [🚨] 인코딩: UTF-8이 아님! 심각한 문제입니다.")
        return # 더 이상 검사 의미 없음

    # 2. 줄바꿈(Line Ending) 문자 검사
    crlf_count = byte_content.count(b'\r\n')
    lf_count = byte_content.count(b'\n') - crlf_count # 순수 LF 개수만 계산

    if crlf_count > 0 and lf_count > 0:
        print(f"  [🚨] 줄바꿈: CRLF({crlf_count}개)와 LF({lf_count}개)가 혼용되어 있습니다.")
    elif crlf_count > 0:
        print(f"  [✅] 줄바꿈: CRLF (Windows/표준, 정상)")
    elif lf_count > 0:
        print(f"  [⚠️]  줄바꿈: LF (Unix/Linux, 일부 Java 파서에서 문제를 일으킬 수 있습니다)")
    else:
        print("  [?] 줄바꿈: 줄바꿈 문자를 찾을 수 없습니다.")

    # 3. CSV 구조(구분자 일관성) 검사
    try:
        # 바이트를 문자열로 변환하여 csv 리더로 분석
        text_stream = io.StringIO(byte_content.decode('utf-8-sig')) # BOM이 있다면 제거하고 읽음
        reader = csv.reader(text_stream)
        
        header = next(reader)
        header_col_count = len(header)
        
        inconsistent_lines = []
        for i, row in enumerate(reader, 2): # 2번째 줄부터 시작
            if len(row) != header_col_count:
                inconsistent_lines.append(i)
        
        if not inconsistent_lines:
            print(f"  [✅] CSV 구조: 모든 행의 컬럼 수가 헤더({header_col_count}개)와 일치합니다 (정상).")
        else:
            print(f"  [🚨] CSV 구조: 총 {len(inconsistent_lines)}개 행의 컬럼 수가 다릅니다!")
            print(f"     -> 예시: {inconsistent_lines[:5]} 번째 줄 등...")

    except (csv.Error, StopIteration) as e:
        print(f"  [🚨] CSV 구조: 파일을 분석하는 중 심각한 오류 발생. ({e})")
    
    print("-" * (len(file_name) + 14))


def inspect_gtfs_zip(gtfs_zip_path):
    """GTFS 압축 파일 내의 모든 .txt 파일 포맷을 검사합니다."""
    print(f"'{gtfs_zip_path}' 파일 분석을 시작합니다...\n")
    try:
        with zipfile.ZipFile(gtfs_zip_path, 'r') as zf:
            txt_files = [name for name in zf.namelist() if name.endswith('.txt')]
            for file_name in txt_files:
                with zf.open(file_name) as f:
                    # 파일 내용을 바이트 그대로 읽어야 정확한 진단 가능
                    content_bytes = f.read()
                    inspect_file_format(file_name, content_bytes)
    except FileNotFoundError:
        print(f"오류: '{gtfs_zip_path}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"분석 중 오류 발생: {e}")

# --- 스크립트 실행 ---
if __name__ == "__main__":
    inspect_gtfs_zip(GTFS_ZIP_PATH)