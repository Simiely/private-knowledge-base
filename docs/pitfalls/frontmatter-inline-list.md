---
id: "docs.pitfalls.frontmatter-inline-list"
title: "frontmatter 内联列表 [a, b] 被当成标量"
summary: "解析器只认块级列表，tags: [a, b] 会被存成一整个字符串。"
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
symptom: "Obsidian 里写的 tags: [docker, obsidian] 读出来是 \"docker, obsidian\" 一个值，按 tag 筛选失效。"
cause: "_parse_yaml 只处理 \"- item\" 形态；以 [ 开头、] 结尾的值没有走逗号切分。"
detect: "造一条内联列表 frontmatter 的笔记，看 API 返回的字段类型；仍是字符串即命中。"
avoid: "值为 [ 开头且 ] 结尾时按逗号切分转列表；块级与内联两种形态都要有测试。"
recover: "已写入的标量需要重新解析源文件并回填索引，不改源文件。"
---

# frontmatter 内联列表 [a, b] 被当成标量

## 影响

Obsidian 用户两种写法都会出现，解析器必须兼容。
