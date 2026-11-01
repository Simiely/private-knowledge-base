"""Markdown 解析：frontmatter / 正文 / 标题结构 / wikilink。

设计：渲染归前端（remark + Quartz 插件），本模块只做"结构化提取"供索引与元数据使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
WIKILINK_RE = re.compile(r"(?<!\!)\[\[([^\]|#]+?)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")


@dataclass
class MarkdownDoc:
    """从单个 md 文件提取的结构化信息。"""

    path: str
    title: str  # frontmatter title 或文件名
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    headings: list[tuple[int, str]] = field(default_factory=list)  # (level, text)
    wikilinks: list[str] = field(default_factory=list)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """识别文档开头的 `---` frontmatter，返回 (frontmatter, 正文)。

    未识别或格式不完整时返回 ({}, 原文本)。结束分隔符缺失时整体视为正文。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    fm_lines: list[str] = []
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :])
            return _parse_yaml(fm_lines), body
        fm_lines.append(line)
        i += 1
    return {}, text  # 没有结束分隔符，视为普通文档


def _parse_yaml(lines: list[str]) -> dict[str, Any]:
    """轻量 YAML 子集解析：标量 / 列表 / 引号。不支持嵌套（Obsidian 常用 frontmatter 足够）。"""
    fm: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    def flush() -> None:
        nonlocal current_key, current_list
        if current_key is not None:
            fm[current_key] = current_list if current_list is not None else ""
            current_key, current_list = None, None

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current_key is None:
                continue
            current_list = current_list or []
            current_list.append(_unquote(line[2:].strip()))
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            flush()
            if value == "":
                current_key = key
                current_list = None
            elif value.startswith("[") and value.endswith("]"):
                # 内联列表 [a, b]
                items = [i.strip() for i in value[1:-1].split(",") if i.strip()]
                fm[key] = [_coerce(i) for i in items]
            else:
                fm[key] = _coerce(value)
    flush()
    return fm


def _coerce(value: str) -> Any:
    value = _unquote(value)
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse(text: str, path: str = "") -> MarkdownDoc:
    """完整解析一个 md 文件文本。"""
    fm, body = parse_frontmatter(text)
    tags: list[str] = []
    if isinstance(fm.get("tags"), list):
        tags = [str(t) for t in fm["tags"]]
    elif isinstance(fm.get("tags"), str) and fm["tags"]:
        tags = [t.strip() for t in fm["tags"].split(",") if t.strip()]
    aliases: list[str] = []
    if isinstance(fm.get("aliases"), list):
        aliases = [str(a) for a in fm["aliases"]]
    title = str(fm.get("title") or "")
    if not title:
        title = _title_from_path(path)
    return MarkdownDoc(
        path=path,
        title=title,
        frontmatter=fm,
        body=body,
        tags=tags,
        aliases=aliases,
        headings=extract_headings(body),
        wikilinks=extract_wikilinks(body),
    )


def _title_from_path(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if name.lower().endswith(".md"):
        name = name[:-3]
    return name


def extract_headings(body: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def extract_wikilinks(body: str) -> list[str]:
    targets: list[str] = []
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        if target and not target.startswith(("http://", "https://", "!")):
            targets.append(target)
    return targets


def strip_comment(text: str) -> str:
    """去掉 Obsidian 注释块 %%...%%（供索引正文使用）。"""
    return re.sub(r"%%[\s\S]*?%%", "", text)
