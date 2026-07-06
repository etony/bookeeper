# -*- coding: utf-8 -*-
"""
Bookeeper - 个人图书管理应用入口

该模块是 Bookeeper 应用的启动入口。功能包括：
- 初始化日志系统，便于调试和问题追踪
- 创建 PyQt6 应用实例并加载全局暗色主题样式
- 启动主窗口并进入事件循环

启动方式：直接运行 python main.py
"""

import sys
import logging

from PyQt6.QtWidgets import QApplication

from config import Config
from ui.theme import DARK_QSS  # 深色主题 QSS 样式表
from ui.main_window import MainWindow  # 应用主窗口


def main():
  """
  应用主入口函数。

  执行顺序：
    1. 配置 logging 日志系统：输出级别 INFO，格式含时间/级别/模块名/消息
    2. 创建 QApplication 应用对象，管理全局事件循环
    3. 设置全局样式表 DARK_QSS，使所有窗口/控件使用统一深色主题
    4. 实例化 MainWindow 主窗口并显示
    5. 进入 app.exec() 事件循环，等待用户交互
       sys.exit() 确保在窗口关闭时返回退出码

  注意事项：
    - 日志格式中的 %(name)s 由各模块的 logging.getLogger(__name__) 提供
    - DARK_QSS 定义在 ui/theme.py 中，覆盖 PyQt6 默认组件样式
  """
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
  )

  app = QApplication(sys.argv)
  app.setStyleSheet(DARK_QSS)  # 应用全局暗色主题

  window = MainWindow()
  window.show()  # 显示主窗口（默认居中，尺寸 950x720）

  sys.exit(app.exec())  # 进入事件循环，窗口关闭后退出进程


if __name__ == '__main__':
  main()
