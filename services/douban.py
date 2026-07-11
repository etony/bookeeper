import json
import logging
import time
from typing import List, Optional

import requests

from config import Config
from models.book import Book

LOG = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


def _request_with_retry(method, url, session=None, **kwargs):
  """HTTP 请求包装：失败时自动重试（指数退避），最多 _MAX_RETRIES 次"""
  requestor = session.request if session else requests.request
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
  """豆瓣 API 封装，支持 ISBN 查询、关键词搜索、封面下载，带重试机制"""

  def __init__(self):
    self._session = requests.Session()
    self._session.headers.update(Config.HEADERS)

  def get_book_by_isbn(self, isbn: str) -> Optional[Book]:
    """根据 ISBN 从豆瓣获取图书信息"""
    if not isbn or len(isbn) not in (13, 17):
      return None
    url = f'{Config.DOUBAN_ISBN_URL}/{isbn}'
    resp = _request_with_retry('POST', url, session=self._session, data={'apikey': Config.DOUBAN_API_KEY})
    if resp is None:
      return None
    try:
      book = Book.from_douban(resp.json())
      if book:
        book.isbn = isbn
      return book
    except (json.JSONDecodeError, ValueError) as e:
      LOG.error(f'ISBN {isbn} 解析失败: {e}')
    return None

  def search_books(self, keyword: str) -> List[Book]:
    """按关键词搜索豆瓣图书"""
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
    """下载图片（用于图书封面），返回原始字节数据"""
    if not url:
      return None
    headers = {}
    if referer:
      headers['Referer'] = referer
    resp = _request_with_retry('GET', url, session=self._session, headers=headers)
    if resp is None:
      return None
    return resp.content
