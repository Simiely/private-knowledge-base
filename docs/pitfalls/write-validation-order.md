---
id: "docs.pitfalls.write-validation-order"
title: "路径校验顺序错，越界写返回 403 而不是 422"
summary: "ensure_writable 先按「点开头」拦了 ..，越界语义被报成禁写。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/vault.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.api-reference"]
severity: "medium"
symptom: "PUT ../逃逸.md 返回 403，与 API 文档约定的 422 不符。"
cause: "Path('../逃逸.md').parts 含 '..'，被隐藏目录规则误判；越界判断被排在后面。"
detect: "用 ../ 路径打一次写接口，比对返回码与 docs/05 的约定。"
avoid: "ensure_writable 遇 .. 直接放行，越界统一由 vault 校验报 422；403 只表示「合法路径但禁写目录」。"
recover: "改校验顺序即可，不涉及数据。"
---

# 路径校验顺序错，越界写返回 403 而不是 422

## 影响

错误码是 API 契约，语义不能混。
