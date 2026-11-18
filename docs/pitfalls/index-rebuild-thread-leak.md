---
id: "docs.pitfalls.index-rebuild-thread-leak"
title: "只 join 初始线程不够，重建线程会撞上已关闭的库"
summary: "rebuild 自己起线程且无人跟踪，lifespan 只 join 初始索引，重建线程报 closed database。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/indexer/service.py"
last_reviewed: "2026-11-02"
related: []
applies_to: ["docs.architecture"]
severity: "medium"
symptom: "pytest 结束报 PytestUnhandledThreadExceptionWarning：api-rebuild 线程 fts5.build 报 Cannot operate on a closed database。"
cause: "POST /api/index/rebuild 与切换库各自起线程，没有登记到服务的关停流程。"
detect: "触发一次重建后立刻退出服务，看是否出现 unhandled thread exception。"
avoid: "IndexService 统一持有重建线程（start_rebuild/rebuilding/shutdown），lifespan 与热切换都调 shutdown()：先 join，超时才跳过 close。"
recover: "已出现的异常不影响数据；重启服务后重建一次索引。"
---

# 只 join 初始线程不够，重建线程会撞上已关闭的库

## 影响

新增后台线程必须登记到所属服务并纳入关停。
