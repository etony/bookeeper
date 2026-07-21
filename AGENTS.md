# Bookeeper

## 快速起步

```bash
pip install -r requirements.txt
python main.py          # 桌面 GUI
python main.pyw         # 无控制台窗口（Windows）
```

## 架构速览

- **PyQt6 桌面应用** + **FastAPI Web 服务**（8899 端口），共用 SQLite
- `main.py` → `MainWindow`（中央协调者） → `BookRepo`（CRUD）/ `DoubanService`（API）/ `WebServer`
- `config.py` 全局配置，首次运行自动生成 `config.json`（含豆瓣 API key，已 gitignore）
- `settings.ini`（QSettings）存储窗口状态，已 gitignore
- `backups/` 保留最近 30 份备份，每 5 分钟自动备份，已 gitignore

## 关键约定

- **所有文本字段用 TEXT 存储**，避免类型转换问题
- **豆瓣 API** 需模拟移动端 User-Agent，v2 接口使用 POST + apikey
- **Web 封面代理**：`/cover/{isbn}` 反向代理豆瓣封面图片（防 403）
- **主题**：暖深色默认，暖橙强调色 `#e8922a`
- **无测试、无 CI、无类型检查**——纯手工验证

## 注意事项

- `new/` 目录是旧版重构实验，已废弃，无需关注
- `/cover/{isbn}` 路由必须在 `/{path:path}` 通配路由之前注册
- 表格模型基于 `pandas.DataFrame`，更新后用 `emitDataChanged()` 刷新
- 豆瓣搜索需要两个不同的 API key（查 ISBN 用 one，关键词搜索用另一个）
- 导出 CSV 列比界面列多（含封面 URL、豆瓣链接等扩展字段）
