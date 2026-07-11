import pandas as pd


def load_csv(path: str) -> pd.DataFrame:
  """加载 CSV 文件，自动映射列名（兼容旧版列名）"""
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
  """保存 DataFrame 为 UTF-8 BOM 编码的 CSV"""
  df.to_csv(path, index=False, encoding='utf-8-sig')


def export_template(path: str, columns: list):
  """导出空模板 CSV（仅含列头）"""
  df = pd.DataFrame(columns=columns)
  df.to_csv(path, index=False, encoding='utf-8-sig')
