---
id: "docs.pitfalls.pydantic-ai-2x"
title: "pydantic-ai 2.x 与 1.x API 差异大，照文档写必然踩空"
summary: "1.x 的 run_with_tool_approval 在 2.21 已不存在，provider 也变成 Literal 预置名。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/agent/llm.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture"]
severity: "high"
symptom: "ImportError / AttributeError：run_with_tool_approval 找不到，OpenAIChatCompatibleProvider 不是类，OpenAIModel 位置变了。"
cause: "大版本重构了 provider 与运行入口；网上教程和模型记忆多数还停在 1.x。"
detect: "升级依赖后先跑最小脚本：构造 Agent(model=\"deepseek:xxx\") 并发一条消息，能返回即 API 对齐。"
avoid: "依赖大版本升级走三步——探查已安装包的真实符号（dir/签名）→ 最小可运行验证 → 再集成；不要照文档或记忆写。"
recover: "已写错的调用按 2.x 入口改写；保留 test_llm.py 冒烟用例防止再漂移。"
---

# pydantic-ai 2.x 与 1.x API 差异大，照文档写必然踩空

## 影响

同类问题适用于所有大版本跳跃的 SDK。
