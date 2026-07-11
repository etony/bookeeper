"""
┌──────────────────────────────────────────┐
│  数据库访问层（Repository 模式）          │
│                                          │
│  封装 SQLite 的所有读写操作，              │
│  上层代码不直接接触 SQL。                 │
└──────────────────────────────────────────┘
"""

import sqlite3
from typing import List, Optional, Dict
from contextlib import contextmanager

from config import Config
from models.book import Book

# ── 数据库建表 DDL ──────────────────────────────────────────
# SQLite 的 CREATE TABLE IF NOT EXISTS 保证多次运行不会重复建表。
# 所有字段都用 TEXT 存储，避免类型转换带来的兼容性问题。
_SCHEMA = '''
CREATE TABLE IF NOT EXISTS books (
  isbn TEXT PRIMARY KEY,              -- ISBN 作为主键，天然唯一
  title TEXT NOT NULL DEFAULT '',      -- 书名（必填）
  author TEXT DEFAULT '',              -- 作者
  publisher TEXT DEFAULT '',           -- 出版社
  price TEXT DEFAULT '',               -- 价格（存字符串，保留原始格式）
  rating TEXT DEFAULT '0',             -- 豆瓣评分
  raters TEXT DEFAULT '0',             -- 评价人数
  status TEXT DEFAULT '默认',           -- 阅读状态
  shelf TEXT DEFAULT '未设置',          -- 所在书柜
  start_date TEXT DEFAULT '',          -- 购书日期
  end_date TEXT DEFAULT '',            -- 已读日期
  cover_url TEXT DEFAULT '',           -- 封面图片 URL
  pubdate TEXT DEFAULT '',             -- 出版日期
  douban_url TEXT DEFAULT '',          -- 豆瓣详情页 URL
  recommend TEXT DEFAULT '0',          -- 推荐度评分
  pages TEXT DEFAULT '',               -- 总页数
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,   -- 创建时间
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP    -- 更新时间（UPSERT 时自动更新）
)
'''


class BookRepo:
  """
  Repository 模式封装 SQLite 数据访问层。

  为什么用 Repository？
    将数据库操作集中管理，未来如果要换数据库（比如 PostgreSQL），
    只需要改这一个文件，上层代码完全不受影响。

  用法：
    repo = BookRepo('books.db')
    repo.get_all()           → 全部图书
    repo.get_by_isbn(isbn)   → 单本查询
    repo.upsert(book)        → 新增或更新
    repo.delete(isbn)        → 删除
    repo.search(keyword)     → 搜索
    repo.count()             → 统计总数
  """

  def __init__(self, db_path: str = None):
    # 如果没传路径，用 Config 中的默认路径
    self._path = db_path or Config.DB_PATH
    self._init_db()

  # ── 数据库连接管理 ──────────────────────────────────────

  @contextmanager
  def _conn(self):
    """
    数据库连接上下文管理器。

    用 with 语句自动处理：
      成功 → commit 提交
      失败 → rollback 回滚
      无论成功失败 → 关闭连接

    用法：
      with self._conn() as conn:
        conn.execute(...)
    """
    conn = sqlite3.connect(self._path)
    conn.row_factory = sqlite3.Row   # 让查询结果支持按列名访问
    try:
      yield conn
      conn.commit()
    except Exception:
      conn.rollback()
      raise
    finally:
      conn.close()

  def _init_db(self):
    """
    初始化数据库：建表 + 建索引。

    首次运行会创建 books 表和两个常用索引。
    后续运行因为 IF NOT EXISTS，不会重复创建。
    """
    with self._conn() as conn:
      conn.execute(_SCHEMA)
      conn.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
      conn.execute('CREATE INDEX IF NOT EXISTS idx_books_status ON books(status)')

  # ── CRUD 基本操作 ──────────────────────────────────────

  def get_all(self) -> List[Book]:
    """
    获取全部图书，按书名排序。

    返回 Book 对象列表，空表返回空列表 []。
    """
    with self._conn() as conn:
      rows = conn.execute('SELECT * FROM books ORDER BY title').fetchall()
      return [Book.from_dict(dict(r)) for r in rows]

  def get_by_isbn(self, isbn: str) -> Optional[Book]:
    """
    根据 ISBN 查询单本图书。

    参数：
      isbn — 13 位或 10 位 ISBN 字符串

    返回 Book 对象或 None（未找到时）。
    """
    with self._conn() as conn:
      row = conn.execute('SELECT * FROM books WHERE isbn = ?', (isbn,)).fetchone()
      return Book.from_dict(dict(row)) if row else None

  def upsert(self, book: Book) -> bool:
    """
    插入或更新（UPSERT）。

    如果 ISBN 已存在 → 更新所有字段
    如果 ISBN 不存在 → 插入新记录

    这里用了 SQLite 的 ON CONFLICT … DO UPDATE SET 语法，
    比先 SELECT 判断再 INSERT/UPDATE 更高效，而且线程安全。
    """
    # 排除 rating_detail——这是豆瓣 API 返回的原始数据，
    # 结构复杂不适合存数据库，只在内存中使用。
    data = {k: v for k, v in book.to_dict().items()
            if k != 'rating_detail'}
    cols = ', '.join(data.keys())
    placeholders = ', '.join('?' for _ in data)
    updates = ', '.join(f'{k}=excluded.{k}' for k in data)
    sql = f'''
      INSERT INTO books ({cols}) VALUES ({placeholders})
      ON CONFLICT(isbn) DO UPDATE SET {updates}, updated_at=CURRENT_TIMESTAMP
    '''
    with self._conn() as conn:
      conn.execute(sql, list(data.values()))
    return True

  def delete(self, isbn: str) -> bool:
    """
    根据 ISBN 删除一条记录。

    返回 True 表示成功删除了某行，False 表示 ISBN 不存在。
    """
    with self._conn() as conn:
      cur = conn.execute('DELETE FROM books WHERE isbn = ?', (isbn,))
      return cur.rowcount > 0

  # ── 搜索与筛选 ──────────────────────────────────────────

  @staticmethod
  def _build_filter(keyword: str = '', status: str = ''):
    """
    构造 WHERE 条件子句和参数列表。

    这是 search 和 count 的公共逻辑，
    避免两处重复写同样的 keyword/status 拼接代码。

    返回 (where_clause, params_list)
    例如：('WHERE title LIKE ? AND status = ?', ['%三体%', '已读'])
    """
    clauses = []
    params = []
    if keyword:
      clauses.append('(title LIKE ? OR author LIKE ? OR publisher LIKE ? OR isbn LIKE ?)')
      kw = f'%{keyword}%'
      params.extend([kw, kw, kw, kw])
    if status:
      clauses.append('status = ?')
      params.append(status)
    where = ' AND '.join(clauses)
    if where:
      where = 'WHERE ' + where
    return where, params

  def search(self, keyword: str = '', status: str = '') -> List[Book]:
    """
    按关键词和状态搜索图书。

    关键词会同时匹配：标题、作者、出版社、ISBN。
    状态精确匹配（如 "已读"、"计划"、"默认"）。

    两个条件都用 AND 连接，可以组合使用。
    """
    where, params = self._build_filter(keyword, status)
    sql = f'SELECT * FROM books {where} ORDER BY title'
    with self._conn() as conn:
      rows = conn.execute(sql, params).fetchall()
      return [Book.from_dict(dict(r)) for r in rows]

  def count(self, keyword: str = '', status: str = '') -> int:
    """
    符合条件的记录总数。

    搜索结果的数量 ≠ 数据库总条数。
    这个方法用于状态栏显示"已筛选 5/100 条记录"。
    """
    where, params = self._build_filter(keyword, status)
    sql = f'SELECT COUNT(*) FROM books {where}'
    with self._conn() as conn:
      return conn.execute(sql, params).fetchone()[0]

  # ── 统计数据 ──────────────────────────────────────────

  def status_counts(self) -> Dict[str, int]:
    """
    各阅读状态的图书数量。

    返回如：{'默认': 12, '已读': 8, '计划': 5}
    用于统计面板的饼图。
    """
    with self._conn() as conn:
      rows = conn.execute('SELECT status, COUNT(*) as cnt FROM books GROUP BY status').fetchall()
      return {r['status']: r['cnt'] for r in rows}

  def publisher_top(self, n: int = 10) -> List[tuple]:
    """
    出版社 TOP N。

    按出版社分组统计，只统计非空的出版社。
    用于统计面板的柱状图。
    """
    with self._conn() as conn:
      rows = conn.execute(
        'SELECT publisher, COUNT(*) as cnt FROM books WHERE publisher != "" GROUP BY publisher ORDER BY cnt DESC LIMIT ?', (n,)
      ).fetchall()
      return [(r['publisher'], r['cnt']) for r in rows]

  def rating_distribution(self) -> Dict[str, int]:
    """
    评分分布：划分为 5 个区间。

    0-6, 6-7, 7-8, 8-9, 9-10
    只统计有评分的图书（排除空和 "0"）。
    """
    with self._conn() as conn:
      rows = conn.execute('SELECT rating FROM books WHERE rating != "" AND rating != "0"').fetchall()
    bins = {'0-6': 0, '6-7': 0, '7-8': 0, '8-9': 0, '9-10': 0}
    for r in rows:
      try:
        val = float(r['rating'])
      except ValueError:
        continue
      if val < 6: bins['0-6'] += 1
      elif val < 7: bins['6-7'] += 1
      elif val < 8: bins['7-8'] += 1
      elif val < 9: bins['8-9'] += 1
      else: bins['9-10'] += 1
    return bins

  # ── CSV 导入导出 ──────────────────────────────────────

  def import_df(self, df) -> int:
    """
    从 pandas DataFrame 逐行导入。

    参数 df 的列名需要和 Config.TABLE_COLUMNS 一致，
    或者经过 services.data.load_csv 的列名映射。

    返回成功导入的条数（跳过了 ISBN 为空的行）。
    """
    imported = 0
    for _, row in df.iterrows():
      b = Book(
        isbn=str(row.get('ISBN', '')),
        title=str(row.get('书名', '')),
        author=str(row.get('作者', '')),
        publisher=str(row.get('出版', '')),
        price=str(row.get('价格', '')),
        rating=str(row.get('评分', '0')),
        raters=str(row.get('人数', '0')),
        status=str(row.get('状态', '默认')),
        shelf=str(row.get('书柜', '未设置')),
        start_date=str(row.get('购书日期', '')),
        end_date=str(row.get('已读日期', '')),
      )
      if b.isbn and self.upsert(b):
        imported += 1
    return imported

  def export_df(self):
    """
    导出全部数据为 pandas DataFrame。

    导出列比界面显示的列多一些，包含封面 URL、豆瓣链接等扩展字段，
    方便在外部做数据分析或迁移。
    """
    import pandas as pd
    with self._conn() as conn:
      rows = conn.execute('SELECT * FROM books ORDER BY title').fetchall()
      data = [dict(r) for r in rows]
    cols = ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期',
            '封面', '出版日期', '详情页', '推荐度', '页数']
    flat = []
    for d in data:
      flat.append([d.get(k, '') for k in
                   ['isbn','title','author','publisher','price','rating','raters','status','shelf',
                    'start_date','end_date','cover_url','pubdate','douban_url','recommend','pages']])
    return pd.DataFrame(flat, columns=cols)
