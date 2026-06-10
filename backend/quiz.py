"""
quiz.py — 파이썬 연습문제 생성 로직.

문제 데이터는 backend/quiz_bank.py 에 있다 (강의자료 기반, 영상 섹터와 동일 구성).
지금은 내장 문제 은행으로 동작하고, 나중에 허깅페이스 모델을 붙이면
_generate_with_model()이 대신 동작한다.

연동 방법(추후):
    1. 환경변수 QUIZ_HF_MODEL 에 모델 ID 지정
       예) export QUIZ_HF_MODEL="Qwen/Qwen2.5-1.5B-Instruct"
    2. _generate_with_model() 안의 TODO 채우기
    3. 반환 형식은 문제 은행과 동일한 dict 리스트면 프론트 수정 불필요
"""
from __future__ import annotations
import os
import random
from typing import List

from .quiz_bank import QUESTION_BANK

HF_MODEL_ID = os.environ.get("QUIZ_HF_MODEL", "")

DIFFICULTIES = ["전체", "쉬움", "보통", "어려움"]

COURSES = [{"name": c, "topics": ["전체"] + list(QUESTION_BANK[c].keys()),
            "total": sum(len(v) for v in QUESTION_BANK[c].values())}
           for c in QUESTION_BANK]


def generate_quiz(course: str = "파이썬 입문", topic: str = "전체",
                  difficulty: str = "전체", count: int = 5) -> dict:
    """문제 세트 생성. HF 모델이 설정돼 있으면 모델, 아니면 내장 은행."""
    count = max(1, min(count, 20))
    if HF_MODEL_ID:
        try:
            qs = _generate_with_model(course, topic, difficulty, count)
            return {"source": "model", "model": HF_MODEL_ID, "questions": qs}
        except NotImplementedError:
            pass  # 아직 연동 전 → 은행으로 폴백
    return {"source": "bank", "model": "",
            "questions": _from_bank(course, topic, difficulty, count)}


def _from_bank(course: str, topic: str, difficulty: str, count: int) -> List[dict]:
    bank = QUESTION_BANK.get(course) or next(iter(QUESTION_BANK.values()))
    pool: List[dict] = []
    topics = bank.keys() if topic == "전체" else [topic]
    for t in topics:
        for q in bank.get(t, []):
            pool.append({**q, "topic": t})

    if difficulty != "전체":
        filtered = [q for q in pool if q["difficulty"] == difficulty]
        if filtered:
            pool = filtered

    random.shuffle(pool)
    picked = pool[:count]

    # 보기 순서도 매번 섞어 준다
    out = []
    for q in picked:
        idxs = list(range(len(q["options"])))
        random.shuffle(idxs)
        out.append({
            "q": q["q"],
            "code": q.get("code", ""),
            "options": [q["options"][i] for i in idxs],
            "answer": idxs.index(q["answer"]),
            "explain": q["explain"],
            "difficulty": q["difficulty"],
            "topic": q["topic"],
        })
    return out


def _generate_with_model(course: str, topic: str, difficulty: str,
                         count: int) -> List[dict]:
    """허깅페이스 모델 연동 지점 (추후 작업).

    TODO(사용자):
        from huggingface_hub import InferenceClient  (또는 transformers pipeline)
        프롬프트로 course/topic/difficulty/count를 넘기고,
        _from_bank()와 같은 형식의 dict 리스트를 반환하면
        프론트는 수정 없이 그대로 동작한다.
        필요 키: q, code(없으면 ""), options(4개), answer(정답 인덱스),
                 explain, difficulty, topic
    """
    raise NotImplementedError("허깅페이스 모델 연동 전입니다.")
