---
id: "docs.pitfalls.sqlite-close-race"
title: "主线程 close 连接时后台索引线程还在跑 → access violation"
summary: "lifespan 退出直接 close，初始索引线程仍在写，Windows 报 access violation。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/indexer/service.py"
last_reviewed: "2026-07-31"
related: ["docs.pitfalls.index-rebuild-thread-leak:see-also"]
applies_to: ["docs.architecture"]
severity: "high"
symptom: "pytest 全量跑崩溃：Windows fatal exception: access violation，栈显示 backend.close() 与 _set_meta 同时访问同一连接。"
cause: "check_same_thread=False 的连接被 close 时，后台线程还在执行 SQL，C 层并发是未定义行为。"
detect: "退出时打日志看是否有线程仍在写；崩溃栈里同时出现 close 与索引函数即命中。"
avoid: "lifespan 退出先 join 索引线程（30 秒超时）再条件 close；超时则跳过 close，交给进程退出回收。"
recover: "已经崩溃只需重启；若库文件损坏，用备份快照恢复。"
---

# 主线程 close 连接时后台索引线程还在跑 → access violation

## 影响

任何「后台线程共享连接」的模式都要保证关闭前 join。
