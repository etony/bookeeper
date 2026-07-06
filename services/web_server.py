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

/* 统计 */
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

BASE = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css}</style></head><body><h1>📚 Bookeeper</h1>{nav}<div id="main">{content}</div></body></html>'


def html_page(title: str, content: str) -> str:
  return BASE.format(title=title, css=CSS, nav=NAV, content=content)


def esc(val) -> str:
  s = str(val) if val is not None else ''
  return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


class BookWebServer:
  def __init__(self, file_path: str, port: int = 8899):
    self._file_path = file_path
    self._port = port
    self._app = FastAPI(title='Bookeeper API')
    self._data: Optional[pd.DataFrame] = None
    self._lock = threading.Lock()
    self._server: Optional[uvicorn.Server] = None
    self._app.add_middleware(
      CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'],
    )
    self._setup_routes()

  # ── 页面渲染 ──────────────────────────────────

  def _list_page(self, q: str, page: int) -> str:
    with self._lock:
      df = self._data.copy() if self._data is not None else pd.DataFrame()
    if q:
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
for(const[k,v]of Object.entries(m)){const el=document.getElementById(v);if(el&&d[k]!==undefined)el.value=d[k];}
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
      ('状态', 'status', '', 'select', b.get('状态', '未读'),
       '<option>未读</option><option>在读</option><option>已读</option>'),
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

  def _setup_routes(self):
    app = self._app

    @app.get('/', response_class=HTMLResponse)
    def root(q: str = '', page: int = Query(1, ge=1)):
      return self._list_page(q, page)

    @app.get('/add', response_class=HTMLResponse)
    def add_page():
      return self._form_page('添加图书', '/add', show_fetch=True)

    @app.get('/api/fetch-isbn/{isbn}')
    def fetch_isbn(isbn: str):
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
        'status': '未读',
      }

    @app.post('/add', response_class=HTMLResponse)
    def add_submit(isbn: str = Form(''), title: str = Form(''), author: str = Form(''), publisher: str = Form(''),
                   price: str = Form(''), rating: str = Form(''), raters: str = Form(''),
                   status: str = Form('未读'), shelf: str = Form(''),
                   start_date: str = Form(''), end_date: str = Form('')):
      with self._lock:
        cols = self._data.columns.tolist()
        vals = dict(zip(cols, [isbn, title, author, publisher, price, rating,
                               raters, status, shelf, start_date, end_date]))
        if any(k not in cols for k in vals):
          cols_extra = cols[11:]
          for k in cols_extra:
            vals[k] = ''
        self._data = pd.concat([self._data, pd.DataFrame([vals])], ignore_index=True)
        DataManager.save_csv(self._file_path, self._data)
      return self._list_page('', 1)

    @app.get('/edit/{isbn}', response_class=HTMLResponse)
    def edit_page(isbn: str):
      with self._lock:
        if self._data is None:
          return html_page('错误', '<div class="msg msg-err">数据未加载</div>')
        mask = self._data.iloc[:, 0].astype(str) == isbn
        if not mask.any():
          return html_page('未找到', '<div class="msg msg-err">图书不存在</div>')
        book = self._data[mask].iloc[0].fillna('').to_dict()
      return self._form_page(f'编辑 - {book.get("书名","")}', f'/edit/{isbn}', book)

    @app.post('/edit/{isbn}', response_class=HTMLResponse)
    def edit_submit(isbn: str, title: str = Form(''), author: str = Form(''), publisher: str = Form(''),
                    price: str = Form(''), rating: str = Form(''), raters: str = Form(''),
                    status: str = Form('未读'), shelf: str = Form(''),
                    start_date: str = Form(''), end_date: str = Form('')):
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

    @app.get('/delete/{isbn}', response_class=HTMLResponse)
    def delete_book(isbn: str):
      with self._lock:
        mask = self._data.iloc[:, 0].astype(str) == isbn
        if not mask.any():
          return html_page('错误', '<div class="msg msg-err">图书不存在</div>')
        self._data.drop(self._data[mask].index, inplace=True)
        DataManager.save_csv(self._file_path, self._data)
      return self._list_page('', 1)

    @app.get('/book/{isbn}', response_class=HTMLResponse)
    def book_detail(isbn: str):
      return self._detail_page(isbn)

    @app.get('/stats', response_class=HTMLResponse)
    def stats():
      return self._stats_page()

    @app.get('/import', response_class=HTMLResponse)
    def import_page():
      return self._import_page()

    @app.post('/import', response_class=HTMLResponse)
    async def import_submit(file: UploadFile = File(...)):
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

    @app.get('/export')
    def export_csv():
      with self._lock:
        if self._data is None:
          raise HTTPException(503, '数据未加载')
        csv_data = self._data.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
      return StreamingResponse(io.BytesIO(csv_data), media_type='text/csv',
                                headers={'Content-Disposition': 'attachment; filename=books.csv'})

    @app.get('/refresh', response_class=HTMLResponse)
    def refresh_page():
      return self._refresh_page()

    @app.post('/refresh', response_class=HTMLResponse)
    def refresh_submit():
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

    # ── JSON API ──
    @app.get('/api/books')
    def list_books_api(q: str = '', page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
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
      with self._lock:
        cols = self._data.columns.tolist()
        new_row = {c: book.get(c, '') for c in cols}
        self._data = pd.concat([self._data, pd.DataFrame([new_row])], ignore_index=True)
        DataManager.save_csv(self._file_path, self._data)
      return {'status': 'ok'}

    @app.put('/api/books/{isbn}')
    def update_book_api(isbn: str, book: dict):
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
      with self._lock:
        mask = self._data.iloc[:, 0].astype(str) == isbn
        if not mask.any():
          raise HTTPException(404, '图书不存在')
        self._data.drop(self._data[mask].index, inplace=True)
        DataManager.save_csv(self._file_path, self._data)
      return {'status': 'ok'}

  def load_data(self):
    with self._lock:
      self._data = DataManager.load_csv(self._file_path)

  def start(self):
    self.load_data()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    config = uvicorn.Config(self._app, host='127.0.0.1', port=self._port, log_level='warning')
    self._server = uvicorn.Server(config)
    loop.run_until_complete(self._server.serve())

  def stop(self):
    if self._server:
      self._server.should_exit = True
