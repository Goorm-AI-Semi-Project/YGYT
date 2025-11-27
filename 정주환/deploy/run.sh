#!/bin/bash
# GraphHopper 서버 실행 스크립트
# 사용법: ./run.sh

echo "Starting GraphHopper Server..."
java -Xmx24g -jar graphhopper-web-12.0-SNAPSHOT.jar server config/config-pt.yml
