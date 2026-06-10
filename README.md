# 강의자료 → 숏폼 제작 프로젝트

AI 강의 슬라이드(PDF)를 숏폼(세로 영상)으로 만들기 위한 프로젝트.
지금은 **1단계(PDF → 내용 추출) + 대시보드**까지 구현돼 있다.
파이썬 백엔드가 PDF를 처리하고, 남색/흰색 HTML 대시보드로 결과를 본다.

## 폴더 구조

```
shortform-lecture/
├── backend/
│   ├── extractor.py     # PDF → 슬라이드 텍스트 + 주제 그룹핑 (PyMuPDF)
│   └── server.py        # FastAPI 서버 (업로드 받아 처리, 대시보드 서빙)
├── frontend/
│   └── index.html       # 남색/흰색 대시보드 (KPI, 주제별 슬라이드 뷰)
├── scripts/             # (이후) 음성·자막·영상 단계용
├── input/               # 강의 PDF를 여기 둔다 (lecture.pdf)
├── output/              # (이후) 완성된 영상
├── data/                # 추출 결과 JSON
├── pipeline.py          # 전체 파이프라인 뼈대 (2~6단계 자리 표시)
└── requirements.txt
```

## 실행 방법

```bash
# 1) 가상환경 (파이썬 3.11 권장 — 3.13은 일부 라이브러리 휠이 아직 없음)
conda create -n shortform python=3.11 -y
conda activate shortform

# 2) 설치
pip install -r requirements.txt

# 3) 대시보드 서버 켜기 (프로젝트 루트에서)
uvicorn backend.server:app --reload

# 4) 브라우저에서 접속
#    http://127.0.0.1:8000
#    → PDF를 끌어다 놓으면 슬라이드별 텍스트가 주제별로 정리돼 나온다
```

명령줄에서만 추출하고 싶으면:

```bash
python backend/extractor.py input/lecture.pdf > data/out.json
```

## 다음 단계

대시보드에서 "전체 텍스트 복사" 또는 "JSON 내려받기"로 내용을 꺼낸 뒤,
그걸 원료로 **2단계(숏폼 대본 작성)** 로 넘어간다.
이후 음성(edge-tts) → 자막(faster-whisper) → 9:16 영상(moviepy) 순으로
`pipeline.py` 의 빈 단계를 채워 나가면 된다.

## 주제 덩어리 바꾸기

다른 강의자료를 쓰거나 묶음을 바꾸려면 `backend/extractor.py` 의
`DEFAULT_GROUPS` 표만 수정하면 된다 (페이지 범위 지정).
