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
- 分层：`ui/components/`（可复用组件）→ `ui/`（界面）→ `services/`（豆瓣、CSV、备份、封面、撤销）→ `core/models/`（领域模型）→ `database.py`（Repository）→ `web/server.py`
- `config/` 模块：`ConfigManager`（配置管理器）+ `ConfigSchema`（验证）+ `EnvLoader`（环境变量）
- `config.json` 首次运行生成（豆瓣 key，gitignore）；`settings.ini`（QSettings 窗口状态）、`backups/`、`covers/` 均 gitignore
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

## 配置系统

`config/` 模块提供统一配置管理：

- `ConfigManager` — 加载配置文件 + 环境变量 + 默认值，支持重载
- `ConfigSchema` — 验证配置类型、范围、长度
- `EnvLoader` — 自动加载 `BOOKEEPER_` 前缀的环境变量
- `AppConfig` — 嵌套数据类（`DoubanConfig`、`DatabaseConfig`、`WebConfig`、`BackupConfig`）
- 旧版 `Config` 类仍可用（已废弃），建议使用 `ConfigManager` 或 `get_config()`

优先级：环境变量 > config.json > 默认值

## UI 组件

`ui/components/` 包含可复用组件：

- `BookFormWidget` — 图书编辑表单（ISBN 输入 + 操作按钮 + 字段编辑）
- `SearchBarWidget` — 搜索栏（关键词 + 状态下拉 + 查询/重置）
- `ToolBarWidget` — 工具栏（导入/导出/统计/搜索/封面墙/Web/备份/主题）
- `WebManager` — Web 服务管理（后台线程启停 + 信号通知）

## Web 模板

`web/templates/` 包含 Jinja2 HTML 模板：

- `base.html` — 基础布局（CSS/JS 引用）
- `index.html` — 图书列表
- `book_detail.html` — 图书详情
- `cover_wall.html` — 封面墙
- `add.html` / `edit.html` — 添加/编辑图书表单
- `stats.html` — 统计页面
- `error.html` — 错误页面

## 测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -v                    # 运行所有测试
pytest tests/ -v -m unit           # 仅单元测试
pytest tests/ -v -m integration    # 仅集成测试
```

测试文件位于 `tests/unit/` 和 `tests/integration/`。

## Workflow

- 每次代码改动完成后 `git add -A && git commit`，提交信息用英文简述
- 无 `opencode.json` / pre-commit；不要假设存在 format/lint 命令
