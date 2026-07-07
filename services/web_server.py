# -*- coding: utf-8 -*-
"""图书管理系统 Web 服务器

模块功能：
  - 提供完整的图书管理 Web 界面（HTML 页面）和 JSON API
  - 支持图书的增删改查、CSV 导入导出、豆瓣信息批量刷新、数据统计

架构说明：
  - 基于 FastAPI 框架，内嵌 uvicorn 服务器
  - 所有路由分为两大类：
    1. HTML 页面路由（以 GET/POST 返回 HTMLResponse）—— 用于浏览器直接访问
    2. JSON API 路由（以 /api/ 前缀返回 JSON）—— 供前端脚本或第三方调用
  - 数据以 pandas.DataFrame 形式常驻内存，通过 threading.Lock 保证线程安全
  - CSV 读写委托给 DataManager，豆瓣 API 调用委托给 DoubanService

线程安全：
  - self._data 是类内部的核心数据，所有读写操作均需先获取 self._lock
  - 多线程场景下防止数据竞争：复制数据用于展示，在锁内修改数据并持久化
  - 注意：pandas 的 DataFrame 自身不是线程安全的，必须通过锁保护
"""

import asyncio
import io
import threading
from typing import Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, Form, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from services.data_manager import DataManager
from services.douban_api import DoubanService
from config import Config

# 页面样式 —— 暗色主题风格，所有样式内嵌在 Python 字符串常量 CSS 中
# 采用 CSS 自定义属性（--xxx）统一管理颜色和尺寸，便于维护和主题切换
# 主要区块：导航栏(.nav) / 工具栏(.toolbar) / 表格(table) / 分页(.pagination)
#           / 消息提示(.msg) / 表单(form) / 统计图表(.chart-box)
CSS = '''
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#12161a;--surface:#1a1f26;--surface2:#222831;--border:#2d3540;--border-hover:#3d4a5a;--text:#c8ccd4;--text2:#8899aa;--text3:#5a6a7a;--accent:#e8b84b;--accent-hover:#f0c860;--accent-dim:#8a7030;--danger:#d44;--danger-bg:#3a1414;--radius:8px;--radius-sm:4px}
body{font-family:-apple-system,"Microsoft YaHei","Noto Sans SC",sans-serif;background:var(--bg);color:var(--text);padding:24px;font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none;transition:color .15s}
a:hover{color:var(--accent-hover);text-decoration:underline}
h1{font-size:26px;font-weight:700;margin-bottom:20px;letter-spacing:-0.3px;background:linear-gradient(135deg,var(--accent),#f0d080);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
h2{font-size:20px;font-weight:600;margin:20px 0 14px;color:var(--text)}

/* 导航栏 */
.nav{display:flex;gap:6px;margin-bottom:24px;flex-wrap:wrap;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)}
.nav a{padding:7px 16px;border-radius:var(--radius-sm);color:var(--text2);font-size:13px;font-weight:500;transition:all .15s}
.nav a:hover{background:var(--surface2);color:var(--accent);text-decoration:none}

/* 工具栏(搜索) */
.toolbar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:center;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)}
.toolbar input,.toolbar select,.toolbar textarea{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:8px 12px;color:var(--text);font-size:14px;transition:border-color .15s;outline:none}
.toolbar input:focus,.toolbar select:focus{border-color:var(--accent);box-shadow:0 0 0 2px rgba(232,184,75,.15)}
.toolbar button,.btn{padding:7px 18px;border-radius:var(--radius-sm);font-size:14px;font-weight:500;cursor:pointer;border:none;transition:all .15s}
.btn-primary{background:var(--accent);color:#12161a}
.btn-primary:hover{background:var(--accent-hover);transform:translateY(-1px)}
.btn-danger{background:var(--danger-bg);border:1px solid var(--danger);color:var(--danger)}
.btn-danger:hover{background:#4a1818}
.btn-sm{padding:4px 12px;font-size:12px;border-radius:3px}

/* 图书表格 */
table{width:100%;border-collapse:separate;border-spacing:0;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
thead{position:sticky;top:0;z-index:1}
th{background:var(--surface2);padding:10px 12px;text-align:left;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--text2);border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:9px 12px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;border-bottom:1px solid var(--border);font-size:13px}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(232,184,75,.04)}
.pagination{margin-top:16px;display:flex;gap:6px;align-items:center;justify-content:center}
.pagination a,.pagination span{padding:6px 14px;border-radius:var(--radius-sm);font-size:13px;font-weight:500}
.pagination a{background:var(--surface);border:1px solid var(--border);color:var(--text2);transition:all .15s}
.pagination a:hover{background:var(--surface2);border-color:var(--accent);color:var(--accent);text-decoration:none}
.pagination .active{background:var(--accent);border:1px solid var(--accent);color:#12161a}
.summary{color:var(--text2);font-size:13px;margin-bottom:12px;text-align:center}

/* 消息 */
.msg{padding:12px 16px;border-radius:var(--radius-sm);margin-bottom:16px;font-size:13px}
.msg-info{background:rgba(232,184,75,.08);border:1px solid rgba(232,184,75,.25);color:var(--accent)}
.msg-err{background:var(--danger-bg);border:1px solid var(--danger);color:var(--danger)}

/* 表单 */
form{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px}
form label{display:block;margin-top:14px;font-size:13px;font-weight:500;color:var(--text2);letter-spacing:.3px}
form label:first-child{margin-top:0}
form input,form select{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:8px 12px;color:var(--text);font-size:14px;width:100%;transition:border-color .15s;outline:none}
form input:focus,form select:focus{border-color:var(--accent);box-shadow:0 0 0 2px rgba(232,184,75,.12)}
form .row{display:flex;gap:16px;flex-wrap:wrap}
form .row>div{flex:1;min-width:240px}
form>div:last-child{margin-top:20px}

/* 统计图表 —— 以纯 CSS 条形图呈现，无需任何 JS 图表库 */
.chart-box{margin-top:20px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px}
.chart-box h3{font-size:15px;margin-bottom:14px;color:var(--text);font-weight:600}
.chart-bar{display:flex;align-items:center;margin:6px 0;gap:10px}
.chart-bar .label{width:150px;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;color:var(--text2);flex-shrink:0}
.chart-bar .fill{height:24px;background:linear-gradient(90deg,var(--accent-dim),var(--accent));border-radius:4px;display:flex;align-items:center;padding:0 10px;color:#12161a;font-size:12px;font-weight:600;min-width:36px}

/* 滚动条 */
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:var(--border-hover)}
'''

# 导航栏 HTML 模板（所有页面上方一致的链接栏）
NAV = '''
<div class="nav">
<a href="/">📚 图书列表</a>
<a href="/add">➕ 添加图书</a>
<a href="/stats">📊 统计</a>
<a href="/import">📂 导入</a>
<a href="/export">📤 导出</a>
<a href="/refresh">🔄 刷新</a>
<a href="/docs" target="_blank">📖 API</a>
</div>'''

# 页面骨架（HTML5 模板），通过 Python str.format() 填入标题、样式、导航和内容
BASE = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css}</style></head><body><h1>📚 Bookeeper</h1>{nav}<div id="main">{content}</div></body></html>'


def html_page(title: str, content: str) -> str:
  """组装完整 HTML 页面

  将标题、样式、导航、内容填充到 BASE 模板中返回。

  参数：
    title:   页面标题（显示在浏览器标签栏）
    content: 页面主体 HTML（不含 <body> 标签，由 BASE 统一包裹）

  返回：
    完整的 HTML 字符串
  """
  return BASE.format(title=title, css=CSS, nav=NAV, content=content)


def esc(val) -> str:
  """HTML 转义工具函数

  将字符串中的 & < > " 转义为 HTML 实体，防止 XSS 攻击。
  所有用户输入或数据库内容在嵌入 HTML 前必须经此函数处理。

  参数：
    val: 任意值，None 会被转为空字符串

  返回：
    转义后的安全字符串
  """
  s = str(val) if val is not None else ''
  return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


class BookWebServer:
  """图书管理系统 Web 服务器

  职责：
    - 启动 FastAPI + uvicorn 提供 HTTP 服务
    - 维护内存中的 DataFrame（self._data）作为数据源
    - 通过 threading.Lock 确保线程安全
    - 同时提供 HTML 页面渲染和 JSON API 两种接口

  路由组织（见 _setup_routes）：
    - HTML 页面：GET /, /add, /edit/{isbn}, /book/{isbn}, /stats, /import, /export, /refresh
    - HTML 表单提交：POST /add, /edit/{isbn}, /import, /refresh
    - JSON API：GET/POST /api/books, GET/PUT/DELETE /api/books/{isbn}
    - 辅助 API：GET /api/fetch-isbn/{isbn}（由前端 JS 调用，返回豆瓣信息）

  生命周期：
    - start() → load_data() → uvicorn server serve → stop()
  """

  def __init__(self, file_path: str, port: int = 8899):
    """初始化服务器实例

    参数：
      file_path: CSV 数据文件的路径（启动时加载，每次修改后写回）
      port:      监听端口（默认 8899）
    """
    self._file_path = file_path
    self._port = port
    self._app = FastAPI(title='Bookeeper API')
    self._data: Optional[pd.DataFrame] = None  # 内存中的核心数据，所有线程通过锁访问
    self._lock = threading.Lock()              # 保护 self._data 的线程锁
    self._server: Optional[uvicorn.Server] = None
    # 允许跨域访问（开发环境或前后端分离时使用）
    self._app.add_middleware(
      CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'],
    )
    self._setup_routes()

  # ── 页面渲染 ──────────────────────────────────
  # 以下 _xxx_page 方法均返回完整 HTML 字符串，通过 html_page() 组装
  # 数据读取时使用 with self._lock 保护，读取后复制一份避免长时间占用锁

  def _list_page(self, q: str, page: int) -> str:
    """渲染图书列表页面（支持搜索 + 分页）

    流程：
      1. 在锁保护下复制数据副本（减少锁持有时间）
      2. 若有关键词 q，逐行扫描（将每列转字符串后检查是否包含 q）
      3. 分页计算：每页 20 条，page 参数从 URL 查询传入
      4. 逐行拼接 HTML 表格行（所有用户数据经 esc() 转义防 XSS）
      5. 底部渲染分页导航按钮

    参数：
      q:    搜索关键词（空字符串表示不过滤）
      page: 页码（从 1 开始）

    返回：
      完整的 HTML 页面字符串
    """
    with self._lock:
      df = self._data.copy() if self._data is not None else pd.DataFrame()
    if q:
      # 搜索：将每行所有列转字符串，检查是否包含关键词（na=False 忽略 NaN）
      mask = df.apply(lambda r: r.astype(str).str.contains(q, na=False).any(), axis=1)
      df = df[mask]
    total = len(df)
    size = 20
    total_pages = max(1, (total + size - 1) // size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * size
    items = df.iloc[start:start + size].fillna('').to_dict(orient='records')
    rows = ''
    for r in items:
      isbn = esc(r.get('ISBN', ''))
      rows += f'''<tr>
<td><a href="/book/{isbn}">{isbn}</a></td>
<td>{esc(r.get('书名',''))}</td>
<td>{esc(r.get('作者',''))}</td>
<td>{esc(r.get('出版',''))}</td>
<td>{esc(r.get('价格',''))}</td>
<td>{esc(r.get('评分',''))}</td>
<td>{esc(r.get('状态',''))}</td>
<td>{esc(r.get('书柜',''))}</td>
<td>
  <a class="btn btn-sm btn-primary" href="/edit/{isbn}">编辑</a>
  <a class="btn btn-sm btn-danger" href="/delete/{isbn}" onclick="return confirm('确定删除 {isbn}？')">删除</a>
</td>
</tr>\n'''
    pages = ''
    for p in range(1, total_pages + 1):
      if p == page:
        pages += f'<span class="active">{p}</span> '
      else:
        pages += f'<a href="/?q={q}&page={p}">{p}</a> '
    search_box = f'''<form class="toolbar" method="get" action="/">
<input type="text" name="q" placeholder="搜索 ISBN/书名/作者..." value="{esc(q)}">
<button class="btn btn-primary">🔎 搜索</button>
</form>'''
    return html_page('图书列表', f'''
{search_box}
<div class="summary">共 {total} 条记录，第 {page}/{total_pages} 页</div>
<table><thead><tr>
<th>ISBN</th><th>书名</th><th>作者</th><th>出版</th>
<th>价格</th><th>评分</th><th>状态</th><th>书柜</th><th>操作</th>
</tr></thead><tbody>{rows}</tbody></table>
<div class="pagination">{pages}</div>''')

  def _form_page(self, title: str, action: str, book: dict = None, show_fetch: bool = False) -> str:
    """渲染图书编辑 / 添加表单页面

    表单包含两列布局：左侧为基本信息（ISBN、书名、作者、出版、价格），
    右侧为评分及管理信息（评分、人数、状态、书柜、日期等）。

    参数：
      title:     页面标题
      action:    表单提交的 URL（如 /add 或 /edit/{isbn}）
      book:      编辑模式下已有的图书数据（添加模式为 None）
      show_fetch: 是否显示"获取信息"按钮（添加模式显示，编辑模式不显示）

    返回：
      完整的 HTML 页面字符串

    注意事项：
      - "获取信息"按钮通过前端 JS（fetchIsbn）异步调用 /api/fetch-isbn/{isbn}
        自动填充豆瓣返回的数据，减少用户手动输入
      - 字段定义在 fields 列表中，集中管理 label / name / 类型 / 默认值
      - 字段自动分为两列（左列前一半，右列后一半），无需手动调整
    """
    b = book or {}
    fetch_btn = ''
    script = ''
    isbn_val = esc(b.get('ISBN', ''))
    if show_fetch:
      fetch_btn = ('<button class="btn btn-primary" type="button" id="fetchBtn"'
                   ' onclick="fetchIsbn()">🌐 获取信息</button>')
      script = '''<script>
async function fetchIsbn(){const i=document.getElementById('isbnInput').value.trim();if(!i)return;
const btn=document.getElementById('fetchBtn');btn.disabled=true;btn.innerText='获取中...';
try{const r=await fetch('/api/fetch-isbn/'+encodeURIComponent(i));if(!r.ok){alert('未找到图书信息');return;}
const d=await r.json();const m={'title':'title','author':'author','publisher':'publisher',
'price':'price','rating':'rating','raters':'raters'};
for(const[k,v]of Object.entries(m)){const el=document.getElementById(v);if(el&&d[k]!==undefined)el.value=d[v];}
}catch(e){alert('请求失败');}finally{btn.disabled=false;btn.innerText='🌐 获取信息';}}
</script>'''
    fields = [
      ('ISBN', 'isbn', 'ISBN 编码', 'text', isbn_val),
      ('书名', 'title', '图书名称', 'text', b.get('书名', '')),
      ('作者', 'author', '作者 / 译者', 'text', b.get('作者', '')),
      ('出版', 'publisher', '出版社', 'text', b.get('出版', '')),
      ('价格', 'price', '定价', 'text', b.get('价格', '')),
      ('评分', 'rating', '豆瓣评分', 'text', b.get('评分', '')),
      ('人数', 'raters', '评价人数', 'text', b.get('人数', '')),
       ('状态', 'status', '', 'select', b.get('状态', '默认'),
       '<option>默认</option><option>计划</option><option>已读</option>'),
      ('书柜', 'shelf', '存放位置', 'text', b.get('书柜', '')),
      ('购书日期', 'start_date', 'YYYY-MM-DD', 'date', b.get('购书日期', '')),
      ('已读日期', 'end_date', 'YYYY-MM-DD', 'date', b.get('已读日期', '')),
    ]
    inputs = []
    for label, key, placeholder, typ, val, *extra in fields:
      inp = ''
      if typ == 'select':
        opts = extra[0] if extra else ''
        inp = f'<select name="{key}">{opts}</select>'
      else:
        inp = f'<input type="{typ}" name="{key}" id="{key}" value="{esc(val)}" placeholder="{placeholder}">'
      if label == 'ISBN' and fetch_btn:
        inp = f'<div style="display:flex;gap:6px"><input type="text" name="isbn" id="isbnInput" value="{isbn_val}" placeholder="ISBN 编码" style="max-width:360px">{fetch_btn}</div>'
      inputs.append(f'<label>{label}</label>{inp}')
    mid = (len(inputs) + 1) // 2
    col1 = '\n'.join(inputs[:mid])
    col2 = '\n'.join(inputs[mid:])
    page = html_page(title, f'''
<form method="post" action="{action}">
<div class="row"><div>{col1}</div><div>{col2}</div></div>
<div style="margin-top:16px"><button class="btn btn-primary" type="submit">💾 保存</button>
<a href="/" style="margin-left:8px;color:#8899aa">取消</a></div>
</form>''')
    if script:
      page = page.replace('</head>', script + '</head>')
    return page

  def _stats_page(self) -> str:
    """渲染统计页面（纯 CSS 条形图，无需 JS）

    三种图表类型：
      - pie: 按分类统计数量，显示百分比（如阅读状态分布）
      - bar: 取前 N 项横向条形图（如出版社 TOP10）
      - hist: 数值分段统计（如评分按区间分布）

    所有图表均使用纯 CSS 实现（.chart-bar + .fill），
    宽度百分比通过 Python 计算后内联到 style 属性中。

    注意：评分字段是字符串，需要先用 pd.to_numeric 转数值再分段。
    """
    with self._lock:
      df = self._data.copy() if self._data is not None else pd.DataFrame()
    charts = ''
    if df.empty:
      charts = '<p style="color:#8899aa">暂无数据</p>'
    else:
      for label, col, chart_type in [
        ('📖 阅读状态', '状态', 'pie'),
        ('🏢 出版社 TOP10', '出版', 'bar'),
        ('⭐ 评分分布', '评分', 'hist'),
      ]:
        if col not in df.columns:
          continue
        if chart_type == 'pie':
          counts = df[col].value_counts()
          total = counts.sum()
          bars = ''
          for k, v in counts.items():
            pct = v / total * 100
            w = max(2, pct * 3)
            bars += f'<div class="chart-bar"><span class="label">{esc(k)}</span><div class="fill" style="width:{w}%">{v} ({pct:.1f}%)</div></div>'
          charts += f'<div class="chart-box"><h3>{label}</h3>{bars}</div>'
        elif chart_type == 'bar':
          counts = df[col].value_counts().head(10)
          mx = counts.max() if not counts.empty else 1
          bars = ''
          for k, v in counts.items():
            w = max(5, v / mx * 80)
            bars += f'<div class="chart-bar"><span class="label">{esc(k)}</span><div class="fill" style="width:{w}%">{v}</div></div>'
          charts += f'<div class="chart-box"><h3>{label}</h3>{bars}</div>'
        elif chart_type == 'hist':
          vals = pd.to_numeric(df[col], errors='coerce').dropna()
          bins = [0, 6, 7, 8, 9, 10]
          labels = ['0-6分', '6-7分', '7-8分', '8-9分', '9-10分']
          cats = pd.cut(vals, bins=bins, labels=labels)
          counts = cats.value_counts().reindex(labels, fill_value=0)
          mx = counts.max() if not counts.empty else 1
          bars = ''
          for k, v in counts.items():
            w = max(5, v / mx * 80)
            bars += f'<div class="chart-bar"><span class="label">{k}</span><div class="fill" style="width:{w}%">{v}</div></div>'
          charts += f'<div class="chart-box"><h3>{label}</h3>{bars}</div>'
    return html_page('统计', f'<h2>📊 统计面板</h2>{charts}')

  def _detail_page(self, isbn: str) -> str:
    """渲染图书详情页面

    以表格形式展示该图书所有字段（第一列是字段名，第二列是值）。
    页面顶部提供"编辑"、"删除"、"返回列表"三个操作入口。

    参数：
      isbn: 要查看的图书 ISBN

    返回：
      HTML 页面，如 ISBN 不存在或数据未加载则返回错误提示页

    注意：
      - 使用 df.iloc[:, 0] 定位第一列为 ISBN（但不依赖列名）
      - 所有用户数据经 esc() 转义
    """
    with self._lock:
      df = self._data
    if df is None:
      return html_page('错误', '<div class="msg msg-err">数据未加载</div>')
    mask = df.iloc[:, 0].astype(str) == isbn
    if not mask.any():
      return html_page('未找到', '<div class="msg msg-err">图书不存在</div>')
    r = df[mask].iloc[0].fillna('').to_dict()
    name = esc(r.get('书名', ''))
    info = '<table style="margin-top:14px">'
    for k in df.columns:
      info += f'<tr><th style="width:100px;text-transform:none;letter-spacing:0">{esc(k)}</th><td>{esc(r.get(k, ""))}</td></tr>'
    info += '</table>'
    return html_page(f'图书详情 - {name}', f'''
<div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px">
<h2 style="margin-top:0">📖 {name}</h2>
<div style="margin:16px 0;display:flex;gap:8px">
<a class="btn btn-primary" href="/edit/{isbn}">✏️ 编辑</a>
<a class="btn btn-danger" href="/delete/{isbn}" onclick="return confirm('确定删除？')">🗑 删除</a>
<a href="/" style="padding:7px 16px;color:var(--text2)">← 返回列表</a>
</div>
{info}
</div>''')

  def _import_page(self, msg: str = '', is_err: bool = False) -> str:
    """渲染 CSV 导入页面

    包含文件上传表单（multipart/form-data，仅接受 .csv 文件）。
    支持旧版列名（分类/开始日期/结束日期）和新版列名（状态/购书日期/已读日期）。

    参数：
      msg:   操作结果消息（为空时不显示消息栏）
      is_err:消息是否为错误类型（决定消息样式：info 或 error）
    """
    cls = 'msg-err' if is_err else 'msg-info'
    banner = f'<div class="msg {cls}">{msg}</div>' if msg else ''
    return html_page('导入 CSV', f'''
<h2>📂 导入 CSV</h2>
{banner}
<form method="post" action="/import" enctype="multipart/form-data">
<label>选择 CSV 文件</label>
<input type="file" name="file" accept=".csv" required>
<div><button class="btn btn-primary" type="submit">📤 上传并导入</button></div>
</form>
<p style="margin-top:14px;color:var(--text2);font-size:13px">支持旧格式（分类列）和新格式（状态列）</p>''')

  def _refresh_page(self, msg: str = '') -> str:
    """渲染批量豆瓣刷新页面

    用户确认后将逐本调用豆瓣 API 更新图书信息。
    请求间隔由 Config.API_REQUEST_DELAY 控制，防止触发豆瓣限流。

    参数：
      msg: 刷新结果消息（为空时不显示）
    """
    banner = f'<div class="msg msg-info">{msg}</div>' if msg else ''
    return html_page('豆瓣刷新', f'''
<h2>🔄 批量豆瓣刷新</h2>
{banner}
<form method="post" action="/refresh">
<p style="margin-bottom:16px;color:var(--text2);font-size:14px">
将从豆瓣 API 重新获取每本书的信息并更新记录，每本间隔 {Config.API_REQUEST_DELAY} 秒。
</p>
<div style="display:flex;gap:8px">
<button class="btn btn-primary" type="submit">🔄 开始刷新</button>
<a href="/" style="padding:7px 16px;color:var(--text2)">返回</a>
</div>
</form>''')

  # ── 路由 ──────────────────────────────────────
  # 路由分为两类：
  #   1. HTML 页面路由（response_class=HTMLResponse）：返回完整的 HTML 页面
  #   2. JSON API 路由（前缀 /api/）：返回 JSON 数据
  # 所有修改数据的操作都需先获取 self._lock，写完后立即保存到 CSV

  def _setup_routes(self):
    """注册所有路由（在 __init__ 中调用，仅执行一次）"""
    app = self._app

    # ── 图书列表首页（支持搜索 + 分页） ──
    @app.get('/', response_class=HTMLResponse)
    def root(q: str = '', page: int = Query(1, ge=1)):
      """GET / — 图书列表首页"""
      return self._list_page(q, page)

    # ── 添加图书页面 ──
    @app.get('/add', response_class=HTMLResponse)
    def add_page():
      """GET /add — 添加图书表单页面（带豆瓣 ISBN 自动获取功能）"""
      return self._form_page('添加图书', '/add', show_fetch=True)

    # ── 豆瓣 ISBN 查询 API（供前端 fetchIsbn() JS 调用） ──
    @app.get('/api/fetch-isbn/{isbn}')
    def fetch_isbn(isbn: str):
      """GET /api/fetch-isbn/{isbn} — 通过 ISBN 查询豆瓣并返回 JSON

        这是前端自动填表功能的端点，由 form 页面的 JavaScript 调用。
        返回的数据直接映射到表单字段的 id。
      """
      from utils import clean_isbn
      isbn = clean_isbn(isbn)
      if not isbn:
        raise HTTPException(400, 'ISBN 无效')
      book = DoubanService().get_book_by_isbn(isbn)
      if not book:
        raise HTTPException(404, '未找到')
      return {
        'title': book.title, 'author': book.author,
        'publisher': book.publisher, 'price': book.price,
        'rating': book.rating, 'raters': book.raters,
        'status': '默认',
      }

    # ── 添加图书表单提交 ──
    @app.post('/add', response_class=HTMLResponse)
    def add_submit(isbn: str = Form(''), title: str = Form(''), author: str = Form(''), publisher: str = Form(''),
                   price: str = Form(''), rating: str = Form(''), raters: str = Form(''),
                    status: str = Form('默认'), shelf: str = Form(''),
                    start_date: str = Form(''), end_date: str = Form('')):
      """POST /add — 提交添加图书表单

        将表单字段按 DataFrame 列顺序组装为新行，追加到数据中。
        如果 DataFrame 有超过 11 个列（额外自定义列），剩余列补空值。
      """
      with self._lock:
        cols = self._data.columns.tolist()
        vals = dict(zip(cols, [isbn, title, author, publisher, price, rating,
                               raters, status, shelf, start_date, end_date]))
        # 如果 DataFrame 列数多于表单字段数（如用户手动添加过自定义列），补充空值
        if any(k not in cols for k in vals):
          cols_extra = cols[11:]
          for k in cols_extra:
            vals[k] = ''
        self._data = pd.concat([self._data, pd.DataFrame([vals])], ignore_index=True)
        DataManager.save_csv(self._file_path, self._data)
      return self._list_page('', 1)

    # ── 编辑图书页面 ──
    @app.get('/edit/{isbn}', response_class=HTMLResponse)
    def edit_page(isbn: str):
      """GET /edit/{isbn} — 编辑图书表单页面"""
      with self._lock:
        if self._data is None:
          return html_page('错误', '<div class="msg msg-err">数据未加载</div>')
        mask = self._data.iloc[:, 0].astype(str) == isbn
        if not mask.any():
          return html_page('未找到', '<div class="msg msg-err">图书不存在</div>')
        book = self._data[mask].iloc[0].fillna('').to_dict()
      return self._form_page(f'编辑 - {book.get("书名","")}', f'/edit/{isbn}', book, show_fetch=True)

    # ── 编辑图书表单提交 ──
    @app.post('/edit/{isbn}', response_class=HTMLResponse)
    def edit_submit(isbn: str, title: str = Form(''), author: str = Form(''), publisher: str = Form(''),
                    price: str = Form(''), rating: str = Form(''), raters: str = Form(''),
                     status: str = Form('默认'), shelf: str = Form(''),
                     start_date: str = Form(''), end_date: str = Form('')):
      """POST /edit/{isbn} — 提交编辑图书表单

        根据表单字段更新 DataFrame 中对应行的值，
        不存在该 ISBN 时返回错误页，不更改数据。
      """
      with self._lock:
        mask = self._data.iloc[:, 0].astype(str) == isbn
        if not mask.any():
          return html_page('错误', '<div class="msg msg-err">图书不存在</div>')
        updates = {'书名': title, '作者': author, '出版': publisher, '价格': price,
                   '评分': rating, '人数': raters, '状态': status, '书柜': shelf,
                   '购书日期': start_date, '已读日期': end_date}
        for k, v in updates.items():
          if k in self._data.columns:
            self._data.loc[mask, k] = v
        DataManager.save_csv(self._file_path, self._data)
      return self._detail_page(isbn)

    # ── 删除图书 ──
    @app.get('/delete/{isbn}', response_class=HTMLResponse)
    def delete_book(isbn: str):
      """GET /delete/{isbn} — 删除指定 ISBN 的图书

        注意：这里是 GET 请求（通过链接点击触发），
        生产环境应考虑改用 POST/DELETE + CSRF 保护。
      """
      with self._lock:
        mask = self._data.iloc[:, 0].astype(str) == isbn
        if not mask.any():
          return html_page('错误', '<div class="msg msg-err">图书不存在</div>')
        self._data.drop(self._data[mask].index, inplace=True)
        DataManager.save_csv(self._file_path, self._data)
      return self._list_page('', 1)

    # ── 图书详情页 ──
    @app.get('/book/{isbn}', response_class=HTMLResponse)
    def book_detail(isbn: str):
      """GET /book/{isbn} — 图书详情页"""
      return self._detail_page(isbn)

    # ── 统计页面 ──
    @app.get('/stats', response_class=HTMLResponse)
    def stats():
      """GET /stats — 统计图表页面"""
      return self._stats_page()

    # ── 导入页面 ──
    @app.get('/import', response_class=HTMLResponse)
    def import_page():
      """GET /import — CSV 导入页面"""
      return self._import_page()

    # ── CSV 上传导入 ──
    @app.post('/import', response_class=HTMLResponse)
    async def import_submit(file: UploadFile = File(...)):
      """POST /import — 上传 CSV 文件并导入

        处理流程：
          1. 将上传的文件保存到临时文件
          2. 用 DataManager.load_csv 加载（自动完成列名映射和空值清洗）
          3. 删除临时文件
          4. 在锁保护下，去重后追加到现有数据（以第一列 ISBN 为唯一标识）
          5. 保存到 CSV 并返回导入结果

        注意：此路由使用 async 是因为 UploadFile.read() 是异步方法。
      """
      try:
        content = await file.read()
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        tmp.write(content)
        tmp.close()
        new_df = DataManager.load_csv(tmp.name)
        os.unlink(tmp.name)
        with self._lock:
          existing = set(self._data.iloc[:, 0].astype(str).tolist()) if self._data is not None else set()
          new_df = new_df[~new_df.iloc[:, 0].astype(str).isin(existing)]
          added = len(new_df)
          self._data = pd.concat([self._data, new_df], ignore_index=True)
          DataManager.save_csv(self._file_path, self._data)
        return self._import_page(f'导入成功，新增 {added} 条记录（跳过 {len(existing & set(new_df.iloc[:, 0].astype(str).tolist()))} 条重复）')
      except Exception as e:
        return self._import_page(f'导入失败：{e}', True)

    # ── CSV 导出下载 ──
    @app.get('/export')
    def export_csv():
      """GET /export — 导出当前数据为 CSV 文件下载

        使用 StreamingResponse 以流式方式返回 CSV 内容，
        浏览器会将其作为附件下载（Content-Disposition: attachment）。
        编码为 utf-8-sig（UTF-8 BOM），确保 Excel 正确识别中文。
      """
      with self._lock:
        if self._data is None:
          raise HTTPException(503, '数据未加载')
        csv_data = self._data.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
      return StreamingResponse(io.BytesIO(csv_data), media_type='text/csv',
                                headers={'Content-Disposition': 'attachment; filename=books.csv'})

    # ── 批量刷新页面 ──
    @app.get('/refresh', response_class=HTMLResponse)
    def refresh_page():
      """GET /refresh — 豆瓣批量刷新页面"""
      return self._refresh_page()

    # ── 批量刷新请求处理 ──
    @app.post('/refresh', response_class=HTMLResponse)
    def refresh_submit():
      """POST /refresh — 执行豆瓣批量刷新

        遍历所有图书的 ISBN，逐本调用豆瓣 API 获取最新信息并更新数据。
        每本书之间间隔 Config.API_REQUEST_DELAY 秒（由 DoubanService 内部控制）。
        更新时逐列写入，确保列顺序和数量正确。

        注意：这是一个耗时操作（取决于图书数量），当前为同步执行会阻塞请求线程。
        数据量大的话应考虑改为异步后台任务。
      """
      with self._lock:
        isbns = self._data.iloc[:, 0].astype(str).tolist()
      api = DoubanService()
      updated = 0
      for isbn in isbns:
        book = api.get_book_by_isbn(isbn)
        if book:
          row = book.to_row()
          with self._lock:
            mask = self._data.iloc[:, 0].astype(str) == isbn
            if mask.any():
              for i, col in enumerate(self._data.columns):
                if i < len(row):
                  self._data.loc[mask, col] = row[i]
          updated += 1
      with self._lock:
        DataManager.save_csv(self._file_path, self._data)
      return self._refresh_page(f'刷新完成，共更新 {updated}/{len(isbns)} 条记录')

    # ── JSON API 路由 ──────────────────────────
    # 以下路由以 /api/ 为前缀，返回 JSON 而非 HTML，
    # 供前端 JavaScript 或第三方客户端调用。
    # 每个端点对应一个基本的 CRUD 操作。

    @app.get('/api/books')
    def list_books_api(q: str = '', page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
      """GET /api/books — 获取图书列表（JSON）

        参数：
          q:    搜索关键词（可选）
          page: 页码（从 1 开始）
          size: 每页条数（1～100）

        返回：
          { total, page, size, items }
      """
      with self._lock:
        df = self._data.copy() if self._data is not None else pd.DataFrame()
      if q:
        mask = df.apply(lambda r: r.astype(str).str.contains(q, na=False).any(), axis=1)
        df = df[mask]
      total = len(df)
      start = (page - 1) * size
      items = df.iloc[start:start + size].fillna('').to_dict(orient='records')
      return {'total': total, 'page': page, 'size': size, 'items': items}

    @app.get('/api/books/{isbn}')
    def get_book_api(isbn: str):
      """GET /api/books/{isbn} — 获取单本图书详情（JSON）"""
      with self._lock:
        df = self._data
      if df is None:
        raise HTTPException(503, '数据未加载')
      mask = df.iloc[:, 0].astype(str) == isbn
      if not mask.any():
        raise HTTPException(404, '图书不存在')
      return df[mask].iloc[0].fillna('').to_dict()

    @app.post('/api/books')
    def create_book_api(book: dict):
      """POST /api/books — 创建新图书（JSON）

        参数：一个包含列名到值的字典
        返回：{ status: 'ok' }
      """
      with self._lock:
        cols = self._data.columns.tolist()
        new_row = {c: book.get(c, '') for c in cols}
        self._data = pd.concat([self._data, pd.DataFrame([new_row])], ignore_index=True)
        DataManager.save_csv(self._file_path, self._data)
      return {'status': 'ok'}

    @app.put('/api/books/{isbn}')
    def update_book_api(isbn: str, book: dict):
      """PUT /api/books/{isbn} — 更新指定图书（JSON）

        参数：一个包含要更新字段的字典
        返回：{ status: 'ok' }
      """
      with self._lock:
        mask = self._data.iloc[:, 0].astype(str) == isbn
        if not mask.any():
          raise HTTPException(404, '图书不存在')
        for k, v in book.items():
          if k in self._data.columns:
            self._data.loc[mask, k] = v
        DataManager.save_csv(self._file_path, self._data)
      return {'status': 'ok'}

    @app.delete('/api/books/{isbn}')
    def delete_book_api(isbn: str):
      """DELETE /api/books/{isbn} — 删除指定图书（JSON）"""
      with self._lock:
        mask = self._data.iloc[:, 0].astype(str) == isbn
        if not mask.any():
          raise HTTPException(404, '图书不存在')
        self._data.drop(self._data[mask].index, inplace=True)
        DataManager.save_csv(self._file_path, self._data)
      return {'status': 'ok'}

  def load_data(self):
    """从 CSV 文件加载数据到内存

    在锁保护下调用 DataManager.load_csv，完成后 self._data 可供所有路由使用。
    通常在 start() 启动时调用，也可用于手动重新加载。
    """
    with self._lock:
      self._data = DataManager.load_csv(self._file_path)

  def start(self):
    """启动 Web 服务器

    流程：
      1. load_data() — 加载 CSV 数据到内存
      2. 创建新的事件循环（避免与已有循环冲突）
      3. 配置 uvicorn（监听 127.0.0.1，指定端口，仅输出 warning 及以上日志）
      4. 启动服务器（阻塞，直到服务器停止）

    注意：此方法会阻塞当前线程。应在独立线程中调用（参见主入口）。
    """
    self.load_data()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    config = uvicorn.Config(self._app, host='127.0.0.1', port=self._port, log_level='warning')
    self._server = uvicorn.Server(config)
    loop.run_until_complete(self._server.serve())

  def stop(self):
    """优雅关闭服务器

    设置 should_exit = True，uvicorn 会在当前请求处理完毕后退出事件循环。
    """
    if self._server:
      self._server.should_exit = True
