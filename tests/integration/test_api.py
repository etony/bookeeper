"""API 集成测试"""
import pytest
from core.models.book import Book
from services import get_repo

# clean_db（每测试清库 + 隔离断言）统一在 tests/conftest.py 中定义


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


class TestAddDataSafety:
    """POST /add 的数据安全（清洗 ISBN / 拒绝空 ISBN / 重复添加不毁数据）"""

    def test_add_cleans_isbn(self, client):
        """连字符 ISBN 入库前被清洗，不产生格式分裂的记录"""
        _add_book(client, isbn='978-7-5442-9116-3')
        repo = get_repo()
        assert repo.count() == 1
        assert repo.get_by_isbn('9787544291163') is not None
        assert repo.get_by_isbn('978-7-5442-9116-3') is None

    def test_add_empty_isbn_rejected(self, client):
        """空 ISBN 拒绝入库（空主键会让第二本书覆盖第一本）"""
        resp = client.post('/add', data={
            'isbn': '', 'title': '没有 ISBN 的书', 'author': '', 'publisher': '',
            'price': '', 'rating': '0', 'status': '默认', 'shelf': '',
            'start_date': '', 'end_date': '',
        })
        assert resp.status_code == 400
        assert 'ISBN 不能为空' in resp.text
        # 用户填写的内容回显在表单里，不丢失输入
        assert '没有 ISBN 的书' in resp.text
        assert get_repo().count() == 0

    def test_add_duplicate_preserves_user_and_extended_fields(self, client):
        """重复添加已有 ISBN：表单保持默认值时不清空旧数据"""
        repo = get_repo()
        repo.upsert(Book(
            isbn='9787544291163', title='旧版', status='已读', shelf='A-1',
            start_date='2024-01-01', end_date='2024-02-01', raters='800',
            cover_url='https://img.douban.com/large.jpg', pubdate='2008-1',
            douban_url='https://book.douban.com/subject/2567698/',
            pages='302', recommend='27',
        ))
        # 添加表单未预填旧值：所有字段都是默认/空
        client.post('/add', data={
            'isbn': '978-7-5442-9116-3', 'title': '新版', 'author': '新作者',
            'publisher': '', 'price': '', 'rating': '0', 'status': '默认',
            'shelf': '', 'start_date': '', 'end_date': '',
        })
        assert repo.count() == 1
        got = repo.get_by_isbn('9787544291163')
        # 内容字段以表单为准
        assert got.title == '新版'
        # 用户字段（表单为默认值时）保留旧记录
        assert got.status == '已读'
        assert got.shelf == 'A-1'
        assert got.start_date == '2024-01-01'
        assert got.end_date == '2024-02-01'
        assert got.raters == '800'
        # 扩展字段不在表单里，始终保留
        assert got.cover_url == 'https://img.douban.com/large.jpg'
        assert got.pubdate == '2008-1'
        assert got.douban_url == 'https://book.douban.com/subject/2567698/'
        assert got.pages == '302'
        assert got.recommend == '27'

    def test_add_duplicate_explicit_form_values_win(self, client):
        """重复添加时用户明确选择的值照常生效"""
        repo = get_repo()
        repo.upsert(Book(isbn='9787544291163', title='旧版', status='已读',
                         shelf='A-1', start_date='2024-01-01', end_date='2024-02-01'))
        client.post('/add', data={
            'isbn': '9787544291163', 'title': '新版', 'author': '', 'publisher': '',
            'price': '', 'rating': '0', 'status': '计划', 'shelf': 'B',
            'start_date': '2024-06-01', 'end_date': '2024-07-01',
        })
        got = repo.get_by_isbn('9787544291163')
        assert got.status == '计划'
        assert got.shelf == 'B'
        assert got.start_date == '2024-06-01'
        assert got.end_date == '2024-07-01'
