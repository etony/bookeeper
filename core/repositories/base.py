"""Repository 基类"""
import sqlite3
from contextlib import contextmanager
from typing import List, Optional, TypeVar, Generic
from config import get_config
from core.exceptions import QueryError

T = TypeVar("T")

class BaseRepository(Generic[T]):
    """Repository 基类，提供通用数据库操作"""
    
    def __init__(self, db_path: str = None):
        config = get_config()
        self._path = db_path or config.database.path
        self._init_db()
    
    @contextmanager
    def _conn(self):
        """数据库连接上下文管理器"""
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise QueryError(f"数据库操作失败: {e}")
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库（子类实现）"""
        pass
    
    def count(self, keyword: str = '', status: str = '') -> int:
        """统计总数（支持按关键词和状态筛选）"""
        with self._conn() as conn:
            table_name = self._get_table_name()
            result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            return result[0]
    
    def _get_table_name(self) -> str:
        """获取表名（子类实现）"""
        raise NotImplementedError