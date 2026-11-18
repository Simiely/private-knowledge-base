---
id: "docs.pitfalls.gitbash-heredoc-newline"
title: "Git Bash 里 heredoc 的 \\n 会变成字面 /n，污染测试数据"
summary: "python - <<EOF 或 -c 里的 \\n 被转成 /n，frontmatter 解析成单行，测试全红但产品没 bug。"
type: "explanation"
kind: "pitfall"
status: "active"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "scripts/m4_smoke.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.dev-guide"]
severity: "high"
symptom: "搜索或标签测试异常，数据里出现 \"/n-docker\"；同一脚本换个环境跑正常。"
cause: "Git Bash 对反斜杠的传递不可靠，内联字符串里的转义在到达 Python 前已被改写。"
detect: "把脚本写入的原始字节打印出来（repr），看到 /n 而不是 \\n 即命中。"
avoid: "含 \\n 的测试或冒烟脚本一律先用 Write 落成文件再执行（如 scripts/m4_smoke.py），不用 heredoc 内联。"
recover: "删除被污染的测试库与索引并重建数据；产品代码无需改。"
---

# Git Bash 里 heredoc 的 \n 会变成字面 /n，污染测试数据

## 影响

凡脚本内嵌多行字符串都要走文件。
