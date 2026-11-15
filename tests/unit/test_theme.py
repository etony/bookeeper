"""
主题与配置的一致性：

强调色 #e8922a 原先在 ui/theme.py 的 QSS 里硬编码 9 次、在
web/templates/base.html 里硬编码 1 次，改一处漏一处。
现在唯一来源是 Config.ACCENT，QSS 用 $ACCENT 占位符、Web 用 Jinja 变量。
"""
import os
import re

import pytest


class TestAccentSingleSource:
  def test_config_is_the_source(self):
    from config import Config
    from ui.theme import ACCENT
    assert ACCENT == Config.ACCENT

  def test_qss_has_no_hardcoded_accent(self):
    from ui.theme import ACCENT, DARK_QSS, LIGHT_QSS
    assert '$ACCENT' not in DARK_QSS
    assert '$ACCENT' not in LIGHT_QSS
    assert ACCENT in DARK_QSS
    assert ACCENT in LIGHT_QSS
    # 源码里不得再出现色值字面量（唯一来源是 Config.ACCENT）
    from pathlib import Path
    src = (Path(__file__).parents[2] / 'ui' / 'theme.py').read_text(encoding='utf-8')
    assert ACCENT not in src

  def test_web_template_uses_accent_variable(self):
    from pathlib import Path
    html = (Path(__file__).parents[2] / 'web' / 'templates' / 'base.html'
            ).read_text(encoding='utf-8')
    assert '--accent:{{ accent }}' in html, 'Web CSS 必须使用 Jinja 注入的 accent'
    assert not re.search(r'--accent:#[0-9a-fA-F]{6}', html)


class TestWebRendersAccent:
  def test_rendered_page_contains_accent(self, client):
    from config import Config
    resp = client.get('/')
    assert resp.status_code == 200
    assert f'--accent:{Config.ACCENT}' in resp.text
