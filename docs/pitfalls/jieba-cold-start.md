---
id: "docs.pitfalls.jieba-cold-start"
title: "jieba 首次加载要 0.7 秒，容器里还可能写不了缓存"
summary: "冷启动构建前缀词典约 0.7 秒；缓存目录不可写时每次启动都重新构建。"
type: "explanation"
kind: "pitfall"
status: "active"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/search_text.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.deploy-windows"]
severity: "low"
symptom: "日志出现 \"Building prefix dict... Loading model cost 0.657 seconds\"，首次搜索明显变慢。"
cause: "jieba 首次调用才构建前缀词典，默认缓存到 %TEMP%/jieba.cache；容器重建或 /tmp 不可写都会丢缓存。"
detect: "连续两次启动对比日志里的 Loading model cost；第二次仍超过 0.5 秒说明缓存没生效。"
avoid: "镜像构建时预热一次并保留缓存目录；容器内确认 temp 可写，或把 jieba 缓存指到持久卷。"
recover: "已经变慢只需预热；不影响正确性，不必回滚。"
---

# jieba 首次加载要 0.7 秒，容器里还可能写不了缓存

## 影响

属于启动成本而非故障，大库首次索引时容易被误判成「索引卡住」。
