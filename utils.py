"""
Bookeeper - 工具函数模块

提供 ISBN（国际标准书号）相关的字符串清洗和校验工具函数。
功能覆盖 ISBN-10 和 ISBN-13 两种格式的验证，以及从任意输入
（如带连字符或空格的字符串）中提取纯数字 ISBN。

所有函数为纯函数，不依赖外部状态，可安全在任意上下文中调用。
"""

import re


def clean_isbn(text: str) -> str:
  """
  从输入字符串中提取纯 ISBN 字符。

  移除所有非数字、非字母 X/x 的字符（如连字符、空格、中文等），
  保留字母并转换为大写场景由调用方处理。

  Args:
    text: 原始输入字符串，例如 "978-7-111-12345-6" 或 "ISBN 9781234567890"

  Returns:
    仅包含数字和大写 X 的字符串，例如 "9787111123456"

  设计意图：
    - 统一处理用户输入的各种 ISBN 格式（带连字符、空格、前缀等）
    - 避免在各处重复编写正则清洗逻辑
  """
  if not text:
    return ''
  return re.sub(r'[^0-9Xx]', '', text.strip())


def is_valid_isbn13(isbn: str) -> bool:
  """
  校验 ISBN-13 是否合法（使用模 10 加权校验算法）。

  校验规则：
    对前 12 位数字，奇数位（索引 0、2、4...）权重为 1，
    偶数位（索引 1、3、5...）权重为 3，求和后模 10 应为 0。
    （最后一位是校验位，与加权结果共同满足模 10 条件）

  Args:
    isbn: 纯 13 位数字字符串（需先经 clean_isbn 处理）

  Returns:
    合法返回 True，否则返回 False

  注意事项：
    - 输入必须为 13 位纯数字，不含 X（ISBN-13 校验位只用数字）
    - 此函数不自动调用 clean_isbn，调用方需保证输入已清洗
  """
  if len(isbn) != 13 or not isbn.isdigit():
    return False
  # 奇数位权重 1，偶数位权重 3，计算加权和
  total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn))
  return total % 10 == 0


def is_valid_isbn10(isbn: str) -> bool:
  """
  校验 ISBN-10 是否合法（使用模 11 加权校验算法）。

  校验规则：
    前 9 位数字分别乘以权重 10、9、8 ... 2，
    第 10 位（校验位）乘以 1（若为 X 则视为 10），
    总和模 11 应为 0。

  Args:
    isbn: 清洗后的字符串（允许最后一位为 X 或 x，需先经 clean_isbn 处理）

  Returns:
    合法返回 True，否则返回 False

  注意事项：
    - ISBN-10 校验位可以是数字或大写 X（代表 10）
    - 函数内部自动将输入转为大写，故小写 x 也能通过
    - 此函数不自动调用 clean_isbn，调用方需保证输入已清洗
  """
  isbn = isbn.upper()
  if len(isbn) != 10:
    return False
  # 前 9 位必须为数字，最后一位可以是数字或 X
  if not (isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == 'X')):
    return False
  # 前 9 位权重 10~2
  total = sum(int(c) * (10 - i) for i, c in enumerate(isbn[:9]))
  # 第 10 位若为 X 则值为 10
  total += (10 if isbn[9] == 'X' else int(isbn[9]))
  return total % 11 == 0
