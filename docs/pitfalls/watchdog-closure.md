---
id: "docs.pitfalls.watchdog-closure"
title: "watchdog handler 闭包拿不到外部对象，异常还只在后台线程抛"
summary: "on_any_event 里访问 self.vault 报 AttributeError，pytest 只给一条 unhandled thread warning。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/runtime.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture"]
severity: "medium"
symptom: "'_Handler' object has no attribute 'vault'；主流程无异常，测试结束才出现 warning。"
cause: "handler 实例化时没注入 watcher 引用，闭包捕获的是错误的 self。"
detect: "触发一次文件变更看日志或线程异常；或直接对 handler 调 on_any_event。"
avoid: "构造 handler 时注入 watcher，经 self._watcher.vault 访问；后台线程入口包 try/except 记日志。"
recover: "重启服务即可，索引会在下次事件或重建时补齐。"
---

# watchdog handler 闭包拿不到外部对象，异常还只在后台线程抛

## 影响

后台线程异常不冒泡，必须靠日志与测试捕获。
