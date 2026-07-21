# Bookeeper

个人图书管理工具 — PyQt6 桌面应用 + FastAPI Web 服务。豆瓣 API 自动填充、ISBN 校验、CSV 导入导出、统计面板、自动备份。

## 功能

- **图书管理** — 增删改查，表格展示，单击填充表单，双击查看详情
- **豆瓣 API** — ISBN 自动获取书名/作者/封面/评分；关键词搜索图书一键入库
- **排序筛选** — 点击表头排序，关键词 + 状态下拉筛选，列可拖拽重排、右键显隐
- **阅读追踪** — 三种状态（默认/计划/已读），书柜位置，购书/已读日期
- **CSV 导入/导出** — UTF-8 BOM 编码，兼容旧版列名映射
- **统计面板** — 阅读状态饼图、出版社 TOP10、评分分布柱状图（matplotlib 深色风格）
- **暗色/亮色主题** — 暖橙强调色 `#e8922a`，一键切换，QSettings 持久化
- **局域网 Web 服务** — FastAPI 完整 CRUD、搜索、分页、统计、封面代理，零 JS
- **ISBN 校验** — 支持 ISBN-10/ISBN-13 校验位验证
- **自动备份** — 每 5 分钟备份至 `backups/`，保留最近 30 份
- **推荐度算法** — `(评分 - 2.5) × ln(评价人数 + 1)`
- **快捷键** — Ctrl+S 保存 / Ctrl+F 搜索 / Ctrl+R 重置 / Ctrl+D 豆瓣搜索

## 安装

```bash
pip install -r requirements.txt
```

依赖：PyQt6、pandas、requests、matplotlib、fastapi、uvicorn

## 使用

```bash
cd new
python main.py
```

首次运行自动生成 `config.json`，内含豆瓣 API key。

### Web 服务

桌面界面点击 **🌐 Web 服务** 启动，访问 `http://127.0.0.1:8899`，支持完整的图书管理操作。

## 配置

编辑 `config.json`（与 `main.py` 同级）：

```json
{
  "DOUBAN_API_KEY": "你的 API key",
  "DOUBAN_API_KEY_SEARCH": "你的搜索 API key"
}
```

主题、列状态等设置通过 `settings.ini` 自动持久化。

## 项目结构

```
├── new/                        # 新版（推荐）
│   ├── main.py                 # 应用入口
│   ├── config.py               # 全局配置（API key、列名、端口等）
│   ├── config.json             # 用户配置（API key）
│   ├── utils.py                # ISBN 校验工具
│   ├── database.py             # 数据访问层（SQLite, Repository 模式）
│   ├── requirements.txt        # Python 依赖清单
│   ├── models/
│   │   ├── book.py             # Book dataclass（领域模型）
│   │   └── table_model.py      # QAbstractTableModel（pandas 后端）
│   ├── services/
│   │   ├── douban.py           # 豆瓣 API 封装
│   │   ├── data.py             # CSV 加载/保存
│   │   └── backup.py           # 定时备份服务
│   ├── ui/
│   │   ├── theme.py            # 暗色/亮色 QSS 主题（暖橙强调色）
│   │   ├── main_window.py      # 主窗口（Mediator 协调者）
│   │   ├── detail_dialog.py    # 图书详情（封面 + 翻页）
│   │   ├── search_dialog.py    # 豆瓣搜索对话框
│   │   └── stats_dialog.py     # 统计面板（matplotlib）
│   ├── web/
│   │   └── server.py           # FastAPI Web 服务
│   └── workers/
│       └── workers.py          # 后台工作线程
├── README.md
├── LICENSE
├── .gitignore
└── requirements.txt            # 依赖清单（与 new/ 一致）
```

## 架构

```
┌──────────────────────────────────────┐
│           UI 层 (PyQt6)              │
│  MainWindow (Mediator)               │
│    ├── BookTableModel (表格模型)      │
│    ├── DetailDialog (详情 + 封面)     │
│    ├── SearchDialog (豆瓣搜索)        │
│    ├── StatsDialog (matplotlib 统计)  │
│    └── Theme (DARK / LIGHT QSS)      │
├──────────────────────────────────────┤
│            Service 层                │
│    DoubanService (豆瓣 API)          │
│    BackupService (定时备份 + 清理)   │
│    CSV Service (load / save)         │
├──────────────────────────────────────┤
│            Data 层                   │
│    BookRepo (Repository + SQLite)    │
│    Book (dataclass 领域模型)          │
├──────────────────────────────────────┤
│        Web 层 (FastAPI)              │
│    BookWebServer (内嵌 uvicorn)      │
│    路由: / /add /edit /delete       │
│    /book /cover /stats              │
└──────────────────────────────────────┘
```

MainWindow 作为中央协调者，通过 Qt 信号-槽连接各模块。所有网络操作在后台线程执行。
