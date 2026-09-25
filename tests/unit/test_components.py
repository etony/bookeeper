"""UI 组件测试"""
import sys
import os
import pytest

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# 设置 PyQt6 所需的环境变量
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    """创建 QApplication 实例（offscreen 模式）"""
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app


# ══════════════════════════════════════════════
#  BookFormWidget 测试
# ══════════════════════════════════════════════

class TestBookFormWidget:
    """测试图书表单组件"""

    def test_create_widget(self, app):
        """测试创建组件"""
        from ui.components.book_form import BookFormWidget
        widget = BookFormWidget()
        assert widget is not None
        assert widget.title() == '图书信息'

    def test_get_form_data_empty(self, app):
        """测试空表单数据"""
        from ui.components.book_form import BookFormWidget
        widget = BookFormWidget()
        data = widget.get_form_data()
        assert data['isbn'] == ''
        assert data['title'] == ''
        assert data['author'] == ''
        assert data['status'] == '默认'

    def test_clear_form(self, app):
        """测试清空表单"""
        from ui.components.book_form import BookFormWidget
        widget = BookFormWidget()
        widget._isbn_input.setText('9787544291163')
        widget._title_input.setText('百年孤独')
        widget.clear_form()
        assert widget._isbn_input.text() == ''
        assert widget._title_input.text() == ''

    def test_get_row_data(self, app):
        """测试获取行数据"""
        from ui.components.book_form import BookFormWidget
        widget = BookFormWidget()
        widget._isbn_input.setText('9787544291163')
        widget._title_input.setText('百年孤独')
        widget._author_input.setText('马尔克斯')
        row = widget.get_row_data()
        assert row[0] == '9787544291163'
        assert row[1] == '百年孤独'
        assert row[2] == '马尔克斯'

    def test_fill_from_row(self, app):
        """测试用行数据填充表单"""
        from ui.components.book_form import BookFormWidget
        widget = BookFormWidget()
        row = ['9787544291163', '百年孤独', '马尔克斯', '南海出版公司', '39.5', '9.2', '12345', '已读', '书架1', '2023-01-01', '2023-06-01']
        widget.fill_from_row(row)
        assert widget._isbn_input.text() == '9787544291163'
        assert widget._title_input.text() == '百年孤独'
        assert widget._author_input.text() == '马尔克斯'

    def test_fetch_signal(self, app):
        """测试获取信号"""
        from ui.components.book_form import BookFormWidget
        widget = BookFormWidget()
        received = []
        widget.fetch_requested.connect(lambda isbn: received.append(isbn))
        widget._isbn_input.setText('9787544291163')
        widget._on_fetch_clicked()
        assert received == ['9787544291163']

    def test_set_fetch_enabled(self, app):
        """测试设置获取按钮状态"""
        from ui.components.book_form import BookFormWidget
        widget = BookFormWidget()
        widget.set_fetch_enabled(False)
        assert not widget._btn_fetch.isEnabled()
        widget.set_fetch_enabled(True)
        assert widget._btn_fetch.isEnabled()

    def test_set_fetch_text(self, app):
        """测试设置获取按钮文字"""
        from ui.components.book_form import BookFormWidget
        widget = BookFormWidget()
        widget.set_fetch_text('测试文字')
        assert widget._btn_fetch.text() == '测试文字'


# ══════════════════════════════════════════════
#  SearchBarWidget 测试
# ══════════════════════════════════════════════

class TestSearchBarWidget:
    """测试搜索栏组件"""

    def test_create_widget(self, app):
        """测试创建组件"""
        from ui.components.search_bar import SearchBarWidget
        widget = SearchBarWidget()
        assert widget is not None
        assert widget.title() == '🔎 搜索'

    def test_get_search_params_default(self, app):
        """测试默认搜索参数"""
        from ui.components.search_bar import SearchBarWidget
        widget = SearchBarWidget()
        keyword, status = widget.get_search_params()
        assert keyword == ''
        assert status == ''

    def test_get_search_params_with_keyword(self, app):
        """测试带关键词的搜索参数"""
        from ui.components.search_bar import SearchBarWidget
        widget = SearchBarWidget()
        widget._search_input.setText('百年孤独')
        keyword, status = widget.get_search_params()
        assert keyword == '百年孤独'
        assert status == ''

    def test_reset(self, app):
        """测试重置搜索"""
        from ui.components.search_bar import SearchBarWidget
        widget = SearchBarWidget()
        widget._search_input.setText('测试')
        widget._search_status.setCurrentIndex(2)
        widget.reset()
        assert widget._search_input.text() == ''
        assert widget._search_status.currentIndex() == 0

    def test_search_signal(self, app):
        """测试搜索信号"""
        from ui.components.search_bar import SearchBarWidget
        widget = SearchBarWidget()
        received = []
        widget.search_requested.connect(lambda k, s: received.append((k, s)))
        widget._search_input.setText('百年孤独')
        widget._on_search()
        assert received == [('百年孤独', '')]

    def test_reset_signal(self, app):
        """测试重置信号"""
        from ui.components.search_bar import SearchBarWidget
        widget = SearchBarWidget()
        received = []
        widget.reset_requested.connect(lambda: received.append(True))
        widget._on_reset()
        assert received == [True]

    def test_set_keyword(self, app):
        """测试设置关键词"""
        from ui.components.search_bar import SearchBarWidget
        widget = SearchBarWidget()
        widget.set_keyword('测试')
        assert widget._search_input.text() == '测试'


# ══════════════════════════════════════════════
#  ToolBarWidget 测试
# ══════════════════════════════════════════════

class TestToolBarWidget:
    """测试工具栏组件"""

    def test_create_widget(self, app):
        """测试创建组件"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        assert widget is not None

    def test_import_signal(self, app):
        """测试导入信号"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        received = []
        widget.import_requested.connect(lambda: received.append(True))
        widget._btn_load.click()
        assert received == [True]

    def test_export_signal(self, app):
        """测试导出信号"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        received = []
        widget.export_requested.connect(lambda: received.append(True))
        widget._btn_save.click()
        assert received == [True]

    def test_stats_signal(self, app):
        """测试统计信号"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        received = []
        widget.stats_requested.connect(lambda: received.append(True))
        widget._btn_stats.click()
        assert received == [True]

    def test_theme_signal(self, app):
        """测试主题信号"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        received = []
        widget.theme_toggled.connect(lambda: received.append(True))
        widget._btn_theme.click()
        assert received == [True]

    def test_web_signal(self, app):
        """测试Web服务信号"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        received = []
        widget.web_toggled.connect(lambda: received.append(True))
        widget._btn_web.click()
        assert received == [True]

    def test_set_file_label(self, app):
        """测试设置文件标签"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        widget.set_file_label('测试标签')
        assert widget._file_label.text() == '测试标签'

    def test_set_web_running(self, app):
        """测试设置Web运行状态"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        widget.set_web_running(True)
        assert widget._btn_web.text() == ' 停止服务'
        widget.set_web_running(False)
        assert widget._btn_web.text() == ' Web 服务'

    def test_set_web_starting(self, app):
        """测试设置Web启动中状态"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        widget.set_web_starting()
        assert widget._btn_web.text() == ' 启动中...'

    def test_set_cover_wall_mode(self, app):
        """测试设置封面墙模式"""
        from ui.components.tool_bar import ToolBarWidget
        widget = ToolBarWidget()
        widget.set_cover_wall_mode(True)
        assert widget._btn_cover_wall.text() == ' 表格视图'
        widget.set_cover_wall_mode(False)
        assert widget._btn_cover_wall.text() == ' 封面墙'


# ══════════════════════════════════════════════
#  WebManager 测试
# ══════════════════════════════════════════════

class TestWebManager:
    """测试 Web 管理器组件"""

    def test_create_manager(self, app):
        """测试创建管理器"""
        from ui.components.web_manager import WebManager
        manager = WebManager()
        assert manager is not None
        assert not manager.is_running

    def test_signals_exist(self, app):
        """测试信号存在"""
        from ui.components.web_manager import WebManager
        manager = WebManager()
        assert hasattr(manager, 'server_started')
        assert hasattr(manager, 'server_stopped')
        assert hasattr(manager, 'error_occurred')
