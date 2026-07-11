"""
┌──────────────────────────────────────────┐
│  图书领域模型                             │
│                                          │
│  Book 类是数据的核心，贯穿整个应用：        │
│  数据库 ↔ Book ↔ UI 表单 / Web 页面。     │
└──────────────────────────────────────────┘
"""

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


@dataclass
class Book:
  """
  图书领域模型（Python dataclass）。

  dataclass 自动生成 __init__、__repr__、__eq__ 等方法，
  比手写类更简洁，适合做数据传输对象（DTO）。

  所有字段都有默认值，所以可以 Book() 创建空对象，
  再逐个赋值，也可以 Book(isbn='...', title='...') 一步到位。
  """

  # ── 基本信息 ──────────────────────────────────────────
  isbn: str = ''              # ISBN（13 位数字，主键）
  title: str = ''             # 书名
  author: str = ''            # 作者/译者
  publisher: str = ''         # 出版社
  price: str = ''             # 定价（原始字符串，可能是 "CNY 39.00"）
  rating: str = '0'           # 豆瓣平均评分
  raters: str = '0'           # 豆瓣评价人数

  # ── 阅读信息 ──────────────────────────────────────────
  status: str = '默认'         # 阅读状态：默认/计划/已读
  shelf: str = '未设置'        # 所在书柜或位置
  start_date: str = ''        # 购书日期（yyyy-MM-dd）
  end_date: str = ''          # 读完日期（yyyy-MM-dd）

  # ── 豆瓣扩展信息 ──────────────────────────────────────
  cover_url: str = ''         # 封面图片 URL
  pubdate: str = ''           # 出版日期
  # rating_detail 是豆瓣 API 返回的原始评分结构，
  # 包含分项评分如 count、star 等，只用于展示不存数据库
  rating_detail: Dict[str, Any] = field(default_factory=dict)
  douban_url: str = ''        # 豆瓣详情页 URL
  recommend: str = '0'        # 推荐度评分（计算值）
  pages: str = ''             # 总页数

  # ── 数据转换方法 ──────────────────────────────────────

  def to_row(self) -> List[str]:
    """
    转为一行的字符串列表，用于填入 QTableView。

    列顺序和 Config.TABLE_COLUMNS 一致：
    ISBN, 书名, 作者, 出版社, 价格, 评分, 人数, 状态, 书柜, 购书日期, 已读日期
    """
    return [
      self.isbn, self.title, self.author, self.publisher,
      self.price, self.rating, self.raters, self.status, self.shelf,
      self.start_date, self.end_date,
    ]

  def to_dict(self) -> dict:
    """
    转为字典，用于数据库 UPSERT。

    asdict() 是 dataclasses 内置方法，自动展开所有字段。
    """
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict) -> 'Book':
    """
    从字典恢复 Book 对象。

    安全过滤：只取 dataclass 中定义的字段，
    忽略 database 行中多余的列（如 created_at）。
    """
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

  @classmethod
  def from_douban(cls, data: Dict[str, Any]) -> Optional['Book']:
    """
    从豆瓣 API 的 JSON 响应创建 Book 对象。

    豆瓣 API 返回的数据结构比较复杂：
      {
        "isbn13": "9787544291163",
        "title": "百年孤独",
        "author": ["加西亚·马尔克斯"],
        "translator": ["范晔"],
        "publisher": "南海出版公司",
        "price": "CNY 39.50",
        "rating": {"average": "9.2", "numRaters": 12345},
        "images": {"large": "https://...", "medium": "...", "small": "..."},
        "pubdate": "2011-06",
        "alt": "https://book.douban.com/subject/...",
        "pages": "360",
      }
    这个方法负责把上面这种结构扁平化为 Book 的简单字段。

    参数 data 为空或字段太少（<=5）时返回 None。
    """
    if not isinstance(data, dict) or len(data) <= 5:
      return None

    book = cls()
    book.isbn = str(data.get('isbn13', ''))
    book.title = str(data.get('title', ''))

    # 作者和译者都是列表，用 "/" 拼接
    authors = data.get('author', []) or []
    translators = data.get('translator', []) or []
    author_str = '/'.join(authors)
    if translators:
      author_str += ' 译者: ' + '/'.join(translators)
    book.author = author_str

    book.publisher = str(data.get('publisher', ''))
    # 价格通常是 "CNY 39.50" 格式，去掉货币符号
    price = str(data.get('price', ''))
    book.price = price.replace('CNY', '').replace('元', '').strip()

    # 评分是嵌套对象
    rating = data.get('rating', {}) or {}
    book.rating = str(rating.get('average', '0'))
    book.raters = str(rating.get('numRaters', '0'))
    book.rating_detail = rating

    # 封面图片——优先大图，其次中图、小图
    images = data.get('images', {}) or {}
    book.cover_url = str(images.get('large', '') or images.get('medium', '') or images.get('small', ''))

    book.pubdate = str(data.get('pubdate', ''))
    book.douban_url = str(data.get('alt', ''))
    book.pages = str(data.get('pages', ''))
    book.recommend = str(cls._calc_recommend(book.rating, book.raters))
    return book

  # ── 辅助方法 ──────────────────────────────────────────

  @staticmethod
  def _calc_recommend(rating: str, raters: str) -> int:
    """
    综合评分和评价人数计算推荐度。

    公式：(评分 - 2.5) × log(评价人数 + 1)

    为什么用这个公式？
      - 评分太低（<2.5）→ 推荐度为 0
      - 评价人数为 0 → 推荐度为 0（没人评的不推荐）
      - log(人数) 让 1000 人和 10000 人的差距缩小，
        避免高人气书完全碾压小众好书

    示例：
      评分 9.0，10000 人 → (9-2.5) × log(10001) ≈ 6.5 × 9.2 ≈ 60
      评分 8.0，500 人   → (8-2.5) × log(501)   ≈ 5.5 × 6.2 ≈ 34
    """
    try:
      avg = float(rating) if rating else 0.0
      num = float(raters) if raters else 0.0
      if avg < 2.5 or num <= 0:
        return 0
      return round((avg - 2.5) * math.log(num + 1))
    except (ValueError, OverflowError):
      return 0
