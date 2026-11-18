---
id: "docs.pitfalls.jieba-hyphen-token"
title: "jieba 把连字符拆成标点，混进 FTS5 MATCH 会变成 NOT"
summary: "空白分词把 docker-compose 拆出 -，裸拼进 MATCH 会被 FTS5 当成 NOT，查询语义反转。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/search_text.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture"]
severity: "high"
symptom: "jieba.lcut(\"docker-compose\") 返回 ['docker','-','compose']；把 token 直接拼进 MATCH 后，\"docker -compose\" 变成「有 docker 且没有 compose」，本该命中的笔记搜不到。"
cause: "FTS5 把 - 当作二元运算符 NOT 的前缀；分词器输出的纯标点 token 没有语义，却被原样拼进查询串。"
detect: "对含连字符或斜杠的查询打印 tokenize_query() 的结果；出现单字符标点 token 即命中。"
avoid: "查询一律走 tokenize_query()：_meaningful() 丢弃无字母、数字、中文的 token；含特殊字符的有意义词用引号包裹。"
recover: "已经拼坏的查询只会少结果、不会坏数据；改回走 tokenize_query() 重搜即可，必要时用原文短语加引号验证。"
---

# jieba 把连字符拆成标点，混进 FTS5 MATCH 会变成 NOT

## 影响

任何拼 FTS5 查询的路径都必须走 tokenize_query()，禁止裸拼用户输入。
