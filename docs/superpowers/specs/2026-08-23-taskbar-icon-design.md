# Bookeeper 任务栏图标设计

日期：2026-08-23

## 问题

`ui/main_window.py:73` 设置的是空图标 `QIcon()`，任务栏显示默认 Qt 占位图标，过于简单。

## 设计决策

- **方案**：字母 B 变体 — 圆角方块底 + 白色衬线体 B
- **实现**：QPainter 动态绘制，零外部依赖
- **覆盖范围**：任务栏/窗口标题、Alt+Tab、系统托盘

## 视觉规格

- 底色：品牌橙 `#e8922a`
- 字母：白色粗体 Georgia 衬线体 B
- 圆角半径：宽度的 ~18%
- 字母垂直居中，字号为画布宽度的 ~65%

## 输出尺寸

| 场景 | 尺寸 | 用途 |
|------|------|------|
| 任务栏/窗口标题 | 32×32, 48×48 | QIcon 通过 setWindowIcon |
| .exe 文件图标 | 16/32/48/256 | 未来 PyInstaller 打包时写入 |
| 系统托盘 | 24×24 | 后续加后台驻留时可用 |

## 实现方式

新建 `ui/icon.py`，包含：

- `make_app_icon() → QIcon`：用 QPixmap + QPainter 绘制，返回 QIcon
- `export_ico(path: str)`：导出多尺寸 .ico 文件（Win32 API 加载用）
- `set_app_user_model_id()`：设置 Windows AppUserModelID，防止被归为 Python 分组
- `apply_window_icon(widget)`：通过 Win32 API 设置窗口类/实例图标

## 任务栏图标修复

Windows 下 PyQt6 的 `setWindowIcon` 仅影响窗口标题栏，不影响任务栏。
需通过 Win32 API 解决：

1. `SetCurrentProcessExplicitAppUserModelID`：在第一个窗口创建前调用，
   让 Windows 识别为独立应用
2. `LoadImageW`：加载 .ico 文件为 HICON
3. `SetClassLongPtrW`：设置窗口类级别图标（对任务栏最可靠）
4. `SendMessageW WM_SETICON`：设置窗口实例级别图标

## 改动范围

1. **新增** `ui/icon.py` —— 绘制 + 导出 + Win32 设置函数
2. **修改** `ui/main_window.py:73` —— `QIcon()` → `make_app_icon()`
3. **修改** `main.py` —— `app.setWindowIcon()` + `set_app_user_model_id()` + `apply_window_icon()`
4. **修改** `main.pyw` —— 同步改动

## 依赖

零新增，PyQt6 自带 QPixmap / QPainter / QImageWriter。
