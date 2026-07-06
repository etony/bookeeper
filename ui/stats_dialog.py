import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import pandas as pd
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTabWidget


class StatsDialog(QDialog):
  def __init__(self, data: pd.DataFrame, parent=None):
    super().__init__(parent)
    self.setWindowTitle('📊 统计面板')
    self.resize(600, 480)
    self._data = data
    layout = QVBoxLayout(self)
    tabs = QTabWidget()
    tabs.addTab(self._make_status_chart(), '阅读状态')
    tabs.addTab(self._make_publisher_chart(), '出版社分布')
    tabs.addTab(self._make_rating_chart(), '评分分布')
    layout.addWidget(tabs)

  def _make_status_chart(self):
    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    counts = self._data.get('状态', pd.Series(dtype=object)).value_counts()
    if not counts.empty:
      ax.pie(counts.values, labels=counts.index.tolist(), autopct='%1.1f%%')
      ax.set_title('图书阅读状态分布')
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center')
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_publisher_chart(self):
    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    counts = self._data.get('出版', pd.Series(dtype=object)).value_counts().head(10)
    if not counts.empty:
      bars = ax.barh(counts.index.tolist()[::-1], counts.values[::-1])
      for bar, v in zip(bars, counts.values[::-1]):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2, str(v),
                ha='left', va='center', fontsize=10)
      ax.set_title('出版社 TOP10')
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center')
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)

  def _make_rating_chart(self):
    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ratings = pd.to_numeric(self._data.get('评分', pd.Series(dtype=object)), errors='coerce').dropna()
    if not ratings.empty:
      bins = [0, 6, 7, 8, 9, 10]
      labels = ['0-6', '6-7', '7-8', '8-9', '9-10']
      cats = pd.cut(ratings, bins=bins, labels=labels)
      counts = cats.value_counts().reindex(labels, fill_value=0)
      bars = ax.bar(counts.index.tolist(), counts.values)
      for bar, v in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1, str(v),
                ha='center', va='bottom', fontsize=10)
      ax.set_title('评分分布')
    else:
      ax.text(0.5, 0.5, '暂无数据', ha='center', va='center')
    fig.tight_layout()
    return FigureCanvasQTAgg(fig)
