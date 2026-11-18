---
id: "docs.pitfalls.bytes-literal-ascii"
title: "bytes 字面量不能含中文"
summary: "b\"# 标题\" 直接 SyntaxError，必须先 encode。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/textcodec.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.dev-guide"]
severity: "low"
symptom: "SyntaxError: bytes can only contain ASCII literal characters。"
cause: "Python 的 bytes 字面量只接受 ASCII 转义。"
detect: "语法检查阶段就会报，不需要运行。"
avoid: "写成 \"# 标题\\r\\n\".encode(\"utf-8\")；需要 BOM 时用 b\"\\xef\\xbb\\xbf\" + 文本.encode()。"
recover: "改写字面量后重跑 import 即可。"
---

# bytes 字面量不能含中文

## 影响

无运行时影响。
