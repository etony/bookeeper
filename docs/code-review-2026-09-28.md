# Bookeeper 代码审查报告

- 审查日期：2026-09-28
- 审查范围：全仓库 Python 源码（约 7000 行，43 个文件）+ Web 模板 + 测试
- 方式：静态阅读 + 在临时库/offscreen Qt 下实测复现
- 基线：`135 passed`（`python -m pytest tests/ -q` 全绿）——**下列问题全部未被现有测试覆盖**

> 结论摘要：整体架构清晰、分层合理、注释质量高于平均水平（尤其 `database.py` / `backup.py`）。
> 但存在 **3 个会造成数据错误/丢失的缺陷**（已实测复现）和 **4 个用户可见的功能缺陷**，
> 建议优先修 P0 三条。

---

## 一、P0 · 数据正确性（已实测复现）

### P0-1 手工「更新记录」会清空封面、出版年、豆瓣链接、页数、推荐度

**位置**：`ui/main_window.py:444-471`（`_update_book`）

`_update_book` 只用表单的 11 个表格列构造 `Book`，而 `cover_url / pubdate / douban_url / pages / recommend`
不在表单里，取 dataclass 默认值（空串）。随后 `UpdateBookCommand.execute()` → `repo.upsert(book)`，
SQL 是 `ON CONFLICT(isbn) DO UPDATE SET cover_url=excluded.cover_url, ...`，于是把已有值**覆盖成空**。

`old_book` 虽然查出来了，却只传给了命令对象用于撤销，没有把扩展字段继承给新记录。

实测（临时库）：

```
更新前: cover_url='https://img.douban.com/large.jpg' pubdate='2008-1'
        douban_url='https://book.douban.com/subject/2567698/' pages='302' recommend='27'
更新后: cover_url=''  pubdate=''  douban_url=''  pages=''  recommend='0'
```

**复现路径**：表格点任意一行 → 改书名 → 点「更新记录」。
后果：详情对话框变「无封面」、Web `/cover/{isbn}` 返 404、封面墙卡片变灰、推荐度归零，且**不可撤销回扩展字段**。

**建议**：`old_book` 存在时，把 `cover_url / pubdate / douban_url / pages / recommend` 一并复制到 `new_book`
（可复用 `_merge_user_fields` 的思路，抽成 `_merge_preserved_fields(old, new)`）。

---

### P0-2 ISBN 未清洗 → 同一本书产生两条记录

**位置**：`ui/main_window.py:444-471`

查重与写入用的是**两个不同来源的 ISBN**：

| 用途 | 代码 | 值 |
|---|---|---|
| 查重 | `isbn = self._book_form.get_isbn()` | `.strip()`，但**不 clean** |
| 入库主键 | `row_data[0]` = `_isbn_input.text()` | 完全原样（含 `-`、含空格） |

而 `_fetch_book` 走的是 `clean_isbn()`，两条路径对同一本书的 ISBN 认定不一致。

实测：

```
A-入库后记录数 = 1
A-手输 978-7-111-12345-6 点「更新记录」后记录数 = 2
  → ['978-7-111-12345-6', '9787111123456']
```

带**首尾空格**时更隐蔽：查重命中旧记录（走 Update），但写入主键带空格 → upsert 视为新记录 → 依然 2 条。

**建议**：`_update_book` 入口 `isbn = clean_isbn(self._book_form.get_isbn())`，并让
`BookFormWidget.get_form_data()['isbn']` 返回清洗后的值（唯一真源）。
`BookRepo.import_df`（`database.py:286`）有同样问题，CSV 导入带连字符的 ISBN 会再生成一份。

---

### P0-3 空 ISBN 作为主键，多条记录互相覆盖

**位置**：`ui/main_window.py:446-465`、`core/models/book.py:44`

ISBN 为空时主键就是 `''`，`upsert` 的 `ON CONFLICT(isbn)` 让**第二本直接覆盖第一本**。

两个触发口：

1. 手输只有书名、不填 ISBN → 插入主键 `''`；
2. 豆瓣搜索结果缺 `isbn13` 时，`Book.from_douban` 只取 `isbn13` 且**不回退 `isbn10`** → `isbn=''`。

实测：

```
B-两本无 ISBN 的书      → 记录数 = 1，只留下「无名书乙」
C-两本缺 isbn13 的搜索结果 → 记录数 = 1，只留下「无isbn13乙」
```

**建议**：
- `Book.from_douban` 增加 `data.get('isbn13') or data.get('isbn10') or ''` 回退；
- ISBN 为空时在 `_update_book` / `_on_search_result` 明确拒绝并提示（或改用 `isbn + title + 时间戳` 的代理键），不要静默写空主键。

---

## 二、P1 · 用户可见的功能缺陷（已实测复现）

### P1-1 封面墙配色与实际主题脱钩：默认暗色主题下是「白底 + 浅灰字」

**位置**：`ui/cover_wall.py:26-42`（`_is_dark_theme` / `_card_colors`）

```python
def _is_dark_theme() -> bool:
    bg = QApplication.instance().palette().color(palette.ColorRole.Window)
    return bg.lightness() < 128
```

但主题是用 **`setStyleSheet`** 实现的（`main.py:57`、`main_window._toggle_theme`），**从不设置 palette**。
所以 `_is_dark_theme()` 反映的是 **Windows 系统主题**，不是应用主题。

实测（套用 `DARK_QSS` 后）：

```
palette.Window = #efefef  lightness = 239
_is_dark_theme() = False  ->  卡片配色 = ('#ffffff', '#d8d6d0')
```

于是默认暗色主题下：卡片底色 `#ffffff` / 封面底 `#f0eeea`，而全局 QSS 的文字色是 `#e0e0e4`
→ **书名、封面上的「加载中…」几乎不可见**。

同类问题（主题切换后颜色不跟随）：
- `ui/tool_bar.py:54,116`：分隔线、文件标签用 `palette().Mid / PlaceholderText` 取色；
- `ui/detail_dialog.py:212`：信息表左侧标签列用 `PlaceholderText` 作为 muted 色。

**建议**：不要从 palette 猜主题。把 `_dark_mode` 显式传入封面墙/工具栏/详情框
（`StatsDialog(repo, dark_mode=...)` 已是正确范式），`_toggle_theme` 时一并 `refresh`。
或者双管齐下：`QApplication.setPalette(...)` 与样式表同步切换。

### P1-2 封面卡片的「状态」「评分」角标从未显示

**位置**：`ui/cover_wall.py:111-128`

```python
self._status_label = QLabel(self._book.status)   # 没给 parent
...
self._status_label.move(4, 4)                    # 也没 addWidget 进布局
```

`QLabel(text)` 的 parent 是 `None`，之后既没 `setParent(self)` 也没加入 layout → 是**游离控件**，不会被绘制。
`grep -n setParent ui/cover_wall.py` 只命中清理逻辑，全文件没有给这两个标签设父对象。

实测：

```
status_label.parent() = None
rating_label.parent() = None
是否在卡片布局内 = False
```

**建议**：`QLabel(self._book.status, self)` / `QLabel(rating_text, self)`，并用 `resizeEvent` 重新定位（现在 `move(111,4)` 的硬编码坐标在卡片宽度变化时也会错位）。

### P1-3 封面墙每次窗口 resize 都全量重建所有卡片

**位置**：`ui/cover_wall.py:430-443`

```python
def _update_auto_columns(self):
    if not self._auto_columns: return
    width = self._scroll_area.viewport().width()
    if width > 0:
        self._columns = max(3, min(8, width // 160))
        self._refresh_grid()          # 无条件重建，即使列数没变
```

`resizeEvent` → `_update_auto_columns` → 无条件 `_refresh_grid()`。而 `_refresh_grid` 会销毁并重建全部
`CoverCard`，每张卡还会重新入队封面下载。

实测（12 本书，连续 6 次 `resize`，列数始终为 7）：

```
6 次 resize 触发 _refresh_grid 次数 = 6
列数序列 = [7, 7, 7, 7, 7, 7]   ← 6 次全是无效重建
```

拖一次窗口边缘就会触发几十上百次重建 → 明显卡顿，且线程池 `_cover_pool`（max_workers=3）被反复灌任务。

**建议**：只有列数真正变化时才刷新：

```python
new_cols = max(3, min(8, width // 160))
if new_cols != self._columns:
    self._columns = new_cols
    self._refresh_grid()
```

### P1-4 快速重复「获取信息」会导致旧查询结果覆盖新查询

**位置**：`ui/main_window.py:396-415`（`_do_fetch_book`）

```python
if hasattr(self, '_fetch_thread') and self._fetch_thread.isRunning():
    self._fetch_thread.quit()
    self._fetch_thread.wait(1000)
```

`quit()` 只能退出线程事件循环，**无法中断正在阻塞的 `requests` 请求**；而且旧 worker 的
`finished` / `failed` 仍连接着 `_on_fetch_success` / `_on_fetch_error`，没有断连。
所以旧请求返回后依然会：填表单、push 一条撤销命令、`_load_data()` ——覆盖用户后一次查询的结果。

**建议**：给每次查询一个自增 `token`，worker 带回 token，回调里 `if token != self._fetch_token: return`。

---

## 三、P2 · 中等问题

| # | 问题 | 位置 | 说明 |
|---|---|---|---|
| P2-1 | `web_host` 配置完全无效（死配置） | `web/server.py:343` | schema/defaults 解析并校验了 host，但 uvicorn 硬编码 `host='127.0.0.1'`，`_apply_to_legacy_config` 也不回写 `Config`。中文 `关于` 对话框却宣传「局域网 Web 服务」。要么接线，要么删掉配置项 |
| P2-2 | 搜索结果表格列数与数据不匹配 | `ui/search_dialog.py:182-187` | 建 `QStandardItemModel(len, 9)` 却灌 `to_row()` 的 11 项。实测列数被撑到 11，末两列表头变成 `10`/`11` |
| P2-3 | 首次启动表头箭头与实际顺序不符 | `ui/main_window.py:163-180, 877-891` | `setSortingEnabled(True)` + 无历史 headerState 时，实测 `isSortIndicatorShown()=True, section=0, Descending`，即 ISBN 列显示 ▼，但数据是 rowid DESC。仅 `_restore_header_state` 里有 `setSortIndicator(-1)`，首启不进这条分支 |
| P2-4 | `_save_header_state` 每次新建 QTimer | `ui/main_window.py:862-869` | 每次列拖动/排序都 `QTimer(self)`，旧 timer 只 `stop()` 不销毁、仍是窗口子对象 → 持续累积。应复用同一实例 |
| P2-5 | 备份在 GUI 线程执行 | `ui/main_window.py:345-362` | `QTimer.singleShot(0, backup)` 与 `closeEvent` 里的 `backup()` 都是同步的 sqlite online backup，库大时卡界面/拖慢关闭 |
| P2-6 | 每个连接都执行 `PRAGMA journal_mode=WAL` | `database.py:87` | WAL 是持久化属性，建库时设一次即可；现在每次读操作都多一次 PRAGMA 往返 |
| P2-7 | `/sync/{isbn}` 的 `back` 参数未校验 | `web/server.py:183,204` | 直接拼进 `RedirectResponse` → 开放重定向（仅本机自用，风险低，但应白名单）。另 `_valid_date` 只做正则，`2026-99-99` 会通过 |
| P2-8 | 封面缓存写入不严谨 | `services/covers.py:73` | `os.write(fd, data)` 不保证写全；异常路径下 fd 可能泄漏。建议 `os.fdopen(fd, 'wb')`。`_COVERS_DIR` 是 import 期常量，靠惰性 import 规避 `init_config()` 改路径，较脆弱 |
| P2-9 | `import_df` 不清洗 ISBN | `database.py:286` | 与 P0-2 同源：CSV 里带连字符的 ISBN 与豆瓣路径不一致，导入会再造重复记录 |

---

## 四、P3 · 代码质量与一致性

- `ui/detail_dialog.py:177-186`：缺封面/出版年时会**静默** `repo.upsert(book)`，不通知主窗口也不置 dirty（因字段不在表格列，暂无实际影响，但属于隐式写库）。
- `ui/cover_wall.py:462-463`：`self._cards[i]._book.isbn` 访问私有成员，应给 `CoverCard` 加 `book` 属性。
- `ui/main_window.py:227-253`：`_make_book_menu` 返回 4 元组 + 用对象身份比较分派，可读性差，建议改用 `action.setData(('cmd', ...))` 统一分派（批量状态项已是这个模式）。
- `web/server.py:282-283`：因为 `get_all()` 是 rowid DESC，`prev_link` 实际指向更新的记录，"上一本/下一本"语义相反。
- `ui/main_window.py:654-663`：导入线程结束后只 `quit()+wait()`，未 `deleteLater()`，与其它线程（fetch / search）的处理不一致。
- `ui/main_window.py:196-200`：`_user_sorted` + `_load_data` 的配对逻辑被多处隐式依赖，但没有注释说明不变量，后续改动容易破坏（建议加断言或抽成 `_reapply_sort()`）。

---

## 五、测试覆盖缺口

现有 135 个用例全绿，但**上述问题无一条被覆盖**。建议补充的回归用例：

1. `_update_book` 后扩展字段仍保留（P0-1）；
2. 带连字符/空格 ISBN 走「更新记录」不产生第二条（P0-2）；
3. 两本 ISBN 为空的书不会互相覆盖（P0-3）；
4. `Book.from_douban` 缺 `isbn13` 时回退 `isbn10`（P0-3）；
5. 封面墙 `resize` 且列数不变时 `_refresh_grid` 不被调用（P1-3）；
6. `CoverCard` 的状态/评分标签 parent 非 None（P1-2）；
7. `search_dialog` 结果模型列数为 9（P2-2）。

---

## 六、修复优先级建议

| 优先级 | 项目 | 影响面 | 改动量 |
|---|---|---|---|
| 1 | P0-1 扩展字段被清空 | 数据丢失，用户必踩 | 小（~10 行） |
| 2 | P0-2 / P0-3 ISBN 主键问题 | 数据重复/覆盖 | 小（~15 行） |
| 3 | P1-3 resize 全量重建 | 卡顿，大库尤甚 | 极小（3 行） |
| 4 | P1-2 角标不显示 | 功能缺失 | 小 |
| 5 | P1-1 主题配色脱钩 | 默认主题下卡片文字不可读 | 中（需贯穿传 dark_mode） |
| 6 | P1-4 查询串台 | 竞态，偶发 | 小 |
| 7 | P2 系列 | 配置无效 / 体验 | 按需 |
