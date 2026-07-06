# -*- coding: utf-8 -*-
"""基于 pandas DataFrame 的自定义表格模型"""

import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class BookTableModel(QAbstractTableModel):
  """适配 pandas DataFrame 的表格模型，支持筛选、排序、增删改查"""

  def __init__(self, data: pd.DataFrame = None):
    super().__init__()
    self._original = data if data is not None else pd.DataFrame(
      {c: [] for c in ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']},
      dtype=object,
    )
    self._data = self._original.copy()

  # ── 必需实现 ──────────────────────────────────

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

  # ── 数据操作 ──────────────────────────────────

  def append_row(self, row_data: dict):
    """新增一行"""
    self.beginResetModel()
    self._original.loc[self._original.shape[0]] = row_data
    self._data.loc[self._data.shape[0]] = row_data
    self.endResetModel()

  def _find_in_df(self, df: pd.DataFrame, isbn: str):
    mask = df.iloc[:, 0].astype(str) == isbn
    return mask, mask.any()

  def update_or_insert(self, row: list):
    """按 ISBN 更新；不存在则插入"""
    isbn = str(row[0])
    self.beginResetModel()
    mask_o, found = self._find_in_df(self._original, isbn)
    cols = self._original.columns.tolist()
    if found:
      for idx in range(1, min(len(row), len(cols))):
        self._original.loc[mask_o, cols[idx]] = row[idx]
      mask_d, _ = self._find_in_df(self._data, isbn)
      for idx in range(1, min(len(row), len(cols))):
        self._data.loc[mask_d, cols[idx]] = row[idx]
    else:
      new_row = pd.DataFrame([row[:len(cols)]], columns=cols)
      self._original = pd.concat([self._original, new_row], ignore_index=True)
      self._data = pd.concat([self._data, new_row], ignore_index=True)
    self.endResetModel()

  def delete_by_isbn_batch(self, isbn_list: list):
    self.beginResetModel()
    mask_o = self._original.iloc[:, 0].astype(str).isin(isbn_list)
    self._original.drop(self._original[mask_o].index, inplace=True)
    mask_d = self._data.iloc[:, 0].astype(str).isin(isbn_list)
    self._data.drop(self._data[mask_d].index, inplace=True)
    self.endResetModel()

  def delete_by_isbn(self, isbn: str):
    """按 ISBN 删除"""
    self.beginResetModel()
    mask_o, _ = self._find_in_df(self._original, isbn)
    self._original.drop(self._original[mask_o].index, inplace=True)
    mask_d, _ = self._find_in_df(self._data, isbn)
    self._data.drop(self._data[mask_d].index, inplace=True)
    self.endResetModel()

  def search(self, keyword: str):
    """基于原始数据模糊搜索"""
    self.beginResetModel()
    df = self._original
    self._data = df[
      df['ISBN'].astype(str).str.contains(keyword, na=False)
      | df['书名'].astype(str).str.contains(keyword, na=False)
      | df['作者'].astype(str).str.contains(keyword, na=False)
      | df['出版'].astype(str).str.contains(keyword, na=False)
      | df['分类'].astype(str).str.contains(keyword, na=False)
    ].copy()
    self._data.reset_index(drop=True, inplace=True)
    self.endResetModel()

  def reset_search(self):
    """恢复显示全部数据"""
    self.beginResetModel()
    self._data = self._original.copy()
    self.endResetModel()

  def get_row(self, row: int) -> list:
    """获取指定行的完整数据列表"""
    if row < 0 or row >= self._data.shape[0]:
      return []
    return self._data.iloc[row].values.tolist()

  def get_column_unique(self, col: int) -> list:
    """获取指定列的去重值"""
    return self._original.iloc[:, col].unique().tolist()

  def sort(self, column: int, order: Qt.SortOrder):
    self.beginResetModel()
    col_name = self._data.columns[column]
    ascending = order == Qt.SortOrder.AscendingOrder
    self._data.sort_values(by=col_name, ascending=ascending, inplace=True)
    self._data.reset_index(drop=True, inplace=True)
    self.endResetModel()

  def export_all(self) -> pd.DataFrame:
    """导出全部原始数据"""
    return self._original

  def load_dataframe(self, df: pd.DataFrame):
    """替换整个数据集"""
    self.beginResetModel()
    df = df.reset_index(drop=True)
    self._original = df
    self._data = df.copy()
    self.endResetModel()
