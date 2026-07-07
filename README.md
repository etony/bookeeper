# 📚 Bookeeper

个人图书管理工具。PyQt6 桌面应用 + FastAPI Web 服务，支持豆瓣 API 自动填充、条形码扫描、CSV 导入导出。

## 功能

- **图书管理** — 增删改查，收藏你自己的书目
- **豆瓣 API** — 输入 ISBN 自动获取书名、作者、封面等信息
- **条形码扫描** — 摄像头或图片扫码，一步添加
- **排序筛选** — 点击表头排序，关键词搜索；列可拖拽重排、右键显隐
- **阅读追踪** — 状态（默认/计划/已读）+ 购书日期 + 已读日期（设为已读时自动填入）
- **CSV 导入/导出** — 与 Excel 无缝交换数据，支持扩展字段导出
- **统计面板** — 阅读状态饼图、出版社 TOP10、评分分布（深色风格）
- **暗色/亮色主题** — 一键切换，QSettings 持久化
- **局域网 Web 服务** — FastAPI 提供完整 CRUD + 搜索/分页/统计
- **ISBN 校验** — 输入失焦自动校验，无效红底提示
- **重复检测** — 导入时检测重复 ISBN，可选跳过/覆盖/合并
- **自动备份** — 每 5 分钟自动备份至 backups/ 目录，保留最近 30 份
- **快捷键** — Ctrl+O 加载 / Ctrl+S 保存 / Ctrl+F 查询 / Ctrl+D 豆瓣搜索 / Ctrl+R 重置

## 安装

```bash
pip install -r requirements.txt
```

依赖：
- PyQt6
- pandas
- opencv-python + pyzbar（条形码扫描）
- requests
- matplotlib（统计图表）
- fastapi + uvicorn（Web 服务）

## 使用

```bash
python main.py
```

首次运行自动生成 `config.json`，内含豆瓣 API key（可直接编辑）。

### Web 服务

主界面点击 **🌐 Web 服务** 启动，默认监听 `http://127.0.0.1:8899`，支持完整图书管理操作。

## 配置

编辑 `config.json`（与 `main.py` 同级）：

```json
{
  "DOUBAN_API_KEY": "你的 API key",
  "DOUBAN_API_KEY_SEARCH": "你的搜索 API key"
}
```

可通过主界面 ☀️/🌙 按钮切换主题，设置自动持久化。

## 项目结构

```
├── main.py                # 入口
├── config.py              # 全局配置
├── config.json            # 用户配置（API key 等）
├── utils.py               # ISBN 校验工具
├── models/
│   ├── book.py            # Book dataclass
│   └── table_model.py     # QSortFilterProxyModel
├── services/
│   ├── douban_api.py      # 豆瓣 API
│   ├── data_manager.py    # CSV 读写
│   └── web_server.py      # FastAPI Web 服务
├── ui/
│   ├── theme.py           # DARK_QSS / LIGHT_QSS
│   ├── main_window.py     # 主窗口
│   ├── detail_dialog.py   # 图书详情
│   ├── search_dialog.py   # 豆瓣搜索
│   ├── stats_dialog.py    # 统计面板
│   └── duplicate_dialog.py# 重复检测
├── workers/
│   └── workers.py         # 后台线程
└── requirements.txt
```
