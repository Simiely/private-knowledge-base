---
id: "docs.pitfalls.sandbox-no-docker"
title: "开发沙箱没有 docker，compose 与镜像只能在用户侧验证"
summary: "沙箱里 docker --version 都失败，Dockerfile/compose 只能静态审阅，真实构建推迟到部署环境。"
type: "explanation"
kind: "pitfall"
status: "active"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "Dockerfile"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.deploy-windows", "docs.dev-guide"]
severity: "medium"
symptom: "docker --version 报 command not found，docker compose config 无法执行；本地 pytest 全绿但镜像可能构建失败。"
cause: "开发沙箱未安装 docker daemon，容器相关能力不在本地可用范围内。"
detect: "任务开始前跑 docker --version；失败就说明本轮无法验证构建。"
avoid: "用 uvicorn 本地起服务 + TestClient 覆盖健康检查、静态页、配置校验；Dockerfile 只做静态审阅，把 docker compose up --build 列进发布前检查单。"
recover: "构建在用户侧失败时按报错改 Dockerfile，不需要回滚代码。"
---

# 开发沙箱没有 docker，compose 与镜像只能在用户侧验证

## 影响

docker 相关 bug 会晚于本地发现；README 快速上手已标注此前提。
