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

## 고급 v1·v2 영상 생성하기

고급 코스의 대본 33편(v1 19편 · v2 14편)이 `data/shorts-plan.json`에 준비돼 있다.
영상을 만들려면 프로젝트 루트에서 한 줄만 실행하면 된다:

```bash
python scripts/generate_all.py
```

이미 만들어진 영상(입문·중급)은 자동으로 건너뛰고 새 대본만 생성한다.
완료되면 "준비 중" 폴더가 실제 코스 폴더로 바뀐다.

## 파이썬 문제 풀이 (대시보드 우측)

`backend/quiz.py` 의 내장 문제 은행(주제 8개 × 난이도 3단계)에서 문제를 뽑아 준다.
허깅페이스 모델로 바꾸려면:

1. 환경변수 `QUIZ_HF_MODEL` 에 모델 ID 지정 (예: `Qwen/Qwen2.5-1.5B-Instruct`)
2. `backend/quiz.py` 의 `_generate_with_model()` 안 TODO 채우기
   (반환 형식만 문제 은행과 맞추면 프론트는 수정 불필요)

연동 전에는 자동으로 문제 은행으로 폴백한다.

## 주제 덩어리 바꾸기

PDF 추출 시 주제 분할 규칙:

1. 업로드한 파일명이 `data/group-tables.json` 에 등록돼 있으면 그 표를 그대로 쓴다
   (lecture.pdf, intermediate.pdf 등록됨 — 고급 자료를 받으면 항목만 추가).
2. 등록 안 된 파일은 "제목만 있는 구분 표지 슬라이드"를 자동 감지해 나눈다
   (같은 형식의 강의자료라면 잘 동작. 중급 PDF로 검증됨).
3. 감지가 안 되면 전체를 한 덩어리로 묶는다.

영상 파이프라인(pipeline.py)은 기존처럼 `backend/extractor.py` 의
`DEFAULT_GROUPS` 를 사용하므로 영향 없음.

## Render 배포 (뷰어 전용)

미리 만든 강의 코스를 웹에서 감상하도록 배포한다. 영상 생성은 꺼진다(`VIEWER_ONLY=1`).

준비 파일: `Dockerfile`, `render.yaml`, `requirements-deploy.txt` (이미 포함됨).

1) GitHub에 올리기 (이미 git 커밋돼 있음):
```bash
# GitHub에서 빈 저장소 생성 후
git remote add origin https://github.com/<사용자명>/shortform-lecture.git
git branch -M main
git push -u origin main
```

2) Render에서 배포:
- render.com 로그인 → New > Blueprint → 위 저장소 선택 → render.yaml 자동 인식 → Apply
- (또는 New > Web Service → 저장소 선택 → Runtime: Docker → 환경변수 `VIEWER_ONLY=1` → Create)

3) 몇 분 후 `https://shortform-lecture.onrender.com` 같은 주소로 접속.
   무료 플랜은 한동안 접속이 없으면 잠들었다가 다음 접속 때 깨어나는 데 ~30초 걸린다.

로컬에서 생성 기능까지 쓰려면 `VIEWER_ONLY` 없이 `uvicorn backend.server:app` 로 실행.
<!— 팀원: 김지성 — AI 튜터 챗봇 담당 —>
<!— 팀원: 정재원 — 파이썬 문제 풀이 · 코드 연습 담당 —>
