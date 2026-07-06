from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget


class DuplicateDialog(QDialog):
  def __init__(self, duplicates, parent=None):
    super().__init__(parent)
    self.setWindowTitle('发现重复记录')
    self.resize(400, 300)
    self.choice = 'skip'
    layout = QVBoxLayout(self)
    layout.addWidget(QLabel(f'发现 {len(duplicates)} 条重复 ISBN：'))
    lst = QListWidget()
    for isbn in duplicates:
      lst.addItem(isbn)
    layout.addWidget(lst)
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
    self.choice = choice
    self.accept()
