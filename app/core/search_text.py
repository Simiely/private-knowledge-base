"""检索文本工具：稳定文档 ID、拼音变体、同义词扩展。

只做纯文本处理，不依赖 Web 框架，供索引与检索层共用。
"""

from __future__ import annotations

import hashlib

from pypinyin import lazy_pinyin

# 单用户知识库的轻量同义词；后续可改为 data/synonyms.json 外置。
SYNONYMS: dict[str, list[str]] = {
    "部署": ["搭建", "安装", "配置"],
    "搭建": ["部署", "安装"],
    "安装": ["部署", "搭建"],
    "配置": ["部署", "设置"],
    "设置": ["配置"],
    "笔记": ["文档", "知识"],
    "文档": ["笔记"],
    "搜索": ["检索", "查找"],
    "检索": ["搜索", "查找"],
    "查找": ["搜索", "检索"],
    "模型": ["大模型", "LLM"],
    "大模型": ["模型", "LLM"],
    "图片": ["图像", "照片"],
    "图像": ["图片"],
}


def doc_id_for_path(path: str) -> str:
    """由相对路径生成稳定短 ID；重命名会变，需由索引层维护映射。"""
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]


def pinyin_variants(text: str) -> list[str]:
    """返回拼音检索变体：分词空格形式 + 连写形式。

    例：「部署」→ ["bu shu", "bushu"]，让 `bushu` 和 `bu shu` 都能命中。
    """
    syllables = [s for s in lazy_pinyin(text, errors="default") if s and s.strip()]
    if not syllables:
        return []
    joined = " ".join(syllables)
    compact = "".join(syllables)
    variants = [joined]
    if compact != joined:
        variants.append(compact)
    return variants


def expand_synonyms(word: str) -> list[str]:
    """返回同义词扩展（不含原词）。"""
    return SYNONYMS.get(word, [])


def pinyin_index_text(*fields: str) -> str:
    """把标题/别名/标签转成拼音索引文本（空格连接）。"""
    parts: list[str] = []
    for field in fields:
        if field:
            parts.extend(pinyin_variants(field))
    return " ".join(parts)
