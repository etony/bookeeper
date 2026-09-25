# Bookeeper

个人图书管理：PyQt6 桌面 + 内嵌 FastAPI（8899），共用本地 SQLite。

## 快速起步

```bash
pip install -r requirements.txt
python main.py          # 桌面 GUI（带控制台）
python main.pyw         # 无控制台（Windows）；只是 10 行包装，直接 import main.main
```

有测试（pytest）/ 无 CI / 无类型检查 / 无 lint——改完跑 GUI、Web 或 pytest 验证。
`requirements-dev.txt` 里的 black/flake8/mypy **没有配置，勿跑**（black 会把 2 空格改成 4 空格）。

## 测试

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q                        # 全部（pytest.ini 的 testpaths=tests）
python -m pytest tests/unit/test_foo.py -q        # 单文件
```

- pytest.ini 定义了 `unit`/`integration`/`slow` markers，但**没有测试打标**——`-m unit` 等会 deselect 全部 135 个，勿用
- **测试库隔离在 `tests/conftest.py`**：import 前就把 `Config.DB_PATH` 换成 `bookeeper_test_*.db` 临时库，`clean_db` 再断言 `repo._path` 含 `bookeeper_test` 才执行 DELETE。历史事故：隔离失效导致 pytest 清空了真实 books.db（406 条）。新增测试用 `repo` fixture（独立临时库），**任何代码不得把 DB_PATH 指回真实 books.db**
- 改 GUI 逻辑（表头/排序/窗口状态）的验证套路：`QT_QPA_PLATFORM=offscreen` + 把 settings.ini 复制到临时目录 + monkeypatch `MainWindow._settings` 指向副本——直接跑会污染真实 settings.ini

## 架构速览

- `main.py` → `MainWindow`（中央协调者，`ui/main_window.py`）→ `BookRepo` / `DoubanService` / `BookWebServer` / `UndoManager`
- 分层：`ui/components/`（可复用组件）→ `ui/`（界面）→ `services/`（豆瓣、CSV、备份、封面、撤销）→ `core/models/`（领域模型）→ `database.py`（Repository）→ `web/server.py`
- `config.json` 首次运行生成（豆瓣 key，gitignore）；`settings.ini`（QSettings 窗口状态）、`backups/`、`covers/` 均 gitignore
- **`books.db` 被 git 追踪**（不在 .gitignore）——误 `git add -A` 会把本地图书数据提交进去

## 关键约定

- **所有文本字段用 TEXT 存**；连接启用 WAL + `timeout=30`（桌面与 Web 并发读写）
- **备份必须用 `sqlite3` online backup**（`services/backup.py`），禁止对活动库 `shutil.copy2`；恢复前先 checkpoint + `journal_mode=DELETE` 再覆盖，并尽力删 `-wal/-shm`
- **豆瓣 API**：模拟移动端 UA；ISBN 查询 `POST + DOUBAN_API_KEY`，关键词搜索 `GET + DOUBAN_API_KEY_SEARCH`（两个 key 不同）；ISBN 收 10 或 13 位
- **Web**：`/cover/{isbn}` 反代豆瓣封面防 403；uvicorn 必须 `log_config=None`（pythonw 下 stdout 为 None）；`start()` 阻塞跑在独立 QThread，`on_started` 在真正监听后才触发，`stop()` 置 `should_exit=True`
- **表格刷新**：全量 `BookTableModel.load_dataframe(df)`，单行 `update_row(row, data)`；没有 `emitDataChanged()` 这种对外 API。价格/评分/人数列按**数值**排序（`_NUMERIC_COLS`）
- **表格排序**：`load_dataframe` 总是重置为 rowid DESC（最新在前），之后 `_load_data` 按 `_user_sorted` 标记重新应用当前表头排序——改刷新逻辑别破坏这个配对
- **启动排序**：固定 rowid DESC，**不恢复** headerState 里的排序（`_restore_header_state` 里 `setSortIndicator(-1)` + 重载抵消 `restoreState` 内部触发的排序）；列顺序/宽度/可见性仍恢复。排序信号槽必须在 `restoreState` **之后**连接，否则启动就被标记成已排序。`BookTableModel.sort` 对越界列直接 return（Qt 清指示器传 -1）
- **撤销**：已存在的书入库走 `UpdateBookCommand`，仅新书用 `AddBookCommand`（否则 Ctrl+Z 会整条删掉）
- **封面墙**：工作线程回调必须 `pyqtSignal` 回主线程，勿在非 Qt 线程 `QTimer.singleShot`
- 导出 CSV 列比界面多（封面 URL、豆瓣链接等）；导入走后台线程 + 进度条
- 主题暖深色默认，强调色 `#e8922a`（`ui/theme.py` 与 Web CSS 各有一份）
- 单实例：`QSharedMemory`，重复启动弹窗退出；create 失败先 attach+detach 清残留段再重试
- 缩进：绝大多数文件 2 空格；**`ui/cover_wall.py` 是 4 空格**，勿全局统一改

## 配置系统

- 优先级：环境变量（`BOOKEEPER_` 前缀）> config.json > 默认值；`ConfigManager` + `ConfigSchema` + `EnvLoader` 在 `config/`
- **`init_config()` 会把结果回写 `Config` 静态类**（`DB_PATH`/`WEB_PORT`/豆瓣 key 等）——代码里大量直接读 `Config.XXX`（如 `Config.TABLE_COLUMNS`、`Config.DB_PATH`），调 `init_config()` 等于改全局状态；测试污染防护见 `conftest._isolate_config`
- config.json 兼容旧版大写 key（`DOUBAN_API_KEY`/`DOUBAN_API_KEY_SEARCH`）

## Workflow

- 每次代码改动完成后 `git add -A && git commit`，提交信息用英文简述，并运行 `git push`，将代码提交到github 
- 无 `opencode.json` / pre-commit；不要假设存在 format/lint 命令
