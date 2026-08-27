# ui/icon.py
"""
应用图标绘制模块。

用 QPainter 动态绘制品牌图标：圆角橙色方块 + 白色衬线体 B。
零外部依赖，支持任意尺寸缩放。

Windows 任务栏图标通过 Win32 API (WM_SETICON) 设置，
确保在任务栏和 Alt+Tab 中正确显示。
"""

import os
import math
import struct
import tempfile
import ctypes
import ctypes.wintypes
from PyQt6.QtCore import Qt, QRectF, QBuffer, QIODevice
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QImage

from ui.theme import ACCENT


RADIUS_RATIO = 0.18
FONT_RATIO = 0.65

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
LR_LOADFROMFILE = 0x00000010
GCLP_HICON = -14
GCLP_HICONSM = -34
APP_ID = 'Bookeeper.Bookeeper'


def _draw_icon(pixmap: QPixmap):
  """在 QPixmap 上绘制图标内容（圆角底 + 字母 B）"""
  w = pixmap.width()
  h = pixmap.height()
  pixmap.fill(Qt.GlobalColor.transparent)

  painter = QPainter(pixmap)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)

  radius = w * RADIUS_RATIO
  painter.setBrush(QColor(ACCENT))
  painter.setPen(Qt.PenStyle.NoPen)
  painter.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

  font = QFont('Georgia')
  font.setPixelSize(int(w * FONT_RATIO))
  font.setBold(True)
  painter.setFont(font)
  painter.setPen(QColor('#ffffff'))
  painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, 'B')

  painter.end()


def make_app_icon() -> QIcon:
  """生成应用图标，返回 QIcon（含 16/32/48/256 多尺寸）。"""
  icon = QIcon()
  for size in (16, 32, 48, 256):
    pm = QPixmap(size, size)
    pm.setDevicePixelRatio(1.0)
    _draw_icon(pm)
    icon.addPixmap(pm)
  return icon


def export_ico(path: str):
  """导出多尺寸 .ico 文件（供 PyInstaller 打包时使用）。

  ICO 格式：header + directory entries + PNG image data。
  """
  sizes = (16, 32, 48, 256)
  png_data_list = []

  # 先把每个尺寸渲染为 PNG
  for s in sizes:
    pm = QPixmap(s, s)
    pm.setDevicePixelRatio(1.0)
    _draw_icon(pm)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.save(buf, 'PNG')
    png_data_list.append(bytes(buf.data()))
    buf.close()

  # 计算偏移量：header(6) + 每个 entry(16) * count
  data_offset = 6 + 16 * len(sizes)

  with open(path, 'wb') as f:
    # ICO header
    f.write(struct.pack('<HHH', 0, 1, len(sizes)))  # reserved, type=icon, count

    # directory entries + 累计偏移
    offset = data_offset
    for s, png_data in zip(sizes, png_data_list):
      w = 0 if s >= 256 else s  # 0 表示 256
      h = 0 if s >= 256 else s
      f.write(struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(png_data), offset))
      offset += len(png_data)

    # PNG 数据
    for png_data in png_data_list:
      f.write(png_data)


def make_theme_icon(dark: bool) -> QIcon:
  """生成主题切换图标：暗色模式显示太阳，亮色模式显示月亮"""
  size = 20
  pm = QPixmap(size, size)
  pm.setDevicePixelRatio(1.0)
  pm.fill(Qt.GlobalColor.transparent)
  painter = QPainter(pm)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)
  painter.setPen(Qt.PenStyle.NoPen)

  if dark:
    # 太阳：亮橙色圆 + 放射线
    painter.setBrush(QColor('#f0a030'))
    painter.drawEllipse(5, 5, 10, 10)
    for angle in range(0, 360, 45):
      rad = math.radians(angle)
      x1 = 10 + 8 * math.cos(rad)
      y1 = 10 + 8 * math.sin(rad)
      painter.drawEllipse(int(x1) - 1, int(y1) - 1, 2, 2)
  else:
    # 月亮：深金色弯月（亮色背景下对比明显）
    painter.setBrush(QColor('#b8940a'))
    painter.drawEllipse(4, 3, 11, 11)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
    painter.drawEllipse(8, 2, 10, 10)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

  painter.end()
  return QIcon(pm)


def make_about_icon() -> QIcon:
  """生成关于图标：圆圈内带 i 字母"""
  size = 20
  pm = QPixmap(size, size)
  pm.setDevicePixelRatio(1.0)
  pm.fill(Qt.GlobalColor.transparent)
  painter = QPainter(pm)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)

  # 外圈
  painter.setPen(QColor('#8a8a8a'))
  painter.setBrush(Qt.BrushStyle.NoBrush)
  painter.drawEllipse(1, 1, 18, 18)

  # i 字母
  font = QFont('Arial')
  font.setPixelSize(12)
  font.setBold(True)
  painter.setFont(font)
  painter.setPen(QColor('#8a8a8a'))
  painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, 'i')

  painter.end()
  return QIcon(pm)


def set_app_user_model_id():
  """设置 Windows AppUserModelID，必须在第一个窗口创建之前调用。"""
  if os.name != 'nt':
    return
  shell32 = ctypes.windll.shell32
  shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def apply_window_icon(widget):
  """通过 Win32 API 设置窗口的任务栏和 Alt+Tab 图标。

  仅在 Windows 平台生效，其他平台静默返回。
  """
  if os.name != 'nt' or widget is None:
    return

  ico_path = os.path.join(tempfile.gettempdir(), 'bookeeper_icon.ico')
  export_ico(ico_path)

  user32 = ctypes.windll.user32
  h_icon = user32.LoadImageW(0, ico_path, 1, 0, 0, LR_LOADFROMFILE)
  if not h_icon:
    return

  hwnd = int(widget.winId())
  user32.SetClassLongPtrW(hwnd, GCLP_HICON, h_icon)
  user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, h_icon)
  user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_icon)
  user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_icon)
