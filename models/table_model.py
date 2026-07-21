"""
┌──────────────────────────────────────────┐
│  Qt 表格模型                             │
│                                          │
│  实现 QAbstractTableModel，               │
│  以 pandas DataFrame 为后端存储，          │
│  支持排序、编辑、删除等操作。              │
└──────────────────────────────────────────┘
"""

import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class BookTableModel(QAbstractTableModel):
  """
  Qt Model/View 框架的表格模型。

  为什么用自定义模型而不是 QStandardItemModel？
    1. 性能更好——批量操作时不需要逐个创建 QStandardItem
    2. 和 pandas DataFrame 无缝衔接，搜索/筛选后直接替换数据
    3. 支持随数据量线性扩展的大列表

  核心数据：
    - self._original: 完整数据集的副本（用于增删操作时保持完整性）
    - self._data: 当前视图数据（搜索/排序后可能只包含子集）
  """

  def __init__(self, data: pd.DataFrame = None):
    super().__init__()
    cols = ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']
    self._original = data if data is not None else pd.DataFrame(
      {c: [] for c in cols}, dtype=object,
    )
    self._data = self._original.copy()

  # ── Qt Model 接口 ──────────────────────────────────────

  def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
    """行数 = DataFrame 的行数"""
    return self._data.shape[0]

  def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
    """列数 = DataFrame 的列数"""
    return self._data.shape[1]

  def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
    """
    返回指定单元格的显示值。

    Qt 的表格在渲染每一格时都会调用这个方法，
    所以必须高效——这里直接用了 pandas 的 iloc 快速定位。
    """
    if role == Qt.ItemDataRole.DisplayRole:
      if 0 <= index.row() < self._data.shape[0]:
        value = self._data.iloc[index.row(), index.column()]
        return str(value) if not pd.isna(value) else ''
    return None

  def headerData(self, section: int, orientation: Qt.Orientation, role: int):
    """
    返回列名（水平标题）和行号（垂直标题）。

    水平标题来自 DataFrame 的列名，
    垂直标题是行号+1（从 1 开始计数，更符合习惯）。
    """
    if role == Qt.ItemDataRole.DisplayRole:
      if orientation == Qt.Orientation.Horizontal:
        return str(self._data.columns[section])
      if orientation == Qt.Orientation.Vertical:
        return str(section + 1)
    return None

  def sort(self, column: int, order: Qt.SortOrder):
    """
    按指定列排序。

    这是 QTableView.setSortingEnabled(True) 的回调，
    当用户点击表头时自动触发。
    """
    self.beginResetModel()
    col_name = self._data.columns[column]
    ascending = order == Qt.SortOrder.AscendingOrder
    self._data.sort_values(by=col_name, ascending=ascending, inplace=True)
    self._data.reset_index(drop=True, inplace=True)
    self.endResetModel()

  def load_dataframe(self, df: pd.DataFrame):
    """
    全量替换表格数据。

    每次从数据库重新加载或搜索后，
    都通过此方法把新数据喂给表格。

    用 beginResetModel / endResetModel 通知 Qt 视图完全刷新。
    """
    self.beginResetModel()
    df = df.reset_index(drop=True)
    self._original = df
    self._data = df.copy()
    self.endResetModel()
