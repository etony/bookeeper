"""
┌──────────────────────────────────────────┐
│  封面本地缓存                            │
│                                          │
│  将下载的封面图片缓存到 covers/ 目录，    │
│  避免每次打开详情页都重新下载。            │
│  按魔数嗅探图片类型，支持 JPEG/PNG/WebP。 │
└──────────────────────────────────────────┘
"""

import logging
import os
import tempfile

import requests

from config import Config

LOG = logging.getLogger(__name__)

_COVERS_DIR = os.path.join(os.path.dirname(Config.DB_PATH), 'covers')


def _sniff_media_type(data: bytes) -> str:
  """根据文件头魔数判断图片类型，未知类型返回通用二进制类型"""
  if data[:3] == b'\xff\xd8\xff':
    return 'image/jpeg'
  if data[:8] == b'\x89PNG\r\n\x1a\n':
    return 'image/png'
  if data[:12] == b'RIFF' and data[8:12] == b'WEBP':
    return 'image/webp'
  return 'application/octet-stream'


def get_cover(isbn: str, cover_url: str, referer: str = None) -> tuple:
  """
  获取封面图片，优先从本地缓存读取。

  返回 (bytes, media_type)，无封面返回 (None, None)。
  """
  if not isbn or not cover_url:
    return None, None

  # 先检查缓存
  cache_path = os.path.join(_COVERS_DIR, f'{isbn}.img')
  try:
    if os.path.exists(cache_path):
      with open(cache_path, 'rb') as f:
        data = f.read()
      if data:
        return data, _sniff_media_type(data)
  except OSError as e:
    LOG.warning('读取封面缓存失败: %s', e)

  # 缓存未命中，下载
  try:
    headers = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Referer': referer or 'https://book.douban.com/',
    }
    resp = requests.get(cover_url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.content
    if not data:
      return None, None

    media_type = _sniff_media_type(data)

    # 原子写入缓存
    os.makedirs(_COVERS_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=_COVERS_DIR, suffix='.tmp')
    try:
      os.write(fd, data)
      os.close(fd)
      os.replace(tmp, cache_path)
    except OSError:
      try:
        os.unlink(tmp)
      except OSError:
        pass

    return data, media_type
  except requests.RequestException as e:
    LOG.warning('封面下载失败 %s: %s', isbn, e)
    return None, None
