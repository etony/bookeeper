"""pytest 配置"""
import os
import sys
import json
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


# init_config() 会把配置回写 Config 静态类（P0 修复），测试污染需要整体快照还原
_CONFIG_KEYS = ('DB_PATH', 'WEB_PORT', 'BACKUP_KEEP', 'BACKUP_INTERVAL_MS',
                'DOUBAN_API_KEY', 'DOUBAN_API_KEY_SEARCH', 'HEADERS')


@pytest.fixture(autouse=True)
def _isolate_config():
    """每个测试前后：快照还原 Config 静态类，并强制钳制 DB_PATH 到临时库。

    防两件事：
    1. 测试调用 init_config() 回写 Config 后污染后续测试
    2. 任何路径把 DB_PATH 指回真实 books.db
    """
    snapshot = {k: getattr(Config, k) for k in _CONFIG_KEYS}
    Config.DB_PATH = TEST_DB_PATH
    yield
    for k, v in snapshot.items():
        setattr(Config, k, v)
    Config.DB_PATH = TEST_DB_PATH


@pytest.fixture(scope="session", autouse=True)
def _restore_db_path():
    """会话结束：还原 Config.DB_PATH、全局配置单例并删除临时数据库"""
    yield
    import config as config_module
    Config.DB_PATH = REAL_DB_PATH
    config_module._config_manager = None
    services._repo = None
    for p in (TEST_DB_PATH, TEST_DB_PATH + '-wal', TEST_DB_PATH + '-shm'):
        try:
            os.remove(p)
        except OSError:
            pass


@pytest.fixture(scope="session")
def test_config():
    """测试配置：database_path 指向临时库，保证回写后仍是隔离路径"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"database_path": TEST_DB_PATH}, f)
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


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清空全局 repo 数据库（含 web_templates 写入的残留）"""
    from services import get_repo
    repo = get_repo()
    # 防线：确认连的是 conftest 创建的临时库，绝不能清空真实 books.db
    assert 'bookeeper_test' in repo._path, (
        f'测试数据库路径异常: {repo._path}（conftest 的 DB_PATH 隔离补丁失效）'
    )
    with repo._conn() as conn:
        conn.execute('DELETE FROM books')
    yield


@pytest.fixture
def repo():
    """创建使用临时文件的 BookRepo 实例"""
    from database import BookRepo
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    r = BookRepo(db_path)
    yield r
    os.unlink(db_path)
