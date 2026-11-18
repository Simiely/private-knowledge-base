---
id: docs.generated.backlinks
title: 反向链接
summary: 从 related 与 pitfall 的 applies_to 自动派生的反向链接；勿手改。
type: reference
kind: index
status: active
owner: "@platform"
source_type: doc
source: schema/taxonomy.json
last_reviewed: 2026-11-11
related: []
---

# 反向链接

> 生成文件，勿手改。方向性关系只存一侧，本页是派生结果；对称关系按规范边去重。
> `applies_to` 是 pitfall 的专用字段，可指向页面 id 或技能 name；技能没有页面可链，故只出现在目标列。

| 目标 id / 技能 | 来源 id | 关系 | 来源页面 |
|---|---|---|---|
| `docs.api-reference` | [路径校验顺序错，越界写返回 403 而不是 422](../pitfalls/write-validation-order.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/write-validation-order.md` |
| `docs.architecture` | [@agent.tool 默认工具名是函数名，带下划线就会被叫错](../pitfalls/agent-tool-name.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/agent-tool-name.md` |
| `docs.architecture` | [模块级 create_app() 会让配置错误变成 import 失败](../pitfalls/app-factory-placeholder.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/app-factory-placeholder.md` |
| `docs.architecture` | [FTS5 空表 count(*) 返回 NULL，不是 0](../pitfalls/fts5-count-null.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/fts5-count-null.md` |
| `docs.architecture` | [不熟的框架 HITL 别硬上，先用暂存式写操作](../pitfalls/hitl-pending-store.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/hitl-pending-store.md` |
| `docs.architecture` | [只 join 初始线程不够，重建线程会撞上已关闭的库](../pitfalls/index-rebuild-thread-leak.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/index-rebuild-thread-leak.md` |
| `docs.architecture` | [jieba 把连字符拆成标点，混进 FTS5 MATCH 会变成 NOT](../pitfalls/jieba-hyphen-token.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/jieba-hyphen-token.md` |
| `docs.architecture` | [pydantic-ai 2.x 与 1.x API 差异大，照文档写必然踩空](../pitfalls/pydantic-ai-2x.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/pydantic-ai-2x.md` |
| `docs.architecture` | [秒级快照 id 会重复，增量判断与恢复都错](../pitfalls/snapshot-id-collision.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/snapshot-id-collision.md` |
| `docs.architecture` | [id 带随机后缀后，字典序不再等于时间序](../pitfalls/snapshot-id-ordering.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/snapshot-id-ordering.md` |
| `docs.architecture` | [快照校验拿自己比自己，篡改永远检测不出来](../pitfalls/snapshot-verify-baseline.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/snapshot-verify-baseline.md` |
| `docs.architecture` | [主线程 close 连接时后台索引线程还在跑 → access violation](../pitfalls/sqlite-close-race.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/sqlite-close-race.md` |
| `docs.architecture` | [单 sqlite 连接跨线程并发 → Linux 段错误](../pitfalls/sqlite-thread-segfault.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/sqlite-thread-segfault.md` |
| `docs.architecture` | [tags 预分词后无法还原展示](../pitfalls/tags-pretokenized.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/tags-pretokenized.md` |
| `docs.architecture` | [watchdog handler 闭包拿不到外部对象，异常还只在后台线程抛](../pitfalls/watchdog-closure.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/watchdog-closure.md` |
| `docs.config-reference` | [备份目录默认在容器可写层，重建容器就没了](../pitfalls/backup-dir-container-layer.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/backup-dir-container-layer.md` |
| `docs.config-reference` | [next_run 只扫 25 小时，跨周末就找不到](../pitfalls/cron-nextrun-window.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/cron-nextrun-window.md` |
| `docs.config-reference` | [cron 的 0 是周日，Python weekday() 的 0 是周一](../pitfalls/cron-weekday-offset.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/cron-weekday-offset.md` |
| `docs.deploy-dpanel` | [容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的](../pitfalls/docker-host-disks-hidden.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/docker-host-disks-hidden.md` |
| `docs.deploy-windows` | [备份目录默认在容器可写层，重建容器就没了](../pitfalls/backup-dir-container-layer.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/backup-dir-container-layer.md` |
| `docs.deploy-windows` | [容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的](../pitfalls/docker-host-disks-hidden.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/docker-host-disks-hidden.md` |
| `docs.deploy-windows` | [jieba 首次加载要 0.7 秒，容器里还可能写不了缓存](../pitfalls/jieba-cold-start.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/jieba-cold-start.md` |
| `docs.deploy-windows` | [npm 官方源不可达，构建与安装必须换镜像](../pitfalls/npm-registry-blocked.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/npm-registry-blocked.md` |
| `docs.deploy-windows` | [只 COPY pyproject.toml 不带 README，pip install . 直接失败](../pitfalls/pip-readme-missing.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/pip-readme-missing.md` |
| `docs.deploy-windows` | [开发沙箱没有 docker，compose 与镜像只能在用户侧验证](../pitfalls/sandbox-no-docker.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/sandbox-no-docker.md` |
| `docs.dev-guide` | [模块级 create_app() 会让配置错误变成 import 失败](../pitfalls/app-factory-placeholder.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/app-factory-placeholder.md` |
| `docs.dev-guide` | [bytes 字面量不能含中文](../pitfalls/bytes-literal-ascii.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/bytes-literal-ascii.md` |
| `docs.dev-guide` | [Git Bash 里 heredoc 的 \n 会变成字面 /n，污染测试数据](../pitfalls/gitbash-heredoc-newline.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/gitbash-heredoc-newline.md` |
| `docs.dev-guide` | [逐文件推送会制造几十个 commit 和一堆 Actions](../pitfalls/github-per-file-push.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/github-per-file-push.md` |
| `docs.dev-guide` | [TestClient 的 httpx 弃用警告：先记录，不急着换](../pitfalls/httpx-deprecation.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/httpx-deprecation.md` |
| `docs.dev-guide` | [npm 官方源不可达，构建与安装必须换镜像](../pitfalls/npm-registry-blocked.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/npm-registry-blocked.md` |
| `docs.dev-guide` | [PyPI 直连偶发 SSL EOF，安装随机失败](../pitfalls/pypi-ssl-eof.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/pypi-ssl-eof.md` |
| `docs.dev-guide` | [开发沙箱没有 docker，compose 与镜像只能在用户侧验证](../pitfalls/sandbox-no-docker.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/sandbox-no-docker.md` |
| `docs.dev-guide` | [TestModel 只生成 dummy 参数，测不了按参数分支的工具](../pitfalls/testmodel-dummy-args.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/testmodel-dummy-args.md` |
| `docs.dev-guide` | [Windows 上 Path.write_text 会把 \n 变成 \r\n](../pitfalls/write-text-crlf.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/write-text-crlf.md` |
| `docs.feature-overview` | [frontmatter 内联列表 [a, b] 被当成标量](../pitfalls/frontmatter-inline-list.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/frontmatter-inline-list.md` |
| `docs.feature-overview` | [wikilink 正则会误吃 ![[嵌入]]](../pitfalls/wikilink-embed.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/wikilink-embed.md` |
| `docs.mcp-setup` | [@agent.tool 默认工具名是函数名，带下划线就会被叫错](../pitfalls/agent-tool-name.md) | applies-to（反向：has-pitfall；来自 applies_to 字段） | `docs/pitfalls/agent-tool-name.md` |
| `docs.pitfalls.cron-nextrun-window` | [cron 的 0 是周日，Python weekday() 的 0 是周一](../pitfalls/cron-weekday-offset.md) | see-also | `docs/pitfalls/cron-weekday-offset.md` |
| `docs.pitfalls.index-rebuild-thread-leak` | [主线程 close 连接时后台索引线程还在跑 → access violation](../pitfalls/sqlite-close-race.md) | see-also | `docs/pitfalls/sqlite-close-race.md` |
| `docs.pitfalls.index-rebuild-thread-leak` | [单 sqlite 连接跨线程并发 → Linux 段错误](../pitfalls/sqlite-thread-segfault.md) | see-also | `docs/pitfalls/sqlite-thread-segfault.md` |
| `docs.pitfalls.snapshot-id-ordering` | [秒级快照 id 会重复，增量判断与恢复都错](../pitfalls/snapshot-id-collision.md) | see-also | `docs/pitfalls/snapshot-id-collision.md` |
| `docs.pitfalls.sqlite-close-race` | [单 sqlite 连接跨线程并发 → Linux 段错误](../pitfalls/sqlite-thread-segfault.md) | see-also | `docs/pitfalls/sqlite-thread-segfault.md` |
