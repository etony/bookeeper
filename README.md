# Bookeeper

个人图书管理工具 — PyQt6 桌面应用 + FastAPI Web 服务。豆瓣 API 自动填充、ISBN 校验、CSV 导入导出、统计面板、撤销重做、自动备份。

## 功能

- **图书管理** — 增删改查，表格展示，单击填充表单，双击查看详情；支持 Ctrl+Z 撤销 / Ctrl+Y 重做
- **封面墙** — 网格浏览封面（Ctrl+W），可排序、调每行数量，后台线程池下载封面
- **豆瓣 API** — ISBN（10/13 位）自动获取书名/作者/封面/评分；关键词搜索图书一键入库
- **排序筛选** — 点击表头排序（价格/评分/人数按数值排序），关键词 + 状态下拉筛选，列可拖拽重排、右键显隐
- **阅读追踪** — 三种状态（默认/计划/已读），书柜位置，购书/已读日期
- **CSV 导入/导出** — UTF-8 BOM 编码，兼容旧版列名映射；导入在后台线程执行并显示进度
- **统计面板** — 阅读状态饼图、出版社 TOP10、评分分布柱状图（matplotlib 深色风格）
- **暗色/亮色主题** — 暖橙强调色 `#e8922a`，一键切换，QSettings 持久化
- **本机 Web 服务** — FastAPI 完整 CRUD、搜索、分页、统计、封面墙、封面代理，零 JS
- **ISBN 校验** — 支持 ISBN-10/ISBN-13 校验位验证
- **自动备份** — 每 5 分钟（有变更时）用 SQLite online backup 生成一致性快照至 `backups/`，保留最近 30 份
- **备份恢复** — 一键从备份恢复，恢复前自动保存当前数据并清理残留 WAL
- **封面缓存** — 下载的封面本地缓存至 `covers/`，避免重复下载
- **推荐度算法** — `(评分 - 2.5) × ln(评价人数 + 1)`
- **快捷键** — Ctrl+S 导出 CSV / Ctrl+F 搜索 / Ctrl+R 重置 / Ctrl+D 豆瓣搜索 / Ctrl+W 封面墙 / Ctrl+Z 撤销 / Ctrl+Y·Ctrl+Shift+Z 重做

## 安装

```bash
pip install -r requirements.txt
```

依赖：PyQt6、pandas、requests、matplotlib、fastapi、uvicorn

## 使用

```bash
python main.py          # 桌面 GUI（带控制台）
python main.pyw         # 无控制台窗口（Windows）
```

首次运行自动生成 `config.json`，内含豆瓣 API key。单实例：重复启动会提示已运行。

### Web 服务

桌面界面点击 **🌐 Web 服务**，监听就绪后自动打开 `http://127.0.0.1:8899`（仅本机），支持完整的图书管理操作。桌面与 Web 共用同一 SQLite（WAL 模式，读写并发）。

## 配置

配置系统支持三种来源（优先级从高到低）：环境变量 → config.json → 默认值。

### 环境变量

使用 `BOOKEEPER_` 前缀：

```bash
BOOKEEPER_WEB_PORT=9000
BOOKEEPER_DATABASE_PATH=/path/to/books.db
```

### 配置文件

编辑 `config.json`（与 `main.py` 同级）：

```json
{
  "douban_api_key": "你的 API key",
  "douban_api_key_search": "你的搜索 API key",
  "web_port": 8899,
  "database_path": "books.db",
  "backup_keep": 30
}
```

### 配置模块

`config/` 模块提供：

- `ConfigManager` — 配置管理器，加载/验证/重载配置
- `ConfigSchema` — 配置验证（类型、范围、长度检查）
- `EnvLoader` — 环境变量自动转换和加载
- `AppConfig` — 配置数据类（嵌套结构）

主题、窗口几何、表头状态通过 `settings.ini` 自动持久化。

## 项目结构

```
├── main.py                 # 应用入口（带控制台）
├── main.pyw                # 应用入口（无控制台，Windows）
├── config/                 # 配置管理模块
│   ├── __init__.py         # ConfigManager + 旧版 Config 兼容类
│   ├── defaults.py         # 配置数据类（AppConfig、DoubanConfig 等）
│   ├── schema.py           # 配置验证模式
│   └── env.py              # 环境变量加载器（BOOKEEPER_ 前缀）
├── config.json             # 用户配置（API key，已 gitignore）
├── core/                   # 核心业务逻辑
│   ├── models/
│   │   ├── base.py         # BaseModel（to_dict / from_dict）
│   │   └── book.py         # Book dataclass（领域模型）
│   ├── repositories/       # Repository 模式（预留）
│   └── services/           # 核心服务（预留）
├── database.py             # 数据访问层（SQLite Repository，WAL）
├── utils.py                # ISBN 校验工具
├── requirements.txt        # Python 依赖清单
├── requirements-dev.txt    # 开发依赖（pytest、black、flake8、mypy）
├── pytest.ini              # pytest 配置
├── models/
│   └── table_model.py      # QAbstractTableModel（pandas 后端）
├── services/
│   ├── __init__.py         # 全局 BookRepo 单例
│   ├── douban.py           # 豆瓣 API 封装（重试）
│   ├── data.py             # CSV 加载/保存
│   ├── backup.py           # 定时备份（online backup API）
│   ├── covers.py           # 封面本地缓存
│   └── undo.py             # 撤销/重做（命令模式）
├── ui/
│   ├── components/         # 可复用 UI 组件
│   │   ├── book_form.py    # 图书编辑表单
│   │   ├── search_bar.py   # 搜索栏
│   │   ├── tool_bar.py     # 工具栏
│   │   └── web_manager.py  # Web 服务管理
│   ├── theme.py            # 暗色/亮色 QSS 主题（暖橙强调色）
│   ├── main_window.py      # 主窗口（Mediator 协调者）
│   ├── cover_wall.py       # 封面墙（线程池下载）
│   ├── detail_dialog.py    # 图书详情（封面 + 翻页）
│   ├── search_dialog.py    # 豆瓣搜索对话框
│   ├── stats_dialog.py     # 统计面板（matplotlib）
│   └── icon.py             # 应用图标绘制（QPainter 动态绘制）
├── web/
│   ├── server.py           # FastAPI Web 服务（内嵌 uvicorn）
│   └── templates/          # Jinja2 HTML 模板
│       ├── base.html       # 基础布局
│       ├── index.html      # 图书列表
│       ├── book_detail.html# 图书详情
│       ├── cover_wall.html # 封面墙
│       ├── add.html        # 添加图书
│       ├── edit.html       # 编辑图书
│       ├── stats.html      # 统计页面
│       └── error.html      # 错误页面
├── tests/                  # 测试套件
│   ├── conftest.py         # pytest fixtures
│   ├── unit/               # 单元测试
│   └── integration/        # 集成测试
├── books.db                # SQLite 数据库（当前被 git 追踪；日常数据变更勿随手提交）
├── backups/                # 自动备份目录（已 gitignore）
├── covers/                 # 封面本地缓存（已 gitignore）
├── README.md
├── LICENSE
└── .gitignore
```

## 架构

```
┌──────────────────────────────────────┐
│           UI 层 (PyQt6)              │
│  MainWindow (Mediator)               │
│    ├── components/                   │
│    │   ├── BookFormWidget (编辑表单) │
│    │   ├── SearchBarWidget (搜索栏)  │
│    │   ├── ToolBarWidget (工具栏)    │
│    │   └── WebManager (Web 服务管理) │
│    ├── BookTableModel (表格模型)      │
│    ├── CoverWallWidget (封面墙)       │
│    ├── DetailDialog (详情 + 封面)     │
│    ├── SearchDialog (豆瓣搜索)        │
│    ├── StatsDialog (matplotlib 统计)  │
│    └── Theme (DARK / LIGHT QSS)      │
├──────────────────────────────────────┤
│           Config 层                  │
│    ConfigManager (配置管理器)        │
│    ConfigSchema (验证模式)           │
│    EnvLoader (环境变量)              │
├──────────────────────────────────────┤
│            Service 层                │
│    DoubanService (豆瓣 API)          │
│    BackupService (定时备份 + 清理)   │
│    UndoManager (命令模式撤销)        │
│    CSV Service (load / save)         │
├──────────────────────────────────────┤
│            Core 层                   │
│    Book (dataclass 领域模型)          │
│    BaseModel (通用序列化)            │
├──────────────────────────────────────┤
│            Data 层                   │
│    BookRepo (Repository + SQLite WAL)│
├──────────────────────────────────────┤
│        Web 层 (FastAPI)              │
│    BookWebServer (内嵌 uvicorn)      │
│    templates/ (Jinja2 HTML 模板)     │
│    路由: / /cover-wall /add /edit    │
│    /delete /book /cover /stats       │
├──────────────────────────────────────┤
│           Tests 层                   │
│    unit/ (单元测试)                  │
│    integration/ (集成测试)           │
└──────────────────────────────────────┘
```

MainWindow 作为中央协调者，通过 Qt 信号-槽连接各模块。网络与 CSV 导入在后台线程执行；封面墙回调经信号回到主线程。

### 测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -v                    # 运行所有测试
pytest tests/ -v -m unit           # 仅单元测试
pytest tests/ -v -m integration    # 仅集成测试
```

测试覆盖：配置系统、数据库操作、数据模型、撤销命令、UI 组件、Web 模板。

### 开发规范

- 每次代码改动完成后按约定 `git add -A && git commit`（英文提交说明）
- 开发依赖：pytest、black、flake8、mypy（见 `requirements-dev.txt`）
