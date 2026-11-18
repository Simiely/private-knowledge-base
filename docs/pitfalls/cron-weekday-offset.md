---
id: "docs.pitfalls.cron-weekday-offset"
title: "cron 的 0 是周日，Python weekday() 的 0 是周一"
summary: "1-5 直接和 dt.weekday() 比，周一被跳过。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/backup/scheduler.py"
last_reviewed: "2026-07-31"
related: ["docs.pitfalls.cron-nextrun-window:see-also"]
applies_to: ["docs.config-reference"]
severity: "high"
symptom: "配「周一到周五 9:00」的自动备份，周一不执行，周二到周五正常。"
cause: "cron 惯例 0=周日；Python weekday() 0=周一，两者差一位。"
detect: "挑一个周一的日期构造 next_run 计算，看返回是否跳到周二。"
avoid: "比较前转换 (dt.weekday() + 1) % 7；文档里注明 cron 惯例。"
recover: "改完重算下次执行时间即可，不会补跑错过的任务。"
---

# cron 的 0 是周日，Python weekday() 的 0 是周一

## 影响

任何实现 cron 的模块都要做这个转换。
