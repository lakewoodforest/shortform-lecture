"""
script_loader.py — 2단계: 숏폼 대본(JSON) 읽기 + 검증.

대본은 클로드나 사람이 손으로 작성한 JSON이다. 이 모듈은 그 파일을 읽어
구조가 올바른지 검사하고, 이후 단계(음성·자막·영상)가 바로 쓸 수 있는
파이썬 객체로 돌려준다.

[대본 JSON 구조]

    {
      "lecture_id":    "lecture",            # input/<id>.pdf 와 매칭
      "lecture_title": "파이썬 기초",          # 표시용
      "voice":         "ko-KR-SunHiNeural",  # 3단계 edge-tts 기본 목소리
      "shorts": [                            # 숏폼 영상 목록 (1개 = 영상 1편)
        {
          "id":          "short-01-variable",  # 파일/폴더 이름에 쓰는 식별자
          "title":       "변수가 뭐예요?",       # 영상 제목
          "topic_index": 2,                     # extractor 주제 그룹 번호(참고용)
          "scenes": [                           # 장면 목록 (1개 = 슬라이드 1장 노출)
            {
              "slide_page": 9,                  # 화면에 띄울 PDF 페이지(1-based)
              "narration":  "여기에 읽어줄 대사" # TTS 음성 + 자막의 원문
            }
          ]
        }
      ]
    }

검증 규칙은 ScriptError 로 알려준다. 한 군데라도 어긋나면 멈춘다.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


class ScriptError(ValueError):
    """대본 JSON 구조가 잘못됐을 때 던지는 예외."""


@dataclass
class Scene:
    slide_page: int
    narration: str


@dataclass
class Short:
    id: str
    title: str
    topic_index: int
    scenes: List[Scene]

    @property
    def narration_chars(self) -> int:
        return sum(len(s.narration) for s in self.scenes)


@dataclass
class Script:
    lecture_id: str
    lecture_title: str
    voice: str
    shorts: List[Short] = field(default_factory=list)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ScriptError(msg)


def _parse_scene(raw: dict, where: str) -> Scene:
    _require(isinstance(raw, dict), f"{where}: scene은 객체여야 합니다.")
    _require("slide_page" in raw, f"{where}: 'slide_page'가 없습니다.")
    _require("narration" in raw, f"{where}: 'narration'이 없습니다.")
    page = raw["slide_page"]
    text = raw["narration"]
    _require(isinstance(page, int) and page >= 1, f"{where}: slide_page는 1 이상 정수여야 합니다 (받은 값: {page!r}).")
    _require(isinstance(text, str) and text.strip(), f"{where}: narration이 비어 있습니다.")
    return Scene(slide_page=page, narration=text.strip())


def _parse_short(raw: dict, idx: int) -> Short:
    where = f"shorts[{idx}]"
    _require(isinstance(raw, dict), f"{where}: short는 객체여야 합니다.")
    for key in ("id", "title", "scenes"):
        _require(key in raw, f"{where}: '{key}'가 없습니다.")
    _require(isinstance(raw["id"], str) and raw["id"].strip(), f"{where}: id가 비어 있습니다.")
    scenes_raw = raw["scenes"]
    _require(isinstance(scenes_raw, list) and scenes_raw, f"{where}: scenes는 비어 있지 않은 배열이어야 합니다.")
    scenes = [_parse_scene(s, f"{where}.scenes[{i}]") for i, s in enumerate(scenes_raw)]
    return Short(
        id=raw["id"].strip(),
        title=str(raw.get("title", "")).strip(),
        topic_index=int(raw.get("topic_index", -1)),
        scenes=scenes,
    )


def load_script(path: str | Path) -> Script:
    """대본 JSON 파일을 읽어 검증된 Script 객체로 돌려준다."""
    path = Path(path)
    _require(path.exists(), f"대본 파일이 없습니다: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ScriptError(f"JSON 형식 오류: {e}") from e

    _require(isinstance(raw, dict), "최상위는 객체여야 합니다.")
    shorts_raw = raw.get("shorts")
    _require(isinstance(shorts_raw, list) and shorts_raw, "'shorts'는 비어 있지 않은 배열이어야 합니다.")

    shorts = [_parse_short(s, i) for i, s in enumerate(shorts_raw)]

    # id 중복 검사 (폴더 이름 충돌 방지)
    ids = [s.id for s in shorts]
    dups = {i for i in ids if ids.count(i) > 1}
    _require(not dups, f"short id가 중복됩니다: {sorted(dups)}")

    return Script(
        lecture_id=str(raw.get("lecture_id", "lecture")),
        lecture_title=str(raw.get("lecture_title", "")),
        voice=str(raw.get("voice", "ko-KR-SunHiNeural")),
        shorts=shorts,
    )


def summarize(script: Script) -> str:
    """사람이 읽기 좋은 요약 한 덩어리."""
    lines = [
        f"강의: {script.lecture_title or script.lecture_id}  (voice={script.voice})",
        f"숏폼 {len(script.shorts)}편",
    ]
    for sh in script.shorts:
        lines.append(
            f"  · [{sh.id}] {sh.title} — 장면 {len(sh.scenes)}개, "
            f"나레이션 {sh.narration_chars}자, 슬라이드 {[s.slide_page for s in sh.scenes]}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "data/script-sample.json"
    try:
        script = load_script(p)
    except ScriptError as e:
        print(f"[대본 검증 실패] {e}")
        sys.exit(1)
    print("[대본 검증 통과]")
    print(summarize(script))
