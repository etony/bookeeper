"""豆瓣 API 服务"""
import json
import logging
import time
from typing import List, Optional
import requests
from config import get_config
from core.models.book import Book

LOG = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1.0

def _request_with_retry(method: str, url: str, session: requests.Session, **kwargs) -> Optional[requests.Response]:
    """带指数退避重试的 HTTP 请求"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.request(method, url, timeout=10, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            LOG.warning(f"请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt))
    return None

class DoubanService:
    """豆瓣图书 API 服务"""
    
    def __init__(self):
        config = get_config()
        self._session = requests.Session()
        self._session.headers.update(config.douban.headers)
        self._api_key = config.douban.api_key
        self._api_key_search = config.douban.api_key_search
        self._isbn_url = f"{config.douban.book_url}/isbn"
        self._search_url = f"{config.douban.book_url}/search"
    
    def get_book_by_isbn(self, isbn: str) -> Optional[Book]:
        """根据 ISBN 获取图书信息"""
        if not isbn or len(isbn) not in (13, 17):
            return None
        
        url = f"{self._isbn_url}/{isbn}"
        resp = _request_with_retry("POST", url, session=self._session,
                                   data={"apikey": self._api_key})
        if resp is None:
            return None
        
        try:
            book = Book.from_douban(resp.json())
            if book:
                book.isbn = isbn
            return book
        except (json.JSONDecodeError, ValueError) as e:
            LOG.error(f"ISBN {isbn} 解析失败: {e}")
        return None
    
    def search_books(self, keyword: str) -> List[Book]:
        """搜索图书"""
        if not keyword:
            return []
        
        resp = _request_with_retry(
            "GET", self._search_url, session=self._session,
            params={"q": keyword, "apikey": self._api_key_search},
        )
        if resp is None:
            return []
        
        try:
            books = []
            for item in resp.json().get("books", []):
                book = Book.from_douban(item)
                if book:
                    books.append(book)
            return books
        except (json.JSONDecodeError, ValueError) as e:
            LOG.error(f"搜索 '{keyword}' 解析失败: {e}")
        return []
    
    def download_image(self, url: str, referer: str = None) -> Optional[bytes]:
        """下载图片"""
        if not url:
            return None
        
        headers = {}
        if referer:
            headers["Referer"] = referer
        
        resp = _request_with_retry("GET", url, session=self._session, headers=headers)
        if resp is None:
            return None
        return resp.content