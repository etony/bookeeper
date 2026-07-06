"""
Bookeeper - 应用配置模块

集中管理应用的所有常量配置，包括：
- 豆瓣 API key、请求地址和请求头
- 窗口/对话框默认尺寸
- 表格列定义、图书状态、分类等业务常量
- 封面缓存目录、API 请求延迟等运行时参数

API key 从同级 config.json 读取，不存在时自动生成默认文件，
方便用户在不修改代码的前提下覆盖配置。
"""

import os
import json


def _load_api_keys() -> dict:
  """
  从同级目录的 config.json 文件中加载豆瓣 API key。

  执行逻辑：
    1. 构造 config.json 的绝对路径（与当前模块同目录）
    2. 设置默认 API key 字典（硬编码默认值）
    3. 若 config.json 存在，读取并合并覆盖到默认值中
       （允许用户在文件中仅提供要覆盖的字段）
    4. 若文件不存在，用默认值创建 config.json，方便用户首次使用
    5. 返回合并后的完整配置字典

  Returns:
    dict: 包含 'DOUBAN_API_KEY' 和 'DOUBAN_API_KEY_SEARCH' 的字典

  注意事项：
    - 默认 API key 为公开测试 key，生产环境建议用户自行申请
    - 文件编码固定为 UTF-8，ensure_ascii=False 保证中文正常写入
  """
  path = os.path.join(os.path.dirname(__file__), 'config.json')
  defaults = {
    'DOUBAN_API_KEY': '0ab215a8b1977939201640fa14c66bab',
    'DOUBAN_API_KEY_SEARCH': '0ac44ae016490db2204ce0a042db2916',
  }
  if os.path.exists(path):
    with open(path, encoding='utf-8') as f:
      overrides = json.load(f)
    defaults.update(overrides)  # 用用户配置覆盖默认值
  else:
    # 首次运行，自动生成配置文件模板
    with open(path, 'w', encoding='utf-8') as f:
      json.dump(defaults, f, indent=2, ensure_ascii=False)
    print(f'已生成配置文件 {path}，可修改其中的 API key')
  return defaults


# 模块加载时立即执行，保证 Config 类能引用到加载后的值
_api_keys = _load_api_keys()


class Config:
  """
  应用全局配置类，所有配置以类属性（静态字段）形式定义。

  使用方式：在代码中通过 Config.APP_NAME 等直接引用，无需实例化。
  设计意图：将所有可调参数集中管理，避免散落在各模块中。
  """

  # ── 应用基本信息 ──
  APP_NAME = 'Bookeeper'           # 应用名称
  APP_VERSION = '2.0.0'            # 当前版本号
  APP_ICON = 'book2.png'           # 窗口图标文件名（位于资源目录）

  # ── 豆瓣 API 配置 ──
  DOUBAN_API_KEY = _api_keys['DOUBAN_API_KEY']             # 豆瓣图书 API key（获取单本书详情）
  DOUBAN_API_KEY_SEARCH = _api_keys['DOUBAN_API_KEY_SEARCH']  # 豆瓣搜索 API key
  DOUBAN_BOOK_URL = 'https://api.douban.com/v2/book'       # 豆瓣图书 API 基础地址
  DOUBAN_ISBN_URL = f'{DOUBAN_BOOK_URL}/isbn'              # ISBN 查询地址（拼接 /isbn/{isbn}）
  DOUBAN_SEARCH_URL = f'{DOUBAN_BOOK_URL}/search'          # 关键词搜索地址（参数 ?q=xxx）
  HEADERS = {                                               # 模拟移动端浏览器请求头，降低被封概率
    'Referer': 'https://m.douban.com/tv/american',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1',
  }

  # ── 窗口/对话框默认尺寸 (宽, 高) ──
  MAIN_WINDOW_SIZE = (950, 720)     # 主窗口尺寸
  SEARCH_DIALOG_SIZE = (500, 420)   # 搜索对话框尺寸
  DETAIL_DIALOG_SIZE = (520, 500)   # 图书详情对话框尺寸

  # ── 表格与业务枚举 ──
  TABLE_COLUMNS = ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']
  STATUSES = ['未读', '在读', '已读']     # 阅读状态枚举，对应表格中"状态"列的可选值
  DEFAULT_STATUS = '未读'                 # 新增图书时的默认阅读状态
  CATEGORIES = ['默认分类', '计划', '已读']  # 分类枚举，目前未展开使用
  DEFAULT_CATEGORY = '计划'               # 新增图书时的默认分类
  DEFAULT_SHELF = '未设置'                # 新增图书时的默认书柜

  # ── 运行时参数 ──
  COVER_CACHE_DIR = 'cover_cache'     # 封面图片缓存子目录名（相对于应用数据目录）
  API_REQUEST_DELAY = 1.0             # 豆瓣 API 请求间隔（秒），避免触发频率限制
  WEB_PORT = 8899                     # Web 服务器端口（用于局域网访问书库）
