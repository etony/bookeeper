# Bookeeper

个人图书管理：PyQt6 桌面 + 内嵌 FastAPI（8899），共用本地 SQLite。

## 快速起步

```bash
pip install -r requirements.txt
python main.py          # 桌面 GUI（带控制台）
python main.pyw         # 无控制台（Windows）；与 main.py 近重复，改入口逻辑需两边同步
```

无测试 / 无 CI / 无类型检查 / 无 lint——改完只能手工跑 GUI 或 Web 验证。

## 架构速览

- `main.py` → `MainWindow`（中央协调者，`ui/main_window.py`）→ `BookRepo` / `DoubanService` / `BookWebServer` / `UndoManager`
- 分层：`ui/`（界面）→ `services/`（豆瓣、CSV、备份、封面、撤销）→ `database.py` + `models/`（Repository + dataclass）→ `web/server.py`
- `config.py` 首次运行生成 `config.json`（豆瓣 key，gitignore）；`settings.ini`（QSettings 窗口状态）、`backups/`、`covers/` 均 gitignore
- **`books.db` 被 git 追踪**（不在 .gitignore）——误 `git add -A` 会把本地图书数据提交进去

## 关键约定

- **所有文本字段用 TEXT 存**；连接启用 WAL + `timeout=30`（桌面与 Web 并发读写）
- **备份必须用 `sqlite3` online backup**（`services/backup.py`），禁止对活动库 `shutil.copy2`；恢复前先 checkpoint + `journal_mode=DELETE` 再覆盖，并尽力删 `-wal/-shm`
- **豆瓣 API**：模拟移动端 UA；ISBN 查询 `POST + DOUBAN_API_KEY`，关键词搜索 `GET + DOUBAN_API_KEY_SEARCH`（两个 key 不同）；ISBN 收 10 或 13 位
- **Web**：`/cover/{isbn}` 反代豆瓣封面防 403；uvicorn 必须 `log_config=None`（pythonw 下 stdout 为 None）；`start()` 阻塞跑在独立 QThread，`on_started` 在真正监听后才触发，`stop()` 置 `should_exit=True`
- **表格刷新**：全量 `BookTableModel.load_dataframe(df)`，单行 `update_row(row, data)`；没有 `emitDataChanged()` 这种对外 API。价格/评分/人数列按**数值**排序（`_NUMERIC_COLS`）
- **撤销**：已存在的书入库走 `UpdateBookCommand`，仅新书用 `AddBookCommand`（否则 Ctrl+Z 会整条删掉）
- **封面墙**：工作线程回调必须 `pyqtSignal` 回主线程，勿在非 Qt 线程 `QTimer.singleShot`
- 导出 CSV 列比界面多（封面 URL、豆瓣链接等）；导入走后台线程 + 进度条
- 主题暖深色默认，强调色 `#e8922a`（`ui/theme.py` 与 Web CSS 各有一份）
- 单实例：`QSharedMemory`，重复启动弹窗退出
- 缩进：绝大多数文件 2 空格；**`ui/cover_wall.py` 是 4 空格**，勿全局统一改

## Workflow

- 每次代码改动完成后 `git add -A && git commit`，提交信息用英文简述
- 无 `opencode.json` / pre-commit；不要假设存在 format/lint 命令
