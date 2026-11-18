---
id: "docs.pitfalls.snapshot-verify-baseline"
title: "快照校验拿自己比自己，篡改永远检测不出来"
summary: "verify 重新计算当前文件哈希并与自身比，任何篡改都通过。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/backup/engine.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture"]
severity: "critical"
symptom: "手动改快照里的文件后 verify 仍报 OK。"
cause: "校验缺少基准；创建时没有把哈希写进 manifest。"
detect: "改一个快照文件再跑 verify；仍 OK 即命中。"
avoid: "创建快照时把抽样文件（≤100 个）MD5 写入 manifest，verify 对照 manifest 比对。"
recover: "旧快照没有基准，无法追溯校验；重新建一份带 manifest 的快照。"
---

# 快照校验拿自己比自己，篡改永远检测不出来

## 影响

校验必须有独立基准，否则只是自证。
