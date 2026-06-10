"""
generate_all.py — data/shorts-plan.json의 모든 숏폼을 일괄 생성한다.

이미 영상이 있는 항목(output/<id>/video.mp4)은 건너뛴다(이어서 돌리기 좋게).

실행(프로젝트 루트에서):
    python scripts/generate_all.py
    python scripts/generate_all.py --voice ko-KR-InJoonNeural --bg "Midnight"
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.generate import generate_short  # noqa: E402

PLAN = ROOT / "data" / "shorts-plan.json"
OUTPUT = ROOT / "output"


def main():
    args = sys.argv[1:]
    voice = "ko-KR-SunHiNeural"
    bg = "Deep Navy"
    force = "--force" in args
    for i, a in enumerate(args):
        if a == "--voice" and i + 1 < len(args):
            voice = args[i + 1]
        if a == "--bg" and i + 1 < len(args):
            bg = args[i + 1]

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    lecture_title = plan.get("lecture_title", "파이썬 기초")
    shorts = plan["shorts"]
    total = len(shorts)
    print(f"[일괄 생성] {total}편  voice={voice}  bg={bg}\n")

    t_all = time.time()
    done = skipped = failed = 0
    for n, sh in enumerate(shorts, start=1):
        sid = sh["id"]
        video = OUTPUT / sid / "video.mp4"
        head = f"[{n}/{total}] {sid}  {sh['title']}"
        if video.exists() and not force:
            print(f"{head}  → 건너뜀(이미 있음)")
            skipped += 1
            continue
        print(f"{head}  → 생성 시작…")
        t0 = time.time()
        try:
            pdf_path = (ROOT / "input" / sh["pdf"]) if sh.get("pdf") else None
            entry = generate_short(
                sh["title"], sh["narration"], voice=voice, bg_style=bg,
                short_id=sid, lecture_title=sh.get("course", lecture_title),
                slide_page=sh.get("slide_page"), pdf_path=pdf_path,
                progress_cb=lambda stage, msg="": print(f"      · {stage} {msg}"),
            )
            done += 1
            print(f"   ✓ 완료 {entry['duration']}s  ({time.time()-t0:.0f}s 소요)\n")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"   ✗ 실패: {e}\n")

    mins = (time.time() - t_all) / 60
    print(f"[완료] 생성 {done} · 건너뜀 {skipped} · 실패 {failed}  (총 {mins:.1f}분)")


if __name__ == "__main__":
    main()
