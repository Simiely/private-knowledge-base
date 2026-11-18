---
id: "docs.pitfalls.npm-registry-blocked"
title: "npm 官方源不可达，构建与安装必须换镜像"
summary: "registry.npmjs.org 返回 000，npm install 卡死；npmmirror 返回 200 可用。"
type: "explanation"
kind: "pitfall"
status: "active"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "Dockerfile"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.dev-guide", "docs.deploy-windows"]
severity: "medium"
symptom: "Docker 构建或本地 npm install 长时间无响应或超时；curl registry.npmjs.org 返回 000。"
cause: "网络策略导致官方源不可达；镜像源与部分 CDN 正常。"
detect: "构建前 curl -I 对比 registry.npmjs.org 与 registry.npmmirror.com 的状态码。"
avoid: "npm install 加 --registry=https://registry.npmmirror.com（Dockerfile 已内置）；海外构建可去掉。"
recover: "构建超时先换源重跑，不需要改代码。"
---

# npm 官方源不可达，构建与安装必须换镜像

## 影响

M4 前端因此才升到 Vue3 + Vite；网络策略是官方源被墙、镜像与部分 CDN 通。
