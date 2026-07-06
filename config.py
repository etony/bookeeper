import os
import json


def _load_api_keys() -> dict:
  """从同级 config.json 加载 API key，不存在则生成默认文件"""
  path = os.path.join(os.path.dirname(__file__), 'config.json')
  defaults = {
    'DOUBAN_API_KEY': '0ab215a8b1977939201640fa14c66bab',
    'DOUBAN_API_KEY_SEARCH': '0ac44ae016490db2204ce0a042db2916',
  }
  if os.path.exists(path):
    with open(path, encoding='utf-8') as f:
      overrides = json.load(f)
    defaults.update(overrides)
  else:
    with open(path, 'w', encoding='utf-8') as f:
      json.dump(defaults, f, indent=2, ensure_ascii=False)
    print(f'已生成配置文件 {path}，可修改其中的 API key')
  return defaults


_api_keys = _load_api_keys()


class Config:
  APP_NAME = 'Bookeeper'
  APP_VERSION = '2.0.0'
  APP_ICON = 'book2.png'

  DOUBAN_API_KEY = _api_keys['DOUBAN_API_KEY']
  DOUBAN_API_KEY_SEARCH = _api_keys['DOUBAN_API_KEY_SEARCH']
  DOUBAN_BOOK_URL = 'https://api.douban.com/v2/book'
  DOUBAN_ISBN_URL = f'{DOUBAN_BOOK_URL}/isbn'
  DOUBAN_SEARCH_URL = f'{DOUBAN_BOOK_URL}/search'
  HEADERS = {
    'Referer': 'https://m.douban.com/tv/american',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1',
  }

  MAIN_WINDOW_SIZE = (950, 720)
  SEARCH_DIALOG_SIZE = (500, 420)
  DETAIL_DIALOG_SIZE = (520, 500)

  TABLE_COLUMNS = ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']
  STATUSES = ['未读', '在读', '已读']
  DEFAULT_STATUS = '未读'
  CATEGORIES = ['默认分类', '计划', '已读']
  DEFAULT_CATEGORY = '计划'
  DEFAULT_SHELF = '未设置'

  COVER_CACHE_DIR = 'cover_cache'
  API_REQUEST_DELAY = 1.0
  WEB_PORT = 8899
