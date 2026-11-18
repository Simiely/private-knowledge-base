---
id: "docs.pitfalls.tags-pretokenized"
title: "tags 预分词后无法还原展示"
summary: "为了检索把 tags 预分词存成空格连接，展示时按逗号切只剩一个词。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/indexer/fts5.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture"]
severity: "medium"
symptom: "库里 tags 列存 \"docker obsidian\"（空格连接），_split_tags 去空格后按逗号切得到 ['dockerobsidian']，标签展示与筛选都错。"
cause: "同一列既要检索友好（分词）又要展示友好（原词），实现只满足了检索侧。"
detect: "建一条带两个 tag 的笔记，读回的 tags 是否还是两个；出现粘连即命中。"
avoid: "tags 存原文逗号连接（docker,obsidian），靠 unicode61 分词器自然切开；中文 tag 同样能整串命中。"
recover: "存量数据按空格还原成逗号需要人工确认（\"a b\" 可能是两个 tag 也可能是一个词），先导出核对再批量改。"
---

# tags 预分词后无法还原展示

## 影响

字段的「存/取」两个方向都要设计，检索友好 ≠ 展示友好。
