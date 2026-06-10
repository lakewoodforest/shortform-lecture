"""
video.py — 5단계: 슬라이드 + 음성 + 자막을 9:16 세로 영상으로 합성한다.

레이아웃(A안, 성수동 톤):
    ┌─────────────┐  1080 x 1920, 남색(#16244a) 배경
    │   제목(흰색)   │
    │  ┌────────┐  │  상단: 슬라이드를 흰 카드에 얹어 16:9로 배치
    │  │ 슬라이드 │  │
    │  └────────┘  │
    │              │
    │   자막(흰색)   │  하단: scene 자막을 cue 타이밍에 맞춰 표시
    │  강의 제목(흐림) │
    └─────────────┘

scene 한 개 = 슬라이드 1장(고정 배경) + 음성 1개 + 자막 cue 여러 개.
scene 클립들을 이어 붙여 output/<short-id>/video.mp4 를 만든다.

[구현 메모]
    - 텍스트는 ImageMagick 없이 PIL로 직접 그린다(가변폰트 NotoSansKR, Bold축).
    - 자막은 cue마다 투명 PNG를 만들어 ImageClip으로 타이밍을 준다.
    - 슬라이드는 PyMuPDF로 렌더해서 흰 카드 위에 올린다.
"""
from __future__ import annotations
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Tuple

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import (ImageClip, AudioFileClip, CompositeVideoClip,
                     VideoClip, concatenate_videoclips, concatenate_audioclips)

ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = ROOT / "assets" / "fonts" / "NotoSansKR-VF.ttf"

W, H = 1080, 1920
NAVY = (22, 36, 74)            # #16244a
WHITE = (255, 255, 255)
MUTED = (150, 165, 200)
MARGIN = 60

# 레이아웃 세로 위치
TITLE_Y = 70
SLIDE_TOP = 200
SUBTITLE_CENTER_Y = 1480
FOOTER_Y = 1860


def _font(size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT_PATH), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def render_slide(pdf_path: str | Path, page_1based: int, target_w: int) -> Image.Image:
    """PDF 한 페이지를 target_w 폭의 PIL 이미지로 렌더."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_1based - 1]
    pix = page.get_pixmap(dpi=150)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    h = round(target_w * img.height / img.width)
    return img.resize((target_w, h), Image.LANCZOS)


def _rounded(draw: ImageDraw.ImageDraw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def make_background(slide: Image.Image, title: str, lecture_title: str) -> Image.Image:
    """남색 배경 + 제목 + 슬라이드 카드 + 하단 강의명. (자막 제외 고정 부분)"""
    bg = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(bg)

    # 제목 (가운데 정렬)
    tf = _font(50, 800)
    tw = d.textbbox((0, 0), title, font=tf)[2]
    d.text(((W - tw) // 2, TITLE_Y), title, font=tf, fill=WHITE)

    # 슬라이드 카드 (흰 라운드 박스 위에 슬라이드)
    pad = 18
    card_w = W - 2 * MARGIN
    sw = card_w - 2 * pad
    slide = slide.resize((sw, round(sw * slide.height / slide.width)), Image.LANCZOS)
    card_h = slide.height + 2 * pad
    card_box = (MARGIN, SLIDE_TOP, MARGIN + card_w, SLIDE_TOP + card_h)
    _rounded(d, card_box, 24, WHITE)
    bg.paste(slide, (MARGIN + pad, SLIDE_TOP + pad))

    # 하단 강의명 (흐린 글씨)
    if lecture_title:
        ff = _font(34, 500)
        fw = d.textbbox((0, 0), lecture_title, font=ff)[2]
        d.text(((W - fw) // 2, FOOTER_Y), lecture_title, font=ff, fill=MUTED)

    return bg


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """픽셀 폭 기준 줄바꿈."""
    words = text.split()
    lines, cur = [], ""
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for w in words:
        trial = (cur + " " + w).strip()
        if dummy.textbbox((0, 0), trial, font=font)[2] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_subtitle(text: str) -> np.ndarray:
    """자막 한 cue를 캔버스 크기 투명 PNG(RGBA np 배열)로 그린다."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(60, 700)
    max_w = W - 2 * MARGIN - 40
    lines = _wrap(text, font, max_w)
    line_h = font.size + 18
    total_h = line_h * len(lines)

    # 반투명 남색 밴드(가독성)
    band_pad_x, band_pad_y = 40, 26
    widths = [d.textbbox((0, 0), ln, font=font)[2] for ln in lines]
    band_w = max(widths) + 2 * band_pad_x
    band_h = total_h + 2 * band_pad_y
    bx0 = (W - band_w) // 2
    by0 = SUBTITLE_CENTER_Y - band_h // 2
    _rounded(d, (bx0, by0, bx0 + band_w, by0 + band_h), 20, (12, 20, 44, 200))

    # 자막 글자(가운데 정렬)
    y = SUBTITLE_CENTER_Y - total_h // 2
    for ln, lw in zip(lines, widths):
        d.text(((W - lw) // 2, y), ln, font=font, fill=WHITE)
        y += line_h
    return np.array(img)


def build_scene_clip(bg_img: Image.Image, audio_path: Path, cues: list, duration: float):
    """scene 1개: 배경 + 자막 cue들 + 음성."""
    bg = ImageClip(np.array(bg_img)).with_duration(duration)
    layers = [bg]
    for c in cues:
        end = min(c["end"], duration)
        if end <= c["start"]:
            continue
        sub = (ImageClip(render_subtitle(c["text"]), transparent=True)
               .with_start(c["start"])
               .with_duration(end - c["start"]))
        layers.append(sub)
    audio = AudioFileClip(str(audio_path))
    return CompositeVideoClip(layers, size=(W, H)).with_duration(duration).with_audio(audio)


def build_video(short, lecture_title: str, pdf_path: str | Path,
                out_root: str | Path = "output", fps: int = 30) -> Path:
    """Short 한 편을 9:16 mp4로 합성."""
    out_dir = Path(out_root) / short.id
    subs = json.loads((out_dir / "subtitles.json").read_text(encoding="utf-8"))
    by_index = {s["index"]: s for s in subs["scenes"]}

    clips = []
    for i, scene in enumerate(short.scenes, start=1):
        meta = by_index.get(i)
        if not meta:
            continue
        slide = render_slide(pdf_path, scene.slide_page, target_w=W - 2 * MARGIN)
        bg = make_background(slide, short.title, lecture_title)
        clip = build_scene_clip(bg, out_dir / f"scene-{i:02d}.mp3",
                                meta["cues"], meta["duration"])
        clips.append(clip)
        print(f"    scene-{i:02d}  p{scene.slide_page}  {meta['duration']}s  cue {len(meta['cues'])}")

    final = concatenate_videoclips(clips, method="compose")
    out_path = out_dir / "video.mp4"
    final.write_videofile(
        str(out_path), fps=fps, codec="libx264", audio_codec="aac",
        preset="medium", threads=4, logger=None,
    )
    return out_path


# ──────────────────────────────────────────────────────────────────────────
# 그라데이션 + 슬라이드 + 마스코트 모드 (웹/일괄 생성기용)
#   레이아웃(세로):  제목 → 강의 슬라이드 카드 → 부기(마스코트) → 자막 → 진행바
#   부기는 살짝 둥실거리고, 자막은 대본을 쉼표/구절 단위로 자연스럽게 끊는다.
# ──────────────────────────────────────────────────────────────────────────

# 배경 스타일: (중심색, 가장자리색)
# 네이비 계열(강의 코스 기본) + 어두운 비-네이비(커스텀 영상용, 흰 자막 가독성 유지)
BG_STYLES = {
    "Deep Navy":  ((42, 63, 122), (7, 12, 28)),
    "Midnight":   ((30, 49, 96),  (5, 8, 20)),
    "Ocean Navy": ((20, 64, 110), (4, 10, 26)),
    "Royal":      ((48, 58, 140), (9, 11, 34)),
    "Plum":       ((92, 50, 130), (24, 10, 36)),
    "Forest":     ((24, 92, 78),  (6, 24, 20)),
    "Sunset":     ((132, 60, 54), (36, 12, 20)),
    "Charcoal":   ((70, 78, 92),  (14, 16, 22)),
}
ACCENT = (110, 150, 240)        # 프로그레스 바 색
MASCOT_PATH = ROOT / "frontend" / "mascot.png"

# 레이아웃 좌표 (슬라이드 크게·여백 줄여 가독성↑)
GSLIDE_W = 1020
GSLIDE_TOP = 215
MASCOT_W = 285
MASCOT_TOP = 825
SUB_BAND_TOP = 1300
SUB_BAND_BOTTOM = 1710
PROGRESS_H = 8
PROGRESS_Y = H - 56

_mascot_cache: dict[int, np.ndarray] = {}


def load_mascot(width: int = MASCOT_W):
    """마스코트(부기) PNG를 RGBA np로 로드(없으면 None)."""
    if not MASCOT_PATH.exists():
        return None
    if width not in _mascot_cache:
        im = Image.open(MASCOT_PATH).convert("RGBA")
        h = round(width * im.height / im.width)
        _mascot_cache[width] = np.array(im.resize((width, h), Image.LANCZOS))
    return _mascot_cache[width]


def natural_cues(text: str, duration: float) -> list[dict]:
    """대본 한 문장을 쉼표·구절 단위로 자연스럽게 끊어 cue로 만든다.

    - 쉼표(,)에서 우선 끊고, 너무 긴 덩어리(>34자)는 가운데 공백에서 한 번 더 나눔.
    - 각 cue 길이는 글자 수 비율로 문장 재생시간을 나눠 가진다.
    """
    text = " ".join(text.split())
    parts = [p.strip() for p in re.split(r"(?<=,)\s*", text) if p.strip()]
    chunks: list[str] = []
    for p in parts:
        p = p.rstrip(",").strip()
        if len(p) > 34:
            mid = len(p) // 2
            left, right = p.rfind(" ", 0, mid), p.find(" ", mid)
            cands = [c for c in (left, right) if c != -1]
            if cands:
                sp = min(cands, key=lambda c: abs(c - mid))
                chunks += [p[:sp].strip(), p[sp + 1:].strip()]
            else:
                chunks.append(p)
        else:
            chunks.append(p)
    chunks = [c for c in chunks if c]

    total_chars = sum(len(c) for c in chunks) or 1
    cues, t = [], 0.0
    for i, c in enumerate(chunks):
        end = duration if i == len(chunks) - 1 else t + duration * (len(c) / total_chars)
        cues.append({"start": round(t, 3), "end": round(end, 3), "text": c})
        t = end
    return cues


def make_gradient_bg(title: str, bg_style: str = "Deep Navy",
                     slide_arr: np.ndarray | None = None) -> np.ndarray:
    """다크 네이비 그라데이션 + 제목 + (선택)강의 슬라이드 카드 + 부기 자리 글로우."""
    center, edge = BG_STYLES.get(bg_style, BG_STYLES["Deep Navy"])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W / 2, H * 0.40
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    d = np.clip(d / (d.max() * 0.85), 0, 1)[..., None]
    arr = (np.array(center, np.float32) * (1 - d) + np.array(edge, np.float32) * d).astype(np.uint8)
    img = Image.fromarray(arr).convert("RGBA")

    # 부기 뒤 은은한 글로우
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gcx, gcy = W // 2, MASCOT_TOP + 200
    gd.ellipse((gcx - 230, gcy - 200, gcx + 230, gcy + 200), fill=(255, 255, 255, 55))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(70)))

    d2 = ImageDraw.Draw(img)
    lab = _font(26, 600)
    lw = d2.textbbox((0, 0), "SHORTFORM", font=lab)[2]
    d2.text(((W - lw) // 2, 70), "SHORTFORM", font=lab, fill=(150, 170, 220))
    tf = _font(58, 800)
    ty = 118
    for line in _wrap(title, tf, W - 2 * MARGIN):
        tw = d2.textbbox((0, 0), line, font=tf)[2]
        d2.text(((W - tw) // 2, ty), line, font=tf, fill=(234, 240, 255))
        ty += tf.size + 8

    # 강의 슬라이드 카드
    if slide_arr is not None:
        slide = Image.fromarray(slide_arr)
        pad = 16
        cx0 = (W - GSLIDE_W) // 2
        card = (cx0 - pad, GSLIDE_TOP - pad,
                cx0 + GSLIDE_W + pad, GSLIDE_TOP + slide.height + pad)
        ImageDraw.Draw(img).rounded_rectangle(card, radius=22, fill=(255, 255, 255, 255))
        img.paste(slide, (cx0, GSLIDE_TOP))

    return np.array(img.convert("RGB"))


def _subtitle_band(text: str) -> np.ndarray:
    """자막 한 cue를 밴드 영역 크기 RGBA(np)로 그린다."""
    band_h = SUB_BAND_BOTTOM - SUB_BAND_TOP
    img = Image.new("RGBA", (W, band_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(62, 700)
    lines = _wrap(text, font, W - 2 * MARGIN - 40)
    line_h = font.size + 16
    total_h = line_h * len(lines)
    widths = [d.textbbox((0, 0), ln, font=font)[2] for ln in lines]

    cy = band_h // 2
    pad_x, pad_y = 38, 24
    bw = max(widths) + 2 * pad_x
    bh = total_h + 2 * pad_y
    bx0 = (W - bw) // 2
    by0 = cy - bh // 2
    d.rounded_rectangle((bx0, by0, bx0 + bw, by0 + bh), radius=20, fill=(12, 20, 44, 210))

    y = cy - total_h // 2
    for ln, lw in zip(lines, widths):
        d.text(((W - lw) // 2, y), ln, font=font, fill=WHITE)
        y += line_h
    return np.array(img)


def build_gradient_video(short, title: str, out_root: str | Path = "output",
                         bg_style: str = "Deep Navy", slide_page: int | None = None,
                         pdf_path: str | Path | None = None, fps: int = 30,
                         progress_cb=None) -> Path:
    """그라데이션 배경 + 강의 슬라이드 + 부기 + 자막 + 진행바로 9:16 영상 합성."""
    out_dir = Path(out_root) / short.id
    audio_meta = json.loads((out_dir / "audio.json").read_text(encoding="utf-8"))
    by_index = {s["index"]: s for s in audio_meta["scenes"]}

    # 슬라이드 렌더(선택)
    slide_arr = None
    if slide_page and pdf_path:
        slide_arr = np.array(render_slide(pdf_path, slide_page, GSLIDE_W))

    bg = make_gradient_bg(title, bg_style, slide_arr)
    mascot = load_mascot(MASCOT_W)
    mh, mw = (mascot.shape[0], mascot.shape[1]) if mascot is not None else (0, 0)
    mx = (W - mw) // 2

    # 대본 기준 자연스러운 자막 cue + 음성 이어붙이기
    audio_clips, cues, offset = [], [], 0.0
    for i, scene in enumerate(short.scenes, start=1):
        meta = by_index.get(i)
        if not meta:
            continue
        audio_clips.append(AudioFileClip(str(out_dir / f"scene-{i:02d}.mp3")))
        for c in natural_cues(scene.narration, meta["duration"]):
            cues.append((offset + c["start"], offset + c["end"], _subtitle_band(c["text"])))
        offset += meta["duration"]

    total = offset
    audio = concatenate_audioclips(audio_clips)

    def frame_function(t):
        frame = bg.copy()
        # 부기(살짝 둥실)
        if mascot is not None:
            my = int(MASCOT_TOP + 10 * math.sin(2 * math.pi * t / 3.0))
            y0, y1 = max(my, 0), min(my + mh, H)
            reg = frame[y0:y1, mx:mx + mw]
            m = mascot[(y0 - my):(y1 - my)]
            a = m[..., 3:4].astype(np.float32) / 255.0
            reg[:] = (reg * (1 - a) + m[..., :3] * a).astype(np.uint8)
        # 자막
        for cs, ce, band in cues:
            if cs <= t < ce:
                region = frame[SUB_BAND_TOP:SUB_BAND_BOTTOM]
                a = band[..., 3:4].astype(np.float32) / 255.0
                region[:] = (region * (1 - a) + band[..., :3] * a).astype(np.uint8)
                break
        # 프로그레스 바
        filled = int(W * min(t / total, 1.0))
        frame[PROGRESS_Y:PROGRESS_Y + PROGRESS_H, :] = (40, 52, 90)
        frame[PROGRESS_Y:PROGRESS_Y + PROGRESS_H, :filled] = ACCENT
        return frame

    if progress_cb:
        progress_cb("영상 렌더", f"{total:.0f}초 분량 인코딩 중")
    clip = VideoClip(frame_function=frame_function, duration=total).with_audio(audio)
    out_path = out_dir / "video.mp4"
    clip.write_videofile(str(out_path), fps=fps, codec="libx264",
                         audio_codec="aac", preset="medium", threads=4, logger=None)
    return out_path


# ──────────────────────────────────────────────────────────────────────────
# 투명 배경 모드: 배경(그라데이션)을 빼고 제목·슬라이드·부기·자막·진행바만 렌더해
# VP9 알파 WebM으로 저장한다. 배경은 대시보드 플레이어가 CSS로 깔아 실시간 교체.
# ──────────────────────────────────────────────────────────────────────────

def _alpha_over(base: np.ndarray, layer: np.ndarray, x: int, y: int) -> None:
    """straight-alpha 'over' 합성: base(RGBA)에 layer(RGBA)를 (x,y) 위치로 올림."""
    h, w = layer.shape[:2]
    y0, y1 = max(y, 0), min(y + h, base.shape[0])
    x0, x1 = max(x, 0), min(x + w, base.shape[1])
    if y1 <= y0 or x1 <= x0:
        return
    lay = layer[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    reg = base[y0:y1, x0:x1].astype(np.float32)
    la = lay[..., 3:4] / 255.0
    ba = reg[..., 3:4] / 255.0
    out_a = la + ba * (1 - la)
    safe = np.where(out_a > 0, out_a, 1.0)
    rgb = (lay[..., :3] * la + reg[..., :3] * ba * (1 - la)) / safe
    base[y0:y1, x0:x1, :3] = rgb.astype(np.uint8)
    base[y0:y1, x0:x1, 3:4] = (out_a * 255).astype(np.uint8)


def _make_fg_base(title: str, slide_arr: np.ndarray | None) -> np.ndarray:
    """투명 배경 + 제목 + 슬라이드 카드 (배경 그라데이션 없음). RGBA 반환."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lab = _font(26, 600)
    lw = d.textbbox((0, 0), "SHORTFORM", font=lab)[2]
    d.text(((W - lw) // 2, 70), "SHORTFORM", font=lab, fill=(176, 192, 230, 255))
    tf = _font(58, 800)
    ty = 118
    for line in _wrap(title, tf, W - 2 * MARGIN):
        tw = d.textbbox((0, 0), line, font=tf)[2]
        d.text(((W - tw) // 2, ty), line, font=tf, fill=(238, 243, 255, 255))
        ty += tf.size + 8
    if slide_arr is not None:
        slide = Image.fromarray(slide_arr).convert("RGBA")
        pad = 16
        cx0 = (W - GSLIDE_W) // 2
        ImageDraw.Draw(img).rounded_rectangle(
            (cx0 - pad, GSLIDE_TOP - pad, cx0 + GSLIDE_W + pad, GSLIDE_TOP + slide.height + pad),
            radius=22, fill=(255, 255, 255, 255))
        img.paste(slide, (cx0, GSLIDE_TOP), slide)
    return np.array(img)


def build_transparent_video(short, title: str, out_root: str | Path = "output",
                            slide_page: int | None = None, pdf_path: str | Path | None = None,
                            fps: int = 30, progress_cb=None) -> Path:
    """배경 투명 9:16 영상(VP9 알파 WebM). 배경색은 재생 시 CSS로 입힌다."""
    out_dir = Path(out_root) / short.id
    audio_meta = json.loads((out_dir / "audio.json").read_text(encoding="utf-8"))
    by_index = {s["index"]: s for s in audio_meta["scenes"]}

    slide_arr = None
    if slide_page and pdf_path:
        slide_arr = np.array(render_slide(pdf_path, slide_page, GSLIDE_W))
    fg = _make_fg_base(title, slide_arr)
    mascot = load_mascot(MASCOT_W)
    mh, mw = (mascot.shape[0], mascot.shape[1]) if mascot is not None else (0, 0)
    mx = (W - mw) // 2

    cues, offset, mp3s = [], 0.0, []
    for i, scene in enumerate(short.scenes, start=1):
        meta = by_index.get(i)
        if not meta:
            continue
        mp3s.append(out_dir / f"scene-{i:02d}.mp3")
        for c in natural_cues(scene.narration, meta["duration"]):
            cues.append((offset + c["start"], offset + c["end"], _subtitle_band(c["text"])))
        offset += meta["duration"]
    total = offset

    # 음성 이어붙이기(임시 파일)
    list_path = out_dir / "_audio_list.txt"
    list_path.write_text("".join(f"file '{p.resolve()}'\n" for p in mp3s), encoding="utf-8")
    audio_tmp = out_dir / "_audio.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
                    "-c", "copy", str(audio_tmp)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    if progress_cb:
        progress_cb("영상 렌더", f"{total:.0f}초 분량 투명 인코딩")

    out_path = out_dir / "video.webm"
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "pipe:0", "-i", str(audio_tmp),
           "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
           "-b:v", "0", "-crf", "32", "-c:a", "libopus", "-b:a", "96k",
           "-shortest", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    nframes = int(total * fps)
    for fi in range(nframes):
        t = fi / fps
        frame = fg.copy()
        if mascot is not None:
            my = int(MASCOT_TOP + 10 * math.sin(2 * math.pi * t / 3.0))
            _alpha_over(frame, mascot, mx, my)
        for cs, ce, band in cues:
            if cs <= t < ce:
                _alpha_over(frame, band, 0, SUB_BAND_TOP)
                break
        filled = int(W * min(t / total, 1.0))
        frame[PROGRESS_Y:PROGRESS_Y + PROGRESS_H, :, :3] = (40, 52, 90)
        frame[PROGRESS_Y:PROGRESS_Y + PROGRESS_H, :, 3] = 255
        frame[PROGRESS_Y:PROGRESS_Y + PROGRESS_H, :filled, :3] = ACCENT
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()

    list_path.unlink(missing_ok=True)
    audio_tmp.unlink(missing_ok=True)
    return out_path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from script_loader import load_script

    script_path = sys.argv[1] if len(sys.argv) > 1 else "data/script.json"
    script = load_script(script_path)
    short = script.shorts[0]
    pdf = ROOT / "input" / f"{script.lecture_id}.pdf"
    print(f"[5] 영상 합성: {short.id}  ({W}x{H}, {len(short.scenes)} scene)")
    out = build_video(short, script.lecture_title, pdf)
    size_mb = out.stat().st_size / 1e6
    print(f"[5] 완료 → {out}  ({size_mb:.1f} MB)")
