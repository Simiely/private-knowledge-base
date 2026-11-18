---
id: "docs.pitfalls.snapshot-id-collision"
title: "秒级快照 id 会重复，增量判断与恢复都错"
summary: "同一秒两次快照 id 相同，prev < snap 恒 False 导致每次全量复制，恢复还可能取错目录。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/backup/engine.py"
last_reviewed: "2026-07-31"
related: ["docs.pitfalls.snapshot-id-ordering:see-also"]
applies_to: ["docs.architecture"]
severity: "critical"
symptom: "同一秒出现两个 snap-20260731-225755；增量备份变成全量；restore_all 用旧 id 取到被覆盖的新目录。"
cause: "id 只含秒级时间戳，createdAt 也是秒级；实现把 id 当成了时间序。"
detect: "连续两次创建快照，比较 manifest 的 id 与 createdAt；id 相同即命中。"
avoid: "id 加 uuid4().hex[:4] 后缀；createdAt 用微秒；「最新快照」一律按 createdAt 排序，绝不按 id 字典序。"
recover: "已重复的 id 需要人工改名并修 manifest；恢复前先建「恢复前快照」。"
---

# 秒级快照 id 会重复，增量判断与恢复都错

## 影响

时间序比较必须基于 createdAt；测试 test_incremental_hardlink 锁死该行为。
