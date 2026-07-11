import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class BookTableModel(QAbstractTableModel):
  """Qt Model/View 框架的表格模型，以 pandas DataFrame 为后端存储"""

  def __init__(self, data: pd.DataFrame = None):
    super().__init__()
    self._original = data if data is not None else pd.DataFrame(
      {c: [] for c in ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']},
      dtype=object,
    )
    self._data = self._original.copy()

  def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
    return self._data.shape[0]

  def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
    return self._data.shape[1]

  def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
    if role == Qt.ItemDataRole.DisplayRole:
      if 0 <= index.row() < self._data.shape[0]:
        value = self._data.iloc[index.row(), index.column()]
        return str(value) if not pd.isna(value) else ''
    return None

  def headerData(self, section: int, orientation: Qt.Orientation, role: int):
    if role == Qt.ItemDataRole.DisplayRole:
      if orientation == Qt.Orientation.Horizontal:
        return str(self._data.columns[section])
      if orientation == Qt.Orientation.Vertical:
        return str(section + 1)
    return None

  def update_or_insert(self, row: list):
    """根据 ISBN 更新或插入一行"""
    isbn = str(row[0])
    self.beginResetModel()
    mask_o = self._original.iloc[:, 0].astype(str) == isbn
    found = mask_o.any()
    cols = self._original.columns.tolist()
    if found:
      for idx in range(1, min(len(row), len(cols))):
        self._original.loc[mask_o, cols[idx]] = row[idx]
    else:
      new_row = pd.DataFrame([row[:len(cols)]], columns=cols)
      self._original = pd.concat([self._original, new_row], ignore_index=True)
    self._data = self._original.copy()
    self.endResetModel()

  def delete_by_isbn(self, isbn: str):
    """根据 ISBN 从表格中删除行"""
    self.beginResetModel()
    mask_o = self._original.iloc[:, 0].astype(str) == isbn
    self._original = self._original[~mask_o]
    self._data = self._original.copy()
    self.endResetModel()

  def sort(self, column: int, order: Qt.SortOrder):
    """按指定列排序"""
    self.beginResetModel()
    col_name = self._data.columns[column]
    ascending = order == Qt.SortOrder.AscendingOrder
    self._data.sort_values(by=col_name, ascending=ascending, inplace=True)
    self._data.reset_index(drop=True, inplace=True)
    self.endResetModel()

  def load_dataframe(self, df: pd.DataFrame):
    """全量替换表格数据（用于从数据库重新加载或搜索后展示）"""
    self.beginResetModel()
    df = df.reset_index(drop=True)
    self._original = df
    self._data = df.copy()
    self.endResetModel()
