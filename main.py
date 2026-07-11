import sys
import logging

logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

from PyQt6.QtWidgets import QApplication

from config import Config
from ui.main_window import MainWindow


def main():
  app = QApplication(sys.argv)
  app.setApplicationName(Config.APP_NAME)

  from ui.theme import DARK_QSS
  app.setStyleSheet(DARK_QSS)

  w = MainWindow()
  w.show()
  sys.exit(app.exec())


if __name__ == '__main__':
  main()
