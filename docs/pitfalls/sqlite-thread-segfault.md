---
id: "docs.pitfalls.sqlite-thread-segfault"
title: "单 sqlite 连接跨线程并发 → Linux 段错误"
summary: "一个 Fts5Index 连接被索引线程与查询线程同时用，Linux CI 直接段错误。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/indexer/fts5.py"
last_reviewed: "2026-08-01"
related: ["docs.pitfalls.sqlite-close-race:see-also", "docs.pitfalls.index-rebuild-thread-leak:see-also"]
applies_to: ["docs.architecture"]
severity: "critical"
symptom: "GitHub Actions 里 pytest 报 Fatal Python error: Segmentation fault（exit 139），栈指向 fts5.py build()；本地 Windows 全绿。"
cause: "check_same_thread=False 只关掉 Python 层检查，不代表线程安全；SQLite C 层并发访问内部状态错乱。"
detect: "本地复现不了时看 CI：Windows 绿、Linux 崩，且栈在 sqlite 调用内，基本就是并发。"
avoid: "用 threading.RLock 串行化所有连接操作（build/upsert/remove/search/count/close），并加并发回归测试。"
recover: "已经写坏索引就重建；数据库文件一般未损坏，但要在加锁后重建一次确认。"
---

# 单 sqlite 连接跨线程并发 → Linux 段错误

## 影响

check_same_thread=False 后必须自己加锁；跨平台差异不可依赖，CI 必须跑测试。
