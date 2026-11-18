---
id: "docs.pitfalls.github-per-file-push"
title: "逐文件推送会制造几十个 commit 和一堆 Actions"
summary: "Contents API 一次一个文件，70 个文件就是 70 次 push，Actions 列表爆炸。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "scripts/upload_github.py"
last_reviewed: "2026-08-01"
related: []
applies_to: ["docs.dev-guide"]
severity: "low"
symptom: "一次上传产生 128 个 workflow run，多数被 concurrency 取消但记录留着。"
cause: "Contents API 单次只能提交一个文件，每次提交都是独立 commit，on: push 每个 commit 触发一次。"
detect: "上传后看 Actions 列表的 run 数是否远大于 1。"
avoid: "用 Git Data API 批量提交：blobs → tree(base_tree) → commit(parents) → PATCH ref，N 个文件 1 个 commit。"
recover: "多余 run 用 DELETE /actions/runs/{id} 清理，只留 success。"
---

# 逐文件推送会制造几十个 commit 和一堆 Actions

## 影响

推送工具已改为 scripts/upload_github.py 的单 commit 实现。
