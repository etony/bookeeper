# -*- coding: utf-8 -*-
"""Bookeeper - 个人图书管理

优雅、完善的 PyQt6 桌面应用，管理个人藏书信息。
支持豆瓣 API 自动填充、条形码扫描、CSV 导入导出。
"""

import sys
import logging

from PyQt6.QtWidgets import QApplication

from config import Config
from ui.theme import DARK_QSS
from ui.main_window import MainWindow


def main():
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
  )

  app = QApplication(sys.argv)
  app.setStyleSheet(DARK_QSS)

  window = MainWindow()
  window.show()
  sys.exit(app.exec())


if __name__ == '__main__':
  main()
