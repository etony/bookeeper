"""Book Repository 实现"""
from typing import List, Optional
from core.models.book import Book
from core.repositories.base import BaseRepository
from core.exceptions import QueryError

class BookRepository(BaseRepository[Book]):
    """Book 专用仓储"""
    
    def _get_table_name(self) -> str:
        return "books"
    
    def _init_db(self):
        """初始化 books 表"""
        with self._conn() as conn:
            conn.execute('''
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_books_status ON books(status)')
    
    def get_by_isbn(self, isbn: str) -> Optional[Book]:
        """根据 ISBN 获取图书"""
        with self._conn() as conn:
            row = conn.execute('SELECT * FROM books WHERE isbn = ?', (isbn,)).fetchone()
            return Book.from_dict(dict(row)) if row else None
    
    def get_all(self) -> List[Book]:
        """获取所有图书"""
        with self._conn() as conn:
            rows = conn.execute('SELECT * FROM books ORDER BY title').fetchall()
            return [Book.from_dict(dict(r)) for r in rows]
    
    def create(self, book: Book) -> bool:
        """创建新图书"""
        data = {k: v for k, v in book.to_dict().items() if k != 'rating_detail'}
        cols = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        sql = f'INSERT INTO books ({cols}) VALUES ({placeholders})'
        
        with self._conn() as conn:
            conn.execute(sql, list(data.values()))
        return True
    
    def update(self, book: Book) -> bool:
        """更新图书"""
        data = {k: v for k, v in book.to_dict().items() if k != 'rating_detail'}
        updates = ', '.join(f'{k}=?' for k in data)
        sql = f'UPDATE books SET {updates}, updated_at=CURRENT_TIMESTAMP WHERE isbn=?'
        
        with self._conn() as conn:
            conn.execute(sql, list(data.values()) + [book.isbn])
        return True
    
    def upsert(self, book: Book) -> bool:
        """插入或更新图书"""
        data = {k: v for k, v in book.to_dict().items() if k != 'rating_detail'}
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
        """删除图书"""
        with self._conn() as conn:
            cur = conn.execute('DELETE FROM books WHERE isbn = ?', (isbn,))
            return cur.rowcount > 0
    
    def search(self, keyword: str = '', status: str = '') -> List[Book]:
        """搜索图书"""
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
        
        sql = f'SELECT * FROM books {where} ORDER BY title'
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [Book.from_dict(dict(r)) for r in rows]
    
    def count(self, keyword: str = '', status: str = '') -> int:
        """统计总数（支持按关键词和状态筛选）"""
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
        sql = f'SELECT COUNT(*) FROM books {where}'
        with self._conn() as conn:
            return conn.execute(sql, params).fetchone()[0]

    def status_counts(self) -> dict:
        """统计各状态数量"""
        with self._conn() as conn:
            rows = conn.execute('SELECT status, COUNT(*) as cnt FROM books GROUP BY status').fetchall()
            return {r['status']: r['cnt'] for r in rows}
    
    def publisher_top(self, n: int = 10) -> list:
        """出版社 TOP N"""
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT publisher, COUNT(*) as cnt FROM books WHERE publisher != "" GROUP BY publisher ORDER BY cnt DESC LIMIT ?',
                (n,)
            ).fetchall()
            return [(r['publisher'], r['cnt']) for r in rows]
    
    def rating_distribution(self) -> dict:
        """评分分布"""
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