#!/bin/bash
# 한입 파이썬 대시보드 켜기 — 이 파일을 더블클릭하면 서버가 켜지고 브라우저가 열립니다.
# 끄려면 이 터미널 창에서 Ctrl + C 를 누르거나 창을 닫으세요.

cd "$(dirname "$0")"

echo "▶ 한입 파이썬 대시보드 준비 중..."

# 필요한 라이브러리 확인 (없으면 설치)
if ! python3 -c "import fastapi, uvicorn, fitz" 2>/dev/null; then
  echo "▶ 처음 실행이라 필요한 라이브러리를 설치합니다 (1~2분 걸릴 수 있어요)..."
  pip3 install --user fastapi "uvicorn[standard]" pymupdf python-multipart
fi

# 3초 뒤 브라우저 자동으로 열기
( sleep 3; open "http://127.0.0.1:8000" ) &

echo "▶ 서버 시작! 잠시 후 브라우저가 자동으로 열립니다."
echo "  (안 열리면 브라우저에서 http://127.0.0.1:8000 직접 입력)"
echo "  끄려면 이 창에서 Ctrl + C"
echo ""

python3 -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
