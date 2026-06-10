"""
tts.py — 3단계: 대본 나레이션을 음성(mp3)으로 만든다.

edge-tts(무료, 마이크로소프트 클라우드 TTS)로 scene별 mp3를 만들고,
각 음성의 길이(초)를 기록한다. 이 길이값이 4단계 자막 싱크와
5단계 슬라이드 표시 시간의 기준이 된다.

[교체 지점]
    synthesize(text, out_path, voice) 한 함수만 "텍스트 -> 음성 파일"을 책임진다.
    나중에 교수님 녹음으로 갈아끼울 땐 이 함수 내부만 바꾸면 되고,
    나머지 파이프라인(scene 순회·메타 기록)은 그대로 둔다.

[출력 구조]
    output/<short-id>/scene-01.mp3
    output/<short-id>/scene-02.mp3
    output/<short-id>/audio.json   ← scene별 길이·슬라이드·대사 메타
"""
from __future__ import annotations
import asyncio
import json
import subprocess
from pathlib import Path
from typing import Iterable, Optional

import edge_tts

DEFAULT_VOICE = "ko-KR-SunHiNeural"  # 한국어 여성. 남성은 ko-KR-InJoonNeural

# 발음 교정 사전: TTS 입력에만 적용한다(자막은 원문 영어/기호 그대로 유지).
# edge-tts가 영어 단어를 영어식으로 읽어 어색해지는 걸 한글 발음으로 바로잡는다.
PRONUNCIATION = {
    "Hello Python": "헬로 파이썬", "Python": "파이썬", "python": "파이썬",
    "print": "프린트", "input": "인풋", "len": "렌",
    "sum": "썸", "min": "민", "max": "맥스", "str": "스트링", "int": "인트",
    "type": "타입", "float": "플로트", "bool": "불",
    "goodmorning": "굿모닝", "good": "굿", "morning": "모닝",
    "weight": "웨이트", "height": "하이트",
    "and": "앤드", "or": "오어", "not": "낫",
    "random": "랜덤", "math": "매스", "IDLE": "아이들", "Run": "런",
    # 중급(조건문·반복문·자료구조) 키워드
    "True": "트루", "False": "폴스",
    "if-else": "이프 엘스", "if": "이프", "elif": "엘리프", "else": "엘스",
    "for": "포", "while": "와일", "range": "레인지", "in": "인",
    "break": "브레이크", "continue": "컨티뉴",
    "list": "리스트", "tuple": "튜플", "dictionary": "딕셔너리", "dict": "딕트",
    "set": "셋", "append": "어펜드", "pop": "팝", "sorted": "소티드",
    "any": "애니", "all": "올", "items": "아이템즈", "keys": "키즈", "values": "밸류즈",
    "key": "키", "value": "밸류",
}


def to_spoken(text: str) -> str:
    """TTS가 자연스럽게 읽도록 영어 단어를 한글 발음으로 치환(자막엔 영향 없음).

    긴 표현부터 치환하고, 단어 경계를 지켜 부분 매칭을 피한다.
    """
    import re as _re
    for term in sorted(PRONUNCIATION, key=len, reverse=True):
        text = _re.sub(rf"(?<![A-Za-z]){_re.escape(term)}(?![A-Za-z])",
                       PRONUNCIATION[term], text)
    return text


def audio_duration(path: str | Path) -> float:
    """ffprobe로 음성 파일 길이(초)를 잰다."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


async def _edge_save(text: str, out_path: Path, voice: str, rate: str) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(out_path))


def synthesize(
    text: str,
    out_path: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> float:
    """텍스트 한 덩어리 -> 음성 파일 1개. 길이(초)를 반환한다.

    *** 이 함수가 교체 지점이다. ***
    교수님 녹음으로 바꾸려면 여기서 edge-tts 대신 녹음 파일을 복사/변환하도록
    바꾸면 된다. 입력(text, out_path, voice)·출력(길이 초) 계약만 지키면
    윗단계는 손댈 필요가 없다.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_edge_save(text, out_path, voice, rate))
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"음성 생성 실패(빈 파일): {out_path}")
    return audio_duration(out_path)


def synthesize_short(
    short,
    out_root: str | Path = "output",
    voice: Optional[str] = None,
    only_scenes: Optional[Iterable[int]] = None,
) -> dict:
    """Short 한 편의 scene들을 음성으로 만들고 메타(audio.json)를 남긴다.

    only_scenes: 1-based scene 번호 집합. 주면 그 scene만 생성(나머지는 건너뜀).
                 None이면 전부 생성.
    """
    voice = voice or DEFAULT_VOICE
    only = set(only_scenes) if only_scenes is not None else None
    out_dir = Path(out_root) / short.id
    out_dir.mkdir(parents=True, exist_ok=True)

    # 기존 메타가 있으면 이어붙이기 (scene01만 먼저 만들고 나중에 나머지 추가하는 흐름)
    meta_path = out_dir / "audio.json"
    existing = {}
    if meta_path.exists():
        try:
            for s in json.loads(meta_path.read_text(encoding="utf-8")).get("scenes", []):
                existing[s["index"]] = s
        except (json.JSONDecodeError, KeyError):
            pass

    scenes_meta = dict(existing)
    for i, scene in enumerate(short.scenes, start=1):
        if only is not None and i not in only:
            continue
        fname = f"scene-{i:02d}.mp3"
        path = out_dir / fname
        dur = synthesize(to_spoken(scene.narration), path, voice)
        scenes_meta[i] = {
            "index": i,
            "slide_page": scene.slide_page,
            "narration": scene.narration,
            "audio": fname,
            "duration": round(dur, 3),
        }
        print(f"    scene-{i:02d}  {dur:5.2f}s  p{scene.slide_page}  {path}")

    ordered = [scenes_meta[k] for k in sorted(scenes_meta)]
    meta = {
        "short_id": short.id,
        "title": short.title,
        "voice": voice,
        "scenes": ordered,
        "total_duration": round(sum(s["duration"] for s in ordered), 3),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from script_loader import load_script

    args = sys.argv[1:]
    script_path = "data/script.json"
    only = None
    for a in args:
        if a.startswith("--scene="):
            only = [int(x) for x in a.split("=", 1)[1].split(",")]
        else:
            script_path = a

    script = load_script(script_path)
    short = script.shorts[0]
    print(f"[3] 음성 생성: {short.id}  (voice={script.voice})"
          + (f"  scene만 {only}" if only else ""))
    meta = synthesize_short(short, voice=script.voice, only_scenes=only)
    print(f"[3] 완료 → output/{short.id}/audio.json  (총 {meta['total_duration']}s, "
          f"scene {len(meta['scenes'])}개 기록)")
