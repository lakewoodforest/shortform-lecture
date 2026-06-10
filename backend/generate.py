"""
generate.py — 웹 생성기: 제목 + 내레이션 스크립트 -> 9:16 숏폼 영상.

대시보드에서 입력한 텍스트를 받아 파이프라인(음성 -> 자막 -> 영상)을 그대로
태운다. 슬라이드 대신 다크 네이비 그라데이션 배경 + 프로그레스 바를 쓴다.

흐름:
    1. 스크립트를 문장 단위 scene으로 쪼갬
    2. scene별 edge-tts 음성 (tts.synthesize_short)
    3. 음성 -> 자막 타임스탬프 (subtitles.subtitle_short)
    4. 그라데이션 영상 합성 (video.build_gradient_video)
    5. output/index.json(매니페스트)에 추가
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from .script_loader import Short, Scene
from .tts import synthesize_short, DEFAULT_VOICE
from .video import build_gradient_video, BG_STYLES

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PDF_PATH = ROOT / "input" / "lecture.pdf"


def split_scenes(text: str) -> list[str]:
    """스크립트를 문장 단위로 쪼갠다(마침표·물음표·느낌표·줄바꿈 기준)."""
    parts = re.split(r"(?<=[.!?。?!])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def make_short_id(title: str, seq: int) -> str:
    """제목에서 안전한 폴더 이름을 만든다(한글은 seq로 대체)."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        slug = "short"
    return f"web-{seq:02d}-{slug}"[:48]


def _append_manifest(entry: dict, lecture_title: str = "웹 생성") -> None:
    """output/index.json에 생성 결과를 추가(같은 id면 갱신)."""
    idx = OUTPUT / "index.json"
    data = {"lecture_id": "web", "lecture_title": lecture_title, "shorts": []}
    if idx.exists():
        try:
            data = json.loads(idx.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    shorts = [s for s in data.get("shorts", []) if s["id"] != entry["id"]]
    shorts.insert(0, entry)
    data["shorts"] = shorts
    data["short_count"] = len(shorts)
    idx.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_short(title: str, script_text: str, voice: str = DEFAULT_VOICE,
                   bg_style: str = "Deep Navy", seq: int = 1,
                   short_id: str | None = None, lecture_title: str = "웹 생성",
                   slide_page: int | None = None, pdf_path: str | Path | None = None,
                   progress_cb=None) -> dict:
    """제목+스크립트로 숏폼 한 편을 만들어 매니페스트 항목을 반환한다.

    short_id를 주면 그 id를 그대로 폴더/식별자로 쓴다(계획 파일 일괄 생성용).
    안 주면 제목+seq로 자동 생성한다(웹 단건 생성용).
    slide_page를 주면 그 강의 슬라이드를 영상 배경에 함께 보여준다.

    자막은 whisper 없이 대본 문장을 쉼표/구절 단위로 끊어 만든다(정확·빠름).
    """
    def report(stage, msg=""):
        if progress_cb:
            progress_cb(stage, msg)

    sentences = split_scenes(script_text)
    if not sentences:
        raise ValueError("스크립트가 비어 있습니다.")
    if bg_style not in BG_STYLES:
        bg_style = "Deep Navy"

    short_id = short_id or make_short_id(title, seq)
    scenes = [Scene(slide_page=slide_page or 0, narration=s) for s in sentences]
    short = Short(id=short_id, title=title or "제목 없음", topic_index=-1, scenes=scenes)

    report("음성 생성", f"문장 {len(sentences)}개")
    audio = synthesize_short(short, out_root=OUTPUT, voice=voice)

    report("영상 렌더", "")
    pdf = pdf_path or PDF_PATH
    video = build_gradient_video(short, short.title, out_root=OUTPUT, bg_style=bg_style,
                                 slide_page=slide_page, pdf_path=pdf if slide_page else None,
                                 progress_cb=progress_cb)

    entry = {
        "id": short_id,
        "title": short.title,
        "duration": audio["total_duration"],
        "scene_count": len(sentences),
        "voice": voice,
        "bg_style": bg_style,
        "slide_page": slide_page,
        "video": f"{short_id}/video.mp4",
    }
    _append_manifest(entry, lecture_title=lecture_title)
    report("완료", f"{video}")
    return entry


if __name__ == "__main__":
    import sys
    txt = sys.argv[1] if len(sys.argv) > 1 else \
        "파이썬은 배우기 쉬운 프로그래밍 언어예요. 오늘은 변수에 대해 알아볼게요."
    e = generate_short("테스트 숏폼", txt, seq=99,
                       progress_cb=lambda s, m: print(f"  · {s} {m}"))
    print("결과:", json.dumps(e, ensure_ascii=False))
