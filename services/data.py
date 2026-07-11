"""
┌──────────────────────────────────────────┐
│  CSV 数据导入/导出                       │
│                                          │
│  处理 CSV 文件的列名映射和编码转换，       │
│  兼容旧版本的列名（如"分类"→"状态"）。     │
└──────────────────────────────────────────┘
"""

import pandas as pd


def load_csv(path: str) -> pd.DataFrame:
  """
  从 CSV 文件加载图书数据。

  兼容处理：
    - "分类" 自动映射为 "状态"
    - "开始日期" 自动映射为 "购书日期"
    - "结束日期" 自动映射为 "已读日期"
    - 缺少的列自动填充空字符串
    - ISBN 为空的行自动丢弃
  """
  df = pd.read_csv(path, dtype='object')
  col_map = {'分类': '状态', '开始日期': '购书日期', '结束日期': '已读日期'}
  df.rename(columns=col_map, inplace=True)
  for col in ['状态', '购书日期', '已读日期']:
    if col not in df.columns:
      df[col] = ''
  df.dropna(subset=['ISBN'], inplace=True)
  df.fillna('', inplace=True)
  return df


def save_csv(path: str, df: pd.DataFrame):
  """
  将 DataFrame 保存为 CSV 文件。

  使用 UTF-8 BOM 编码，确保 Excel（尤其是 Windows 版）
  能正确识别中文，不会出现乱码。
  """
  df.to_csv(path, index=False, encoding='utf-8-sig')
