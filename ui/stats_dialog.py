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
  """
  统计面板对话框，以 tab 切换形式展示三个统计图表：
    1. 阅读状态饼图（默认/计划/已读 占比）
    2. 出版社 TOP10 水平条形图
    3. 评分区间（0-6 / 6-7 / 7-8 / 8-9 / 9-10）柱状图

  使用 matplotlib 的 FigureCanvasQTAgg 嵌入 Qt 界面，
  图表配色与暗色主题保持一致的色系（深色背景 + 冷白文字）。
  """

  def __init__(self, data: pd.DataFrame, parent=None):
    """初始化统计对话框

    接收主窗口的完整 DataFrame，创建三个统计图表 tab。
    注意：传入的是 DataFrame 引用，外部修改会影响本对话框的数据。

    参数:
      data:   图书数据 DataFrame（必须包含"状态""出版""评分"列）
      parent: 父窗口
    """
    super().__init__(parent)
    self.setWindowTitle('📊 统计面板')
    self.resize(680, 500)
    self._data = data
    layout = QVBoxLayout(self)
    layout.setContentsMargins(8, 8, 8, 8)
    tabs = QTabWidget()
    # 三个 tab 分别展示三种统计维度
    tabs.addTab(self._make_status_chart(), '阅读状态')    # 饼图：各状态占比
    tabs.addTab(self._make_publisher_chart(), '出版社分布')  # 条形图：出版社 TOP10
    tabs.addTab(self._make_rating_chart(), '评分分布')     # 柱状图：评分区间分布
    layout.addWidget(tabs)

  def _style_ax(self, ax):
    """统一设置 matplotlib 坐标轴样式，保持与暗色主题一致。

    所有图表共享同样的暗色背景、冷白文字、浅色坐标轴线。
    """
    ax.set_facecolor('#1a1e2a')
    ax.tick_params(colors=DARK_FG, labelsize=10)
    ax.spines['bottom'].set_color('#2a3142')
    ax.spines['left'].set_color('#2a3142')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

  def _make_status_chart(self) -> FigureCanvasQTAgg:
    """生成阅读状态饼图（默认/计划/已读 各占多少本）。"""
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('图书阅读状态分布', color=DARK_FG, fontsize=13, pad=12)
    # 统计各状态数量
    counts = self._data.get('状态', pd.Series(dtype=object)).value_counts()
    if not counts.empty:
      colors = ['#4a8cff', '#52c41a', '#faad14', '#ff4d4f', '#b37feb', '#13c2c2']
      wedges, texts, autotexts = ax.pie(
        counts.values, labels=counts.index.tolist(), autopct='%1.1f%%',
        colors=colors[:len(counts)], startangle=90,
        textprops={'color': DARK_FG, 'fontsize': 11},
        pctdistance=0.75, labeldistance=1.1)
      # 百分比文字设为白色加粗，在饼图中更清晰
      for t in autotexts:
        t.set_color('#fff')
        t.set_fontweight('bold')
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', color=DARK_FG, fontsize=14)
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_publisher_chart(self) -> FigureCanvasQTAgg:
    """生成出版社 TOP10 水平条形图。

    统计所有图书的出版社字段，取出现次数最多的前 10 个。
    使用水平条形图便于显示出版社名称（文字较长时不易重叠）。
    """
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('出版社 TOP10', color=DARK_FG, fontsize=13, pad=12)
    counts = self._data.get('出版', pd.Series(dtype=object)).value_counts().head(10)
    if not counts.empty:
      # [::-1] 反转排序，使数量最多的排在最上方（barh 默认从下往上画）
      bars = ax.barh(counts.index.tolist()[::-1], counts.values[::-1],
                     color=ACCENT, height=0.65, alpha=0.85)
      # 在每个条形右侧标注具体数值
      for bar, v in zip(bars, counts.values[::-1]):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2, str(v),
                ha='left', va='center', fontsize=10, color=DARK_FG)
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', color=DARK_FG, fontsize=14)
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_rating_chart(self) -> FigureCanvasQTAgg:
    """生成评分区间柱状图。

    将评分分为 0-6、6-7、7-8、8-9、9-10 五个区间，
    统计每个区间的图书数量。柱状图颜色从冷到暖渐变，
    代表评分从低到高。
    """
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('评分分布', color=DARK_FG, fontsize=13, pad=12)
    # 评分列是字符串，需转成数值，无法转换的设为 NaN 并丢弃
    ratings = pd.to_numeric(self._data.get('评分', pd.Series(dtype=object)), errors='coerce').dropna()
    if not ratings.empty:
      bins = [0, 6, 7, 8, 9, 10]
      labels = ['0-6', '6-7', '7-8', '8-9', '9-10']
      # pd.cut 将连续评分值划分到离散区间中
      cats = pd.cut(ratings, bins=bins, labels=labels)
      # 统计每个区间的数量，reindex 保证空区间也显示（值为 0）
      counts = cats.value_counts().reindex(labels, fill_value=0)
      # 颜色从左到右从冷到暖：灰色→浅灰→蓝→绿→黄
      bar_colors = ['#8a8a8a', '#b3b3b3', '#4a8cff', '#52c41a', '#faad14']
      bars = ax.bar(counts.index.tolist(), counts.values, color=bar_colors, width=0.55, alpha=0.85)
      # 在每个柱状图上方标注具体数值
      for bar, v in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15, str(v),
                ha='center', va='bottom', fontsize=11, color=DARK_FG, fontweight='bold')
      ax.set_xlabel('评分区间', color=DARK_FG, fontsize=11)
      ax.set_ylabel('图书数量', color=DARK_FG, fontsize=11)
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', color=DARK_FG, fontsize=14)
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)
