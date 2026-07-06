"""
重复记录处理对话框模块 — DuplicateDialog。

功能：加载 CSV 时，若新文件中的 ISBN 与已有记录重复，
      弹出此对话框让用户选择处理方式：
        - skip（跳过）     : 不导入重复记录
        - overwrite（覆盖）  : 删除旧记录、写入新记录
        - merge（合并）      : 用新数据更新旧记录字段
选择结果保存在 self.choice 中，由 MainWindow._load_csv 读取。
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget


class DuplicateDialog(QDialog):
  """让用户在导入重复 ISBN 时选择处理策略。"""

  def __init__(self, duplicates, parent=None):
    """
    参数:
      duplicates: 重复的 ISBN 字符串列表（list[str]）
      parent: 父窗口
    choice 属性:
      用户选择的策略字符串：'skip' | 'overwrite' | 'merge'
    """
    super().__init__(parent)
    self.setWindowTitle('发现重复记录')
    self.resize(400, 300)
    self.choice = 'skip'  # 默认跳过
    layout = QVBoxLayout(self)
    layout.addWidget(QLabel(f'发现 {len(duplicates)} 条重复 ISBN：'))

    # 使用 QListWidget 列出所有重复的 ISBN，供用户直观查看
    lst = QListWidget()
    for isbn in duplicates:
      lst.addItem(isbn)
    layout.addWidget(lst)

    # 三个决策按钮，点击后设置 choice 并关闭对话框
    btns = QHBoxLayout()
    skip_btn = QPushButton('跳过（保留现有）')
    overwrite_btn = QPushButton('覆盖（用新数据替换）')
    merge_btn = QPushButton('合并（新数据更新旧记录）')
    skip_btn.clicked.connect(lambda: self._choose('skip'))
    overwrite_btn.clicked.connect(lambda: self._choose('overwrite'))
    merge_btn.clicked.connect(lambda: self._choose('merge'))
    btns.addWidget(skip_btn)
    btns.addWidget(overwrite_btn)
    btns.addWidget(merge_btn)
    layout.addLayout(btns)

  def _choose(self, choice):
    """记录用户选择并关闭对话框，由 MainWindow._load_csv 读取 self.choice。"""
    self.choice = choice
    self.accept()
