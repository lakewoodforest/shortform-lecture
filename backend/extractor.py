"""
extractor.py — PDF 슬라이드에서 텍스트를 뽑고 주제 덩어리로 묶는다.

영상 파이프라인의 1단계(PDF -> 텍스트)에 해당.
나중에 여기서 나온 결과가 대본 생성 -> 음성 -> 영상으로 이어진다.
"""
from __future__ import annotations
import fitz  # PyMuPDF
from dataclasses import dataclass, asdict
from typing import List, Dict


# 주제 덩어리 정의 (1-based 페이지 범위).
# 새 강의자료를 쓸 땐 이 표만 바꾸면 된다.
DEFAULT_GROUPS = [
    {"title": "표지 · 학습목표", "from_page": 1, "to_page": 2},
    {"title": "파이썬 시작하기", "from_page": 3, "to_page": 7},
    {"title": "변수", "from_page": 8, "to_page": 20},
    {"title": "자료형", "from_page": 21, "to_page": 25},
    {"title": "연산자", "from_page": 26, "to_page": 40},
    {"title": "모듈 (random · math)", "from_page": 41, "to_page": 43},
    {"title": "마무리", "from_page": 44, "to_page": 9999},
]


@dataclass
class Slide:
    page: int
    title: str
    text: str
    char_count: int


def _line_text(page: "fitz.Page") -> str:
    """글자 좌표의 간격을 보고 공백을 복원.

    이 PDF는 한글을 글자마다 쪼개 저장하고 공백 문자를 누락한다.
    rawdict로 글자별 bbox를 받아, 앞 글자와의 가로 간격이 글자 폭의
    일정 비율을 넘으면 단어 경계로 보고 공백을 삽입한다.
    """
    raw = page.get_text("rawdict")
    out_lines = []
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            buf = []
            prev_x1 = None
            prev_w = None
            for span in line.get("spans", []):
                for ch in span.get("chars", []):
                    c = ch["c"]
                    x0, _, x1, _ = ch["bbox"]
                    w = x1 - x0
                    if prev_x1 is not None:
                        gap = x0 - prev_x1
                        # 간격이 직전 글자폭의 30%를 넘고, 양쪽이 공백이 아니면 띄움
                        ref = (prev_w or w) or 1
                        if c != " " and buf and buf[-1] != " " and gap > ref * 0.3:
                            buf.append(" ")
                    buf.append(c)
                    prev_x1, prev_w = x1, w
            text = "".join(buf).strip()
            if text:
                out_lines.append(text)
    text = "\n".join(out_lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    # 연속 공백 정리
    import re
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _title_of(text: str) -> str:
    if not text:
        return "(빈 슬라이드)"
    first = next((l for l in text.split("\n") if l.strip()), "")
    return first[:40] + "…" if len(first) > 40 else first


def extract_slides(pdf_path: str) -> List[Slide]:
    """PDF의 각 페이지에서 텍스트를 뽑아 Slide 목록으로 반환."""
    doc = fitz.open(pdf_path)
    slides: List[Slide] = []
    for i, page in enumerate(doc, start=1):
        text = _line_text(page)
        slides.append(
            Slide(
                page=i,
                title=_title_of(text),
                text=text,
                char_count=len(text.replace(" ", "").replace("\n", "")),
            )
        )
    doc.close()
    return slides


def group_slides(slides: List[Slide], groups=None) -> List[Dict]:
    """슬라이드를 주제 덩어리로 묶는다."""
    groups = groups or DEFAULT_GROUPS
    out = []
    for gi, g in enumerate(groups):
        members = [s for s in slides if g["from_page"] <= s.page <= g["to_page"]]
        if not members:
            continue
        out.append(
            {
                "index": gi,
                "title": g["title"],
                "from_page": g["from_page"],
                "to_page": min(g["to_page"], members[-1].page),
                "slides": [asdict(s) for s in members],
            }
        )
    return out


def build_payload(pdf_path: str, groups=None) -> Dict:
    """프론트엔드/파이프라인이 쓸 최종 JSON 구조."""
    slides = extract_slides(pdf_path)
    grouped = group_slides(slides, groups)
    filled = [s for s in slides if s.text]
    return {
        "filename": pdf_path.split("/")[-1],
        "total_slides": len(slides),
        "filled_slides": len(filled),
        "total_chars": sum(s.char_count for s in slides),
        "groups": grouped,
        "slides": [asdict(s) for s in slides],
    }


if __name__ == "__main__":
    import sys, json
    path = sys.argv[1] if len(sys.argv) > 1 else "input/lecture.pdf"
    payload = build_payload(path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
