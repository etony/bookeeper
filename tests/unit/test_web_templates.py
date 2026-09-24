"""Web模板测试"""
import pytest
from fastapi.testclient import TestClient


def test_index_page(client):
    """测试首页模板"""
    response = client.get('/')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    # 检查模板是否正确渲染
    assert '图书列表' in response.text
    assert 'Bookeeper' in response.text


def test_book_detail_page(client):
    """测试图书详情页模板"""
    # 假设数据库中有一本ISBN为'123'的书
    response = client.get('/book/123')
    # 如果书不存在，应该返回错误页面
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    # 检查模板是否正确渲染
    assert 'Bookeeper' in response.text


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
