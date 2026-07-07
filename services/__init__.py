# -*- coding: utf-8 -*-
"""Bookeeper - 服务层包

提供应用的核心业务服务：
  - douban_api.py：豆瓣 API 封装
  - data_manager.py：CSV 数据文件管理
"""

from .douban_api import DoubanService
from .data_manager import DataManager

__all__ = ['DoubanService', 'DataManager']
