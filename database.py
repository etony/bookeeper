import sqlite3
import logging
from typing import List, Optional, Dict
from contextlib import contextmanager

from config import Config
from models.book import Book

LOG = logging.getLogger(__name__)

# 数据库建表 DDL
_SCHEMA = '''
CREATE TABLE IF NOT EXISTS books (
  isbn TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  author TEXT DEFAULT '',
  publisher TEXT DEFAULT '',
  price TEXT DEFAULT '',
  rating TEXT DEFAULT '0',
  raters TEXT DEFAULT '0',
  status TEXT DEFAULT '默认',
  shelf TEXT DEFAULT '未设置',
  start_date TEXT DEFAULT '',
  end_date TEXT DEFAULT '',
  cover_url TEXT DEFAULT '',
  pubdate TEXT DEFAULT '',
  douban_url TEXT DEFAULT '',
  recommend TEXT DEFAULT '0',
  pages TEXT DEFAULT '',
  notes TEXT DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
'''


class BookRepo:
  """Repository 模式封装 SQLite 数据访问层"""

  def __init__(self, db_path: str = None):
    self._path = db_path or Config.DB_PATH
    self._init_db()

  @contextmanager
  def _conn(self):
    """上下文管理器：自动提交/回滚数据库连接"""
    conn = sqlite3.connect(self._path)
    conn.row_factory = sqlite3.Row
    try:
      yield conn
      conn.commit()
    except Exception:
      conn.rollback()
      raise
    finally:
      conn.close()

  def _init_db(self):
    """初始化表结构和索引"""
    with self._conn() as conn:
      conn.execute(_SCHEMA)
      conn.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
      conn.execute('CREATE INDEX IF NOT EXISTS idx_books_status ON books(status)')

  # ── CRUD ──

  def get_all(self) -> List[Book]:
    """获取全部图书，按标题排序"""
    with self._conn() as conn:
      rows = conn.execute('SELECT * FROM books ORDER BY title').fetchall()
      return [Book.from_dict(dict(r)) for r in rows]

  def get_by_isbn(self, isbn: str) -> Optional[Book]:
    """根据 ISBN 查询单本图书"""
    with self._conn() as conn:
      row = conn.execute('SELECT * FROM books WHERE isbn = ?', (isbn,)).fetchone()
      return Book.from_dict(dict(row)) if row else None

  def upsert(self, book: Book) -> bool:
    """插入或更新（UPSERT）：存在则更新，不存在则新增"""
    data = {k: v for k, v in book.to_dict().items()
            if k in Book.__dataclass_fields__ and k != 'rating_detail'}
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
    """根据 ISBN 删除一条记录"""
    with self._conn() as conn:
      cur = conn.execute('DELETE FROM books WHERE isbn = ?', (isbn,))
      return cur.rowcount > 0

  def delete_batch(self, isbns: List[str]) -> int:
    """批量删除多条记录"""
    if not isbns:
      return 0
    placeholders = ', '.join('?' for _ in isbns)
    with self._conn() as conn:
      cur = conn.execute(f'DELETE FROM books WHERE isbn IN ({placeholders})', isbns)
      return cur.rowcount

  # ── 搜索与筛选 ──

  def search(self, keyword: str = '', status: str = '') -> List[Book]:
    """按关键词（标题/作者/出版社/ISBN）和状态搜索"""
    sql = 'SELECT * FROM books WHERE 1=1'
    params = []
    if keyword:
      sql += ' AND (title LIKE ? OR author LIKE ? OR publisher LIKE ? OR isbn LIKE ?)'
      kw = f'%{keyword}%'
      params.extend([kw, kw, kw, kw])
    if status:
      sql += ' AND status = ?'
      params.append(status)
    sql += ' ORDER BY title'
    with self._conn() as conn:
      rows = conn.execute(sql, params).fetchall()
      return [Book.from_dict(dict(r)) for r in rows]

  def count(self, keyword: str = '', status: str = '') -> int:
    """符合条件的记录总数（用于状态栏显示）"""
    sql = 'SELECT COUNT(*) FROM books WHERE 1=1'
    params = []
    if keyword:
      sql += ' AND (title LIKE ? OR author LIKE ? OR publisher LIKE ? OR isbn LIKE ?)'
      kw = f'%{keyword}%'
      params.extend([kw, kw, kw, kw])
    if status:
      sql += ' AND status = ?'
      params.append(status)
    with self._conn() as conn:
      return conn.execute(sql, params).fetchone()[0]

  # ── 统计 ──

  def status_counts(self) -> Dict[str, int]:
    """各阅读状态的图书数量"""
    with self._conn() as conn:
      rows = conn.execute('SELECT status, COUNT(*) as cnt FROM books GROUP BY status').fetchall()
      return {r['status']: r['cnt'] for r in rows}

  def publisher_top(self, n: int = 10) -> List[tuple]:
    """出版社 TOP N"""
    with self._conn() as conn:
      rows = conn.execute(
        'SELECT publisher, COUNT(*) as cnt FROM books WHERE publisher != "" GROUP BY publisher ORDER BY cnt DESC LIMIT ?', (n,)
      ).fetchall()
      return [(r['publisher'], r['cnt']) for r in rows]

  def rating_distribution(self) -> Dict[str, int]:
    """评分分布：划分为 5 个区间"""
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

  def import_df(self, df) -> int:
    """从 pandas DataFrame 逐行导入，返回成功导入的数量"""
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
    """导出全部数据为 pandas DataFrame，含扩展字段"""
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
