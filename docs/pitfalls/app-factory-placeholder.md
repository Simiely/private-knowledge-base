---
id: "docs.pitfalls.app-factory-placeholder"
title: "模块级 create_app() 会让配置错误变成 import 失败"
summary: "vault 不存在时 import app.main 直接抛异常，测试和工具都起不来。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/main.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture", "docs.dev-guide"]
severity: "medium"
symptom: "import app.main 抛 VaultError；pytest 收集阶段就失败，看不到具体配置问题。"
cause: "模块导入时立即构造应用，配置错误被提前成导入期异常。"
detect: "用一个不存在的 vault 路径 import app.main，看是抛异常还是返回可查询的 500。"
avoid: "create_app(settings) 工厂支持注入；模块级创建包 try/except 降级为 placeholder app，health 返回 500 暴露错误。"
recover: "已受影响的测试改为注入临时配置；生产配置错误从 health 看原因。"
---

# 模块级 create_app() 会让配置错误变成 import 失败

## 影响

测试注入临时配置是 e2e 可写的前提。
