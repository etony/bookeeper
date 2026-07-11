import asyncio

import uvicorn
import requests
from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from config import Config
from services import get_repo

# 内联 CSS（暗色风格，无外部依赖）
CSS = '''
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#1c1c1f;--surface:#242428;--surface2:#2c2c31;--border:#323238;--border-hover:#404048;--text:#e0e0e4;--text2:#9a9aa0;--text3:#6a6a70;--accent:#e8922a;--accent-hover:#f0a840;--accent-dim:#8a6020;--danger:#e05050;--danger-bg:#3a1818;--radius:8px;--radius-sm:4px}
body{font-family:-apple-system,"Microsoft YaHei","Noto Sans SC",sans-serif;background:var(--bg);color:var(--text);padding:24px;font-size:14px;line-height:1.6}
a{color:var(--accent);text-decoration:none}
a:hover{color:var(--accent-hover);text-decoration:underline}
h1{font-size:26px;font-weight:700;margin-bottom:20px;background:linear-gradient(135deg,var(--accent),#f0b060);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.nav{display:flex;gap:6px;margin-bottom:24px;flex-wrap:wrap;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)}
.nav a{padding:7px 16px;border-radius:var(--radius-sm);color:var(--text2);font-size:13px;font-weight:500}
.nav a:hover{background:var(--surface2);color:var(--accent);text-decoration:none}
.toolbar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:center;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)}
.toolbar input,.toolbar select{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:8px 12px;color:var(--text);font-size:14px;outline:none}
.toolbar input:focus,.toolbar select:focus{border-color:var(--accent);box-shadow:0 0 0 2px rgba(232,146,42,.15)}
.toolbar button,.btn{padding:7px 18px;border-radius:var(--radius-sm);font-size:14px;font-weight:500;cursor:pointer;border:none}
.btn-primary{background:var(--accent);color:#1c1c1f}
.btn-primary:hover{background:var(--accent-hover)}
.btn-danger{background:var(--danger-bg);border:1px solid var(--danger);color:var(--danger)}
table{width:100%;border-collapse:separate;border-spacing:0;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
th{background:var(--surface2);padding:10px 12px;text-align:left;font-weight:600;font-size:12px;color:var(--text2);border-bottom:1px solid var(--border)}
td{padding:9px 12px;border-bottom:1px solid var(--border);font-size:13px}
tr:hover td{background:rgba(232,146,42,.06)}
.pagination{margin-top:16px;display:flex;gap:6px;align-items:center;justify-content:center}
.pagination a,.pagination span{padding:6px 14px;border-radius:var(--radius-sm);font-size:13px;font-weight:500}
.pagination a{background:var(--surface);border:1px solid var(--border);color:var(--text2)}
.pagination a:hover{background:var(--surface2);border-color:var(--accent);color:var(--accent);text-decoration:none}
.pagination .active{background:var(--accent);border:1px solid var(--accent);color:#1c1c1f}
.summary{color:var(--text2);font-size:13px;margin-bottom:12px;text-align:center}
.msg{padding:12px 16px;border-radius:var(--radius-sm);margin-bottom:16px;font-size:13px}
.msg-info{background:rgba(232,146,42,.08);border:1px solid rgba(232,146,42,.25);color:var(--accent)}
.msg-err{background:var(--danger-bg);border:1px solid var(--danger);color:var(--danger)}
.chart-box{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-bottom:14px}
.chart-box h3{margin:0 0 12px;font-size:15px;color:var(--text)}
.chart-bar{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.chart-bar .label{flex:0 0 100px;font-size:12px;color:var(--text2);text-align:right}
.chart-bar .fill{background:var(--accent);color:#1c1c1f;font-size:11px;font-weight:600;padding:3px 8px;border-radius:3px;min-width:20px;text-align:right}
form{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px;max-width:500px}
form label{display:block;font-size:12px;color:var(--text2);margin-top:12px;margin-bottom:4px}
form input,form select{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:8px 12px;color:var(--text);font-size:14px;outline:none}
form input:focus,form select:focus{border-color:var(--accent)}
'''

NAV = '''
<div class="nav">
<a href="/">📚 图书列表</a>
<a href="/add">➕ 添加</a>
<a href="/stats">📊 统计</a>
</div>'''

# HTML 页面模板
BASE = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css}</style></head><body><h1>📚 Bookeeper</h1>{nav}<div id="main">{content}</div></body></html>'


def page(title: str, content: str) -> str:
  """组装完整 HTML 页面"""
  return BASE.format(title=title, css=CSS, nav=NAV, content=content)


def esc(val) -> str:
  """HTML 转义，防止 XSS"""
  s = str(val) if val is not None else ''
  return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


class BookWebServer:
  """内嵌 FastAPI Web 服务，提供完整的图书管理 Web 界面"""

  def __init__(self):
    self._repo = get_repo()
    self._app = FastAPI(title='Bookeeper API')
    self._server = None
    self._douban_tried = set()  # 避免重复查询豆瓣
    self._setup_routes()

  def _setup_routes(self):
    app = self._app

    @app.get('/', response_class=HTMLResponse)
    def root(q: str = '', page_no: int = Query(1, ge=1, alias='page')):
      """图书列表首页：分页 + 搜索"""
      books = self._repo.search(q) if q else self._repo.get_all()
      total = len(books)
      size = 20
      total_pages = max(1, (total + size - 1) // size)
      page_no = max(1, min(page_no, total_pages))
      start = (page_no - 1) * size
      items = books[start:start + size]
      rows = ''
      for b in items:
        rows += f'''<tr>
<td><a href="/book/{esc(b.isbn)}">{esc(b.isbn)}</a></td>
<td>{esc(b.title)}</td><td>{esc(b.author)}</td><td>{esc(b.publisher)}</td>
<td>{esc(b.price)}</td><td>{esc(b.rating)}</td><td>{esc(b.status)}</td>
<td>{esc(b.shelf)}</td>
<td><a href="/edit/{esc(b.isbn)}">编辑</a> <a href="/delete/{esc(b.isbn)}" onclick="return confirm('确定删除？')">删除</a></td>
</tr>'''
      pages_html = ''
      for p in range(1, total_pages + 1):
        if p == page_no:
          pages_html += f'<span class="active">{p}</span> '
        else:
          pages_html += f'<a href="/?q={esc(q)}&page={p}">{p}</a> '
      search = f'''<form class="toolbar" method="get" action="/">
<input type="text" name="q" placeholder="搜索..." value="{esc(q)}">
<button class="btn btn-primary">🔎 搜索</button></form>'''
      return page('图书列表', f'{search}<div class="summary">共 {total} 条</div>'
                  f'<table><thead><tr><th>ISBN</th><th>书名</th><th>作者</th><th>出版</th>'
                  f'<th>价格</th><th>评分</th><th>状态</th><th>书柜</th><th>操作</th>'
                  f'</tr></thead><tbody>{rows}</tbody></table>'
                  f'<div class="pagination">{pages_html}</div>')

    @app.get('/add', response_class=HTMLResponse)
    def add_page(isbn: str = '', fetch: str = ''):
      """添加图书页面：支持 ISBN 自动获取豆瓣数据"""
      vals = dict(isbn='', title='', author='', publisher='', price='', rating='0', status='默认', shelf='')
      if fetch == '1' and isbn:
        from services.douban import DoubanService
        api_book = DoubanService().get_book_by_isbn(isbn)
        if api_book:
          vals.update(isbn=api_book.isbn, title=api_book.title, author=api_book.author,
                      publisher=api_book.publisher, price=api_book.price, rating=api_book.rating,
                      shelf=api_book.shelf)
          if api_book.status:
            vals['status'] = api_book.status
      opts = ''.join(f'<option{" selected" if vals["status"]==s else ""}>{s}</option>' for s in Config.STATUSES)
      return page('添加图书', f'''
<div style="display:flex;gap:12px;align-items:center;margin-bottom:16px;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)">
  <form method="get" action="/add" style="display:flex;gap:8px;align-items:center;padding:0;border:none;background:none;margin:0">
    <label style="margin:0;white-space:nowrap">ISBN</label>
    <input type="text" name="isbn" placeholder="输入 ISBN 获取" value="{esc(isbn)}" style="width:200px">
    <input type="hidden" name="fetch" value="1">
    <button class="btn btn-primary" type="submit">🌐 获取</button>
  </form>
</div>
<form method="post" action="/add">
<label>ISBN</label><input type="text" name="isbn" required value="{esc(vals['isbn'])}">
<label>书名</label><input type="text" name="title" value="{esc(vals['title'])}">
<label>作者</label><input type="text" name="author" value="{esc(vals['author'])}">
<label>出版社</label><input type="text" name="publisher" value="{esc(vals['publisher'])}">
<label>价格</label><input type="text" name="price" value="{esc(vals['price'])}">
<label>评分</label><input type="text" name="rating" value="{esc(vals['rating'])}">
<label>状态</label><select name="status">{opts}</select>
<label>书柜</label><input type="text" name="shelf" value="{esc(vals['shelf'])}">
<div><button class="btn btn-primary" type="submit">保存</button></div>
</form>''')

    @app.post('/add')
    def add_submit(isbn: str = Form(...), title: str = '', author: str = '', publisher: str = '',
                   price: str = '', rating: str = '0', status: str = '默认', shelf: str = ''):
      """提交添加图书表单"""
      from models.book import Book
      book = Book(isbn=isbn, title=title, author=author, publisher=publisher,
                  price=price, rating=rating, status=status, shelf=shelf)
      self._repo.upsert(book)
      return RedirectResponse(url='/', status_code=302)

    @app.get('/edit/{isbn}', response_class=HTMLResponse)
    def edit_page(isbn: str, sync: str = ''):
      """编辑图书页面：支持一键从豆瓣同步"""
      book = self._repo.get_by_isbn(isbn)
      if not book:
        return page('错误', '<div class="msg msg-err">图书不存在</div>')
      if sync == '1':
        from services.douban import DoubanService
        api_book = DoubanService().get_book_by_isbn(isbn)
        if api_book:
          book.title = api_book.title
          book.author = api_book.author
          book.publisher = api_book.publisher
          book.price = api_book.price
          book.rating = api_book.rating
          book.raters = api_book.raters
          book.cover_url = api_book.cover_url
          book.pubdate = api_book.pubdate
          book.douban_url = api_book.douban_url
          book.pages = api_book.pages
          self._repo.upsert(book)
          msg = '<div class="msg msg-info">已从豆瓣同步图书信息</div>'
        else:
          msg = '<div class="msg msg-err">豆瓣未找到该 ISBN 对应的图书</div>'
      else:
        msg = ''
      opts = ''.join(f'<option{" selected" if s==book.status else ""}>{s}</option>' for s in Config.STATUSES)
      return page(f'编辑 - {book.title}', f'''
{msg}
<div style="display:flex;gap:12px;align-items:center;margin-bottom:16px;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)">
  <a href="/edit/{esc(isbn)}?sync=1" class="btn btn-primary">🌐 从豆瓣同步</a>
  <span style="color:var(--text2);font-size:13px">通过 ISBN 重新获取豆瓣数据</span>
</div>
<form method="post" action="/edit/{esc(isbn)}">
<label>ISBN</label><input type="text" name="isbn" value="{esc(book.isbn)}" readonly>
<label>书名</label><input type="text" name="title" value="{esc(book.title)}">
<label>作者</label><input type="text" name="author" value="{esc(book.author)}">
<label>出版社</label><input type="text" name="publisher" value="{esc(book.publisher)}">
<label>价格</label><input type="text" name="price" value="{esc(book.price)}">
<label>评分</label><input type="text" name="rating" value="{esc(book.rating)}">
<label>状态</label><select name="status">{opts}</select>
<label>书柜</label><input type="text" name="shelf" value="{esc(book.shelf)}">
<div><button class="btn btn-primary" type="submit">保存</button></div>
</form>''')

    @app.post('/edit/{isbn}')
    def edit_submit(isbn: str, title: str = '', author: str = '', publisher: str = '',
                    price: str = '', rating: str = '0', status: str = '默认', shelf: str = ''):
      """提交编辑图书表单"""
      book = self._repo.get_by_isbn(isbn)
      if not book:
        return RedirectResponse(url='/', status_code=302)
      book.title = title
      book.author = author
      book.publisher = publisher
      book.price = price
      book.rating = rating
      book.status = status
      book.shelf = shelf
      self._repo.upsert(book)
      return RedirectResponse(url='/', status_code=302)

    @app.get('/delete/{isbn}')
    def delete_book(isbn: str):
      """删除图书"""
      self._repo.delete(isbn)
      return RedirectResponse(url='/', status_code=302)

    @app.get('/cover/{isbn}')
    def cover_proxy(isbn: str):
      """封面代理：解决豆瓣图片防盗链问题"""
      book = self._repo.get_by_isbn(isbn)
      if not book or not book.cover_url:
        raise HTTPException(status_code=404)
      try:
        resp = requests.get(book.cover_url, headers={
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': 'https://book.douban.com/',
        }, timeout=10)
        resp.raise_for_status()
        return Response(content=resp.content, media_type=resp.headers.get('Content-Type', 'image/jpeg'))
      except requests.RequestException:
        raise HTTPException(status_code=502)

    @app.get('/book/{isbn}', response_class=HTMLResponse)
    def book_detail(isbn: str):
      """图书详情页：封面、信息、上下本导航、推荐度"""
      book = self._repo.get_by_isbn(isbn)
      if not book:
        return page('未找到', '<div class="msg msg-err">图书不存在</div>')
      from models.book import Book as BookModel
      if not book.cover_url and isbn not in self._douban_tried:
        self._douban_tried.add(isbn)
        from services.douban import DoubanService
        api_book = DoubanService().get_book_by_isbn(isbn)
        if api_book and api_book.cover_url:
          book.cover_url = api_book.cover_url
          if api_book.pubdate:
            book.pubdate = api_book.pubdate
          self._repo.upsert(book)
      all_books = self._repo.get_all()
      isbn_list = [b.isbn for b in all_books]
      idx = isbn_list.index(isbn) if isbn in isbn_list else -1
      prev_link = f'/book/{esc(isbn_list[idx-1])}' if idx > 0 else ''
      next_link = f'/book/{esc(isbn_list[idx+1])}' if 0 <= idx < len(isbn_list)-1 else ''
      nav_html = '<div style="display:flex;gap:8px;justify-content:center;margin-top:16px">'
      if prev_link:
        nav_html += f'<a href="{prev_link}" style="padding:6px 18px;border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text2);text-decoration:none">◀ 上一本</a>'
      else:
        nav_html += '<span style="padding:6px 18px;border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text3)">◀ 上一本</span>'
      if next_link:
        nav_html += f'<a href="{next_link}" style="padding:6px 18px;border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text2);text-decoration:none">下一本 ▶</a>'
      else:
        nav_html += '<span style="padding:6px 18px;border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text3)">下一本 ▶</span>'
      nav_html += '</div>'
      rec = BookModel._calc_recommend(book.rating, book.raters)
      cover_url = f'/cover/{esc(isbn)}' if book.cover_url else ''
      cover = f'<img src="{cover_url}" alt="封面" style="width:200px;height:280px;object-fit:contain;border-radius:4px;background:#2c2c31">' if cover_url else '<div style="width:200px;height:280px;border-radius:4px;background:#2c2c31;display:flex;align-items:center;justify-content:center;color:#6a6a70;font-size:13px">无封面</div>'
      fields = [
        ('ISBN', book.isbn), ('书名', book.title), ('作者', book.author),
        ('出版社', book.publisher), ('价格', book.price),
        ('评分', f'{book.rating} 分 / {book.raters} 人'),
        ('推荐', str(rec)), ('状态', book.status), ('书柜', book.shelf),
        ('出版年', book.pubdate),
        ('购书日期', book.start_date), ('已读日期', book.end_date),
      ]
      info = ''.join(f'<tr><th style="width:80px;text-transform:none;padding:6px 12px;color:#9a9aa0;font-weight:500;border-bottom:1px solid #2c2c31">{esc(k)}</th><td style="padding:6px 12px;border-bottom:1px solid #2c2c31">{esc(v)}</td></tr>' for k, v in fields if v)
      return page(f'{book.title}', f'''
<div style="display:flex;gap:24px;padding:24px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)">
  <div style="display:flex;flex-direction:column;align-items:center;gap:16px">
    {cover}
    {nav_html}
  </div>
  <div style="flex:1;min-width:0">
    <h2 style="margin-top:0;margin-bottom:16px">📖 {esc(book.title)}</h2>
    <div style="margin-bottom:16px"><a href="/edit/{esc(isbn)}">✏️ 编辑</a> | <a href="/">← 返回</a></div>
    <table style="width:100%;border-collapse:collapse">{info}</table>
  </div>
</div>''')

    @app.get('/stats', response_class=HTMLResponse)
    def stats():
      """统计页面：阅读状态 / 出版社 TOP10 / 评分分布"""
      status_counts = self._repo.status_counts()
      pubs = self._repo.publisher_top(10)
      dist = self._repo.rating_distribution()
      charts = ''
      if status_counts:
        total = sum(status_counts.values())
        bars = ''
        for k, v in status_counts.items():
          pct = v / total * 100
          bars += f'<div class="chart-bar"><span class="label">{esc(k)}</span><div class="fill" style="width:{max(2,pct*3)}%">{v} ({pct:.1f}%)</div></div>'
        charts += f'<div class="chart-box"><h3>阅读状态</h3>{bars}</div>'
      if pubs:
        mx = pubs[0][1]
        bars = ''
        for k, v in pubs:
          bars += f'<div class="chart-bar"><span class="label">{esc(k)}</span><div class="fill" style="width:{max(5,v/mx*80)}%">{v}</div></div>'
        charts += f'<div class="chart-box"><h3>出版社 TOP10</h3>{bars}</div>'
      if any(dist.values()):
        mx = max(dist.values())
        bars = ''
        for k, v in dist.items():
          bars += f'<div class="chart-bar"><span class="label">{k}</span><div class="fill" style="width:{max(5,v/mx*80)}%">{v}</div></div>'
        charts += f'<div class="chart-box"><h3>评分分布</h3>{bars}</div>'
      if not charts:
        charts = '<p style="color:#9a9aa0">暂无数据</p>'
      return page('统计', f'<h2>📊 统计面板</h2>{charts}')

  def start(self):
    """启动 uvicorn 服务（阻塞，需在独立线程中运行）"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    config = uvicorn.Config(self._app, host='127.0.0.1', port=Config.WEB_PORT, log_level='warning')
    self._server = uvicorn.Server(config)
    loop.run_until_complete(self._server.serve())

  def stop(self):
    """停止服务"""
    if self._server:
      self._server.should_exit = True
