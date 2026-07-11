import os
import json

# 加载或生成 config.json（用户可编辑的 API key 配置文件）
_path = os.path.join(os.path.dirname(__file__), 'config.json')
_defaults = {
  'DOUBAN_API_KEY': '0ab215a8b1977939201640fa14c66bab',
  'DOUBAN_API_KEY_SEARCH': '0ac44ae016490db2204ce0a042db2916',
}
if os.path.exists(_path):
  with open(_path, encoding='utf-8') as f:
    _defaults.update(json.load(f))
else:
  with open(_path, 'w', encoding='utf-8') as f:
    json.dump(_defaults, f, indent=2, ensure_ascii=False)
  print(f'已生成配置文件 {_path}，可修改其中的 API key')


class Config:
  """全局静态配置，所有模块通过此类引用常量"""

  APP_NAME = 'Bookeeper'
  APP_VERSION = '3.0.0'
  DB_PATH = os.path.join(os.path.dirname(__file__), 'books.db')

  # 豆瓣 API
  DOUBAN_API_KEY = _defaults['DOUBAN_API_KEY']
  DOUBAN_API_KEY_SEARCH = _defaults['DOUBAN_API_KEY_SEARCH']
  DOUBAN_BOOK_URL = 'https://api.douban.com/v2/book'
  DOUBAN_ISBN_URL = f'{DOUBAN_BOOK_URL}/isbn'
  DOUBAN_SEARCH_URL = f'{DOUBAN_BOOK_URL}/search'
  HEADERS = {
    'Referer': 'https://m.douban.com/tv/american',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) '
                  'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1',
  }

  # 界面尺寸与列定义
  TABLE_COLUMNS = ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']
  MAIN_WINDOW_SIZE = (950, 1000)
  SEARCH_DIALOG_SIZE = (500, 420)
  DETAIL_DIALOG_SIZE = (520, 500)

  # 图书状态与书柜
  STATUSES = ['默认', '计划', '已读']
  DEFAULT_STATUS = '默认'
  DEFAULT_SHELF = '未设置'

  # 网络与备份
  WEB_PORT = 8899
  BACKUP_KEEP = 30
  BACKUP_INTERVAL_MS = 300000
