# -*- coding: utf-8 -*-
"""基于 pandas DataFrame 的自定义 Qt 表格模型

为图书管理应用提供 QAbstractTableModel 实现，将 pandas DataFrame 包装为 Qt 表格视图可用的数据源。
核心设计是"双表机制"（_original / _data），实现搜索筛选与原始数据分离：
  - _original：始终持有完整数据，永不修改行数
  - _data：当前 UI 显示的数据快照，搜索时从中筛选，排序操作也仅影响此副本
这样 reset_search() 只需从 _original 复制即可恢复，无需重新加载文件。
"""

import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class BookTableModel(QAbstractTableModel):
  """适配 pandas DataFrame 的 Qt 表格模型，支持筛选、排序、增删改查

  双表设计（_original / _data）：
    这是本模型最核心的设计。_original 始终保存完整数据集，所有数据修改（增删改）
    同时操作两个表；_data 是当前 UI 看到的数据快照，search() 从这个快照中筛选行，
    sort() 也只排序 _data。这样 reset_search() 直接复制 _original 即可恢复全量显示，
    避免了每次搜索都要从原始文件重新加载的性能开销。

  Qt 接口说明：
    继承 QAbstractTableModel 后必须实现 rowCount、columnCount、data 三个方法，
    headerData 为可选，但不实现则表格无表头。
  """

  def __init__(self, data: pd.DataFrame = None):
    """初始化表格模型

    参数:
      data: 包含完整图书数据的 DataFrame。默认列依次为：
            ISBN、书名、作者、出版、价格、评分、人数、状态、书柜、购书日期、已读日期
            如果传入 None，则创建一个空表（保留列结构，方便后续动态添加数据）。
    """
    super().__init__()
    # _original: 原始完整数据集，所有增删改操作基于此表，搜索时作为筛选源
    self._original = data if data is not None else pd.DataFrame(
      {c: [] for c in ['ISBN', '书名', '作者', '出版', '价格', '评分', '人数', '状态', '书柜', '购书日期', '已读日期']},
      dtype=object,
    )
    # _data: UI 显示的数据快照，search() 和 sort() 只操作此副本
    self._data = self._original.copy()
    self._search_keyword = ''   # 当前搜索关键词，空串表示未搜索
    self._status_filter = ''    # 当前状态筛选值，空串表示不过滤状态

  # ── 必需实现（QAbstractTableModel 抽象方法） ──

  def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
    """返回当前显示的数据行数（_data 的行数）"""
    return self._data.shape[0]

  def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
    """返回表格列数"""
    return self._data.shape[1]

  def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
    """返回指定单元格的显示值

    Qt 表格视图在绘制每个单元格时都会调用此方法。
    只处理 DisplayRole 角色，其他角色（如背景色、对齐方式等）返回 None 使用默认样式。
    NaN 值转换为空字符串，避免表格中显示 "nan"。
    """
    if role == Qt.ItemDataRole.DisplayRole:
      if 0 <= index.row() < self._data.shape[0]:
        value = self._data.iloc[index.row(), index.column()]
        return str(value) if not pd.isna(value) else ''
    return None

  def headerData(self, section: int, orientation: Qt.Orientation, role: int):
    """返回表头（横向为列名，纵向为行号）"""
    if role == Qt.ItemDataRole.DisplayRole:
      if orientation == Qt.Orientation.Horizontal:
        return str(self._data.columns[section])
      if orientation == Qt.Orientation.Vertical:
        return str(section + 1)  # 行号从 1 开始
    return None

  # ── 数据操作（双表同步） ──────────────────────

  def _rebuild_data(self):
    """从 _original 按关键词+状态筛选重建 _data"""
    df = self._original.copy()
    # 关键词模糊搜索（遍历所有列）
    if self._search_keyword:
      mask = pd.Series(False, index=df.index)
      for col in df.columns:
        mask |= df[col].astype(str).str.contains(self._search_keyword, na=False)
      df = df[mask]
    # 状态精确筛选（仅匹配"状态"列）
    if self._status_filter and '状态' in df.columns:
      df = df[df['状态'].astype(str) == self._status_filter]
    self._data = df
    self._data.reset_index(drop=True, inplace=True)

  def _find_in_df(self, df: pd.DataFrame, isbn: str):
    """在 DataFrame 中按 ISBN 查找行

    返回 (bool_mask, 是否找到) 二元组。使用 mask 而非 index 定位，
    是因为 drop 或筛选后行号可能改变但 mask 始终有效。
    """
    mask = df.iloc[:, 0].astype(str) == isbn  # 第 0 列固定为 ISBN
    return mask, mask.any()

  def update_or_insert(self, row: list):
    """按 ISBN 更新已有行；未找到则追加为新行

    更新仅在 _original 上执行，然后调用 _rebuild_data() 重建 _data。
    这样做的原因：搜索状态下直接更新 _data 会导致修改后的行不再匹配
    当前搜索关键词但仍然显示在结果中（如搜索"已读"后修改状态为"默认"）。
    通过 _original → _rebuild_data() 的方式，每次修改后都重新评估筛选条件。

    注意：此方法会丢失当前排序状态，因为 _rebuild_data() 会重建 _data。

    参数:
      row: 表格行数据列表（第 0 项为 ISBN，后续依次为各列值）
    """
    isbn = str(row[0])
    self.beginResetModel()
    mask_o, found = self._find_in_df(self._original, isbn)
    cols = self._original.columns.tolist()
    if found:
      for idx in range(1, min(len(row), len(cols))):
        self._original.loc[mask_o, cols[idx]] = row[idx]
    else:
      new_row = pd.DataFrame([row[:len(cols)]], columns=cols)
      self._original = pd.concat([self._original, new_row], ignore_index=True)
    # 更新/插入后重新构建 _data，使当前搜索筛选条件重新生效
    # 例如：搜索"已读"后修改状态为"默认"，该书应移出筛选结果
    self._rebuild_data()
    self.endResetModel()

  def delete_by_isbn_batch(self, isbn_list: list):
    """批量删除指定 ISBN 的行（一次性操作比逐条删除更高效）

    使用 isin() 一次匹配多个 ISBN，比循环调用 delete_by_isbn 减少
    beginResetModel/endResetModel 的刷新开销。
    """
    self.beginResetModel()
    mask_o = self._original.iloc[:, 0].astype(str).isin(isbn_list)
    self._original.drop(self._original[mask_o].index, inplace=True)
    mask_d = self._data.iloc[:, 0].astype(str).isin(isbn_list)
    self._data.drop(self._data[mask_d].index, inplace=True)
    self.endResetModel()

  def delete_by_isbn(self, isbn: str):
    """按 ISBN 删除单条记录"""
    self.beginResetModel()
    mask_o, _ = self._find_in_df(self._original, isbn)
    self._original.drop(self._original[mask_o].index, inplace=True)
    mask_d, _ = self._find_in_df(self._data, isbn)
    self._data.drop(self._data[mask_d].index, inplace=True)
    self.endResetModel()

  def search(self, keyword: str):
    """基于关键词和状态筛选更新 _data

    与 _rebuild_data() 的区别：search 同时设置 _search_keyword，
    而 _rebuild_data() 只使用已设置的值重新构建。

    注意：会丢失排序状态。
    """
    self._search_keyword = keyword
    self.beginResetModel()
    self._rebuild_data()
    self.endResetModel()

  def apply_filters(self, keyword: str, status: str = ''):
    """同时设置关键词和状态筛选，仅触发一次 _rebuild_data()

    参数:
      keyword: 模糊搜索关键词（空串表示无关键词筛选）
      status:  状态精确匹配值（空串表示无状态筛选）
    """
    self._search_keyword = keyword
    self._status_filter = status
    self.beginResetModel()
    self._rebuild_data()
    self.endResetModel()

  def set_status_filter(self, status: str):
    """仅设置状态筛选值，触发 _rebuild_data()

    参数为空串时清除状态筛选。单设状态时用此方法。
    """
    self._status_filter = status
    self.beginResetModel()
    self._rebuild_data()
    self.endResetModel()

  def reset_search(self):
    """重置搜索和状态筛选，恢复显示全部数据"""
    self._search_keyword = ''
    self._status_filter = ''
    self.beginResetModel()
    self._data = self._original.copy()
    self.endResetModel()

  def get_row(self, row: int) -> list:
    """获取当前显示数据中指定行的完整值列表

    用于导出选中行数据、或传递给编辑对话框。
    行号超出范围时返回空列表而非抛异常。
    """
    if row < 0 or row >= self._data.shape[0]:
      return []
    return self._data.iloc[row].values.tolist()

  def get_column_unique(self, col: int) -> list:
    """获取指定列的所有不重复值

    用于下拉筛选（如"书柜"列去重后列出可用值）。
    从 _original 取数据确保覆盖全量，不受当前搜索状态影响。
    """
    return self._original.iloc[:, col].unique().tolist()

  def sort(self, column: int, order: Qt.SortOrder):
    """按指定列排序

    实现原理：
      只对 _data 排序，不影响 _original。这样搜索之后可以排序，
      重置搜索后回到 _original 的原始顺序。
      使用 inplace=True 直接修改 _data 避免创建副本。

    参数:
      column: 列索引（0-based）
      order: Qt.SortOrder.AscendingOrder 或 DescendingOrder
    """
    self.beginResetModel()
    col_name = self._data.columns[column]
    ascending = order == Qt.SortOrder.AscendingOrder
    self._data.sort_values(by=col_name, ascending=ascending, inplace=True)
    self._data.reset_index(drop=True, inplace=True)
    self.endResetModel()

  def export_all(self) -> pd.DataFrame:
    """导出全部原始数据（用于保存到文件）

    返回 _original 的引用而非副本，调用方不应修改返回的 DataFrame。
    如果调用方需要修改，应自行 .copy()。
    """
    return self._original

  def load_dataframe(self, df: pd.DataFrame):
    """用新的 DataFrame 替换整个数据集

    用于从文件重新加载数据后刷新模型。
    会重置所有搜索和排序状态。
    reset_index(drop=True) 保证行号从 0 开始连续。
    """
    self.beginResetModel()
    df = df.reset_index(drop=True)
    self._original = df
    self._data = df.copy()
    self.endResetModel()
