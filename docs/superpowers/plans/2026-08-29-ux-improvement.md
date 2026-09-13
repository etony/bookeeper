# Bookeeper UX 改进计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全面改善 Bookeeper 桌面应用的用户体验，解决"所有操作都不顺手"的问题

**Architecture:** 采用渐进式改进策略，先解决性能瓶颈，再优化交互流程和视觉反馈，最后添加缺失功能。每个改进独立可测试。

**Tech Stack:** PyQt6, pandas, QThread, QSS

---

## 问题分析

### 1. 性能问题
- 每次增删改查都调用 `_load_data()` 全量重新加载数据
- 封面墙每个卡片都创建独立的 QThread，可能造成线程开销
- 表格模型基于 pandas DataFrame，更新后用 `emitDataChanged()` 刷新

### 2. 交互流程问题
- 表单操作复杂，需要填写多个字段
- 搜索功能分散在主窗口和豆瓣搜索两个入口
- 缺少批量操作（批量修改状态、批量删除等）
- 没有撤销/重做功能

### 3. 视觉反馈问题
- 加载状态提示不够明显
- 表格选中状态的视觉反馈可能不够突出
- 封面墙样式硬编码了暗色主题颜色，可能不跟随主题切换

### 4. 功能缺失
- 没有快捷键提示或帮助文档
- 没有数据验证或输入格式提示
- 日期字段使用 1900-01-01 作为"未设置"的特殊值，可能不够直观

---

## 文件结构

### 修改的文件
- `ui/main_window.py` - 主窗口交互优化
- `ui/theme.py` - 主题样式改进
- `ui/cover_wall.py` - 封面墙性能优化
- `models/table_model.py` - 表格模型性能优化
- `services/data.py` - 数据操作优化

### 新增的文件
- `ui/widgets.py` - 可复用的UI组件
- `services/undo.py` - 撤销/重做功能

---

## 任务分解

### Task 1: 性能优化 - 表格模型增量更新

**Files:**
- Modify: `models/table_model.py:88-101`

- [ ] **Step 1: 添加增量更新方法**

```python
def update_row(self, row: int, data: list):
    """更新单行数据，避免全量刷新"""
    if 0 <= row < self._data.shape[0]:
        for col, value in enumerate(data):
            if col < self._data.shape[1]:
                self._data.iloc[row, col] = value
        self.dataChanged.emit(
            self.index(row, 0),
            self.index(row, self._data.shape[1] - 1)
        )

def insert_row(self, row: int, data: list):
    """插入新行"""
    new_row = pd.DataFrame([data], columns=self._data.columns)
    self.beginInsertRows(QModelIndex(), row, row)
    self._data = pd.concat([self._data.iloc[:row], new_row, self._data.iloc[row:]], 
                           ignore_index=True)
    self.endInsertRows()

def remove_rows(self, rows: list):
    """删除指定行"""
    self.beginResetModel()
    self._data = self._data.drop(rows).reset_index(drop=True)
    self.endResetModel()
```

- [ ] **Step 2: 运行测试验证**

Run: `python -c "from models.table_model import BookTableModel; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add models/table_model.py
git commit -m "feat: add incremental update methods to table model"
```

---

### Task 2: 性能优化 - 主窗口使用增量更新

**Files:**
- Modify: `ui/main_window.py:508-541`

- [ ] **Step 1: 修改 _update_book 方法使用增量更新**

```python
def _update_book(self):
    """从表单读取数据，更新到数据库（使用增量更新）"""
    isbn = self._isbn_input.text().strip()
    title = self._title_input.text().strip()
    if not isbn and not title:
        QMessageBox.warning(self, '提示', '请至少填写 ISBN 或书名')
        return
    
    # 获取当前选中行
    selected = self._table.currentIndex()
    row = selected.row() if selected.isValid() else -1
    
    row_data = [
        isbn,
        self._title_input.text(),
        self._author_input.text(),
        self._publisher_input.text(),
        self._price_input.text(),
        self._rating_input.text().split('/')[0].strip() if '/' in self._rating_input.text() else '0',
        self._rating_input.text().split('/')[-1].strip() if '/' in self._rating_input.text() else '0',
        self._status_combo.currentText() or Config.DEFAULT_STATUS,
        self._shelf_input.text() or Config.DEFAULT_SHELF,
        self._get_date(self._start_date),
        self._get_date(self._end_date),
    ]
    
    book = Book(
        isbn=row_data[0], title=row_data[1], author=row_data[2], publisher=row_data[3],
        price=row_data[4], rating=row_data[5], raters=row_data[6], status=row_data[7],
        shelf=row_data[8], start_date=row_data[9], end_date=row_data[10],
    )
    self._repo.upsert(book)
    self._mark_dirty()
    
    # 使用增量更新
    if row >= 0:
        self._model.update_row(row, row_data)
    else:
        self._load_data()
    
    self.statusBar().showMessage('已更新')
```

- [ ] **Step 2: 运行测试验证**

Run: `python -c "from ui.main_window import MainWindow; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add ui/main_window.py
git commit -m "perf: use incremental update for book editing"
```

---

### Task 3: 性能优化 - 封面墙线程池

**Files:**
- Modify: `ui/cover_wall.py:25-46`

- [ ] **Step 1: 创建封面下载线程池**

```python
import threading
from queue import Queue

class CoverDownloadPool:
    """封面下载线程池，限制并发数量"""
    
    def __init__(self, max_workers=3):
        self._queue = Queue()
        self._workers = []
        self._lock = threading.Lock()
        
        for _ in range(max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self._workers.append(worker)
    
    def _worker_loop(self):
        while True:
            isbn, cover_url, callback = self._queue.get()
            try:
                from services.covers import get_cover
                data, _ = get_cover(isbn, cover_url)
                if callback:
                    callback(isbn, data)
            except Exception:
                if callback:
                    callback(isbn, None)
            finally:
                self._queue.task_done()
    
    def submit(self, isbn: str, cover_url: str, callback=None):
        """提交下载任务"""
        self._queue.put((isbn, cover_url, callback))

# 全局线程池实例
_cover_pool = CoverDownloadPool()
```

- [ ] **Step 2: 修改 CoverCard 使用线程池**

```python
def _start_cover_download(self):
    """使用线程池下载封面"""
    from ui.cover_wall import _cover_pool
    _cover_pool.submit(
        self._book.isbn,
        self._book.cover_url,
        self._on_cover_ready
    )
```

- [ ] **Step 3: 运行测试验证**

Run: `python -c "from ui.cover_wall import CoverWallWidget; print('OK')"`
Expected: OK

- [ ] **Step 4: 提交**

```bash
git add ui/cover_wall.py
git commit -m "perf: use thread pool for cover downloads"
```

---

### Task 4: 交互优化 - 搜索栏即时搜索

**Files:**
- Modify: `ui/main_window.py:262-285`

- [ ] **Step 1: 添加搜索防抖定时器**

```python
def _make_search_bar(self):
    """搜索栏：关键词输入 + 状态下拉 + 查询/重置按钮"""
    g = QGroupBox('🔎 搜索')
    row = QHBoxLayout(g)
    row.setContentsMargins(8, 14, 8, 6)
    row.setSpacing(4)

    self._search_input = QLineEdit()
    self._search_input.setPlaceholderText('输入关键词搜索书名/作者/出版社/ISBN')
    self._search_input.setFixedHeight(34)
    row.addWidget(self._search_input, stretch=1)
    row.addWidget(QLabel('状态'))
    self._search_status = QComboBox()
    self._search_status.addItems(['全部'] + Config.STATUSES)
    self._search_status.setCurrentIndex(0)
    self._search_status.setFixedHeight(34)
    row.addWidget(self._search_status)
    self._btn_search = QPushButton('🔎 查询')
    self._btn_search.setFixedHeight(34)
    self._btn_reset = QPushButton('⟲ 重置')
    self._btn_reset.setFixedHeight(34)
    row.addWidget(self._btn_search)
    row.addWidget(self._btn_reset)
    
    # 添加搜索防抖定时器
    self._search_timer = QTimer(self)
    self._search_timer.setSingleShot(True)
    self._search_timer.timeout.connect(self._search)
    self._search_input.textChanged.connect(self._on_search_text_changed)
    
    return g

def _on_search_text_changed(self, text):
    """搜索文本变化时重置定时器（防抖 300ms）"""
    self._search_timer.stop()
    self._search_timer.start(300)
```

- [ ] **Step 2: 运行测试验证**

Run: `python -c "from ui.main_window import MainWindow; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add ui/main_window.py
git commit -m "feat: add instant search with debounce"
```

---

### Task 5: 交互优化 - 批量操作

**Files:**
- Modify: `ui/main_window.py:619-658`

- [ ] **Step 1: 添加批量修改状态功能**

```python
def _show_context_menu(self, pos):
    """表格右键菜单：删除选中行、批量修改状态"""
    if self._model.rowCount() == 0:
        return
    indexes = self._table.selectedIndexes()
    isbn_list = []
    seen = set()
    for idx in indexes:
        if idx.column() != 0:
            continue
        v = idx.data()
        if v and v not in seen:
            seen.add(v)
            isbn_list.append(str(v))
    if not isbn_list:
        return
    menu = QMenu(self)
    view_action = QAction(QIcon(), '📖 查看详情', self)
    edit_action = QAction(QIcon(), '✏️ 编辑', self)
    delete_action = QAction(QIcon(), '🗑 删除选中', self)
    
    # 批量操作子菜单
    batch_menu = QMenu('批量操作', menu)
    for status in Config.STATUSES:
        action = QAction(QIcon(), f'设为"{status}"', batch_menu)
        action.setData(('status', status))
        batch_menu.addAction(action)
    
    menu.addAction(view_action)
    menu.addAction(edit_action)
    menu.addSeparator()
    menu.addMenu(batch_menu)
    menu.addSeparator()
    menu.addAction(delete_action)
    
    action = menu.exec(self._table.mapToGlobal(pos))
    if action == view_action and isbn_list:
        self._open_detail(isbn_list[0])
    elif action == edit_action and isbn_list:
        self._load_by_isbn(isbn_list[0])
    elif action and action.data() and action.data()[0] == 'status':
        # 批量修改状态
        new_status = action.data()[1]
        self._batch_update_status(isbn_list, new_status)
    elif action == delete_action:
        ret = QMessageBox.question(
            self, '确认删除',
            f'确定删除选中的 {len(isbn_list)} 本图书？此操作不可撤销。',
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        for isbn in isbn_list:
            self._repo.delete(isbn)
        self._mark_dirty()
        self._load_data()

def _batch_update_status(self, isbn_list: list, new_status: str):
    """批量修改图书状态"""
    for isbn in isbn_list:
        book = self._repo.get_by_isbn(isbn)
        if book:
            book.status = new_status
            self._repo.upsert(book)
    self._mark_dirty()
    self._load_data()
    self.statusBar().showMessage(f'已将 {len(isbn_list)} 本图书设为"{new_status}"')
```

- [ ] **Step 2: 运行测试验证**

Run: `python -c "from ui.main_window import MainWindow; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add ui/main_window.py
git commit -m "feat: add batch status update in context menu"
```

---

### Task 6: 视觉优化 - 加载状态提示

**Files:**
- Modify: `ui/main_window.py:454-490`

- [ ] **Step 1: 改进豆瓣查询的加载提示**

```python
def _fetch_book(self):
    """从豆瓣 API 获取 ISBN 对应的图书信息并填入表单"""
    from utils import clean_isbn, is_valid_isbn13, is_valid_isbn10
    raw = self._isbn_input.text().strip()
    isbn = clean_isbn(raw)
    if not isbn:
        return

    if len(isbn) == 13 and not is_valid_isbn13(isbn):
        QMessageBox.warning(self, '错误', f'ISBN-13 校验位无效: {isbn}')
        return
    if len(isbn) == 10 and not is_valid_isbn10(isbn):
        QMessageBox.warning(self, '错误', f'ISBN-10 校验位无效: {isbn}')
        return

    # 禁用按钮，显示加载状态
    self._btn_fetch.setEnabled(False)
    self._btn_fetch.setText('⏳ 查询中...')
    self.statusBar().showMessage('正在查询豆瓣...')
    
    # 使用 QTimer.singleShot 模拟异步（实际仍是同步，但界面会更新）
    QTimer.singleShot(50, lambda: self._do_fetch_book(isbn))

def _do_fetch_book(self, isbn: str):
    """实际执行豆瓣查询"""
    book = self._api.get_book_by_isbn(isbn)
    
    # 恢复按钮状态
    self._btn_fetch.setEnabled(True)
    self._btn_fetch.setText('🌐 获取信息')
    
    if not book:
        QMessageBox.warning(self, '错误', f'未找到图书: {isbn}')
        self.statusBar().showMessage('查询失败')
        return

    self._merge_user_fields(book)
    self._fill_form(book)
    self._repo.upsert(book)
    self._mark_dirty()
    self._load_data()
    self.statusBar().showMessage(f'已获取: {book.title}')
```

- [ ] **Step 2: 运行测试验证**

Run: `python -c "from ui.main_window import MainWindow; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add ui/main_window.py
git commit -m "feat: improve loading feedback for Douban API calls"
```

---

### Task 7: 视觉优化 - 表格选中状态

**Files:**
- Modify: `ui/theme.py:60-113`

- [ ] **Step 1: 改进表格选中状态样式**

```python
# 暗色主题 QSS：深灰背景 + 橙色强调
DARK_QSS = BASE + '''
QWidget { background-color: #1c1c1f; color: #e0e0e4; }
QLineEdit, QComboBox, QTextBrowser {
  background-color: #26262b; border: 1px solid #38383f; color: #eaeaea;
}
QDateEdit { background-color: #26262b; border: 1px solid #38383f; color: #eaeaea; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
  border-color: #e8922a; background-color: #202025;
}
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
  image: none; border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid #7a7a80; margin-right: 6px;
}
QComboBox QAbstractItemView {
  background-color: #26262b; border: 1px solid #38383f;
  selection-background-color: #3a3528;
}
QPushButton { background-color: #2c2c33; border: 1px solid #3a3a42; color: #e0e0e4; }
QPushButton:hover { background-color: #363640; border-color: #e8922a; }
QPushButton:pressed { background-color: #222228; }
QPushButton:disabled { background-color: #202024; color: #5a5a60; }
QGroupBox { background-color: #242428; border-color: #323238; }
QGroupBox::title { color: #eaeaea; }
QTableView {
  background-color: #1c1c1f; alternate-background-color: #252528;
  border-color: #323238; gridline-color: #28282e;
  selection-background-color: #3a3528; selection-color: #fff;
}
QTableView::item:hover { background-color: #2a2825; }
QTableView::item:selected { 
  background-color: #e8922a; color: #1c1c1f; 
  border: 1px solid #e8922a;
}
QHeaderView::section {
  background-color: #26262b;
  border-right: 1px solid #323238; border-bottom: 1px solid #323238;
  color: #9a9aa0;
}
QScrollBar::handle:vertical { background: #38383f; }
QScrollBar::handle:vertical:hover { background: #484850; }
QScrollBar::handle:horizontal { background: #38383f; }
QScrollBar::handle:horizontal:hover { background: #484850; }
QStatusBar { background: #242428; border-top-color: #323238; color: #8a8a8a; }
QMenu { background-color: #26262b; border: 1px solid #38383f; }
QMenu::item:selected { background-color: #3a3528; }
QDialog { background-color: #1c1c1f; }
QTextBrowser { background-color: #242428; }
QMessageBox { background-color: #1c1c1f; }
QMessageBox QLabel { color: #e0e0e4; }
QToolTip {
  background-color: #26262b; color: #e0e0e4;
  border: 1px solid #38383f; padding: 4px 8px;
  border-radius: 4px; font-size: 12px;
}

'''
```

- [ ] **Step 2: 运行测试验证**

Run: `python -c "from ui.theme import DARK_QSS; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add ui/theme.py
git commit -m "style: improve table selection visibility"
```

---

### Task 8: 视觉优化 - 封面墙跟随主题

**Files:**
- Modify: `ui/cover_wall.py:127-132`

- [ ] **Step 1: 修改封面墙样式跟随主题**

```python
def _update_style(self, hovered: bool):
    """更新卡片边框样式（跟随主题）"""
    from ui.theme import ACCENT
    if hovered:
        self.setStyleSheet(f'QFrame {{ border: 2px solid {ACCENT}; border-radius: 6px; background-color: #2a2a2e; }}')
    else:
        self.setStyleSheet('QFrame { border: 1px solid #3a3a40; border-radius: 6px; background-color: #2a2a2e; }')
```

- [ ] **Step 2: 运行测试验证**

Run: `python -c "from ui.cover_wall import CoverCard; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add ui/cover_wall.py
git commit -m "style: make cover wall follow theme accent color"
```

---

### Task 9: 功能增强 - 撤销/重做基础

**Files:**
- Create: `services/undo.py`

- [ ] **Step 1: 创建撤销/重做服务**

```python
"""
┌──────────────────────────────────────────┐
│  撤销/重做服务                            │
│                                          │
│  基于命令模式的撤销/重做功能，             │
│  支持图书的增删改操作。                    │
└──────────────────────────────────────────┘
"""

from typing import List, Callable
from models.book import Book


class UndoCommand:
    """撤销/重做命令基类"""
    
    def __init__(self, description: str):
        self.description = description
    
    def execute(self):
        raise NotImplementedError
    
    def undo(self):
        raise NotImplementedError


class AddBookCommand(UndoCommand):
    """添加图书命令"""
    
    def __init__(self, repo, book: Book):
        super().__init__(f'添加《{book.title}》')
        self._repo = repo
        self._book = book
    
    def execute(self):
        self._repo.upsert(self._book)
    
    def undo(self):
        self._repo.delete(self._book.isbn)


class DeleteBookCommand(UndoCommand):
    """删除图书命令"""
    
    def __init__(self, repo, book: Book):
        super().__init__(f'删除《{book.title}》')
        self._repo = repo
        self._book = book
    
    def execute(self):
        self._repo.delete(self._book.isbn)
    
    def undo(self):
        self._repo.upsert(self._book)


class UpdateBookCommand(UndoCommand):
    """更新图书命令"""
    
    def __init__(self, repo, old_book: Book, new_book: Book):
        super().__init__(f'更新《{new_book.title}》')
        self._repo = repo
        self._old_book = old_book
        self._new_book = new_book
    
    def execute(self):
        self._repo.upsert(self._new_book)
    
    def undo(self):
        self._repo.upsert(self._old_book)


class UndoManager:
    """撤销/重做管理器"""
    
    def __init__(self, max_history: int = 50):
        self._undo_stack: List[UndoCommand] = []
        self._redo_stack: List[UndoCommand] = []
        self._max_history = max_history
    
    def execute(self, command: UndoCommand):
        """执行命令并加入撤销栈"""
        command.execute()
        self._undo_stack.append(command)
        self._redo_stack.clear()
        
        # 限制历史记录数量
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
    
    def undo(self) -> bool:
        """撤销上一个命令"""
        if not self._undo_stack:
            return False
        
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        return True
    
    def redo(self) -> bool:
        """重做上一个撤销的命令"""
        if not self._redo_stack:
            return False
        
        command = self._redo_stack.pop()
        command.execute()
        self._undo_stack.append(command)
        return True
    
    def can_undo(self) -> bool:
        """是否可以撤销"""
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """是否可以重做"""
        return len(self._redo_stack) > 0
    
    def clear(self):
        """清空历史记录"""
        self._undo_stack.clear()
        self._redo_stack.clear()
```

- [ ] **Step 2: 运行测试验证**

Run: `python -c "from services.undo import UndoManager; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add services/undo.py
git commit -m "feat: add undo/redo service with command pattern"
```

---

### Task 10: 功能增强 - 集成撤销/重做到主窗口

**Files:**
- Modify: `ui/main_window.py:53-66`

- [ ] **Step 1: 在主窗口集成撤销管理器**

```python
def __init__(self):
    super().__init__()
    self._repo = get_repo()
    self._api = DoubanService()
    self._backup_svc = BackupService()
    self._undo_manager = UndoManager()  # 新增
    self._dirty = False
    self._dark_mode = True
    self._setup_ui()
    self._init_table()
    self._connect_signals()
    self._setup_shortcuts()
    self._setup_backup_timer()
    self._load_settings()
```

- [ ] **Step 2: 添加撤销/重做快捷键**

```python
def _setup_shortcuts(self):
    """注册全局快捷键"""
    QShortcut(QKeySequence('Ctrl+S'), self, self._save_csv)
    QShortcut(QKeySequence('Ctrl+F'), self, self._search_input.setFocus)
    QShortcut(QKeySequence('Ctrl+R'), self, self._reset_search)
    QShortcut(QKeySequence('Ctrl+D'), self, self._open_search_dialog)
    QShortcut(QKeySequence('Ctrl+W'), self, self._toggle_cover_wall)
    QShortcut(QKeySequence('Ctrl+Z'), self, self._undo)  # 新增
    QShortcut(QKeySequence('Ctrl+Y'), self, self._redo)  # 新增
    QShortcut(QKeySequence('Ctrl+Shift+Z'), self, self._redo)  # 新增
```

- [ ] **Step 3: 添加撤销/重做方法**

```python
def _undo(self):
    """撤销上一个操作"""
    if self._undo_manager.undo():
        self._load_data()
        self.statusBar().showMessage('已撤销')
    else:
        self.statusBar().showMessage('没有可撤销的操作')

def _redo(self):
    """重做上一个撤销的操作"""
    if self._undo_manager.redo():
        self._load_data()
        self.statusBar().showMessage('已重做')
    else:
        self.statusBar().showMessage('没有可重做的操作')
```

- [ ] **Step 4: 运行测试验证**

Run: `python -c "from ui.main_window import MainWindow; print('OK')"`
Expected: OK

- [ ] **Step 5: 提交**

```bash
git add ui/main_window.py
git commit -m "feat: integrate undo/redo into main window"
```

---

## 验证计划

### 功能测试
1. 测试表格增量更新：编辑图书后验证表格实时更新
2. 测试即时搜索：输入关键词后验证自动搜索
3. 测试批量操作：右键菜单批量修改状态
4. 测试撤销/重做：Ctrl+Z/Ctrl+Y 快捷键

### 性能测试
1. 测试大量数据时的表格响应速度
2. 测试封面墙加载多个封面时的性能
3. 测试搜索大量数据时的响应速度

### 视觉测试
1. 测试表格选中状态的可见性
2. 测试封面墙颜色是否跟随主题
3. 测试加载状态提示是否明显

---

## 执行选项

**计划已保存到 `docs/superpowers/plans/2026-08-29-ux-improvement.md`。两种执行方式：**

**1. Subagent-Driven (推荐)** - 每个任务分发一个新子代理，任务间审查，快速迭代

**2. Inline Execution** - 在当前会话中执行任务，批量执行带检查点

**选择哪种方式？**