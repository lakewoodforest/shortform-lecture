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


def auto_groups(slides: List[Slide]) -> List[Dict] | None:
    """구분(섹션 표지) 슬라이드를 자동 감지해 주제 덩어리를 만든다.

    이 강의 슬라이드 형식은 새 주제가 시작될 때 제목만 있는 표지 페이지가
    들어간다(예: '조건문', '반복문'). 글자 수가 매우 적은 한두 줄짜리
    페이지를 구분 슬라이드로 보고, 그 사이를 한 주제로 묶는다.

    한계: 구분 표지가 없는 강의자료에서는 감지가 안 되므로 None을 반환하고
    호출 쪽에서 기본 표(DEFAULT_GROUPS)나 단일 그룹으로 처리해야 한다.
    """
    dividers: List[tuple[Slide, str]] = []
    for s in slides:
        if s.page == 1 or not s.text:
            continue
        lines = [l.strip() for l in s.text.split("\n") if l.strip()]
        if s.char_count > 18 or len(lines) > 2:
            continue
        joined = " ".join(lines)
        tokens = joined.split()
        # 내용 슬라이드는 보통 끝에 페이지 번호가 붙는다(예: '집합의 연산 89').
        # 진짜 구분 표지는 제목뿐이므로, 숫자로 끝나면 제외한다.
        if tokens and tokens[-1].isdigit():
            continue
        dividers.append((s, joined))
    if len(dividers) < 2:
        return None

    last_page = slides[-1].page
    groups: List[Dict] = []
    if dividers[0][0].page > 1:
        groups.append({"title": "표지 · 학습목표",
                       "from_page": 1, "to_page": dividers[0][0].page - 1})
    for i, (d, title) in enumerate(dividers):
        end = dividers[i + 1][0].page - 1 if i + 1 < len(dividers) else last_page
        if "감사" in title:
            title = "마무리"
        groups.append({"title": title, "from_page": d.page, "to_page": end})
    return groups


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


def build_payload(pdf_path: str, groups=None, auto: bool = False) -> Dict:
    """프론트엔드/파이프라인이 쓸 최종 JSON 구조.

    auto=True 면 구분 슬라이드를 자동 감지해 주제를 나눈다(업로드 추출용).
    감지가 안 되면 전체를 하나의 그룹으로 묶는다.
    auto=False(기본)는 기존 동작 그대로 DEFAULT_GROUPS를 쓴다(파이프라인용).
    """
    slides = extract_slides(pdf_path)
    grouping = "table"
    if groups is None and auto:
        detected = auto_groups(slides)
        if detected:
            groups, grouping = detected, "auto"
        else:
            groups = [{"title": "전체 내용", "from_page": 1, "to_page": 9999}]
            grouping = "single"
    grouped = group_slides(slides, groups)
    filled = [s for s in slides if s.text]
    return {
        "filename": pdf_path.split("/")[-1],
        "total_slides": len(slides),
        "filled_slides": len(filled),
        "total_chars": sum(s.char_count for s in slides),
        "grouping": grouping,
        "groups": grouped,
        "slides": [asdict(s) for s in slides],
    }


if __name__ == "__main__":
    import sys, json
    path = sys.argv[1] if len(sys.argv) > 1 else "input/lecture.pdf"
    payload = build_payload(path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
