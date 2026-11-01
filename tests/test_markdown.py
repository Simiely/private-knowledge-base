"""M2：markdown 解析测试（frontmatter / 正文 / 标题 / wikilink）。"""

from __future__ import annotations

from app.core.markdown import (
    extract_headings,
    extract_wikilinks,
    parse,
    parse_frontmatter,
    strip_comment,
)


def test_frontmatter_scalar_and_list() -> None:
    text = """---
title: 检索方案
tags:
  - search
  - obsidian
aliases:
  - 搜索方案
created: 2026-07-31
---
正文内容
"""
    fm, body = parse_frontmatter(text)
    assert fm["title"] == "检索方案"
    assert fm["tags"] == ["search", "obsidian"]
    assert fm["aliases"] == ["搜索方案"]
    assert body == "正文内容"


def test_frontmatter_tags_comma_form() -> None:
    fm, body = parse_frontmatter("---\ntags: a, b, c\n---\n# 标题\n")
    assert fm["tags"] == "a, b, c"  # 逗号形式按原始标量保存，tags 归一在 parse() 中


def test_no_frontmatter() -> None:
    fm, body = parse_frontmatter("# 普通文档\n内容")
    assert fm == {}
    assert body == "# 普通文档\n内容"


def test_unclosed_frontmatter_treated_as_body() -> None:
    text = "---\ntitle: 未闭合\n没有结束符"
    fm, body = parse_frontmatter(text)
    assert fm == {}
    assert body == text


def test_parse_full_doc_title_from_frontmatter() -> None:
    doc = parse("---\ntitle: 自定义标题\ntags: [a, b]\n---\n正文", path="文件.md")
    assert doc.title == "自定义标题"
    assert doc.tags == ["a", "b"]
    assert doc.body == "正文"


def test_parse_title_fallback_to_filename() -> None:
    doc = parse("纯文本", path="Projects/我的笔记.md")
    assert doc.title == "我的笔记"


def test_parse_boolean_and_int() -> None:
    fm, _ = parse_frontmatter("---\ndone: true\ncount: 42\n---\n")
    assert fm["done"] is True
    assert fm["count"] == 42


def test_headings_extraction() -> None:
    body = "# 一级\n## 二级\n普通行\n### 三级\n"
    assert extract_headings(body) == [(1, "一级"), (2, "二级"), (3, "三级")]


def test_wikilinks_extraction() -> None:
    body = "见 [[Docker 部署]] 与 [[Obsidian|别名]]，还有 [[笔记#标题]]"
    assert extract_wikilinks(body) == ["Docker 部署", "Obsidian", "笔记"]


def test_wikilinks_skip_http_and_embed() -> None:
    body = "![[图片.png]] 和 https://example.com [[有效链接]]"
    assert extract_wikilinks(body) == ["有效链接"]


def test_strip_comment() -> None:
    text = "可见内容 %%这%% 是注释\n%%\n多行注释\n%%\n后文"
    assert strip_comment(text) == "可见内容  是注释\n\n后文"
