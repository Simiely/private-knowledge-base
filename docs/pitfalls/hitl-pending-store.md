---
id: "docs.pitfalls.hitl-pending-store"
title: "不熟的框架 HITL 别硬上，先用暂存式写操作"
summary: "框架 approval 流程资料少、调试慢，拖住写操作安全链路；改自研暂存层后行为能被测试锁死。"
type: "explanation"
kind: "pitfall"
status: "active"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/agent/safety.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture"]
severity: "low"
symptom: "按框架文档接 DeferredToolRequests，端到端确认链路迟迟跑不通，写操作安全性无法验证。"
cause: "2.x 的 HITL API 变更且示例少，调试成本高于自研一个暂存层。"
detect: "先给「工具写文件 + 用户确认」写一个端到端用例；跑不通就先别接框架 approval。"
avoid: "工具只做校验、备份、diff 并暂存，用户确认后才落盘；语义写进 system prompt 告知 LLM。"
recover: "已接入一半的框架 approval 直接移除，改暂存式；注意清理未落盘的 pending 状态。"
---

# 不熟的框架 HITL 别硬上，先用暂存式写操作

## 影响

写操作安全性与框架解耦，测试性好；LLM 不知晓最终确认结果，可接受。
