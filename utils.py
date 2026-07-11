import re


def clean_isbn(text: str) -> str:
  """去除 ISBN 字符串中的非数字字符，统一转为纯数字"""
  if not text:
    return ''
  return re.sub(r'[^0-9Xx]', '', text.strip())


def is_valid_isbn13(isbn: str) -> bool:
  """校验 ISBN-13：加权和模 10 验证"""
  if len(isbn) != 13 or not isbn.isdigit():
    return False
  total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn))
  return total % 10 == 0


def is_valid_isbn10(isbn: str) -> bool:
  """校验 ISBN-10：加权和模 11 验证，末位可为 X"""
  isbn = isbn.upper()
  if len(isbn) != 10:
    return False
  if not (isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == 'X')):
    return False
  total = sum(int(c) * (10 - i) for i, c in enumerate(isbn[:9]))
  total += (10 if isbn[9] == 'X' else int(isbn[9]))
  return total % 11 == 0
