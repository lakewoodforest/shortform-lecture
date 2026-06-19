"""
챗봇 API 연결 테스트
- 목적: Qwen 모델이 API로 답을 잘 돌려주는지 '확인'만 하는 용도
- 프로젝트에 넣기 전에, 여기서 먼저 작동되는지 본다
"""

import os
from huggingface_hub import InferenceClient

# 1) 발급받은 허깅페이스 토큰을 여기에 넣기 (따옴표 안)
#    또는 터미널에서 export HF_TOKEN="..." 로 환경변수 설정도 가능
HF_TOKEN = os.environ.get("HF_TOKEN", "여기에_허깅페이스_토큰_붙여넣기")

# 2) 사용할 모델
MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"   # 가벼운 3B로 바꾸려면: Qwen/Qwen2.5-Coder-3B-Instruct

client = InferenceClient(model=MODEL, token=HF_TOKEN)

# 3) 챗봇한테 보낼 질문
질문 = "파이썬에서 리스트랑 튜플의 차이가 뭐야? 초보가 이해하기 쉽게 알려줘."

print("질문:", 질문)
print("-" * 40)
print("답변 받는 중...\n")

응답 = client.chat_completion(
    messages=[
        {"role": "system", "content": "너는 파이썬을 가르치는 친절한 튜터야. 한국어로 쉽게 설명해."},
        {"role": "user", "content": 질문},
    ],
    max_tokens=500,
)

print(응답.choices[0].message.content)
