import os
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def chat(prompt):
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    while True:
        user_input = input("질문: ")
        answer = chat(user_input)
        print("답변:", answer)
