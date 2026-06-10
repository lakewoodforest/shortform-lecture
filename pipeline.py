"""
pipeline.py — 전체 숏폼 제작 파이프라인.

PDF 한 장에서 9:16 숏폼 영상까지 한 번에 굴린다. 각 단계는 결과물이 이미
있으면 건너뛰므로(idempotent), 다시 돌려도 바뀐 부분만 새로 만든다.

    1. PDF -> 슬라이드 텍스트/이미지      [extractor]       data/lecture-content.json
    2. 텍스트 -> 숏폼 대본(JSON)          [수동/LLM]        data/script.json
    3. 대본 -> 음성(TTS)                  [edge-tts]        output/<id>/scene-NN.mp3, audio.json
    4. 음성 -> 자막 타임스탬프            [faster-whisper]  output/<id>/subtitles.json
    5. 슬라이드+음성+자막 -> 9:16 영상    [moviepy]         output/<id>/video.mp4
    6. 강의별 폴더 정리 + 매니페스트       [여기]            output/index.json

3단계의 "텍스트 -> 음성 파일"은 backend/tts.py 의 synthesize() 한 함수로 분리돼
있다. 나중에 교수님 녹음으로 바꿀 땐 그 함수만 교체하면 된다.

실행:
    python pipeline.py                # data/script.json 으로 전체 실행
    python pipeline.py --force        # 기존 결과 무시하고 전부 재생성
    python pipeline.py --script data/other.json
"""
from __future__ import annotations
from pathlib import Path
import json

from backend.extractor import build_payload
from backend.script_loader import load_script, summarize

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
DATA = ROOT / "data"


def step1_extract(pdf_path: str) -> dict:
    """1단계: PDF에서 슬라이드 텍스트를 뽑아 JSON으로 저장."""
    payload = build_payload(pdf_path)
    DATA.mkdir(exist_ok=True)
    out = DATA / "lecture-content.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[1] 추출 완료 → {out}  (슬라이드 {payload['total_slides']}, 주제 {len(payload['groups'])})")
    return payload


def step2_load_script(script_path: str):
    """2단계: 손으로 작성한 숏폼 대본(JSON)을 읽어 검증한다."""
    script = load_script(script_path)
    print(f"[2] 대본 검증 통과 → {script_path}")
    print(summarize(script))
    return script


def _audio_done(short, out_dir: Path) -> bool:
    meta = out_dir / "audio.json"
    if not meta.exists():
        return False
    try:
        got = {s["index"] for s in json.loads(meta.read_text(encoding="utf-8"))["scenes"]}
    except (json.JSONDecodeError, KeyError):
        return False
    return got >= set(range(1, len(short.scenes) + 1))


def step3_tts(short, voice: str, out_dir: Path, force: bool = False) -> dict:
    """3단계: scene별 음성(mp3) 생성. 이미 다 있으면 건너뜀."""
    if not force and _audio_done(short, out_dir):
        meta = json.loads((out_dir / "audio.json").read_text(encoding="utf-8"))
        print(f"[3] 음성 — 건너뜀(이미 있음, 총 {meta['total_duration']}s)")
        return meta
    from backend.tts import synthesize_short
    print("[3] 음성 생성…")
    return synthesize_short(short, out_root=out_dir.parent, voice=voice)


def step4_subtitles(short, out_dir: Path, force: bool = False) -> dict:
    """4단계: 음성에서 자막 타임스탬프 추출. 이미 있으면 건너뜀."""
    subs = out_dir / "subtitles.json"
    if not force and subs.exists():
        print("[4] 자막 — 건너뜀(이미 있음)")
        return json.loads(subs.read_text(encoding="utf-8"))
    from backend.subtitles import subtitle_short
    print("[4] 자막 추출…")
    return subtitle_short(short, out_root=out_dir.parent)


def step5_video(short, lecture_title: str, pdf_path: Path, out_dir: Path, force: bool = False) -> Path:
    """5단계: 9:16 영상 합성. 이미 있으면 건너뜀."""
    video = out_dir / "video.mp4"
    if not force and video.exists():
        print(f"[5] 영상 — 건너뜀(이미 있음, {video.stat().st_size/1e6:.1f} MB)")
        return video
    from backend.video import build_video
    print("[5] 영상 합성… (M1에서 1분 영상당 약 4분 소요)")
    return build_video(short, lecture_title, pdf_path, out_root=out_dir.parent)


def build_short(short, script, pdf_path: Path, force: bool = False) -> dict:
    """숏폼 한 편을 음성→자막→영상까지 만든다. 매니페스트용 정보 반환."""
    out_dir = OUTPUT / short.id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n── 숏폼 [{short.id}] {short.title} ──")
    audio = step3_tts(short, script.voice, out_dir, force)
    step4_subtitles(short, out_dir, force)
    video = step5_video(short, script.lecture_title, pdf_path, out_dir, force)
    return {
        "id": short.id,
        "title": short.title,
        "duration": audio["total_duration"],
        "scene_count": len(short.scenes),
        "voice": script.voice,
        "video": f"{short.id}/video.mp4",
    }


def write_manifest(script, shorts_info: list[dict]) -> Path:
    """6단계: 강의 단위로 결과를 한 파일에 정리(대시보드가 읽음)."""
    manifest = {
        "lecture_id": script.lecture_id,
        "lecture_title": script.lecture_title,
        "short_count": len(shorts_info),
        "shorts": shorts_info,
    }
    out = OUTPUT / "index.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[6] 매니페스트 정리 완료 → {out}  (숏폼 {len(shorts_info)}편)")
    return out


def run(lecture_id: str = "lecture", script_path: str | None = None, force: bool = False):
    pdf = INPUT / f"{lecture_id}.pdf"
    if not pdf.exists():
        raise FileNotFoundError(f"{pdf} 가 없습니다. input/ 에 PDF를 넣으세요.")

    step1_extract(str(pdf))

    spath = Path(script_path) if script_path else DATA / "script.json"
    if not spath.exists():
        print(f"[2] 대본 파일이 없어 3단계 이후를 건너뜁니다: {spath}")
        return
    script = step2_load_script(str(spath))

    shorts_info = [build_short(sh, script, pdf, force) for sh in script.shorts]
    write_manifest(script, shorts_info)
    print("\n✅ 전체 파이프라인 완료.")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    force = "--force" in args
    script_path = None
    lecture_id = "lecture"
    i = 0
    rest = [a for a in args if a != "--force"]
    while i < len(rest):
        if rest[i] == "--script":
            script_path = rest[i + 1]; i += 2
        else:
            lecture_id = rest[i]; i += 1
    run(lecture_id, script_path=script_path, force=force)
