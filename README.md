# Bookeeper

个人图书管理工具 — PyQt6 桌面应用 + FastAPI Web 服务，豆瓣 API 自动填充、ISBN 校验、CSV 导入导出、统计面板、自动备份。

## 功能

- **图书管理** — 增删改查，表格展示，双击查看详情
- **豆瓣 API** — 输入 ISBN 自动获取书名、作者、封面、评分等信息；Web 编辑页支持一键同步；支持重试机制
- **排序筛选** — 点击表头排序，关键词搜索 + 状态筛选；列可拖拽重排、右键显隐
- **阅读追踪** — 状态（默认/计划/已读）、书柜位置、购书日期、已读日期（设为已读时自动填入）
- **CSV 导入/导出** — UTF-8 BOM 编码，支持扩展字段，导入显示进度条
- **统计面板** — 阅读状态饼图、出版社 TOP10、评分分布（深色风格，matplotlib 渲染）
- **暗色/亮色主题** — 一键切换，QSettings 持久化保存
- **局域网 Web 服务** — FastAPI 提供完整 CRUD、搜索、分页、统计页面，带启动状态反馈
- **ISBN 校验** — 输入失焦自动校验（支持 ISBN-10/ISBN-13），无效红底提示
- **自动备份** — 每 5 分钟自动备份至 `backups/` 目录，保留最近 30 份，失败时打日志不崩溃
- **推荐度算法** — 综合评分和评价人数计算推荐指数 `(rating - 2.5) * log(raters + 1)`
- **后台线程** — 豆瓣搜索、封面下载等网络操作不阻塞 UI
- **快捷键** — Ctrl+S 保存 / Ctrl+F 搜索 / Ctrl+R 重置 / Ctrl+D 豆瓣搜索

## 安装

```bash
pip install -r requirements.txt
```

依赖：PyQt6、pandas、requests、matplotlib、fastapi、uvicorn

## 使用

```bash
python main.py
```

首次运行自动生成 `config.json`，内含豆瓣 API key（可直接编辑修改）。

### Web 服务

主界面点击 **🌐 Web 服务** 启动，默认监听 `http://127.0.0.1:8899`，支持完整的图书管理操作。

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
├── main.py                   # 应用入口
├── config.py                 # 全局配置（API key、列名、端口等）
├── config.json               # 用户配置（API key，不纳入 git 追踪）
├── utils.py                  # ISBN 校验工具
├── database.py               # 数据访问层（SQLite, Repository 模式）
├── settings.ini              # QSettings 持久化（主题、表头状态）
├── books.db                  # SQLite 数据库文件（不纳入 git 追踪）
├── .gitignore                # Git 忽略规则
├── models/
│   ├── book.py               # Book dataclass（领域模型）
│   └── table_model.py        # QAbstractTableModel（pandas DataFrame 后端）
├── services/
│   ├── __init__.py           # 共享 BookRepo 单例工厂
│   ├── douban.py             # 豆瓣 API 封装（含重试机制）
│   ├── data.py               # CSV 加载/保存/模板导出
│   └── backup.py             # 定时备份服务（异常安全）
├── ui/
│   ├── theme.py              # 暗色/亮色 QSS 主题
│   ├── main_window.py        # 主窗口（Mediator 协调所有模块）
│   ├── detail_dialog.py      # 图书详情（封面后台下载 + LRU 缓存）
│   ├── search_dialog.py      # 豆瓣搜索（后台线程不阻塞 UI）
│   └── stats_dialog.py       # 统计面板（matplotlib 图表）
├── web/
│   └── server.py             # FastAPI Web 服务（支持豆瓣同步、封面代理）
├── workers/
│   └── workers.py            # （预留）
└── requirements.txt
```

## 架构

```
UI 层 (PyQt6)  ─→  Service 层  ─→  Data 层 (SQLite)
MainWindow         DoubanService    BookRepo
DetailDialog       BackupService    Book (dataclass)
SearchDialog       Web Server       pandas DataFrame
StatsDialog        CSV data
```

`MainWindow` 作为中央协调者，通过 Qt 信号-槽机制连接各个模块。
