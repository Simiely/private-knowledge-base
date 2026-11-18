---
id: "docs.pitfalls.testmodel-dummy-args"
title: "TestModel 只生成 dummy 参数，测不了按参数分支的工具"
summary: "TestModel(call_tools=[...]) 总是传 schema 首值，参数校验类用例会被误判。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "tests/test_agent.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.dev-guide"]
severity: "medium"
symptom: "用 TestModel 测「仅允许 .md」，工具收到的 path 永远是 \"a\"，用例要么恒失败要么恒通过。"
cause: "TestModel 按 schema 造最小合法参数，不执行真实语义。"
detect: "打印工具调用收到的 args；所有用例都是同一组默认值即命中。"
avoid: "需要控制参数时改用 FunctionModel，handler 精确返回 ToolCallPart(args={...})，第一轮调工具、后续轮返回文本。"
recover: "把 TestModel 用例改写为 FunctionModel 即可，不涉及产品代码。"
---

# TestModel 只生成 dummy 参数，测不了按参数分支的工具

## 影响

TestModel 只适合验证不依赖参数的调用链。
