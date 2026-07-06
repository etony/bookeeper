# -*- coding: utf-8 -*-
"""豆瓣图书 API 封装

提供 ISBN 查询、关键词搜索、图片下载功能。
统一使用 requests.Session 复用连接。
"""

import json
import logging
from typing import List, Optional, Dict, Any

import requests

from config import Config
from models.book import Book

LOG = logging.getLogger(__name__)


class DoubanService:
  """豆瓣 API 服务（单例模式，复用 Session）"""

  def __init__(self):
    self._session = requests.Session()
    self._session.headers.update(Config.HEADERS)

  # ── 公共接口 ──────────────────────────────────

  def get_book_by_isbn(self, isbn: str) -> Optional[Book]:
    """通过 ISBN 查询单本图书"""
    if not isbn or len(isbn) not in (13, 17):
      return None
    url = f'{Config.DOUBAN_ISBN_URL}/{isbn}'
    try:
      resp = self._session.post(url, data={'apikey': Config.DOUBAN_API_KEY}, timeout=10)
      resp.raise_for_status()
      data = resp.json()
      book = Book.from_douban(data)
      if book:
        book.isbn = isbn
      return book
    except requests.RequestException as e:
      LOG.error(f'ISBN {isbn} 请求失败: {e}')
    except (json.JSONDecodeError, KeyError) as e:
      LOG.error(f'ISBN {isbn} 数据解析失败: {e}')
    return None

  def search_books(self, keyword: str) -> List[Book]:
    """按关键词搜索图书"""
    if not keyword:
      return []
    try:
      resp = self._session.get(
        Config.DOUBAN_SEARCH_URL,
        params={'q': keyword, 'apikey': Config.DOUBAN_API_KEY_SEARCH},
        timeout=10,
      )
      resp.raise_for_status()
      books = []
      for item in resp.json().get('books', []):
        book = Book.from_douban(item)
        if book:
          books.append(book)
      return books
    except requests.RequestException as e:
      LOG.error(f'搜索 "{keyword}" 失败: {e}')
    except (json.JSONDecodeError, KeyError) as e:
      LOG.error(f'搜索 "{keyword}" 数据解析失败: {e}')
    return []

  def download_image(self, url: str, referer: str = None) -> Optional[bytes]:
    """下载图片二进制数据"""
    if not url:
      return None
    headers = {}
    if referer:
      headers['Referer'] = referer
    try:
      resp = self._session.get(url, headers=headers, timeout=10)
      resp.raise_for_status()
      return resp.content
    except requests.RequestException as e:
      LOG.warning(f'图片下载失败 {url}: {e}')
    return None
