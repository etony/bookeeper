"""
CSV 导入导出控制器（从 ui/main_window.py 拆出）。

导入走后台线程 + 进度条，导出在主线程完成；
主窗口只负责把工具栏信号接过来、导入成功后刷新表格。
"""
import os
import sys
import time

import pandas as pd
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ISBN = '9787544291163'


@pytest.fixture(scope='session')
def app():
  from PyQt6.QtWidgets import QApplication
  if not QApplication.instance():
    return QApplication(sys.argv)
  return QApplication.instance()


def _wait_until(cond, timeout=8.0):
  from PyQt6.QtWidgets import QApplication
  deadline = time.time() + timeout
  while time.time() < deadline:
    if cond():
      return True
    QApplication.processEvents()
    time.sleep(0.01)
  return bool(cond())


@pytest.fixture
def controller(app, repo, monkeypatch):
  # 对话框会阻塞测试：一律替换成记录调用
  from ui import import_export
  calls = {'warning': [], 'info': []}
  monkeypatch.setattr(import_export.QMessageBox, 'warning',
                      lambda *a, **k: calls['warning'].append(a[2] if len(a) > 2 else a))
  monkeypatch.setattr(import_export.QMessageBox, 'information',
                      lambda *a, **k: calls['info'].append(a[2] if len(a) > 2 else a))
  ctl = import_export.CsvController(repo)
  ctl.calls = calls
  return ctl


def _write_csv(tmp_path, rows):
  from services.data import save_csv
  path = tmp_path / 'books.csv'
  save_csv(str(path), pd.DataFrame(rows))
  return str(path)


class TestImportCsv:
  def test_import_inserts_rows_in_background(self, controller, repo,
                                             tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    path = _write_csv(tmp_path, [{'ISBN': ISBN, '书名': '百年孤独'}])
    monkeypatch.setattr(QFileDialog, 'getOpenFileName',
                        lambda *a, **k: (path, 'CSV 文件 (*.csv)'))
    got, busy = [], []
    controller.imported.connect(got.append)
    controller.busy_changed.connect(busy.append)

    controller.import_csv()
    assert _wait_until(lambda: got), '导入完成后必须发出 imported 信号'
    assert got == [1]
    assert repo.count() == 1
    assert busy == [True, False], '导入期间应禁用导入按钮，结束后恢复'
    assert controller.calls['info'], '导入完成应提示用户'

  def test_cancel_file_dialog_does_nothing(self, controller, repo,
                                           tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: ('', ''))
    got = []
    controller.imported.connect(got.append)
    controller.import_csv()
    assert got == []
    assert repo.count() == 0

  def test_unreadable_csv_warns_and_returns(self, controller, repo,
                                            tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    import services.data as data
    monkeypatch.setattr(QFileDialog, 'getOpenFileName',
                        lambda *a, **k: (str(tmp_path / 'bad.csv'), ''))
    monkeypatch.setattr(data, 'load_csv',
                        lambda p: (_ for _ in ()).throw(ValueError('编码错误')))
    got = []
    controller.imported.connect(got.append)
    controller.import_csv()
    assert got == []
    assert controller.calls['warning'], '读取失败必须提示用户'


class TestExportCsv:
  def test_export_writes_all_rows(self, controller, repo, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    from core.models.book import Book
    repo.upsert(Book(isbn=ISBN, title='百年孤独'))
    out = tmp_path / 'out.csv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName',
                        lambda *a, **k: (str(out), 'CSV 文件 (*.csv)'))
    controller.export_csv()
    assert out.exists()
    assert ISBN in out.read_text(encoding='utf-8-sig')

  def test_export_cancel_does_nothing(self, controller, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: ('', ''))
    controller.export_csv()
    assert list(tmp_path.iterdir()) == []
