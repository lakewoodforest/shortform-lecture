"""
live_bank.py — 실전 코딩 문제 은행 (전체 코드 작성 + 브라우저 실행 채점).

채점은 프론트의 Pyodide(브라우저 내 파이썬)가 수행한다:
  1. 사용자가 작성한 코드를 exec
  2. tests의 call을 eval 해서 expected(repr 문자열)와 비교
     - 넘파이 배열은 tolist()로 변환 후 비교
     - 실수는 오차 허용(isclose) 비교

형식: prompt / starter(시작 코드) / tests[{call, expected}]
      / solution(참고 정답) / needs(필요 패키지) / difficulty / topic
"""
from __future__ import annotations
from typing import Dict, List

LIVE_BANK: Dict[str, List[dict]] = {

"파이썬 입문": [
    {"topic": "변수와 문자열", "difficulty": "쉬움",
     "prompt": "이름을 받아 '안녕하세요, OO님!' 형태의 문자열을 반환하는 함수 greet(name)을 작성하세요.",
     "starter": "def greet(name):\n    # 여기에 작성하세요\n    ",
     "tests": [
         {"call": "greet('한성')", "expected": "'안녕하세요, 한성님!'"},
         {"call": "greet('부기')", "expected": "'안녕하세요, 부기님!'"},
     ],
     "solution": "def greet(name):\n    return '안녕하세요, ' + name + '님!'"},
    {"topic": "연산자", "difficulty": "쉬움",
     "prompt": "반지름 r를 받아 원의 면적(3.14 * r * r)을 반환하는 함수 circle_area(r)를 작성하세요.",
     "starter": "def circle_area(r):\n    # 여기에 작성하세요\n    ",
     "tests": [
         {"call": "circle_area(5)", "expected": "78.5"},
         {"call": "circle_area(1)", "expected": "3.14"},
     ],
     "solution": "def circle_area(r):\n    return 3.14 * r * r"},
    {"topic": "연산자", "difficulty": "보통",
     "prompt": "두 정수 a, b를 받아 (몫, 나머지) 튜플을 반환하는 함수 divide(a, b)를 작성하세요.",
     "starter": "def divide(a, b):\n    # // 와 % 를 사용해 보세요\n    ",
     "tests": [
         {"call": "divide(7, 2)", "expected": "(3, 1)"},
         {"call": "divide(10, 3)", "expected": "(3, 1)"},
         {"call": "divide(8, 4)", "expected": "(2, 0)"},
     ],
     "solution": "def divide(a, b):\n    return a // b, a % b"},
    {"topic": "자료형", "difficulty": "보통",
     "prompt": "숫자로 된 문자열 두 개를 받아 정수로 변환한 합을 반환하는 함수 str_sum(s1, s2)을 작성하세요.",
     "starter": "def str_sum(s1, s2):\n    # int() 변환을 잊지 마세요\n    ",
     "tests": [
         {"call": "str_sum('7', '3')", "expected": "10"},
         {"call": "str_sum('100', '200')", "expected": "300"},
     ],
     "solution": "def str_sum(s1, s2):\n    return int(s1) + int(s2)"},
],

"파이썬 중급": [
    {"topic": "조건문", "difficulty": "보통",
     "prompt": "점수를 받아 90 이상 'A', 80 이상 'B', 60 이상 'C', 그 외 'F'를 반환하는 함수 grade(score)를 작성하세요.",
     "starter": "def grade(score):\n    # if-elif-else 를 사용하세요\n    ",
     "tests": [
         {"call": "grade(95)", "expected": "'A'"},
         {"call": "grade(85)", "expected": "'B'"},
         {"call": "grade(70)", "expected": "'C'"},
         {"call": "grade(50)", "expected": "'F'"},
     ],
     "solution": "def grade(score):\n    if score >= 90:\n        return 'A'\n    elif score >= 80:\n        return 'B'\n    elif score >= 60:\n        return 'C'\n    else:\n        return 'F'"},
    {"topic": "반복문", "difficulty": "보통",
     "prompt": "1부터 n까지의 합을 반복문으로 계산해 반환하는 함수 sum_to(n)을 작성하세요.",
     "starter": "def sum_to(n):\n    total = 0\n    # for 또는 while 로 반복하세요\n    ",
     "tests": [
         {"call": "sum_to(10)", "expected": "55"},
         {"call": "sum_to(100)", "expected": "5050"},
         {"call": "sum_to(1)", "expected": "1"},
     ],
     "solution": "def sum_to(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total"},
    {"topic": "리스트", "difficulty": "보통",
     "prompt": "정수 리스트에서 짝수의 개수를 세어 반환하는 함수 count_even(nums)를 작성하세요.",
     "starter": "def count_even(nums):\n    # % 2 == 0 으로 짝수를 판별하세요\n    ",
     "tests": [
         {"call": "count_even([1, 2, 3, 4])", "expected": "2"},
         {"call": "count_even([1, 3, 5])", "expected": "0"},
         {"call": "count_even([2, 4, 6, 8])", "expected": "4"},
     ],
     "solution": "def count_even(nums):\n    count = 0\n    for n in nums:\n        if n % 2 == 0:\n            count += 1\n    return count"},
    {"topic": "리스트", "difficulty": "어려움",
     "prompt": "단어 리스트를 받아 각 단어의 길이 리스트를 반환하는 함수 word_lengths(words)를 작성하세요. (리스트 함축을 써 보세요)",
     "starter": "def word_lengths(words):\n    # [식 for 변수 in 리스트] 형태\n    ",
     "tests": [
         {"call": "word_lengths(['hi', 'python'])", "expected": "[2, 6]"},
         {"call": "word_lengths(['a', 'ab', 'abc'])", "expected": "[1, 2, 3]"},
     ],
     "solution": "def word_lengths(words):\n    return [len(w) for w in words]"},
],

"파이썬 고급 v1": [
    {"topic": "인자와 반환값", "difficulty": "보통",
     "prompt": "start부터 end까지의 합을 반환하는 함수 get_sum(start, end)을 작성하세요.",
     "starter": "def get_sum(start, end):\n    # range(start, end + 1) 에 주의하세요\n    ",
     "tests": [
         {"call": "get_sum(1, 10)", "expected": "55"},
         {"call": "get_sum(5, 7)", "expected": "18"},
     ],
     "solution": "def get_sum(start, end):\n    total = 0\n    for i in range(start, end + 1):\n        total += i\n    return total"},
    {"topic": "인자와 반환값", "difficulty": "보통",
     "prompt": "두 수를 받아 (합, 차, 곱) 세 값을 한 번에 반환하는 함수 calc(a, b)를 작성하세요.",
     "starter": "def calc(a, b):\n    # return 값1, 값2, 값3 형태로 여러 값을 반환할 수 있어요\n    ",
     "tests": [
         {"call": "calc(4, 2)", "expected": "(6, 2, 8)"},
         {"call": "calc(10, 5)", "expected": "(15, 5, 50)"},
     ],
     "solution": "def calc(a, b):\n    return a + b, a - b, a * b"},
    {"topic": "디폴트 인자", "difficulty": "보통",
     "prompt": "버거 이름과 피클 여부(기본값 True)를 받아 (버거, 피클여부) 튜플을 반환하는 함수 order(burger, pickle=True)를 작성하세요.",
     "starter": "def order(burger, pickle=True):\n    # 디폴트 인자를 그대로 활용하세요\n    ",
     "tests": [
         {"call": "order('불고기버거')", "expected": "('불고기버거', True)"},
         {"call": "order('치즈버거', False)", "expected": "('치즈버거', False)"},
     ],
     "solution": "def order(burger, pickle=True):\n    return burger, pickle"},
    {"topic": "재귀 함수", "difficulty": "어려움",
     "prompt": "재귀 호출로 n!(팩토리얼)을 계산하는 함수 factorial(n)을 작성하세요. (1! = 1이 종료 조건)",
     "starter": "def factorial(n):\n    # 자기 자신을 호출해 보세요\n    ",
     "tests": [
         {"call": "factorial(5)", "expected": "120"},
         {"call": "factorial(1)", "expected": "1"},
         {"call": "factorial(3)", "expected": "6"},
     ],
     "solution": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)"},
],

"파이썬 고급 v2": [
    {"topic": "넘파이 기초", "difficulty": "보통", "needs": ["numpy"],
     "prompt": "두 리스트를 넘파이 배열로 바꿔 벡터합을 구한 뒤, 리스트로 변환해 반환하는 함수 add_arrays(a, b)를 작성하세요.",
     "starter": "import numpy as np\n\ndef add_arrays(a, b):\n    # np.array() 로 변환 후 더하고 .tolist() 로 반환\n    ",
     "tests": [
         {"call": "add_arrays([10, 20], [30, 40])", "expected": "[40, 60]"},
         {"call": "add_arrays([1, 2, 3], [4, 5, 6])", "expected": "[5, 7, 9]"},
     ],
     "solution": "import numpy as np\n\ndef add_arrays(a, b):\n    return (np.array(a) + np.array(b)).tolist()"},
    {"topic": "배열 연산", "difficulty": "보통", "needs": ["numpy"],
     "prompt": "월급 리스트와 인상액을 받아 모든 요소에 인상액을 더한 리스트를 반환하는 함수 raise_salary(salary, amount)를 작성하세요. (넘파이 활용)",
     "starter": "import numpy as np\n\ndef raise_salary(salary, amount):\n    # 배열에 수를 더하면 모든 요소에 적용돼요\n    ",
     "tests": [
         {"call": "raise_salary([220, 250, 230], 100)", "expected": "[320, 350, 330]"},
         {"call": "raise_salary([100], 50)", "expected": "[150]"},
     ],
     "solution": "import numpy as np\n\ndef raise_salary(salary, amount):\n    return (np.array(salary) + amount).tolist()"},
    {"topic": "논리 인덱싱", "difficulty": "어려움", "needs": ["numpy"],
     "prompt": "정수 리스트에서 논리 인덱싱으로 짝수만 골라 리스트로 반환하는 함수 evens(nums)를 작성하세요.",
     "starter": "import numpy as np\n\ndef evens(nums):\n    arr = np.array(nums)\n    # arr[조건] 형태의 논리 인덱싱을 사용하세요\n    ",
     "tests": [
         {"call": "evens([1, 2, 3, 4])", "expected": "[2, 4]"},
         {"call": "evens([5, 7, 9])", "expected": "[]"},
         {"call": "evens([2, 4, 6])", "expected": "[2, 4, 6]"},
     ],
     "solution": "import numpy as np\n\ndef evens(nums):\n    arr = np.array(nums)\n    return arr[arr % 2 == 0].tolist()"},
    {"topic": "난수와 통계", "difficulty": "어려움", "needs": ["numpy"],
     "prompt": "리스트를 받아 (평균, 최댓값) 튜플을 반환하는 함수 stats(nums)를 작성하세요. 평균은 float로요. (np.mean, np.max 활용)",
     "starter": "import numpy as np\n\ndef stats(nums):\n    # float(), int() 로 파이썬 기본형으로 바꿔 반환하세요\n    ",
     "tests": [
         {"call": "stats([1, 2, 3])", "expected": "(2.0, 3)"},
         {"call": "stats([10, 20, 30, 40])", "expected": "(25.0, 40)"},
     ],
     "solution": "import numpy as np\n\ndef stats(nums):\n    arr = np.array(nums)\n    return float(np.mean(arr)), int(np.max(arr))"},
],
}
