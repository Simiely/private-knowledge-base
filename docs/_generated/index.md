---
id: docs.generated.index
title: 生成索引
summary: 从 frontmatter 自动生成的导航；勿手改。
type: reference
kind: index
status: active
owner: "@platform"
source_type: doc
source: schema/taxonomy.json
last_reviewed: 2026-11-11
related: []
---

# 生成索引

> 生成文件，勿手改。运行 `python tools/repo-kit/generate.py --root . --write` 重建。

## 按 type

### tutorial

| 页面 | kind | status | owner | tier | source |
|---|---|---|---|---|---|
| [快速开始](../03-快速开始.md) | note | active | @simiely | normal | `docker-compose.yml` |

### how-to

| 页面 | kind | status | owner | tier | source |
|---|---|---|---|---|---|
| [DPanel 部署](../部署-DPanel.md) | note | active | @simiely | normal | `docker-compose.yml` |
| [Windows 部署](../部署-Windows.md) | note | active | @simiely | normal | `docker-compose.yml` |
| [开发指南](../06-开发指南.md) | note | active | @simiely | normal | `pyproject.toml` |
| [MCP 接入](../MCP接入.md) | note | active | @simiely | normal | `app/mcp/server.py` |

### reference

| 页面 | kind | status | owner | tier | source |
|---|---|---|---|---|---|
| [API 参考](../05-API参考.md) | note | active | @simiely | normal | `app/schemas.py` |
| [配置参考](../04-配置参考.md) | note | active | @simiely | normal | `app/config.py` |
| [功能说明](../01-功能说明.md) | note | active | @simiely | normal | `README.md` |
| [踩坑记录](../08-踩坑记录.md) | index | active | @simiely | normal | `schema/taxonomy.json` |

### explanation

| 页面 | kind | status | owner | tier | source |
|---|---|---|---|---|---|
| [架构设计](../02-架构设计.md) | note | active | @simiely | normal | `app/main.py` |

## Reports

| 页面 | status | owner | tier | source |
|---|---|---|---|---|
| [更新日志](../07-更新日志.md) | active | @simiely | normal | `CHANGELOG.md` |
| [代码梳理与重构计划](../10-代码梳理与重构计划.md) | active | @simiely | normal | `docs/10-代码梳理与重构计划.md` |
| [技术调研与方案审核](../09-技术调研与方案审核.md) | active | @simiely | normal | `docs/09-技术调研与方案审核.md` |

## Pitfalls

| 坑 | severity | 症状 | applies_to | status |
|---|---|---|---|---|
| [备份目录默认在容器可写层，重建容器就没了](../pitfalls/backup-dir-container-layer.md) | critical | Docker 部署后快照「消失」，宿主机找不到备份文件。 | `docs.deploy-windows`, `docs.config-reference` | resolved |
| [秒级快照 id 会重复，增量判断与恢复都错](../pitfalls/snapshot-id-collision.md) | critical | 同一秒出现两个 snap-20260731-225755；增量备份变成全量；restore_all 用旧 id 取到被覆盖的新目录。 | `docs.architecture` | resolved |
| [快照校验拿自己比自己，篡改永远检测不出来](../pitfalls/snapshot-verify-baseline.md) | critical | 手动改快照里的文件后 verify 仍报 OK。 | `docs.architecture` | resolved |
| [单 sqlite 连接跨线程并发 → Linux 段错误](../pitfalls/sqlite-thread-segfault.md) | critical | GitHub Actions 里 pytest 报 Fatal Python error: Segmentation fault（exit 139），栈指向 fts5.py build()；本地 Windows 全绿。 | `docs.architecture` | resolved |
| [cron 的 0 是周日，Python weekday() 的 0 是周一](../pitfalls/cron-weekday-offset.md) | high | 配「周一到周五 9:00」的自动备份，周一不执行，周二到周五正常。 | `docs.config-reference` | resolved |
| [容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的](../pitfalls/docker-host-disks-hidden.md) | high | iStoreOS + Docker 部署，DirPicker 只能看到挂载点根目录，点进去没有子目录；左侧出现 /mnt、/media 等空目录。 | `docs.deploy-dpanel`, `docs.deploy-windows` | resolved |
| [Git Bash 里 heredoc 的 \n 会变成字面 /n，污染测试数据](../pitfalls/gitbash-heredoc-newline.md) | high | 搜索或标签测试异常，数据里出现 "/n-docker"；同一脚本换个环境跑正常。 | `docs.dev-guide` | active |
| [jieba 把连字符拆成标点，混进 FTS5 MATCH 会变成 NOT](../pitfalls/jieba-hyphen-token.md) | high | jieba.lcut("docker-compose") 返回 ['docker','-','compose']；把 token 直接拼进 MATCH 后，"docker -compose" 变成「有 docker 且没有 compose」，本该命中的笔记搜不到。 | `docs.architecture` | resolved |
| [pydantic-ai 2.x 与 1.x API 差异大，照文档写必然踩空](../pitfalls/pydantic-ai-2x.md) | high | ImportError / AttributeError：run_with_tool_approval 找不到，OpenAIChatCompatibleProvider 不是类，OpenAIModel 位置变了。 | `docs.architecture` | resolved |
| [id 带随机后缀后，字典序不再等于时间序](../pitfalls/snapshot-id-ordering.md) | high | 快照列表顺序错乱；按 id 倒序取到旧快照。 | `docs.architecture` | resolved |
| [主线程 close 连接时后台索引线程还在跑 → access violation](../pitfalls/sqlite-close-race.md) | high | pytest 全量跑崩溃：Windows fatal exception: access violation，栈显示 backend.close() 与 _set_meta 同时访问同一连接。 | `docs.architecture` | resolved |
| [bytes 字面量不能含中文](../pitfalls/bytes-literal-ascii.md) | low | SyntaxError: bytes can only contain ASCII literal characters。 | `docs.dev-guide` | resolved |
| [逐文件推送会制造几十个 commit 和一堆 Actions](../pitfalls/github-per-file-push.md) | low | 一次上传产生 128 个 workflow run，多数被 concurrency 取消但记录留着。 | `docs.dev-guide` | resolved |
| [不熟的框架 HITL 别硬上，先用暂存式写操作](../pitfalls/hitl-pending-store.md) | low | 按框架文档接 DeferredToolRequests，端到端确认链路迟迟跑不通，写操作安全性无法验证。 | `docs.architecture` | active |
| [TestClient 的 httpx 弃用警告：先记录，不急着换](../pitfalls/httpx-deprecation.md) | low | StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead。 | `docs.dev-guide` | active |
| [jieba 首次加载要 0.7 秒，容器里还可能写不了缓存](../pitfalls/jieba-cold-start.md) | low | 日志出现 "Building prefix dict... Loading model cost 0.657 seconds"，首次搜索明显变慢。 | `docs.deploy-windows` | active |
| [PyPI 直连偶发 SSL EOF，安装随机失败](../pitfalls/pypi-ssl-eof.md) | low | SSL: UNEXPECTED_EOF_WHILE_READING，部分包直接装不上；换网络后正常。 | `docs.dev-guide` | active |
| [@agent.tool 默认工具名是函数名，带下划线就会被叫错](../pitfalls/agent-tool-name.md) | medium | 测试或 LLM 调用 write_file 时报 KeyError；工具列表里出现带下划线的名字。 | `docs.architecture`, `docs.mcp-setup` | resolved |
| [模块级 create_app() 会让配置错误变成 import 失败](../pitfalls/app-factory-placeholder.md) | medium | import app.main 抛 VaultError；pytest 收集阶段就失败，看不到具体配置问题。 | `docs.architecture`, `docs.dev-guide` | resolved |
| [next_run 只扫 25 小时，跨周末就找不到](../pitfalls/cron-nextrun-window.md) | medium | next_run 返回空或抛异常；周一 9:00 的任务在周五晚上算不出来。 | `docs.config-reference` | resolved |
| [frontmatter 内联列表 [a, b] 被当成标量](../pitfalls/frontmatter-inline-list.md) | medium | Obsidian 里写的 tags: [docker, obsidian] 读出来是 "docker, obsidian" 一个值，按 tag 筛选失效。 | `docs.feature-overview` | resolved |
| [FTS5 空表 count(*) 返回 NULL，不是 0](../pitfalls/fts5-count-null.md) | medium | status() 偶发 TypeError: NoneType not subscriptable，只在索引重建窗口出现。 | `docs.architecture` | resolved |
| [只 join 初始线程不够，重建线程会撞上已关闭的库](../pitfalls/index-rebuild-thread-leak.md) | medium | pytest 结束报 PytestUnhandledThreadExceptionWarning：api-rebuild 线程 fts5.build 报 Cannot operate on a closed database。 | `docs.architecture` | resolved |
| [npm 官方源不可达，构建与安装必须换镜像](../pitfalls/npm-registry-blocked.md) | medium | Docker 构建或本地 npm install 长时间无响应或超时；curl registry.npmjs.org 返回 000。 | `docs.dev-guide`, `docs.deploy-windows` | active |
| [只 COPY pyproject.toml 不带 README，pip install . 直接失败](../pitfalls/pip-readme-missing.md) | medium | Actions 构建失败：OSError: Readme file does not exist: README.md。 | `docs.deploy-windows` | resolved |
| [开发沙箱没有 docker，compose 与镜像只能在用户侧验证](../pitfalls/sandbox-no-docker.md) | medium | docker --version 报 command not found，docker compose config 无法执行；本地 pytest 全绿但镜像可能构建失败。 | `docs.deploy-windows`, `docs.dev-guide` | active |
| [tags 预分词后无法还原展示](../pitfalls/tags-pretokenized.md) | medium | 库里 tags 列存 "docker obsidian"（空格连接），_split_tags 去空格后按逗号切得到 ['dockerobsidian']，标签展示与筛选都错。 | `docs.architecture` | resolved |
| [TestModel 只生成 dummy 参数，测不了按参数分支的工具](../pitfalls/testmodel-dummy-args.md) | medium | 用 TestModel 测「仅允许 .md」，工具收到的 path 永远是 "a"，用例要么恒失败要么恒通过。 | `docs.dev-guide` | resolved |
| [watchdog handler 闭包拿不到外部对象，异常还只在后台线程抛](../pitfalls/watchdog-closure.md) | medium | '_Handler' object has no attribute 'vault'；主流程无异常，测试结束才出现 warning。 | `docs.architecture` | resolved |
| [wikilink 正则会误吃 ![[嵌入]]](../pitfalls/wikilink-embed.md) | medium | ![[图片.png]] 被识别为链接 target="图片.png"，嵌入的图片不显示，反链里多出一条不存在的引用。 | `docs.feature-overview` | resolved |
| [Windows 上 Path.write_text 会把 \n 变成 \r\n](../pitfalls/write-text-crlf.md) | medium | 同一段 fixture 在 Windows 上断言失败、Linux 通过；文件多出 \r。 | `docs.dev-guide` | resolved |
| [路径校验顺序错，越界写返回 403 而不是 422](../pitfalls/write-validation-order.md) | medium | PUT ../逃逸.md 返回 403，与 API 文档约定的 422 不符。 | `docs.api-reference` | resolved |

## 全部页面

| id | 标题 | type | kind | status |
|---|---|---|---|---|
| `docs.api-reference` | [API 参考](../05-API参考.md) | reference | note | active |
| `docs.architecture` | [架构设计](../02-架构设计.md) | explanation | note | active |
| `docs.changelog-archive` | [更新日志](../07-更新日志.md) | reference | report | active |
| `docs.config-reference` | [配置参考](../04-配置参考.md) | reference | note | active |
| `docs.deploy-dpanel` | [DPanel 部署](../部署-DPanel.md) | how-to | note | active |
| `docs.deploy-windows` | [Windows 部署](../部署-Windows.md) | how-to | note | active |
| `docs.dev-guide` | [开发指南](../06-开发指南.md) | how-to | note | active |
| `docs.feature-overview` | [功能说明](../01-功能说明.md) | reference | note | active |
| `docs.mcp-setup` | [MCP 接入](../MCP接入.md) | how-to | note | active |
| `docs.pitfalls-index` | [踩坑记录](../08-踩坑记录.md) | reference | index | active |
| `docs.pitfalls.agent-tool-name` | [@agent.tool 默认工具名是函数名，带下划线就会被叫错](../pitfalls/agent-tool-name.md) | explanation | pitfall | resolved |
| `docs.pitfalls.app-factory-placeholder` | [模块级 create_app() 会让配置错误变成 import 失败](../pitfalls/app-factory-placeholder.md) | explanation | pitfall | resolved |
| `docs.pitfalls.backup-dir-container-layer` | [备份目录默认在容器可写层，重建容器就没了](../pitfalls/backup-dir-container-layer.md) | explanation | pitfall | resolved |
| `docs.pitfalls.bytes-literal-ascii` | [bytes 字面量不能含中文](../pitfalls/bytes-literal-ascii.md) | explanation | pitfall | resolved |
| `docs.pitfalls.cron-nextrun-window` | [next_run 只扫 25 小时，跨周末就找不到](../pitfalls/cron-nextrun-window.md) | explanation | pitfall | resolved |
| `docs.pitfalls.cron-weekday-offset` | [cron 的 0 是周日，Python weekday() 的 0 是周一](../pitfalls/cron-weekday-offset.md) | explanation | pitfall | resolved |
| `docs.pitfalls.docker-host-disks-hidden` | [容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的](../pitfalls/docker-host-disks-hidden.md) | explanation | pitfall | resolved |
| `docs.pitfalls.frontmatter-inline-list` | [frontmatter 内联列表 [a, b] 被当成标量](../pitfalls/frontmatter-inline-list.md) | explanation | pitfall | resolved |
| `docs.pitfalls.fts5-count-null` | [FTS5 空表 count(*) 返回 NULL，不是 0](../pitfalls/fts5-count-null.md) | explanation | pitfall | resolved |
| `docs.pitfalls.gitbash-heredoc-newline` | [Git Bash 里 heredoc 的 \n 会变成字面 /n，污染测试数据](../pitfalls/gitbash-heredoc-newline.md) | explanation | pitfall | active |
| `docs.pitfalls.github-per-file-push` | [逐文件推送会制造几十个 commit 和一堆 Actions](../pitfalls/github-per-file-push.md) | explanation | pitfall | resolved |
| `docs.pitfalls.hitl-pending-store` | [不熟的框架 HITL 别硬上，先用暂存式写操作](../pitfalls/hitl-pending-store.md) | explanation | pitfall | active |
| `docs.pitfalls.httpx-deprecation` | [TestClient 的 httpx 弃用警告：先记录，不急着换](../pitfalls/httpx-deprecation.md) | explanation | pitfall | active |
| `docs.pitfalls.index-rebuild-thread-leak` | [只 join 初始线程不够，重建线程会撞上已关闭的库](../pitfalls/index-rebuild-thread-leak.md) | explanation | pitfall | resolved |
| `docs.pitfalls.jieba-cold-start` | [jieba 首次加载要 0.7 秒，容器里还可能写不了缓存](../pitfalls/jieba-cold-start.md) | explanation | pitfall | active |
| `docs.pitfalls.jieba-hyphen-token` | [jieba 把连字符拆成标点，混进 FTS5 MATCH 会变成 NOT](../pitfalls/jieba-hyphen-token.md) | explanation | pitfall | resolved |
| `docs.pitfalls.npm-registry-blocked` | [npm 官方源不可达，构建与安装必须换镜像](../pitfalls/npm-registry-blocked.md) | explanation | pitfall | active |
| `docs.pitfalls.pip-readme-missing` | [只 COPY pyproject.toml 不带 README，pip install . 直接失败](../pitfalls/pip-readme-missing.md) | explanation | pitfall | resolved |
| `docs.pitfalls.pydantic-ai-2x` | [pydantic-ai 2.x 与 1.x API 差异大，照文档写必然踩空](../pitfalls/pydantic-ai-2x.md) | explanation | pitfall | resolved |
| `docs.pitfalls.pypi-ssl-eof` | [PyPI 直连偶发 SSL EOF，安装随机失败](../pitfalls/pypi-ssl-eof.md) | explanation | pitfall | active |
| `docs.pitfalls.sandbox-no-docker` | [开发沙箱没有 docker，compose 与镜像只能在用户侧验证](../pitfalls/sandbox-no-docker.md) | explanation | pitfall | active |
| `docs.pitfalls.snapshot-id-collision` | [秒级快照 id 会重复，增量判断与恢复都错](../pitfalls/snapshot-id-collision.md) | explanation | pitfall | resolved |
| `docs.pitfalls.snapshot-id-ordering` | [id 带随机后缀后，字典序不再等于时间序](../pitfalls/snapshot-id-ordering.md) | explanation | pitfall | resolved |
| `docs.pitfalls.snapshot-verify-baseline` | [快照校验拿自己比自己，篡改永远检测不出来](../pitfalls/snapshot-verify-baseline.md) | explanation | pitfall | resolved |
| `docs.pitfalls.sqlite-close-race` | [主线程 close 连接时后台索引线程还在跑 → access violation](../pitfalls/sqlite-close-race.md) | explanation | pitfall | resolved |
| `docs.pitfalls.sqlite-thread-segfault` | [单 sqlite 连接跨线程并发 → Linux 段错误](../pitfalls/sqlite-thread-segfault.md) | explanation | pitfall | resolved |
| `docs.pitfalls.tags-pretokenized` | [tags 预分词后无法还原展示](../pitfalls/tags-pretokenized.md) | explanation | pitfall | resolved |
| `docs.pitfalls.testmodel-dummy-args` | [TestModel 只生成 dummy 参数，测不了按参数分支的工具](../pitfalls/testmodel-dummy-args.md) | explanation | pitfall | resolved |
| `docs.pitfalls.watchdog-closure` | [watchdog handler 闭包拿不到外部对象，异常还只在后台线程抛](../pitfalls/watchdog-closure.md) | explanation | pitfall | resolved |
| `docs.pitfalls.wikilink-embed` | [wikilink 正则会误吃 ![[嵌入]]](../pitfalls/wikilink-embed.md) | explanation | pitfall | resolved |
| `docs.pitfalls.write-text-crlf` | [Windows 上 Path.write_text 会把 \n 变成 \r\n](../pitfalls/write-text-crlf.md) | explanation | pitfall | resolved |
| `docs.pitfalls.write-validation-order` | [路径校验顺序错，越界写返回 403 而不是 422](../pitfalls/write-validation-order.md) | explanation | pitfall | resolved |
| `docs.quickstart` | [快速开始](../03-快速开始.md) | tutorial | note | active |
| `docs.refactor-plan` | [代码梳理与重构计划](../10-代码梳理与重构计划.md) | explanation | report | active |
| `docs.research-review` | [技术调研与方案审核](../09-技术调研与方案审核.md) | explanation | report | active |
