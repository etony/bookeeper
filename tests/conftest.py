"""pytest 配置"""
import os
import sys
import tempfile
import pytest
from config import init_config
from core.repositories.book_repo import BookRepository

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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
def temp_db():
    """临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    repo = BookRepository(db_path)
    yield repo
    
    os.unlink(db_path)

@pytest.fixture
def sample_books():
    """示例图书数据"""
    return [
        {"isbn": "9787544291163", "title": "百年孤独", "author": "加西亚·马尔克斯"},
        {"isbn": "9787530217337", "title": "活着", "author": "余华"},
        {"isbn": "9787544270878", "title": "1984", "author": "乔治·奥威尔"},
    ]
