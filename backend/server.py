"""
server.py — 대시보드 백엔드.

브라우저가 PDF를 업로드하면 PyMuPDF로 처리해서 JSON으로 돌려준다.
프론트엔드(frontend/index.html)도 이 서버가 함께 서빙한다.

실행:
    uvicorn backend.server:app --reload
    (프로젝트 루트에서)
그 다음 브라우저에서 http://127.0.0.1:8000 접속.
"""
from __future__ import annotations
import os
import tempfile
import threading
import traceback
import uuid
from pathlib import Path

import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .extractor import build_payload

app = FastAPI(title="한입 파이썬")

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
OUTPUT = ROOT / "output"

# 선택지 (사이드바)
VOICES = [
    {"id": "ko-KR-SunHiNeural", "label": "선희 (여성)"},
    {"id": "ko-KR-InJoonNeural", "label": "인준 (남성)"},
    {"id": "ko-KR-HyunsuMultilingualNeural", "label": "현수 (남성·멀티)"},
]
BG_STYLE_LIST = ["Deep Navy", "Midnight", "Ocean Navy", "Royal",
                 "Plum", "Forest", "Sunset", "Charcoal"]

# 뷰어 모드: 배포(Render 등)에서 VIEWER_ONLY=1 이면 생성 기능을 끄고 감상만.
VIEWER_ONLY = os.environ.get("VIEWER_ONLY", "").lower() in ("1", "true", "yes")

# 진행 중인 생성 작업 (메모리)
JOBS: dict[str, dict] = {}


@app.get("/", response_class=HTMLResponse)
def index():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


def _group_table_for(filename: str):
    """data/group-tables.json에 등록된 파일이면 그 표를 쓴다(하드코딩 우선).

    등록 안 된 파일은 None을 돌려주고, 구분 표지 자동 감지로 처리된다.
    고급 자료를 받으면 group-tables.json에 항목만 추가하면 된다.
    """
    path = ROOT / "data" / "group-tables.json"
    if not path.exists():
        return None
    try:
        tables = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    table = tables.get(filename)
    if isinstance(table, str):          # 별칭(다른 파일명 가리킴) 지원
        table = tables.get(table)
    return table if isinstance(table, list) and table else None


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF 파일만 업로드할 수 있습니다.")

    # 임시 파일로 저장 후 처리
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        table = _group_table_for(file.filename)
        payload = build_payload(tmp_path, groups=table, auto=True)
        payload["filename"] = file.filename
        return JSONResponse(payload)
    finally:
        os.unlink(tmp_path)


@app.get("/api/shorts")
def shorts():
    """완성된 숏폼 목록(output/index.json). 파이프라인이 만들어 둔 매니페스트."""
    idx = OUTPUT / "index.json"
    if not idx.exists():
        return JSONResponse({"shorts": [], "lecture_title": ""})
    return JSONResponse(json.loads(idx.read_text(encoding="utf-8")))


@app.get("/api/options")
def options():
    """사이드바 선택지(목소리·배경 스타일) + 뷰어 모드 여부."""
    return {"voices": VOICES, "bg_styles": BG_STYLE_LIST, "viewer_only": VIEWER_ONLY}


# 나중에 채워질 코스(폴더) — 로드맵 표시용 (영상이 생성되면 자동으로 실제 폴더가 됨)
UPCOMING_COURSES = ["파이썬 고급 v1", "파이썬 고급 v2"]


def _short_item(sh: dict) -> dict | None:
    """생성된 숏폼 1편을 코스 항목으로(영상 없으면 None)."""
    if not (OUTPUT / sh["id"] / "video.mp4").exists():
        return None
    dur = None
    am = OUTPUT / sh["id"] / "audio.json"
    if am.exists():
        try:
            dur = json.loads(am.read_text(encoding="utf-8")).get("total_duration")
        except json.JSONDecodeError:
            pass
    return {"id": sh["id"], "title": sh["title"], "topic": sh.get("topic", ""),
            "slide_page": sh.get("slide_page"), "duration": dur,
            "video": f"{sh['id']}/video.mp4"}


@app.get("/api/courses")
def courses():
    """코스(폴더) 목록. shorts-plan.json을 course별로 묶어 학습 순서대로 돌려준다.

    short에 'course' 필드가 있으면 그걸로, 없으면 '파이썬 입문'으로 묶는다.
    UPCOMING_COURSES는 '준비 중' 폴더로 함께 내려준다(로드맵).
    """
    plan_path = ROOT / "data" / "shorts-plan.json"
    order, bucket = [], {}
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for sh in plan.get("shorts", []):
            item = _short_item(sh)
            if not item:
                continue
            c = sh.get("course", "파이썬 입문")
            if c not in bucket:
                bucket[c] = []
                order.append(c)
            bucket[c].append(item)

    result = [{"name": c, "items": bucket[c], "count": len(bucket[c]), "ready": True}
              for c in order]
    for c in UPCOMING_COURSES:
        if c not in bucket:
            result.append({"name": c, "items": [], "count": 0, "ready": False})
    return {"courses": result}


class GenerateReq(BaseModel):
    title: str = "제목 없음"
    script: str
    voice: str = "ko-KR-SunHiNeural"
    bg_style: str = "Deep Navy"


def _next_seq() -> int:
    """기존 web 숏폼 개수 기준으로 다음 번호."""
    idx = OUTPUT / "index.json"
    n = 0
    if idx.exists():
        try:
            n = sum(1 for s in json.loads(idx.read_text(encoding="utf-8")).get("shorts", [])
                    if str(s.get("id", "")).startswith("web-"))
        except json.JSONDecodeError:
            pass
    return n + 1


def _run_job(job_id: str, req: GenerateReq, seq: int) -> None:
    from .generate import generate_short
    job = JOBS[job_id]

    def cb(stage, msg=""):
        job["stage"] = stage
        job["message"] = msg

    try:
        job["status"] = "running"
        entry = generate_short(req.title, req.script, voice=req.voice,
                               bg_style=req.bg_style, seq=seq, progress_cb=cb)
        job["status"] = "done"
        job["stage"] = "완료"
        job["result"] = entry
    except Exception as e:  # noqa: BLE001
        job["status"] = "error"
        job["error"] = str(e)
        job["trace"] = traceback.format_exc()


@app.post("/api/generate")
def generate(req: GenerateReq):
    if VIEWER_ONLY:
        raise HTTPException(403, "이 사이트는 감상 전용입니다(영상 생성 비활성화).")
    if not req.script.strip():
        raise HTTPException(400, "스크립트를 입력하세요.")
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "queued", "stage": "대기", "message": "",
                    "title": req.title, "result": None}
    t = threading.Thread(target=_run_job, args=(job_id, req, _next_seq()), daemon=True)
    t.start()
    return {"job_id": job_id}


@app.get("/api/job/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "작업을 찾을 수 없습니다.")
    return job


# 완성 영상/메타 서빙 (예: /media/short-01-start/video.mp4)
if OUTPUT.exists():
    app.mount("/media", StaticFiles(directory=str(OUTPUT)), name="media")

# 정적 파일(필요 시 CSS/JS 분리할 때)
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
