"""
数据丢失类缺陷的回归测试（对应 docs/code-review-2026-09-28.md P0 与 2026-11 分析）：

1. 更新/添加时不保留扩展字段（封面、出版年、豆瓣链接、页数、推荐度）
2. ISBN 未清洗（连字符/空格）产生重复记录
3. 空 ISBN 作为主键互相覆盖
4. 豆瓣数据缺 isbn13 时未回退 isbn10
"""
import os
import sys

import pytest

# GUI 测试需要 offscreen 平台（必须在 QApplication 创建前设置）
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from core.models.book import Book


def _full_book(isbn='9787544291163'):
  """带全部扩展字段的完整记录（模拟豆瓣抓取后的数据）"""
  return Book(
    isbn=isbn, title='百年孤独', author='加西亚·马尔克斯', publisher='南海出版公司',
    price='39.50', rating='9.2', raters='800', status='已读', shelf='A-1',
    start_date='2024-01-01', end_date='2024-02-01',
    cover_url='https://img.douban.com/large.jpg', pubdate='2008-1',
    douban_url='https://book.douban.com/subject/2567698/', pages='302', recommend='27',
  )


class _NoopCoverPool:
  """测试期间禁止真实封面下载"""

  def submit(self, *args, **kwargs):
    return None


class _RecordingMessageBox:
  """记录 QMessageBox.warning 调用，避免测试卡在模态对话框"""

  calls = []

  @classmethod
  def warning(cls, parent, title, text):
    cls.calls.append((title, text))


# ══════════════════════════════════════════════════
#  A. repo.upsert 扩展字段保留
# ══════════════════════════════════════════════════


class TestUpsertPreservesExtended:
  """upsert 不得用空的扩展字段覆盖已有值（表单只含 11 个表格列）"""

  def test_empty_extended_fields_keep_existing(self, repo):
    repo.upsert(_full_book())
    # 表单构建的 Book：扩展字段全是 dataclass 默认值
    repo.upsert(Book(isbn='9787544291163', title='百年孤独（修订版）', author='马尔克斯'))
    got = repo.get_by_isbn('9787544291163')
    assert got.cover_url == 'https://img.douban.com/large.jpg'
    assert got.pubdate == '2008-1'
    assert got.douban_url == 'https://book.douban.com/subject/2567698/'
    assert got.pages == '302'
    assert got.recommend == '27'
    # 表单里有的字段照常更新
    assert got.title == '百年孤独（修订版）'
    assert got.author == '马尔克斯'

  def test_non_empty_extended_fields_overwrite(self, repo):
    """带新值时照常覆盖（豆瓣同步等场景不受影响）"""
    repo.upsert(_full_book())
    repo.upsert(Book(isbn='9787544291163', title='x',
                     cover_url='https://new/cover.jpg', pubdate='2020-2',
                     douban_url='https://new/url', pages='400', recommend='35'))
    got = repo.get_by_isbn('9787544291163')
    assert got.cover_url == 'https://new/cover.jpg'
    assert got.pubdate == '2020-2'
    assert got.douban_url == 'https://new/url'
    assert got.pages == '400'
    assert got.recommend == '35'


# ══════════════════════════════════════════════════
#  B. 豆瓣数据 ISBN 回退
# ══════════════════════════════════════════════════


class TestFromDoubanIsbn:

  def test_falls_back_to_isbn10(self):
    data = {
      'isbn10': '7544291163', 'title': '百年孤独', 'author': ['加西亚·马尔克斯'],
      'publisher': '南海出版公司', 'price': '39.50元',
      'rating': {'average': '9.2', 'numRaters': 800}, 'images': {},
      'pubdate': '2008-1', 'alt': 'https://book.douban.com/subject/2567698/',
    }
    book = Book.from_douban(data)
    assert book is not None
    assert book.isbn == '7544291163'

  def test_isbn13_preferred_over_isbn10(self):
    data = {
      'isbn13': '9787544291163', 'isbn10': '7544291163', 'title': '百年孤独',
      'author': ['加西亚·马尔克斯'], 'publisher': '南海出版公司',
      'rating': {'average': '9.2', 'numRaters': 800}, 'images': {},
    }
    book = Book.from_douban(data)
    assert book.isbn == '9787544291163'


# ══════════════════════════════════════════════════
#  C. CSV 导入清洗 ISBN
# ══════════════════════════════════════════════════


class TestImportCleansIsbn:

  def test_import_cleans_hyphenated_isbn(self, repo):
    import pandas as pd
    df = pd.DataFrame([{'ISBN': '978-7-5442-9116-3', '书名': '百年孤独', '作者': '马尔克斯'}])
    assert repo.import_df(df) == 1
    assert repo.get_by_isbn('9787544291163') is not None
    assert repo.count() == 1

  def test_reimport_other_format_no_duplicate(self, repo):
    import pandas as pd
    repo.import_df(pd.DataFrame([{'ISBN': '9787544291163', '书名': '百年孤独'}]))
    repo.import_df(pd.DataFrame([{'ISBN': '978-7-5442-9116-3', '书名': '百年孤独'}]))
    assert repo.count() == 1
    assert repo.get_by_isbn('9787544291163') is not None

  def test_import_skips_row_whose_isbn_cleans_to_empty(self, repo):
    import pandas as pd
    df = pd.DataFrame([{'ISBN': 'abc', '书名': '没有 ISBN 的垃圾行'}])
    assert repo.import_df(df) == 0
    assert repo.count() == 0


# ══════════════════════════════════════════════════
#  D. 桌面「更新记录」与豆瓣回调
# ══════════════════════════════════════════════════


@pytest.fixture(scope='session')
def app():
  from PyQt6.QtWidgets import QApplication
  if not QApplication.instance():
    return QApplication(sys.argv)
  return QApplication.instance()


@pytest.fixture
def window(app, monkeypatch, tmp_path):
  from PyQt6.QtCore import QSettings
  from ui.main_window import MainWindow

  # settings.ini 隔离（AGENTS.md 规范）：写到临时副本，不污染真实文件
  settings_file = tmp_path / 'settings.ini'
  settings_file.write_text('[General]\n', encoding='utf-8')
  monkeypatch.setattr(
    MainWindow, '_settings',
    lambda self: QSettings(str(settings_file), QSettings.Format.IniFormat))
  # 封面墙卡片创建即尝试下载封面——测试里禁止真实网络
  monkeypatch.setattr('ui.cover_wall._cover_pool', _NoopCoverPool())
  win = MainWindow()
  yield win
  win.close()


def _seed():
  from services import get_repo
  get_repo().upsert(_full_book())


class TestUpdateBook:
  """桌面「更新记录」按钮的数据安全"""

  def test_keeps_extended_fields(self, window):
    from services import get_repo
    _seed()
    window._book_form.fill_form(get_repo().get_by_isbn('9787544291163'))
    window._book_form._title_input.setText('百年孤独（更新测试）')
    window._update_book()
    repo = get_repo()
    assert repo.count() == 1
    got = repo.get_by_isbn('9787544291163')
    assert got.title == '百年孤独（更新测试）'
    assert got.cover_url == 'https://img.douban.com/large.jpg'
    assert got.pubdate == '2008-1'
    assert got.douban_url == 'https://book.douban.com/subject/2567698/'
    assert got.pages == '302'
    assert got.recommend == '27'
    assert got.raters == '800'
    assert got.status == '已读'
    assert got.shelf == 'A-1'

  def test_cleans_isbn_no_duplicate(self, window):
    from services import get_repo
    _seed()
    window._book_form.fill_form(get_repo().get_by_isbn('9787544291163'))
    window._book_form._isbn_input.setText('978-7-5442-9116-3')
    window._book_form._title_input.setText('百年孤独（连字符）')
    window._update_book()
    repo = get_repo()
    # 同一本书不得出现第二条记录
    assert repo.count() == 1
    assert repo.get_by_isbn('9787544291163').title == '百年孤独（连字符）'
    assert repo.get_by_isbn('978-7-5442-9116-3') is None

  def test_rejects_empty_isbn(self, window, monkeypatch):
    _RecordingMessageBox.calls.clear()
    monkeypatch.setattr('ui.main_window.QMessageBox', _RecordingMessageBox)
    window._book_form.clear_form()
    window._book_form._title_input.setText('没有 ISBN 的书')
    window._update_book()
    from services import get_repo
    assert get_repo().count() == 0
    assert _RecordingMessageBox.calls, '应弹出 ISBN 不能为空的警告'
    assert 'ISBN' in _RecordingMessageBox.calls[0][1]


class TestDoubanCallbackWithoutIsbn:
  """豆瓣返回的数据缺 ISBN 时：填表单但不入库（空 ISBN 会互相覆盖）"""

  def test_search_result_not_saved(self, window):
    window._on_search_result(Book(isbn='', title='豆瓣未返回 ISBN 的书'))
    from services import get_repo
    assert get_repo().count() == 0
    # 表单照常填充，方便手动补全 ISBN 后保存
    assert window._book_form._title_input.text() == '豆瓣未返回 ISBN 的书'

  def test_fetch_success_not_saved(self, window):
    window._on_fetch_success(Book(isbn='', title='豆瓣未返回 ISBN 的书'))
    from services import get_repo
    assert get_repo().count() == 0
    assert window._book_form._title_input.text() == '豆瓣未返回 ISBN 的书'
    # 查询结束后按钮恢复可用
    assert window._book_form._btn_fetch.isEnabled()
