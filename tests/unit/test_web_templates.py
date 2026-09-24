"""Web模板测试"""
import pytest
from fastapi.testclient import TestClient
from core.models.book import Book


def test_index_page(client):
    """测试首页模板"""
    response = client.get('/')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    # 检查模板是否正确渲染
    assert '图书列表' in response.text
    assert 'Bookeeper' in response.text


def test_book_detail_page(client):
    """测试图书详情页模板 - 图书不存在时返回错误页"""
    response = client.get('/book/123')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    assert '图书不存在' in response.text


def test_book_detail_page_with_real_book(client):
    """测试图书详情页模板 - 图书存在时正确渲染"""
    from services import get_repo
    repo = get_repo()
    book = Book(isbn='9787544291163', title='百年孤独', author='加西亚·马尔克斯',
                publisher='南海出版公司', price='39.50', rating='9.3', raters='123456',
                status='已读', shelf='A', start_date='2024-01-01', end_date='2024-01-15')
    repo.upsert(book)
    response = client.get('/book/9787544291163')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    assert '百年孤独' in response.text
    assert '加西亚·马尔克斯' in response.text
    assert '南海出版公司' in response.text


def test_cover_wall_page(client):
    """测试封面墙页面模板"""
    response = client.get('/cover-wall')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    # 检查模板是否正确渲染
    assert '封面墙' in response.text
    assert 'Bookeeper' in response.text


def test_add_book_form(client):
    """测试添加图书表单"""
    response = client.get('/add')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    # 检查模板是否正确渲染
    assert '添加图书' in response.text
    assert 'ISBN' in response.text
    assert '书名' in response.text


def test_edit_book_form(client):
    """测试编辑图书表单 - 图书不存在时返回错误页"""
    response = client.get('/edit/123')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    # 图书不存在，应显示错误信息
    assert '图书不存在' in response.text


def test_edit_book_form_with_real_book(client):
    """测试编辑图书表单 - 图书存在时正确渲染"""
    from services import get_repo
    repo = get_repo()
    book = Book(isbn='9787530217337', title='活着', author='余华',
                publisher='作家出版社', price='20.00', rating='9.4', status='默认')
    repo.upsert(book)
    response = client.get('/edit/9787530217337')
    assert response.status_code == 200
    assert '活着' in response.text
    assert '余华' in response.text
