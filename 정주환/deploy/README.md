# GraphHopper 배포 패키지

## 필수 파일 체크리스트

배포 전에 다음 파일들을 `data/` 디렉토리에 복사하세요:

```
deploy/
├── graphhopper-web-12.0-SNAPSHOT.jar    ✓ (이미 복사됨)
├── config/
│   └── config-pt.yml                     ✓ (이미 복사됨)
├── custom_models/
│   └── foot.json                         ✓ (이미 복사됨)
├── data/                                 ⚠️ 아래 파일들을 복사하세요
│   ├── south-korea-251014.osm.pbf
│   └── 202303_GTFS_DataSet.zip
├── graphs/                               (자동 생성됨)
├── run.bat                               ✓ Windows 실행 스크립트
└── run.sh                                ✓ Linux/Mac 실행 스크립트

```

## 데이터 파일 복사 방법

### Windows (PowerShell 또는 CMD)
```bash
copy ..\south-korea-251014.osm.pbf data\
copy ..\202303_GTFS_DataSet.zip data\
```

### Linux/Mac
```bash
cp ../south-korea-251014.osm.pbf data/
cp ../202303_GTFS_DataSet.zip data/
```

## 서버 실행

### Windows
```bash
run.bat
```

### Linux/Mac
```bash
chmod +x run.sh
./run.sh
```

또는 직접 실행:
```bash
java -Xmx24g -jar graphhopper-web-12.0-SNAPSHOT.jar server config/config-pt.yml
```

## 서버 접속

- **API 서버**: http://localhost:8989
- **관리자 페이지**: http://localhost:8990

## 디렉토리 구조 설명

- `graphhopper-web-12.0-SNAPSHOT.jar`: GraphHopper 실행 파일 (47MB)
- `config/config-pt.yml`: 서버 설정 파일
- `custom_models/foot.json`: 보행자 라우팅 모델
- `data/`: OSM 및 GTFS 데이터 파일 (사용자가 복사)
- `graphs/`: 그래프 캐시 (첫 실행 시 자동 생성)

## 메모리 설정

현재 24GB로 설정되어 있습니다. 시스템 사양에 맞게 조정하세요:
- `-Xmx24g`: 최대 힙 메모리 24GB
- `-Xmx16g`: 최대 힙 메모리 16GB (메모리가 적은 경우)
- `-Xmx32g`: 최대 힙 메모리 32GB (메모리가 많은 경우)
