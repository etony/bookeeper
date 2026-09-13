# Bookeeper 任务栏图标实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 QPainter 动态绘制品牌图标（圆角橙色方块 + 白色衬线体 B），替换空 QIcon，覆盖任务栏/窗口标题/系统托盘。

**Architecture:** 新建 `ui/icon.py` 封装绘制逻辑，`make_app_icon()` 返回 QIcon，`export_ico()` 导出多尺寸 .ico 供打包用。主窗口和 QApplication 各调用一次。

**Tech Stack:** PyQt6 (QPixmap, QPainter, QColor, QFont, QImageWriter)

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 新增 | `ui/icon.py` | 图标绘制 + .ico 导出 |
| 修改 | `ui/main_window.py:73` | 窗口图标 → `make_app_icon()` |
| 修改 | `main.py:36` 后 | 全局应用图标 → `make_app_icon()` |

---

### Task 1: 创建 `ui/icon.py`

**Files:** Create `ui/icon.py`

- [ ] **Step 1: 创建绘制函数**

```python
# ui/icon.py
"""
应用图标绘制模块。

用 QPainter 动态绘制品牌图标：圆角橙色方块 + 白色衬线体 B。
零外部依赖，支持任意尺寸缩放。
"""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QFontMetrics, QIcon, QImage, QImageWriter
from PyQt6.QtCore import QBuffer, QIODevice


# 品牌色
ACCENT = '#e8922a'
RADIUS_RATIO = 0.18   # 圆角半径占宽度的比例
FONT_RATIO = 0.65     # 字号占画布宽度的比例


def _draw_icon(pixmap: QPixmap):
  """在 QPixmap 上绘制图标内容（圆角底 + 字母 B）"""
  w = pixmap.width()
  h = pixmap.height()
  pixmap.fill(Qt.GlobalColor.transparent)

  painter = QPainter(pixmap)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)

  # 圆角方块底
  radius = w * RADIUS_RATIO
  painter.setBrush(QColor(ACCENT))
  painter.setPen(Qt.PenStyle.NoPen)
  painter.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

  # 白色衬线体 B
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
  """导出多尺寸 .ico 文件（供 PyInstaller 打包时使用）。"""
  sizes = (16, 32, 48, 256)
  images = []
  for s in sizes:
    pm = QPixmap(s, s)
    pm.setDevicePixelRatio(1.0)
    _draw_icon(pm)
    images.append(pm.toImage())

  writer = QImageWriter(path)
  writer.setFormat('ico')
  # ICO 格式支持多尺寸：逐个写入
  # QImageWriter ICO 写入最后一个 image 作为多尺寸
  # 需要用 QBuffer 组合
  buf = QBuffer()
  buf.open(QIODevice.OpenModeFlag.WriteOnly)
  for img in images:
    w = QImageWriter(buf, 'ico')
    w.write(img)
  buf.close()
```

- [ ] **Step 2: 验证语法**

Run: `python -c "import ast; ast.parse(open('ui/icon.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ui/icon.py
git commit -m "feat: add app icon module with QPainter-based B logo"
```

---

### Task 2: 主窗口使用图标

**Files:** Modify `ui/main_window.py:73`

- [ ] **Step 1: 修改 `_setup_ui` 方法**

```python
# ui/main_window.py 第 72-73 行
# 从：
    self.setWindowTitle(Config.APP_NAME)
    self.setWindowIcon(QIcon())
# 改为：
    self.setWindowTitle(Config.APP_NAME)
    from ui.icon import make_app_icon
    self.setWindowIcon(make_app_icon())
```

- [ ] **Step 2: 验证语法**

Run: `python -c "import ast; ast.parse(open('ui/main_window.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ui/main_window.py
git commit -m "feat: set window icon to branded B logo"
```

---

### Task 3: 应用级别设置图标

**Files:** Modify `main.py:36` 后

- [ ] **Step 1: 在 `main()` 中添加应用图标**

```python
# main.py，在 app = QApplication(sys.argv) 之后添加
def main():
  app = QApplication(sys.argv)
  app.setApplicationName(Config.APP_NAME)
+ from ui.icon import make_app_icon
+ app.setWindowIcon(make_app_icon())
```

- [ ] **Step 2: 验证语法**

Run: `python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: set app-level icon for taskbar and process"
```

---

### Task 4: 手工验证

- [ ] **Step 1: 运行程序验证图标**

Run: `python main.py`
Expected: 任务栏和窗口标题栏显示橙色圆角方块 + 白色衬线体 B 图标，不再是默认 Qt 占位图标。

- [ ] **Step 2: 验证 .ico 导出功能**

Run: `python -c "from ui.icon import export_ico; export_ico('test_icon.ico'); print('OK')"`
Expected: 生成 `test_icon.ico` 文件（可双击在 Windows 图片查看器中预览）。验证后删除 `test_icon.ico`。
