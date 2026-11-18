---
id: "docs.pitfalls.write-text-crlf"
title: "Windows 上 Path.write_text 会把 \\n 变成 \\r\\n"
summary: "fixture 用 write_text 造文件，读回是 CRLF，字节级断言连环失败。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "tests/conftest.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.dev-guide"]
severity: "medium"
symptom: "同一段 fixture 在 Windows 上断言失败、Linux 通过；文件多出 \\r。"
cause: "文本模式默认做换行转换；write_bytes 不做。"
detect: "读回文件取前几个字节，看到 0d 0a 即命中。"
avoid: "测试 fixture 统一 write_bytes(x.encode(\"utf-8\"))；产品写文件显式控制换行。"
recover: "删掉被写坏的文件重建；断言改为按字节比较。"
---

# Windows 上 Path.write_text 会把 \n 变成 \r\n

## 影响

所有涉及换行的 fixture 都要注意。
