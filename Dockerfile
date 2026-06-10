# 강의 숏폼 스튜디오 — 뷰어 전용 배포 이미지 (Render 등)
# 미리 만든 강의 코스 감상 + PDF 추출만. 영상 생성은 비활성(VIEWER_ONLY=1).
FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 설치(레이어 캐시)
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

# 앱 복사 (미리 렌더된 영상 output/ 포함)
COPY . .

ENV VIEWER_ONLY=1
EXPOSE 8000

# Render가 주는 $PORT에 바인딩 (없으면 8000)
CMD ["sh", "-c", "uvicorn backend.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
