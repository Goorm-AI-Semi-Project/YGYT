#!/bin/bash

# --- 스크립트 실행 중 오류가 발생하면 즉시 중단 ---
set -e

echo "스크립트 실행을 시작합니다..."

# 1. 특정 버전의 sentence-transformers 설치
echo "Installing sentence-transformers==5.1.2..."
pip install sentence-transformers==5.1.2

# 2. 기타 필수 패키지 설치
echo "Installing other dependencies (uvicorn, fastapi, gradio, etc.)..."
pip install uvicorn fastapi gradio openai dotenv chromadb hf_transfer

# 3. OpenAI API 키 환경 변수로 설정
echo "Setting OPENAI_API_KEY..."
export OPENAI_API_KEY='YOUR KEY IN HERE'

# 4. 메인 애플리케이션 실행
echo "Starting the application (app_main.py)..."
python app_main.py

echo "스크립트 실행 완료."