"""pytest 配置"""
import os
import sys
import tempfile
import pytest

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import Config, init_config
from fastapi.testclient import TestClient

# ── 测试数据库隔离 ──────────────────────────────────────
# 必须在任何项目模块（database/services/web）被导入前执行：
# BookRepo 读取 Config.DB_PATH，不打这个补丁，
# 集成测试的 DELETE FROM books 会清空真实 books.db。
_fd, TEST_DB_PATH = tempfile.mkstemp(suffix='.db', prefix='bookeeper_test_')
os.close(_fd)
REAL_DB_PATH = Config.DB_PATH
Config.DB_PATH = TEST_DB_PATH

import services
services._repo = None  # 丢弃可能已用真实路径创建的单例


@pytest.fixture(scope="session", autouse=True)
def _restore_db_path():
  """会话结束：还原 Config.DB_PATH 并删除临时数据库"""
  yield
  Config.DB_PATH = REAL_DB_PATH
  services._repo = None
  for p in (TEST_DB_PATH, TEST_DB_PATH + '-wal', TEST_DB_PATH + '-shm'):
    try:
      os.remove(p)
    except OSError:
      pass


@pytest.fixture(scope="session")
def test_config():
    """测试配置"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"database_path": ":memory:"}')
        config_path = f.name

    init_config(config_path)
    yield

    os.unlink(config_path)

@pytest.fixture
def client(test_config):
    """测试客户端"""
    from web.server import BookWebServer
    server = BookWebServer()
    return TestClient(server._app)

@pytest.fixture
def sample_books():
    """示例图书数据"""
    return [
        {"isbn": "9787544291163", "title": "百年孤独", "author": "加西亚·马尔克斯"},
        {"isbn": "9787530217337", "title": "活着", "author": "余华"},
        {"isbn": "9787544270878", "title": "1984", "author": "乔治·奥威尔"},
    ]


@pytest.fixture
def repo():
    """创建使用临时文件的 BookRepo 实例"""
    from database import BookRepo
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    r = BookRepo(db_path)
    yield r
    os.unlink(db_path)
