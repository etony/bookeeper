import re


def clean_isbn(text: str) -> str:
  return re.sub(r'[^0-9Xx]', '', text.strip())


def is_valid_isbn13(isbn: str) -> bool:
  if len(isbn) != 13 or not isbn.isdigit():
    return False
  total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn))
  return total % 10 == 0


def is_valid_isbn10(isbn: str) -> bool:
  isbn = isbn.upper()
  if len(isbn) != 10:
    return False
  if not (isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == 'X')):
    return False
  total = sum(int(c) * (10 - i) for i, c in enumerate(isbn[:9]))
  total += (10 if isbn[9] == 'X' else int(isbn[9]))
  return total % 11 == 0
