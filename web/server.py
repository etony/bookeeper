"""
┌──────────────────────────────────────────┐
│  内嵌 Web 服务（FastAPI）                 │
│                                          │
│  提供完整的图书管理 Web 界面，             │
│  支持增删改查、豆瓣同步、统计图表。         │
│  通过主窗口 「Web 服务」按钮启动/停止。     │
└──────────────────────────────────────────┘
"""

import asyncio
import re
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from config import Config
from services import get_repo


def _valid_date(val: str) -> str:
  """校验日期格式 yyyy-MM-dd，无效则返回空串"""
  if val and re.fullmatch(r'\d{4}-\d{2}-\d{2}', val.strip()):
    return val.strip()
  return ''


class BookWebServer:
  """
  内嵌 FastAPI Web 服务。

  提供路由：
    GET  /           → 图书列表（分页 + 搜索）
    GET  /add        → 添加图书表单
    POST /add        → 提交添加
    GET  /edit/{id}  → 编辑表单（支持?sync=1从豆瓣同步）
    POST /edit/{id}  → 提交编辑
    GET  /book/{id}  → 图书详情（含封面）
    GET  /cover/{id} → 封面代理（解决豆瓣防盗链）
    GET  /stats      → 统计面板
    POST /delete/{id} → 删除图书

  全部返回纯 HTML，不依赖 JavaScript。
  """

  def __init__(self, on_started=None):
    self._repo = get_repo()
    self._app = FastAPI(title='Bookeeper API')
    self._server = None
    # uvicorn 开始监听后的回调（在服务线程中调用）
    self._on_started = on_started
    # 避免在详情页重复查询豆瓣 API（单次会话内有效）
    self._douban_tried = set()
    # 配置Jinja2模板
    templates_dir = Path(__file__).parent / 'templates'
    self._templates = Jinja2Templates(directory=str(templates_dir))
    self._setup_routes()

  def _setup_routes(self):
    """注册所有 FastAPI 路由"""
    app = self._app

    @app.get('/', response_class=HTMLResponse)
    def root(request: Request, q: str = '', page_no: int = Query(1, ge=1, alias='page')):
      """图书列表首页：分页 + 搜索"""
      books = self._repo.search(q) if q else self._repo.get_all()
      total = len(books)
      size = 20
      total_pages = max(1, (total + size - 1) // size)
      page_no = max(1, min(page_no, total_pages))
      start = (page_no - 1) * size
      items = books[start:start + size]
      
      return self._templates.TemplateResponse(request, "index.html", {
        "q": q,
        "total": total,
        "page_no": page_no,
        "total_pages": total_pages,
        "books": items,
      })

    @app.get('/cover-wall', response_class=HTMLResponse)
    def cover_wall(request: Request, q: str = '', sort: str = 'title'):
      """封面墙页面：以封面网格展示图书"""
      books = self._repo.search(q) if q else self._repo.get_all()
      # 排序
      if sort == 'rating':
        def rating_key(b):
          try: return -float(b.rating)
          except: return 0
        books = sorted(books, key=rating_key)
      elif sort == 'date':
        books = sorted(books, key=lambda b: b.start_date or '9999')
      elif sort == 'added':
        books = sorted(books, key=lambda b: b.isbn)
      else:  # title
        books = sorted(books, key=lambda b: b.title.lower())
      
      sort_options = [('title', '书名'), ('rating', '评分'), ('date', '购书日期'), ('added', '添加时间')]
      
      return self._templates.TemplateResponse(request, "cover_wall.html", {
        "q": q,
        "sort": sort,
        "sort_options": sort_options,
        "books": books,
      })

    @app.get('/add', response_class=HTMLResponse)
    def add_page(request: Request, isbn: str = '', fetch: str = ''):
      """
      添加图书页面。

      支持 ?isbn=xxx&fetch=1 参数自动获取豆瓣数据，
      填入表单各字段，用户确认后提交保存。
      """
      vals = dict(isbn='', title='', author='', publisher='', price='', rating='0', status='默认', shelf='',
                  start_date='', end_date='')
      if fetch == '1' and isbn:
        from services.douban import DoubanService
        api_book = DoubanService().get_book_by_isbn(isbn)
        if api_book:
          vals.update(isbn=api_book.isbn, title=api_book.title, author=api_book.author,
                      publisher=api_book.publisher, price=api_book.price, rating=api_book.rating,
                      shelf=api_book.shelf)
          if api_book.status:
            vals['status'] = api_book.status
      
      return self._templates.TemplateResponse(request, "add.html", {
        "isbn": isbn,
        "vals": vals,
        "statuses": Config.STATUSES,
      })

    @app.post('/add')
    def add_submit(isbn: str = Form(...), title: str = Form(''), author: str = Form(''),
                   publisher: str = Form(''), price: str = Form(''), rating: str = Form('0'),
                   status: str = Form('默认'), shelf: str = Form(''),
                   start_date: str = Form(''), end_date: str = Form('')):
      """提交添加图书表单"""
      from core.models.book import Book
      book = Book(isbn=isbn, title=title, author=author, publisher=publisher,
                  price=price, rating=rating, status=status, shelf=shelf,
                  start_date=_valid_date(start_date), end_date=_valid_date(end_date))
      self._repo.upsert(book)
      return RedirectResponse(url='/', status_code=302)

    @app.get('/edit/{isbn}', response_class=HTMLResponse)
    def edit_page(request: Request, isbn: str, sync: str = ''):
      """
      编辑图书页面。

      支持 ?sync=1 从豆瓣同步最新数据。
      同步后自动更新图书信息并保存到数据库。
      """
      book = self._repo.get_by_isbn(isbn)
      if not book:
        return self._templates.TemplateResponse(request, "error.html", {
          "message": "图书不存在",
        })

      msg = ''
      msg_type = ''
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
          msg = '已从豆瓣同步图书信息'
          msg_type = 'info'
        else:
          msg = '豆瓣未找到该 ISBN 对应的图书'
          msg_type = 'err'
      
      return self._templates.TemplateResponse(request, "edit.html", {
        "book": book,
        "msg": msg,
        "msg_type": msg_type,
        "statuses": Config.STATUSES,
      })

    @app.post('/edit/{isbn}')
    def edit_submit(isbn: str, title: str = Form(''), author: str = Form(''),
                    publisher: str = Form(''), price: str = Form(''),
                    rating: str = Form('0'), status: str = Form('默认'),
                    shelf: str = Form(''), start_date: str = Form(''),
                    end_date: str = Form('')):
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
      book.start_date = _valid_date(start_date)
      book.end_date = _valid_date(end_date)
      self._repo.upsert(book)
      return RedirectResponse(url='/', status_code=302)

    @app.post('/delete/{isbn}')
    def delete_book(isbn: str):
      """删除图书"""
      self._repo.delete(isbn)
      return RedirectResponse(url='/', status_code=302)

    @app.get('/cover/{isbn}')
    def cover_proxy(isbn: str):
      """
      封面代理。

      豆瓣图片有防盗链，直接在 HTML 中引用豆瓣 URL 会 403。
      此路由充当代理：从本地缓存读取，未命中则下载并缓存。
      """
      book = self._repo.get_by_isbn(isbn)
      if not book or not book.cover_url:
        raise HTTPException(status_code=404)
      from services.covers import get_cover
      data, media_type = get_cover(isbn, book.cover_url)
      if not data:
        raise HTTPException(status_code=502)
      return Response(content=data, media_type=media_type)

    @app.get('/book/{isbn}', response_class=HTMLResponse)
    def book_detail(request: Request, isbn: str):
      """
      图书详情页。

      展示完整图书信息、上下本导航、推荐度。
      如果数据库缺少封面 URL，尝试从豆瓣获取。
      """
      book = self._repo.get_by_isbn(isbn)
      if not book:
        return self._templates.TemplateResponse(request, "error.html", {
          "message": "图书不存在",
        })

      from core.models.book import Book as BookModel

      # 如果缺少封面且之前没试过，尝试从豆瓣补充
      if not book.cover_url and isbn not in self._douban_tried:
        self._douban_tried.add(isbn)
        from services.douban import DoubanService
        api_book = DoubanService().get_book_by_isbn(isbn)
        if api_book and api_book.cover_url:
          book.cover_url = api_book.cover_url
          if api_book.pubdate:
            book.pubdate = api_book.pubdate
          self._repo.upsert(book)

      # 获取全部 ISBN 列表，构造上下本导航
      all_books = self._repo.get_all()
      isbn_list = [b.isbn for b in all_books]
      idx = isbn_list.index(isbn) if isbn in isbn_list else -1
      prev_link = f'/book/{isbn_list[idx-1]}' if idx > 0 else ''
      next_link = f'/book/{isbn_list[idx+1]}' if 0 <= idx < len(isbn_list)-1 else ''

      rec = BookModel._calc_recommend(book.rating, book.raters)
      fields = [
        ('ISBN', book.isbn), ('书名', book.title), ('作者', book.author),
        ('出版社', book.publisher), ('价格', book.price),
        ('评分', f'{book.rating} 分 / {book.raters} 人'),
        ('推荐', str(rec)), ('状态', book.status), ('书柜', book.shelf),
        ('出版年', book.pubdate),
        ('购书日期', book.start_date), ('已读日期', book.end_date),
      ]
      
      return self._templates.TemplateResponse(request, "book_detail.html", {
        "book": book,
        "prev_link": prev_link,
        "next_link": next_link,
        "fields": fields,
      })

    @app.get('/stats', response_class=HTMLResponse)
    def stats(request: Request):
      """
      统计页面。

      用纯 CSS 柱状图展示：
        - 阅读状态分布（各状态数量 + 百分比）
        - 出版社 TOP10
        - 评分分布（5 个区间）
      """
      status_counts = self._repo.status_counts()
      pubs = self._repo.publisher_top(10)
      dist = self._repo.rating_distribution()

      status_total = max(1, sum(status_counts.values())) if status_counts else 1
      pubs_max = max(1, pubs[0][1]) if pubs else 1
      dist_max = max(dist.values()) if dist else 0
      charts_exist = bool(status_counts or pubs or any(dist.values()))

      return self._templates.TemplateResponse(request, "stats.html", {
        "status_counts": status_counts,
        "status_total": status_total,
        "pubs": pubs,
        "pubs_max": pubs_max,
        "dist": dist,
        "charts_exist": charts_exist,
      })

  def start(self):
    """
    启动 uvicorn 服务。

    这是一个阻塞调用，必须在独立线程中执行。
    使用 asyncio 事件循环支持 FastAPI 的异步特性。
    监听就绪后调用 on_started 回调，再继续 serve 直到停止。
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # log_config=None：跳过 uvicorn 自带日志配置，避免无控制台（pythonw）下
    # sys.stdout 为 None 导致 formatter 配置失败；日志统一走应用根 logger
    config = uvicorn.Config(self._app, host='127.0.0.1', port=Config.WEB_PORT,
                            log_level='warning', log_config=None)
    server = uvicorn.Server(config)
    self._server = server

    async def _serve():
      task = loop.create_task(server.serve())
      while not server.started:
        if task.done():
          task.result()
          return
        await asyncio.sleep(0.05)
      if self._on_started:
        self._on_started()
      await task

    loop.run_until_complete(_serve())

  def stop(self):
    """停止服务"""
    if self._server:
      self._server.should_exit = True
