"""
┌──────────────────────────────────────────┐
│  豆瓣 API 封装层                         │
│                                          │
│  ISBN 查询、关键词搜索、封面下载，         │
│  所有网络请求带指数退避重试，               │
│  避免因网络抖动导致搜索失败。               │
└──────────────────────────────────────────┘
"""

import json
import logging
import time
from typing import List, Optional

import requests

from config import Config
from models.book import Book

LOG = logging.getLogger(__name__)

# 重试参数
_MAX_RETRIES = 3        # 最多重试 3 次
_RETRY_DELAY = 1.0      # 首次重试间隔 1 秒，后续翻倍


def _request_with_retry(method, url, session=None, **kwargs):
  """
  带指数退避重试的 HTTP 请求包装。

  为什么需要重试？
    豆瓣 API 偶尔会超时或返回 5xx 错误，
    短时间重试往往即可恢复正常。

  策略：
    第一次失败 → 等 1 秒
    第二次失败 → 等 2 秒
    第三次失败 → 放弃，返回 None
  """
  requestor = session.request
  for attempt in range(_MAX_RETRIES):
    try:
      resp = requestor(method, url, timeout=10, **kwargs)
      resp.raise_for_status()
      return resp
    except requests.RequestException as e:
      LOG.warning('请求失败 (尝试 %d/%d): %s', attempt + 1, _MAX_RETRIES, e)
      if attempt < _MAX_RETRIES - 1:
        time.sleep(_RETRY_DELAY * (2 ** attempt))
  return None


class DoubanService:
  """
  豆瓣图书 API 服务。

  提供三个功能：
    - get_book_by_isbn(isbn)     → 单本精确查询
    - search_books(keyword)      → 关键词模糊搜索
    - download_image(url)        → 封面图片下载

  内部维护一个 requests.Session 来复用连接，
  并统一添加 User-Agent 等请求头。
  """

  def __init__(self):
    # 使用 Session 连接池，比每次新建连接更高效
    self._session = requests.Session()
    self._session.headers.update(Config.HEADERS)

  def get_book_by_isbn(self, isbn: str) -> Optional[Book]:
    """
    根据 ISBN 从豆瓣获取单本图书信息。

    ISBN 可以是 13 位或 17 位（含连字符），
    函数内会自动传递给豆瓣 API。

    返回 Book 对象，如果 ISBN 无效或网络失败则返回 None。
    """
    if not isbn or len(isbn) not in (13, 17):
      return None

    url = f'{Config.DOUBAN_ISBN_URL}/{isbn}'
    resp = _request_with_retry('POST', url, session=self._session,
                               data={'apikey': Config.DOUBAN_API_KEY})
    if resp is None:
      return None

    try:
      book = Book.from_douban(resp.json())
      if book:
        book.isbn = isbn       # 保证 ISBN 统一用用户输入的格式
      return book
    except (json.JSONDecodeError, ValueError) as e:
      LOG.error(f'ISBN {isbn} 解析失败: {e}')
    return None

  def search_books(self, keyword: str) -> List[Book]:
    """
    按关键词搜索豆瓣图书，返回匹配的 Book 列表。

    搜索范围包括书名、作者等（由豆瓣 API 决定）。
    结果按豆瓣返回的顺序排列，最多约 20 条。
    """
    if not keyword:
      return []

    resp = _request_with_retry(
      'GET', Config.DOUBAN_SEARCH_URL, session=self._session,
      params={'q': keyword, 'apikey': Config.DOUBAN_API_KEY_SEARCH},
    )
    if resp is None:
      return []

    try:
      books = []
      for item in resp.json().get('books', []):
        book = Book.from_douban(item)
        if book:
          books.append(book)
      return books
    except (json.JSONDecodeError, ValueError) as e:
      LOG.error(f'搜索 "{keyword}" 解析失败: {e}')
    return []

  def download_image(self, url: str, referer: str = None) -> Optional[bytes]:
    """
    下载图片，返回原始字节数据。

    主要用于图书封面下载。
    referer 参数用于绕过部分网站的防盗链。
    """
    if not url:
      return None

    headers = {}
    if referer:
      headers['Referer'] = referer

    resp = _request_with_retry('GET', url, session=self._session, headers=headers)
    if resp is None:
      return None
    return resp.content
