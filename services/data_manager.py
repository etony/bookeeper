# -*- coding: utf-8 -*-
"""数据管理：CSV 加载 / 保存 / 模板导出"""

import pandas as pd
from config import Config


class DataManager:
  """处理 CSV 文件的读写和空值清洗"""

  @staticmethod
  def load_csv(path: str) -> pd.DataFrame:
    """从 CSV 加载数据，清洗空值和索引"""
    df = pd.read_csv(path, dtype='object')
    col_map = {'分类': '状态', '开始日期': '购书日期', '结束日期': '已读日期'}
    df.rename(columns=col_map, inplace=True)
    for col in ['状态', '购书日期', '已读日期']:
      if col not in df.columns:
        df[col] = ''
    df.dropna(subset=['ISBN'], inplace=True)
    df.fillna('', inplace=True)
    return df

  @staticmethod
  def save_csv(path: str, data: pd.DataFrame):
    """保存 DataFrame 到 CSV"""
    data.to_csv(path, index=False, encoding='utf-8-sig')

  @staticmethod
  def export_template(path: str, columns: list):
    """导出空表头模板"""
    df = pd.DataFrame(columns=columns)
    df.to_csv(path, index=False, encoding='utf-8-sig')
