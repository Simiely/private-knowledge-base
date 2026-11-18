---
id: "docs.pitfalls.wikilink-embed"
title: "wikilink 正则会误吃 ![[嵌入]]"
summary: "嵌入语法 ![[图片.png]] 被当成普通 wikilink，解析出的 target 丢了感叹号语义。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/markdown.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.feature-overview"]
severity: "medium"
symptom: "![[图片.png]] 被识别为链接 target=\"图片.png\"，嵌入的图片不显示，反链里多出一条不存在的引用。"
cause: "正则只匹配 [[...]]，没有排除前面的 !；embed 与 link 是两种语义。"
detect: "用一条含 ![[x.png]] 和 [[y]] 的笔记跑解析，打印提取到的链接列表，看是否多出图片项。"
avoid: "正则加负向断言 (?<!\\!)\\[\\[；解析 Obsidian 方言时显式区分 link / embed / block reference 三种形态。"
recover: "已索引的错误引用重建索引即可消除；源文件未被改写。"
---

# wikilink 正则会误吃 ![[嵌入]]

## 影响

解析方言必须区分形态，否则渲染和反链同时错。
