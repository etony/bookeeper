"""API 集成测试"""
import pytest
from core.models.book import Book


@pytest.fixture(autouse=True)
def clean_db(client):
    """每个测试前清空数据库，确保隔离"""
    from services import get_repo
    repo = get_repo()
    # 防线：确认连的是 conftest 创建的临时库，绝不能清空真实 books.db
    assert 'bookeeper_test' in repo._path, (
        f'测试数据库路径异常: {repo._path}（conftest 的 DB_PATH 隔离补丁失效）'
    )
    with repo._conn() as conn:
        conn.execute('DELETE FROM books')
    yield


def _add_book(client, isbn='9787544291163', title='百年孤独', author='加西亚·马尔克斯',
              status='默认'):
    """辅助函数：通过 POST 添加一本图书"""
    return client.post('/add', data={
        'isbn': isbn,
        'title': title,
        'author': author,
        'publisher': '南海出版公司',
        'price': '39.50',
        'rating': '9.3',
        'status': status,
        'shelf': 'A',
        'start_date': '2024-01-01',
        'end_date': '',
    })


class TestGetAllBooks:
    """测试获取所有图书"""

    def test_empty_list(self, client):
        """空库返回空列表"""
        response = client.get('/')
        assert response.status_code == 200
        assert '图书列表' in response.text

    def test_with_books(self, client):
        """有图书时正确显示"""
        _add_book(client)
        response = client.get('/')
        assert response.status_code == 200
        assert '百年孤独' in response.text

    def test_search(self, client):
        """搜索功能"""
        _add_book(client)
        _add_book(client, isbn='9787530217337', title='活着', author='余华')
        response = client.get('/?q=活着')
        assert response.status_code == 200
        assert '活着' in response.text
        assert '百年孤独' not in response.text


class TestAddBook:
    """测试添加图书"""

    def test_add_book_redirect(self, client):
        """添加图书后重定向到首页"""
        response = _add_book(client)
        assert response.status_code == 200

    def test_add_book_appears_in_list(self, client):
        """添加的图书出现在列表中"""
        _add_book(client)
        response = client.get('/')
        assert '百年孤独' in response.text
        assert '加西亚·马尔克斯' in response.text

    def test_add_multiple_books(self, client):
        """添加多本图书"""
        _add_book(client)
        _add_book(client, isbn='9787530217337', title='活着', author='余华')
        response = client.get('/')
        assert '百年孤独' in response.text
        assert '活着' in response.text


class TestEditBook:
    """测试编辑图书"""

    def test_edit_page_exists(self, client):
        """编辑存在的图书"""
        _add_book(client)
        response = client.get('/edit/9787544291163')
        assert response.status_code == 200
        assert '百年孤独' in response.text

    def test_edit_page_not_exists(self, client):
        """编辑不存在的图书显示错误"""
        response = client.get('/edit/0000000000000')
        assert response.status_code == 200
        assert '图书不存在' in response.text

    def test_edit_submit(self, client):
        """提交编辑后数据更新"""
        _add_book(client)
        client.post('/edit/9787544291163', data={
            'title': '百年孤独（修订版）',
            'author': '加西亚·马尔克斯',
            'publisher': '南海出版公司',
            'price': '45.00',
            'rating': '9.5',
            'status': '已读',
            'shelf': 'B',
            'start_date': '2024-01-01',
            'end_date': '2024-02-01',
        })
        response = client.get('/')
        assert '百年孤独（修订版）' in response.text


class TestDeleteBook:
    """测试删除图书"""

    def test_delete_book(self, client):
        """删除图书"""
        _add_book(client)
        response = client.post('/delete/9787544291163')
        assert response.status_code == 200
        # 删除后列表中不应有该书
        response = client.get('/')
        assert '百年孤独' not in response.text

    def test_delete_nonexistent_book(self, client):
        """删除不存在的图书不报错"""
        response = client.post('/delete/0000000000000')
        assert response.status_code == 200


class TestBookDetail:
    """测试图书详情"""

    def test_detail_exists(self, client):
        """查看存在的图书详情"""
        _add_book(client)
        response = client.get('/book/9787544291163')
        assert response.status_code == 200
        assert '百年孤独' in response.text
        assert '加西亚·马尔克斯' in response.text

    def test_detail_not_exists(self, client):
        """查看不存在的图书显示错误"""
        response = client.get('/book/0000000000000')
        assert response.status_code == 200
        assert '图书不存在' in response.text


class TestCoverWall:
    """测试封面墙"""

    def test_cover_wall_page(self, client):
        """封面墙页面正常渲染"""
        response = client.get('/cover-wall')
        assert response.status_code == 200
        assert '封面墙' in response.text

    def test_cover_wall_with_books(self, client):
        """封面墙显示图书"""
        _add_book(client)
        response = client.get('/cover-wall')
        assert response.status_code == 200
        assert '百年孤独' in response.text

    def test_cover_wall_sort_by_rating(self, client):
        """封面墙按评分排序"""
        _add_book(client)
        _add_book(client, isbn='9787530217337', title='活着', author='余华')
        response = client.get('/cover-wall?sort=rating')
        assert response.status_code == 200

    def test_cover_wall_search(self, client):
        """封面墙搜索"""
        _add_book(client)
        _add_book(client, isbn='9787530217337', title='活着', author='余华')
        response = client.get('/cover-wall?q=活着')
        assert response.status_code == 200
        assert '活着' in response.text
        assert '百年孤独' not in response.text


class TestStats:
    """测试统计页面"""

    def test_stats_page(self, client):
        """统计页面正常渲染"""
        response = client.get('/stats')
        assert response.status_code == 200

    def test_stats_with_data(self, client):
        """有数据时统计页面显示"""
        _add_book(client)
        _add_book(client, isbn='9787530217337', title='活着', author='余华',
                   status='已读')
        response = client.get('/stats')
        assert response.status_code == 200
