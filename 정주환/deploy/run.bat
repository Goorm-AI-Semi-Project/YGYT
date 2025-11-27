@echo off
REM GraphHopper 서버 실행 스크립트
REM 사용법: run.bat

echo Starting GraphHopper Server...
java -Xmx24g -jar graphhopper-web-12.0-SNAPSHOT.jar server config/config-pt.yml
