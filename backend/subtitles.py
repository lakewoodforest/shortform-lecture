"""
subtitles.py — 4단계: scene별 음성에서 자막 타임스탬프를 뽑는다.

faster-whisper(CPU int8)로 각 scene mp3를 전사해 단어 단위 타임스탬프를 얻고,
9:16 세로 영상에 맞게 짧은 캡션(cue)으로 묶는다.

[M1 메모]
    device="cpu", compute_type="int8"  — 애플 실리콘엔 GPU가 없으니 CPU int8.
    small 모델 기준 대략 실시간의 3~4배 속도로 처리된다.

[타이밍 기준]
    각 cue의 start/end는 "그 scene 안에서의" 상대 시간(초)이다.
    5단계 moviepy가 scene 클립을 각각 만든 뒤 이어 붙이므로, scene 상대 시간이
    가장 쓰기 좋다. 전체 타임라인이 필요하면 audio.json의 scene 순서로 누적하면 된다.

[원본 대사 vs 전사]
    whisper는 "파이썬"을 "파이선"처럼 살짝 다르게 받아쓸 수 있다. 우리는 정확한
    원본 대사를 이미 갖고 있으므로, 기본값(use_script_text=True)은 cue 텍스트를
    whisper가 아니라 "원본 대사에서 잘라온 글자"로 채운다. 타임스탬프만 whisper를 쓴다.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

from faster_whisper import WhisperModel

DEFAULT_MODEL = "small"
MAX_CUE_CHARS = 16      # 세로 영상 한 줄 권장 글자 수
MAX_CUE_GAP = 0.6       # 단어 사이 공백이 이보다 길면 끊는다(초)

_model_cache: dict[str, WhisperModel] = {}


def get_model(name: str = DEFAULT_MODEL) -> WhisperModel:
    """모델을 한 번만 로드해서 재사용(scene마다 새로 로드하면 느리다)."""
    if name not in _model_cache:
        _model_cache[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _model_cache[name]


@dataclass
class Cue:
    start: float   # scene 안에서의 상대 시간(초)
    end: float
    text: str


def _transcribe_words(mp3_path: str | Path, model: WhisperModel, language: str = "ko"):
    """mp3 -> 단어 목록 [(start, end, word), ...] (scene 상대 시간)."""
    segments, _ = model.transcribe(str(mp3_path), language=language, word_timestamps=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append((w.start, w.end, w.word))
    return words


def _group_words(words, max_chars: int = MAX_CUE_CHARS, max_gap: float = MAX_CUE_GAP) -> List[Cue]:
    """단어들을 짧은 캡션으로 묶는다(글자수 한도 또는 긴 공백에서 끊음)."""
    cues: List[Cue] = []
    buf: list[str] = []
    start = end = None
    for ws, we, word in words:
        token = word.strip()
        if not token:
            continue
        gap = (ws - end) if end is not None else 0.0
        cur = "".join(buf)
        too_long = len(cur) + len(token) > max_chars
        if buf and (too_long or gap > max_gap):
            cues.append(Cue(round(start, 3), round(end, 3), cur.strip()))
            buf, start = [], None
        if start is None:
            start = ws
        buf.append((" " if cur and not token.startswith((" ", ",", ".")) else "") + token)
        end = we
    if buf:
        cues.append(Cue(round(start, 3), round(end, 3), "".join(buf).strip()))
    return cues


def _retext_from_script(cues: List[Cue], script_text: str) -> List[Cue]:
    """cue 타이밍은 두되, 글자는 원본 대사를 글자수 비율대로 잘라 채운다.

    whisper 전사의 오타(파이선 등)를 피하려고, 원본 대사를 cue별 글자수 비중에
    맞춰 순서대로 분배한다. 완벽한 단어 정렬은 아니지만 표시 텍스트는 정확해진다.
    """
    clean = " ".join(script_text.split())
    total = sum(len(c.text) for c in cues) or 1
    out: List[Cue] = []
    pos = 0
    for i, c in enumerate(cues):
        if i == len(cues) - 1:
            piece = clean[pos:]
        else:
            take = round(len(clean) * (len(c.text) / total))
            end_pos = pos + take
            # 단어 중간에서 자르지 않도록 다음 공백까지 확장
            sp = clean.find(" ", end_pos)
            end_pos = sp if sp != -1 else end_pos
            piece = clean[pos:end_pos]
            pos = end_pos + 1 if sp != -1 else end_pos
        out.append(Cue(c.start, c.end, piece.strip()))
    return [c for c in out if c.text]


def subtitle_short(
    short,
    out_root: str | Path = "output",
    model_name: str = DEFAULT_MODEL,
    language: str = "ko",
    use_script_text: bool = True,
) -> dict:
    """Short 한 편의 scene별 자막을 만들어 subtitles.json으로 저장."""
    out_dir = Path(out_root) / short.id
    audio_meta = json.loads((out_dir / "audio.json").read_text(encoding="utf-8"))
    by_index = {s["index"]: s for s in audio_meta["scenes"]}

    model = get_model(model_name)
    scenes_out = []
    for i, scene in enumerate(short.scenes, start=1):
        meta = by_index.get(i)
        if not meta:
            continue
        mp3 = out_dir / meta["audio"]
        words = _transcribe_words(mp3, model, language)
        cues = _group_words(words)
        if use_script_text:
            cues = _retext_from_script(cues, scene.narration)
        scenes_out.append({
            "index": i,
            "slide_page": scene.slide_page,
            "duration": meta["duration"],
            "cues": [asdict(c) for c in cues],
        })
        print(f"    scene-{i:02d}  cue {len(cues)}개  ({meta['duration']}s)")

    result = {
        "short_id": short.id,
        "model": model_name,
        "language": language,
        "text_source": "script" if use_script_text else "whisper",
        "scenes": scenes_out,
    }
    (out_dir / "subtitles.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from script_loader import load_script

    args = sys.argv[1:]
    script_path = "data/script.json"
    use_script_text = True
    for a in args:
        if a == "--whisper-text":
            use_script_text = False
        else:
            script_path = a

    script = load_script(script_path)
    short = script.shorts[0]
    print(f"[4] 자막 추출: {short.id}  (model={DEFAULT_MODEL}, "
          f"텍스트={'원본대사' if use_script_text else 'whisper전사'})")
    res = subtitle_short(short, use_script_text=use_script_text)
    n = sum(len(s["cues"]) for s in res["scenes"])
    print(f"[4] 완료 → output/{short.id}/subtitles.json  (총 cue {n}개)")
