"""
┌──────────────────────────────────────────┐
│  程序入口                                │
│                                          │
│  初始化日志 → 创建 Qt 应用 → 启动主窗口。 │
└──────────────────────────────────────────┘
"""

import sys
import logging

# 根日志配置：所有模块的日志都遵循此格式
logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

from PyQt6.QtWidgets import QApplication

from config import Config
from ui.main_window import MainWindow


def main():
  """
  应用主入口。

  流程：
    1. 创建 QApplication（Qt 应用必备）
    2. 单实例检测
    3. 设置应用名称（影响窗口标题和系统托盘等）
    4. 加载暗色主题作为默认外观
    5. 创建并显示主窗口
    6. 进入 Qt 事件循环，等待用户操作
  """
  app = QApplication(sys.argv)
  app.setApplicationName(Config.APP_NAME)

  from PyQt6.QtCore import QSharedMemory
  from PyQt6.QtWidgets import QMessageBox
  _single = QSharedMemory('Bookeeper-' + Config.APP_NAME)
  if not _single.create(1):
    QMessageBox.warning(None, Config.APP_NAME, '程序已在运行中')
    sys.exit(0)

  from ui.theme import DARK_QSS
  app.setStyleSheet(DARK_QSS)

  w = MainWindow()
  w.show()
  sys.exit(app.exec())


if __name__ == '__main__':
  main()
