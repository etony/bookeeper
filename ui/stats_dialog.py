"""
统计面板模块 — StatsDialog。

功能：从主窗口接收 pandas DataFrame，生成三个统计图表：
  1. 阅读状态饼图
  2. 出版社 TOP10 水平条形图
  3. 评分区间柱状图
使用 matplotlib 的 FigureCanvasQTAgg 嵌入 Qt 界面。
必须在使用前设置 matplotlib.use('QtAgg')，否则在无头环境会崩溃。
"""

import matplotlib
matplotlib.use('QtAgg')  # 指定 QtAgg 后端，使 matplotlib 嵌入 PyQt6
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import pandas as pd
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTabWidget


class StatsDialog(QDialog):
  """统计面板对话框，内部以 QTabWidget 容纳多个 matplotlib 图表。"""

  def __init__(self, data: pd.DataFrame, parent=None):
    """
    参数:
      data: 主窗口表格的原始 pandas DataFrame（self._model._original）
      parent: 父窗口
    """
    super().__init__(parent)
    self.setWindowTitle('📊 统计面板')
    self.resize(600, 480)
    self._data = data
    layout = QVBoxLayout(self)
    # 三个图表以 QTabWidget 标签页切换，每个标签页是一个 FigureCanvasQTAgg
    tabs = QTabWidget()
    tabs.addTab(self._make_status_chart(), '阅读状态')
    tabs.addTab(self._make_publisher_chart(), '出版社分布')
    tabs.addTab(self._make_rating_chart(), '评分分布')
    layout.addWidget(tabs)

  def _make_status_chart(self) -> FigureCanvasQTAgg:
    """
    构建「阅读状态分布」饼图。
    从 DataFrame 的 '状态' 列统计频次，用 matplotlib pie 绘制。
    FigureCanvasQTAgg 将 matplotlib Figure 封装为 Qt 控件。
    """
    fig = Figure(figsize=(6, 4))          # 新建 Figure，尺寸英寸
    ax = fig.add_subplot(111)              # 添加单个子图（1行1列第1个）
    counts = self._data.get('状态', pd.Series(dtype=object)).value_counts()
    if not counts.empty:
      ax.pie(counts.values, labels=counts.index.tolist(), autopct='%1.1f%%')
      ax.set_title('图书阅读状态分布')
    else:
      # 无数据时在图表中央显示占位文字
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center')
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_publisher_chart(self) -> FigureCanvasQTAgg:
    """
    构建「出版社 TOP10」水平条形图。
    取 '出版' 列频次前 10，倒序排列（顶部显示最多的出版社）。
    """
    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    counts = self._data.get('出版', pd.Series(dtype=object)).value_counts().head(10)
    if not counts.empty:
      # [::-1] 倒序，使最多的出版社在图表上方
      bars = ax.barh(counts.index.tolist()[::-1], counts.values[::-1])
      # 在每个条形右侧标注数量
      for bar, v in zip(bars, counts.values[::-1]):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2, str(v),
                ha='left', va='center', fontsize=10)
      ax.set_title('出版社 TOP10')
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center')
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_rating_chart(self) -> FigureCanvasQTAgg:
    """
    构建「评分分布」柱状图。
    将 '评分' 列转为数值后按 [0-6, 6-7, 7-8, 8-9, 9-10] 分箱统计。
    pd.cut 做区间划分，reindex 保证缺失的箱显示为 0。
    """
    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ratings = pd.to_numeric(self._data.get('评分', pd.Series(dtype=object)), errors='coerce').dropna()
    if not ratings.empty:
      bins = [0, 6, 7, 8, 9, 10]
      labels = ['0-6', '6-7', '7-8', '8-9', '9-10']
      cats = pd.cut(ratings, bins=bins, labels=labels)
      counts = cats.value_counts().reindex(labels, fill_value=0)
      bars = ax.bar(counts.index.tolist(), counts.values)
      # 柱顶标注数量
      for bar, v in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1, str(v),
                ha='center', va='bottom', fontsize=10)
      ax.set_title('评分分布')
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center')
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)
