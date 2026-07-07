"""
统计面板模块 — StatsDialog。

功能：从主窗口接收 pandas DataFrame，生成三个统计图表：
  1. 阅读状态饼图
  2. 出版社 TOP10 水平条形图
  3. 评分区间柱状图
使用 matplotlib 的 FigureCanvasQTAgg 嵌入 Qt 界面。
"""

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import pandas as pd
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTabWidget

DARK_BG = '#161920'
DARK_FG = '#c8ccd4'
ACCENT = '#4a8cff'


class StatsDialog(QDialog):

  def __init__(self, data: pd.DataFrame, parent=None):
    super().__init__(parent)
    self.setWindowTitle('📊 统计面板')
    self.resize(680, 500)
    self._data = data
    layout = QVBoxLayout(self)
    layout.setContentsMargins(8, 8, 8, 8)
    tabs = QTabWidget()
    tabs.addTab(self._make_status_chart(), '阅读状态')
    tabs.addTab(self._make_publisher_chart(), '出版社分布')
    tabs.addTab(self._make_rating_chart(), '评分分布')
    layout.addWidget(tabs)

  def _style_ax(self, ax):
    ax.set_facecolor('#1a1e2a')
    ax.tick_params(colors=DARK_FG, labelsize=10)
    ax.spines['bottom'].set_color('#2a3142')
    ax.spines['left'].set_color('#2a3142')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

  def _make_status_chart(self) -> FigureCanvasQTAgg:
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('图书阅读状态分布', color=DARK_FG, fontsize=13, pad=12)
    counts = self._data.get('状态', pd.Series(dtype=object)).value_counts()
    if not counts.empty:
      colors = ['#4a8cff', '#52c41a', '#faad14', '#ff4d4f', '#b37feb', '#13c2c2']
      wedges, texts, autotexts = ax.pie(
        counts.values, labels=counts.index.tolist(), autopct='%1.1f%%',
        colors=colors[:len(counts)], startangle=90,
        textprops={'color': DARK_FG, 'fontsize': 11},
        pctdistance=0.75, labeldistance=1.1)
      for t in autotexts:
        t.set_color('#fff')
        t.set_fontweight('bold')
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', color=DARK_FG, fontsize=14)
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_publisher_chart(self) -> FigureCanvasQTAgg:
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('出版社 TOP10', color=DARK_FG, fontsize=13, pad=12)
    counts = self._data.get('出版', pd.Series(dtype=object)).value_counts().head(10)
    if not counts.empty:
      bars = ax.barh(counts.index.tolist()[::-1], counts.values[::-1],
                     color=ACCENT, height=0.65, alpha=0.85)
      for bar, v in zip(bars, counts.values[::-1]):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2, str(v),
                ha='left', va='center', fontsize=10, color=DARK_FG)
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', color=DARK_FG, fontsize=14)
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_rating_chart(self) -> FigureCanvasQTAgg:
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('评分分布', color=DARK_FG, fontsize=13, pad=12)
    ratings = pd.to_numeric(self._data.get('评分', pd.Series(dtype=object)), errors='coerce').dropna()
    if not ratings.empty:
      bins = [0, 6, 7, 8, 9, 10]
      labels = ['0-6', '6-7', '7-8', '8-9', '9-10']
      cats = pd.cut(ratings, bins=bins, labels=labels)
      counts = cats.value_counts().reindex(labels, fill_value=0)
      bar_colors = ['#8a8a8a', '#b3b3b3', '#4a8cff', '#52c41a', '#faad14']
      bars = ax.bar(counts.index.tolist(), counts.values, color=bar_colors, width=0.55, alpha=0.85)
      for bar, v in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15, str(v),
                ha='center', va='bottom', fontsize=11, color=DARK_FG, fontweight='bold')
      ax.set_xlabel('评分区间', color=DARK_FG, fontsize=11)
      ax.set_ylabel('图书数量', color=DARK_FG, fontsize=11)
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', color=DARK_FG, fontsize=14)
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)
