# -*- coding: utf-8 -*-
"""豆瓣图书 API 封装

模块功能：
  - get_book_by_isbn(): 通过 ISBN 查询单本图书详情
  - search_books():     按关键词搜索图书列表
  - download_image():   下载图书封面等图片的二进制数据

设计要点：
  - 统一使用 requests.Session 实例复用 TCP 连接，减少握手开销
  - Session 在 __init__ 中初始化后，所有 API 调用共享同一连接池
  - 所有网络请求均设置 10 秒超时，防止长时间阻塞
  - 异常统一捕获 log 后返回 None/空列表，避免上层调用者处理异常
"""

import json
import logging
from typing import List, Optional, Dict, Any

import requests

from config import Config
from models.book import Book

LOG = logging.getLogger(__name__)


class DoubanService:
  """豆瓣 API 服务

  复用 requests.Session 实例，避免每次请求都重新建立 TCP 连接。
  主要用于 get_book_by_isbn / search_books / download_image 三个场景。
  注意：当前没有实现单例模式，每次实例化都会新建 Session。
  """

  def __init__(self):
    """初始化 Session 并设置通用请求头

    Session 实例创建后，所有 HTTP 请求共享以下资源：
      - TCP 连接池（默认最多 10 个连接）
      - Cookie 持久化
      - 默认请求头（从 Config.HEADERS 读取，含 User-Agent 等）
    """
    self._session = requests.Session()
    self._session.headers.update(Config.HEADERS)

  # ── 公共接口 ──────────────────────────────────

  def get_book_by_isbn(self, isbn: str) -> Optional[Book]:
    """通过 ISBN 查询单本图书

    向豆瓣 API 发送 POST 请求（携带 apikey），获取图书 JSON 数据。
    成功后将 ISBN 回填到 Book 对象（豆瓣返回的数据可能不含 ISBN 字段）。

    参数：
      isbn: 13 位纯数字 ISBN 或 17 位带连字符 ISBN（如 978-7-XXX-XXXXX-X）

    返回：
      成功返回 Book 对象，失败返回 None

    注意事项：
      - 调用前应使用 utils.clean_isbn 清洗 ISBN 格式
      - 豆瓣 API 的 ISBN URL 末尾不带 /，此处拼接 /
      - apikey 使用 Config.DOUBAN_API_KEY（搜索用另一个 key）
    """
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
    """按关键词搜索图书

    向豆瓣搜索 API 发送 GET 请求，使用独立的 apikey（Config.DOUBAN_API_KEY_SEARCH）。

    参数：
      keyword: 搜索关键词（书名、作者等）

    返回：
      匹配的 Book 对象列表，失败或空关键词时返回 []（永不返回 None）

    注意事项：
      - 豆瓣搜索接口可能返回大量结果，此处未做分页控制
      - 搜索用 apikey 与 ISBN 查询用的 apikey 不同，见 Config 配置
    """
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
    """下载图片二进制数据

    用于下载豆瓣图书封面等图片。部分图片服务器需要 Referer 头才返回数据，
    因此提供可选的 referer 参数以应对防盗链。

    参数：
      url:     图片的完整 URL
      referer: 可选的 Referer 请求头（防盗链场景使用）

    返回：
      图片的原始二进制内容（bytes），失败返回 None
    """
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
