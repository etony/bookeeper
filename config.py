"""
┌──────────────────────────────────────────┐
│  全局配置模块                             │
│                                          │
│  所有模块通过 Config 类引用常量，          │
│  不直接硬编码路径和参数。                  │
└──────────────────────────────────────────┘
"""

import os
import json

# ── 从 config.json 加载用户配置 ──────────────────────────────
# 如果 config.json 不存在，会用默认 API key 自动生成一个，
# 方便用户修改自己的 key。config.json 不在 git 追踪范围内。
_path = os.path.join(os.path.dirname(__file__), 'config.json')
_defaults = {
  'DOUBAN_API_KEY': '0ab215a8b1977939201640fa14c66bab',
  'DOUBAN_API_KEY_SEARCH': '0ac44ae016490db2204ce0a042db2916',
}
if os.path.exists(_path):
  # 已有配置文件 → 读取并合并到默认值（用户配置优先）
  with open(_path, encoding='utf-8') as f:
    _defaults.update(json.load(f))
else:
  # 首次运行 → 生成配置文件供用户编辑
  with open(_path, 'w', encoding='utf-8') as f:
    json.dump(_defaults, f, indent=2, ensure_ascii=False)
  print(f'已生成配置文件 {_path}，可修改其中的 API key')


class Config:
  """
  全局静态配置。

  用法：Config.DB_PATH、Config.WEB_PORT……
  所有配置集中在此，方便统一修改和维护。
  """

  # ── 应用基本信息 ──────────────────────────────────────────
  APP_NAME = 'Bookeeper'
  APP_VERSION = '3.0.0'
  DB_PATH = os.path.join(os.path.dirname(__file__), 'books.db')

  # ── 豆瓣 API ──────────────────────────────────────────────
  # 豆瓣 v2 API 的 key 和端点 URL
  DOUBAN_API_KEY = _defaults['DOUBAN_API_KEY']
  DOUBAN_API_KEY_SEARCH = _defaults['DOUBAN_API_KEY_SEARCH']
  DOUBAN_BOOK_URL = 'https://api.douban.com/v2/book'
  DOUBAN_ISBN_URL = f'{DOUBAN_BOOK_URL}/isbn'
  DOUBAN_SEARCH_URL = f'{DOUBAN_BOOK_URL}/search'
  # 豆瓣要求模拟移动端 User-Agent 才能正常返回数据
  HEADERS = {
    'Referer': 'https://m.douban.com/tv/american',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) '
                  'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1',
  }

  # ── 界面尺寸与列定义 ──────────────────────────────────────
  TABLE_COLUMNS = ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']
  MAIN_WINDOW_SIZE = (950, 1000)
  SEARCH_DIALOG_SIZE = (500, 420)
  DETAIL_DIALOG_SIZE = (520, 500)

  # ── 图书状态与书柜 ────────────────────────────────────────
  STATUSES = ['默认', '计划', '已读']
  DEFAULT_STATUS = '默认'
  DEFAULT_SHELF = '未设置'

  # ── 网络与备份 ────────────────────────────────────────────
  WEB_PORT = 8899                      # 内嵌 Web 服务的端口
  BACKUP_KEEP = 30                     # 保留最近多少份备份
  BACKUP_INTERVAL_MS = 300000          # 自动备份间隔（毫秒，5 分钟）
