# -*- coding: utf-8 -*-
"""图书数据模型

定义 Book 数据类，统一全书数据格式，消除魔法数字索引。
在旧代码中图书用 list 表示，通过下标（如 row[3] 表示出版社）访问，可读性差且易出错。
本模块通过 dataclass 封装所有字段，提供清晰的属性名访问，并整合豆瓣 API 数据转换逻辑。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class Book:
  """图书数据模型，替代原始的 list 索引访问

  所有字段均用 str 类型而非 int/float，是为了与表格界面中统一用字符串显示保持一致。
  空值用空字符串 '' 而非 None，可避免在 UI 中处理 NoneType 异常。
  """
  isbn: str = ''          # ISBN 编号，作为图书的唯一标识（主键），用于增删改查时的匹配
  title: str = ''         # 书名
  author: str = ''        # 作者；豆瓣 API 返回的是 list，转换为 "作者1/作者2 译者: 译名" 格式
  publisher: str = ''     # 出版社
  price: str = ''         # 价格（去掉 "CNY"、"元" 等前缀后缀后的纯数字字符串）
  rating: str = '0'       # 豆瓣评分（如 "8.5"），字符串类型，便于 UI 显示
  raters: str = '0'       # 评价人数（如 "1234"），用于计算推荐度
  status: str = '未读'     # 阅读状态：未读 / 在读 / 已读
  shelf: str = '未设置'    # 所在书柜/书架分类
  start_date: str = ''    # 开始阅读日期
  end_date: str = ''      # 读完日期
  cover_url: str = ''     # 封面图片 URL（豆瓣 small 尺寸）
  pubdate: str = ''       # 出版日期（豆瓣格式如 "2024-1"）
  rating_detail: Dict[str, Any] = field(default_factory=dict)  # 豆瓣评分原始详情 dict，保留以备扩展
  douban_url: str = ''    # 豆瓣图书主页 URL
  recommend: str = '0'    # 推荐度（0-10，由 _calc_recommend 根据评分和人数计算）
  pages: str = ''         # 页数（豆瓣返回的字符串，如 "320"）

  def to_row(self) -> List[str]:
    """转为表格行数据（用于写入 CSV/Excel）

    按表格列顺序返回，仅包含表格界面中需要展示的字段，
    cover_url、rating_detail 等元数据不包含在内。
    返回的列表长度与表格列数一致，保证索引对应。
    """
    return [
      self.isbn, self.title, self.author, self.publisher,
      self.price, self.rating, self.raters, self.status, self.shelf,
      self.start_date, self.end_date,
    ]

  @classmethod
  def from_douban(cls, data: Dict[str, Any]) -> Optional['Book']:
    """从豆瓣 API 返回的 dict 创建 Book 实例

    这是一个工厂方法，封装了豆瓣 API 响应到 Book 模型的转换逻辑。
    豆瓣 API 的字段结构与 Book 模型不完全一致（如 author 是 list、rating 是嵌套 dict），
    因此需要逐个字段处理、清洗。

    参数:
      data: 豆瓣 API 返回的图书详情 dict（如 isbn13、title、author、rating 等字段）

    返回:
      构造好的 Book 实例；如果 data 为空、不是 dict 或长度不足则返回 None

    注意:
      空值检查使用 len(data) <= 5 而非空判断，是因为豆瓣 API 即使没有数据也会返回
      少量顶层字段（如 rating 为空 dict），确保只过滤真正无效的响应。
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
    """计算推荐度：(平均分 - 2.5) × ln(评价人数 + 1)

    设计思路：
      - 2.5 为基准分，低于此分视为不值得推荐，直接返回 0
      - 乘以 ln(人数+1) 是为了考虑评价基数的可信度：
        同样 8.5 分，1000 人评价比 10 人评价更有参考价值
      - 结果取整，范围约 0-10，用于排序和筛选

    参数:
      rating: 豆瓣评分字符串（如 "8.5"）
      raters: 评价人数字符串（如 "1234"）

    返回:
      推荐度整数；异常数据（无法转换或溢出）返回 0
    """
    import math
    try:
      avg = float(rating) if rating else 0.0
      num = float(raters) if raters else 0.0
      if avg < 2.5 or num <= 0:
        return 0
      return round((avg - 2.5) * math.log(num + 1))
    except (ValueError, OverflowError):
      return 0
