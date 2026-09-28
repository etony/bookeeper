"""封面图标签：随控件尺寸等比缩放，避免拉伸变形"""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel


class CoverLabel(QLabel):
  """
  可等比缩放的封面标签。

  保存原始 QImage，控件尺寸变化时按 KeepAspectRatio 重新缩放，
  保证布局前/后、窗口缩放时图片都不变形。

  sizeHint/minimumSizeHint 固定为构造时给定值：QLabel 默认用
  pixmap 尺寸当 sizeHint，会把图片尺寸反馈进布局，导致卡片
  被越撑越高（图片撑布局 → 布局变大 → 图片更大 …）。
  """

  def __init__(self, text='', size_hint=None, parent=None):
    super().__init__(text, parent)
    self._image = None
    self._size_hint = size_hint or QSize(130, 180)

  def set_image(self, image):
    """设置封面原图；image 为 None 时清除图片（保留文本提示）"""
    self._image = image
    if image is None:
      self.setPixmap(QPixmap())
    else:
      self._rescale()

  def clear_image(self):
    """清除封面图，回退到文本提示"""
    self.set_image(None)

  def sizeHint(self):
    return self._size_hint

  def minimumSizeHint(self):
    return self._size_hint

  def _rescale(self):
    """按当前控件尺寸等比重缩放原图"""
    if self._image is None:
      return
    w = self.width() - 4
    h = self.height() - 4
    if w <= 0 or h <= 0:
      return
    scaled = QPixmap.fromImage(self._image).scaled(
      w, h, Qt.AspectRatioMode.KeepAspectRatio,
      Qt.TransformationMode.SmoothTransformation)
    self.setPixmap(scaled)

  def resizeEvent(self, a0):
    super().resizeEvent(a0)
    self._rescale()
