---
id: "docs.pitfalls.pip-readme-missing"
title: "只 COPY pyproject.toml 不带 README，pip install . 直接失败"
summary: "pyproject 声明 readme = README.md，Dockerfile 没拷这个文件，构建元数据报错。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "Dockerfile"
last_reviewed: "2026-08-01"
related: []
applies_to: ["docs.deploy-windows"]
severity: "medium"
symptom: "Actions 构建失败：OSError: Readme file does not exist: README.md。"
cause: "构建阶段只 COPY 了 pyproject.toml 与 app/，读元数据时找不到 README。"
detect: "本地跑 pip install --no-cache-dir . 或 docker build 即可复现；CI 日志里是 OSError。"
avoid: "Dockerfile 补 COPY README.md ./；凡是 pyproject 引用的文件（readme/license）都要在构建层可见。"
recover: "补一行 COPY 重跑构建。"
---

# 只 COPY pyproject.toml 不带 README，pip install . 直接失败

## 影响

打包元数据与运行依赖是两套要求，别只测 import。
