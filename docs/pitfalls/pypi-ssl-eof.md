---
id: "docs.pitfalls.pypi-ssl-eof"
title: "PyPI 直连偶发 SSL EOF，安装随机失败"
summary: "pip install 报 UNEXPECTED_EOF_WHILE_READING，重试有时能过。"
type: "explanation"
kind: "pitfall"
status: "active"
owner: "@simiely"
topics: ["development"]
source_type: "doc"
source: "docs/06-开发指南.md"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.dev-guide"]
severity: "low"
symptom: "SSL: UNEXPECTED_EOF_WHILE_READING，部分包直接装不上；换网络后正常。"
cause: "到 PyPI 的 TLS 连接在当前网络下不稳定，不是包本身的问题。"
detect: "连续 pip download 同一包，出现 EOF 即命中。"
avoid: "统一加 -i https://pypi.tuna.tsinghua.edu.cn/simple；CI 与本地都走镜像。"
recover: "换镜像重装即可，已装好的环境不受影响。"
---

# PyPI 直连偶发 SSL EOF，安装随机失败

## 影响

后续所有 pip 安装默认带镜像参数。
