---
id: "docs.pitfalls.agent-tool-name"
title: "@agent.tool 默认工具名是函数名，带下划线就会被叫错"
summary: "def _tool_write_file 注册出的工具名是 _tool_write_file，按 write_file 调用直接 KeyError。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/agent/service.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture", "docs.mcp-setup"]
severity: "medium"
symptom: "测试或 LLM 调用 write_file 时报 KeyError；工具列表里出现带下划线的名字。"
cause: "装饰器默认取 __name__，私有前缀被原样带进工具名。"
detect: "启动后打印 agent 的工具清单，与提示词里声明的名字逐一比对。"
avoid: "agent.tool(fn, name=\"write_file\") 显式命名；工具名当契约维护，改名前先全仓搜提示词与测试。"
recover: "改回显式名字即可；历史会话里的旧名字不会自动迁移，需重开对话。"
---

# @agent.tool 默认工具名是函数名，带下划线就会被叫错

## 影响

工具名是 LLM 与测试的契约，必须稳定可读。
