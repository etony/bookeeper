# -*- coding: utf-8 -*-
"""数据管理：CSV 加载 / 保存 / 模板导出

模块功能：
  - load_csv():          从 CSV 文件加载数据，同时兼容旧版列名（列名映射转换）
  - save_csv():          将 DataFrame 保存为 CSV 文件（UTF-8 BOM 编码）
  - export_template():   生成仅有表头的空 CSV 模板文件

列名映射说明：
  旧版本使用 '分类' / '开始日期' / '结束日期' 等列名，
  新版本改为 '状态' / '购书日期' / '已读日期'。
  load_csv 自动将旧列名映射到新列名，保证数据兼容。
"""

import pandas as pd
from config import Config


class DataManager:
  """处理 CSV 文件的读写和空值清洗

  所有方法均为静态方法，不持有状态。
  load_csv 内部处理列名兼容性（旧→新映射）和空值清洗，
  save_csv 与 export_template 专职写入。
  """

  @staticmethod
  def load_csv(path: str) -> pd.DataFrame:
    """从 CSV 加载数据，清洗空值和索引

    处理流程：
      1. 以 object 类型（字符串）读取 CSV，避免 pandas 自动推断类型导致 ISBN 等字段丢失前导零
      2. 执行列名映射：旧版列名 -> 新版列名
         - '分类'    -> '状态'      （阅读状态：未读/在读/已读）
         - '开始日期' -> '购书日期'   （购买日期）
         - '结束日期' -> '已读日期'   （读完日期）
      3. 确保目标列存在，缺失则补充空字符串
      4. 删除 ISBN 为空的行（无 ISBN 的数据无意义）
      5. 其余空值全部填充为空字符串

    参数：
      path: CSV 文件的绝对路径或相对路径

    返回：
      清洗后的 DataFrame，所有值为字符串类型

    注意事项：
      - dtype='object' 防止 ISBN 这类纯数字被当作 int 读取（丢失前导 0）
      - 映射字典 col_map 中已包含旧→新的全部映射关系
      - dropna(subset=['ISBN']) 删除关键数据缺失的行
      - 此处没有对列的顺序做假设：映射后保留原 CSV 的所有列（映射过的列名已替换，未映射的保留原样）
    """
    df = pd.read_csv(path, dtype='object')
    # 旧列名 → 新列名映射：兼容旧版本 CSV 格式
    col_map = {'分类': '状态', '开始日期': '购书日期', '结束日期': '已读日期'}
    df.rename(columns=col_map, inplace=True)
    # 确保新版本的必需列存在，缺失则补充空值（防止后续代码访问不存在的列）
    for col in ['状态', '购书日期', '已读日期']:
      if col not in df.columns:
        df[col] = ''
    df.dropna(subset=['ISBN'], inplace=True)
    df.fillna('', inplace=True)
    return df

  @staticmethod
  def save_csv(path: str, data: pd.DataFrame):
    """保存 DataFrame 到 CSV

    使用 UTF-8 BOM 编码（utf-8-sig），确保 Excel 打开 CSV 时正确识别中文。
    不保存行索引（index=False）。

    参数：
      path: 输出文件路径
      data: 要保存的 DataFrame
    """
    data.to_csv(path, index=False, encoding='utf-8-sig')

  @staticmethod
  def export_template(path: str, columns: list):
    """导出空表头模板

    生成一个只包含列名、没有任何数据行的空白 CSV 文件，
    用户可以基于此模板填写数据后再导入。

    参数：
      path:    模板文件保存路径
      columns: 列名列表，决定模板的列顺序
    """
    df = pd.DataFrame(columns=columns)
    df.to_csv(path, index=False, encoding='utf-8-sig')
