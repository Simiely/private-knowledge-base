---
id: "docs.pitfalls.httpx-deprecation"
title: "TestClient 的 httpx 弃用警告：先记录，不急着换"
summary: "starlette 提示改用 httpx2，项目装的仍是 httpx 0.28，只影响测试警告。"
type: "explanation"
kind: "pitfall"
status: "active"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "pyproject.toml"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.dev-guide"]
severity: "low"
symptom: "StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead。"
cause: "starlette 新版建议 httpx2，依赖尚未跟进。"
detect: "跑 pytest -W error::DeprecationWarning，看是否升级成失败；不失败就只是噪音。"
avoid: "现阶段忽略警告；升级 starlette 时一并评估 httpx2，不要单独换测试栈。"
recover: "若 TestClient 行为异常，先回退 httpx 版本再排查。"
---

# TestClient 的 httpx 弃用警告：先记录，不急着换

## 影响

待验证项：M2/M3 若 TestClient 受影响再评估切换。
