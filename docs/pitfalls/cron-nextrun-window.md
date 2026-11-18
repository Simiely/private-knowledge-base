---
id: "docs.pitfalls.cron-nextrun-window"
title: "next_run 只扫 25 小时，跨周末就找不到"
summary: "周五 22:30 求「工作日 9:00」的下次执行，窗口内没有候选。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/backup/scheduler.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.config-reference"]
severity: "medium"
symptom: "next_run 返回空或抛异常；周一 9:00 的任务在周五晚上算不出来。"
cause: "扫描窗口按 24+1 小时设计，跨周末最长要 3 天。"
detect: "用周五 22:30 + 工作日 9:00 跑一次计算；结果为空即命中。"
avoid: "窗口扩到 7 天（逐分钟 10080 次，开销可忽略）。"
recover: "改窗口后重算；错过的任务不会自动补。"
---

# next_run 只扫 25 小时，跨周末就找不到

## 影响

无数据风险，只影响调度显示与触发。
