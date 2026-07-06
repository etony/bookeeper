# -*- coding: utf-8 -*-
"""图书数据模型

定义 Book 数据类，统一全书数据格式，消除魔法数字索引。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class Book:
  """图书数据模型，替代原始的 list 索引访问"""
  isbn: str = ''
  title: str = ''
  author: str = ''
  publisher: str = ''
  price: str = ''
  rating: str = '0'
  raters: str = '0'
  status: str = '未读'
  shelf: str = '未设置'
  start_date: str = ''
  end_date: str = ''
  cover_url: str = ''
  pubdate: str = ''
  rating_detail: Dict[str, Any] = field(default_factory=dict)
  douban_url: str = ''
  recommend: str = '0'
  pages: str = ''

  def to_row(self) -> List[str]:
    """转为表格行数据"""
    return [
      self.isbn, self.title, self.author, self.publisher,
      self.price, self.rating, self.raters, self.status, self.shelf,
      self.start_date, self.end_date,
    ]

  @classmethod
  def from_douban(cls, data: Dict[str, Any]) -> Optional['Book']:
    """从豆瓣 API 返回的 dict 创建 Book

    传入空 dict 或残缺数据时返回 None。
    """
    if not data or not isinstance(data, dict) or len(data) <= 5:
      return None

    book = cls()
    book.isbn = str(data.get('isbn13', ''))
    book.title = str(data.get('title', ''))

    authors = data.get('author', []) or []
    translators = data.get('translator', []) or []
    author_str = '/'.join(authors)
    if translators:
      author_str += ' 译者: ' + '/'.join(translators)
    book.author = author_str
    book.publisher = str(data.get('publisher', ''))

    price = str(data.get('price', ''))
    book.price = price.replace('CNY', '').replace('元', '').strip()

    rating = data.get('rating', {}) or {}
    book.rating = str(rating.get('average', '0'))
    book.raters = str(rating.get('numRaters', '0'))
    book.rating_detail = rating

    images = data.get('images', {}) or {}
    book.cover_url = str(images.get('small', ''))
    book.pubdate = str(data.get('pubdate', ''))
    book.douban_url = str(data.get('alt', ''))
    book.pages = str(data.get('pages', ''))

    book.recommend = str(cls._calc_recommend(book.rating, book.raters))
    return book

  @staticmethod
  def _calc_recommend(rating: str, raters: str) -> int:
    """计算推荐度：(平均分 - 2.5) × ln(评价人数 + 1)"""
    import math
    try:
      avg = float(rating) if rating else 0.0
      num = float(raters) if raters else 0.0
      if avg < 2.5 or num <= 0:
        return 0
      return round((avg - 2.5) * math.log(num + 1))
    except (ValueError, OverflowError):
      return 0
