import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTabWidget

from database import BookRepo

# 统计面板暗色配色
DARK_BG = '#1c1c1f'
DARK_FG = '#e0e0e4'
ACCENT = '#e8922a'


class StatsDialog(QDialog):
  """统计面板：阅读状态饼图、出版社 TOP10 柱状图、评分分布柱状图"""

  def __init__(self, repo: BookRepo, parent=None):
    super().__init__(parent)
    self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    self.setWindowTitle('📊 统计面板')
    self.resize(680, 500)
    self._repo = repo
    layout = QVBoxLayout(self)
    layout.setContentsMargins(8, 8, 8, 8)
    tabs = QTabWidget()
    tabs.addTab(self._make_status_chart(), '阅读状态')
    tabs.addTab(self._make_publisher_chart(), '出版社分布')
    tabs.addTab(self._make_rating_chart(), '评分分布')
    layout.addWidget(tabs)

  def _style_ax(self, ax):
    """统一暗色图表样式"""
    ax.set_facecolor('#242428')
    ax.tick_params(colors=DARK_FG, labelsize=10)
    ax.spines['bottom'].set_color('#323238')
    ax.spines['left'].set_color('#323238')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

  def _make_status_chart(self):
    """阅读状态饼图"""
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('图书阅读状态分布', color=DARK_FG, fontsize=13, pad=12)
    counts = self._repo.status_counts()
    if counts:
      colors = [ACCENT, '#52c41a', '#4a8cff', '#ff4d4f', '#b37feb', '#13c2c2']
      wedges, texts, autotexts = ax.pie(
        list(counts.values()), labels=list(counts.keys()), autopct='%1.1f%%',
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

  def _make_publisher_chart(self):
    """出版社 TOP10 水平柱状图"""
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('出版社 TOP10', color=DARK_FG, fontsize=13, pad=12)
    pubs = self._repo.publisher_top(10)
    if pubs:
      labels, values = zip(*pubs)
      labels = list(labels)[::-1]
      values = list(values)[::-1]
      bars = ax.barh(labels, values, color=ACCENT, height=0.65, alpha=0.85)
      for bar, v in zip(bars, values):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2, str(v),
                ha='left', va='center', fontsize=10, color=DARK_FG)
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', color=DARK_FG, fontsize=14)
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_rating_chart(self):
    """评分分布柱状图（5 个区间）"""
    fig = Figure(figsize=(7, 4.5), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    self._style_ax(ax)
    ax.set_title('评分分布', color=DARK_FG, fontsize=13, pad=12)
    dist = self._repo.rating_distribution()
    if any(dist.values()):
      labels = list(dist.keys())
      values = list(dist.values())
      bar_colors = ['#8a8a8a', '#b3b3b3', ACCENT, '#52c41a', '#faad14']
      bars = ax.bar(labels, values, color=bar_colors, width=0.55, alpha=0.85)
      for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15, str(v),
                ha='center', va='bottom', fontsize=11, color=DARK_FG, fontweight='bold')
      ax.set_xlabel('评分区间', color=DARK_FG, fontsize=11)
      ax.set_ylabel('图书数量', color=DARK_FG, fontsize=11)
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', color=DARK_FG, fontsize=14)
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)
