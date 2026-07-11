"""
┌──────────────────────────────────────────┐
│  工具函数                                │
│                                          │
│  ISBN 校验和清洗，不依赖项目其他模块。     │
└──────────────────────────────────────────┘
"""

import re


def clean_isbn(text: str) -> str:
  """
  清洗 ISBN 字符串，只保留数字和 X/x。

  "ISBN 978-7-111-12345-6" → "9787111123456"
  去掉常见的连字符、空格和前缀，方便数据库匹配。
  """
  if not text:
    return ''
  return re.sub(r'[^0-9Xx]', '', text.strip())


def is_valid_isbn13(isbn: str) -> bool:
  """
  ISBN-13 校验位验证。

  算法：
    1. 奇数位 ×1，偶数位 ×3，求和
    2. 如果和能被 10 整除则合法
  这是国际标准 ISBN-13 的校验算法。
  """
  if len(isbn) != 13 or not isbn.isdigit():
    return False
  total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn))
  return total % 10 == 0


def is_valid_isbn10(isbn: str) -> bool:
  """
  ISBN-10 校验位验证。

  算法：
    1. 第 1-9 位 ×10, 9, 8, …, 2
    2. 末位如果是 X 则视为 10
    3. 求和后模 11 应为 0
  这是国际标准 ISBN-10 的校验算法。
  """
  isbn = isbn.upper()
  if len(isbn) != 10:
    return False
  if not (isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == 'X')):
    return False
  total = sum(int(c) * (10 - i) for i, c in enumerate(isbn[:9]))
  total += (10 if isbn[9] == 'X' else int(isbn[9]))
  return total % 11 == 0
