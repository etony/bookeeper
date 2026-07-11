from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


@dataclass
class Book:
  """图书领域模型，映射数据库字段并提供豆瓣 API 数据转换"""
  isbn: str = ''
  title: str = ''
  author: str = ''
  publisher: str = ''
  price: str = ''
  rating: str = '0'
  raters: str = '0'
  status: str = '默认'
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
    """转为表格行的字符串列表"""
    return [
      self.isbn, self.title, self.author, self.publisher,
      self.price, self.rating, self.raters, self.status, self.shelf,
      self.start_date, self.end_date,
    ]

  def to_dict(self) -> dict:
    """转为字典（用于数据库 UPSERT）"""
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict) -> 'Book':
    """从字典恢复 Book 对象，仅保留 dataclass 中定义的字段"""
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

  @classmethod
  def from_douban(cls, data: Dict[str, Any]) -> Optional['Book']:
    """从豆瓣 API 响应创建 Book 对象"""
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
    book.cover_url = str(images.get('large', '') or images.get('medium', '') or images.get('small', ''))
    book.pubdate = str(data.get('pubdate', ''))
    book.douban_url = str(data.get('alt', ''))
    book.pages = str(data.get('pages', ''))
    book.recommend = str(cls._calc_recommend(book.rating, book.raters))
    return book

  @staticmethod
  def _calc_recommend(rating: str, raters: str) -> int:
    """综合评分和评价人数计算推荐指数：(评分 - 2.5) * log(人数 + 1)"""
    import math
    try:
      avg = float(rating) if rating else 0.0
      num = float(raters) if raters else 0.0
      if avg < 2.5 or num <= 0:
        return 0
      return round((avg - 2.5) * math.log(num + 1))
    except (ValueError, OverflowError):
      return 0
