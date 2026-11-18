---
id: docs.generated.pitfalls
title: 踩坑索引
summary: 从 kind=pitfall 页面自动生成的失败模式索引；勿手改。
type: reference
kind: index
status: active
owner: "@platform"
source_type: doc
source: schema/taxonomy.json
last_reviewed: 2026-11-11
related: []
---

# 踩坑索引

> 生成文件，勿手改。运行 `python tools/repo-kit/generate.py --root . --write` 重建。
> 每个坑的权威内容在它自己的页面；本页只做导航。

## 未解决（7）

| 严重度 | 坑 | 症状 | 检测 | 适用 | status |
|---|---|---|---|---|---|
| high | [Git Bash 里 heredoc 的 \n 会变成字面 /n，污染测试数据](../pitfalls/gitbash-heredoc-newline.md) | 搜索或标签测试异常，数据里出现 "/n-docker"；同一脚本换个环境跑正常。 | 把脚本写入的原始字节打印出来（repr），看到 /n 而不是 \n 即命中。 | `docs.dev-guide` | active |
| medium | [npm 官方源不可达，构建与安装必须换镜像](../pitfalls/npm-registry-blocked.md) | Docker 构建或本地 npm install 长时间无响应或超时；curl registry.npmjs.org 返回 000。 | 构建前 curl -I 对比 registry.npmjs.org 与 registry.npmmirror.com 的状态码。 | `docs.dev-guide`, `docs.deploy-windows` | active |
| medium | [开发沙箱没有 docker，compose 与镜像只能在用户侧验证](../pitfalls/sandbox-no-docker.md) | docker --version 报 command not found，docker compose config 无法执行；本地 pytest 全绿但镜像可能构建失败。 | 任务开始前跑 docker --version；失败就说明本轮无法验证构建。 | `docs.deploy-windows`, `docs.dev-guide` | active |
| low | [不熟的框架 HITL 别硬上，先用暂存式写操作](../pitfalls/hitl-pending-store.md) | 按框架文档接 DeferredToolRequests，端到端确认链路迟迟跑不通，写操作安全性无法验证。 | 先给「工具写文件 + 用户确认」写一个端到端用例；跑不通就先别接框架 approval。 | `docs.architecture` | active |
| low | [TestClient 的 httpx 弃用警告：先记录，不急着换](../pitfalls/httpx-deprecation.md) | StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead。 | 跑 pytest -W error::DeprecationWarning，看是否升级成失败；不失败就只是噪音。 | `docs.dev-guide` | active |
| low | [jieba 首次加载要 0.7 秒，容器里还可能写不了缓存](../pitfalls/jieba-cold-start.md) | 日志出现 "Building prefix dict... Loading model cost 0.657 seconds"，首次搜索明显变慢。 | 连续两次启动对比日志里的 Loading model cost；第二次仍超过 0.5 秒说明缓存没生效。 | `docs.deploy-windows` | active |
| low | [PyPI 直连偶发 SSL EOF，安装随机失败](../pitfalls/pypi-ssl-eof.md) | SSL: UNEXPECTED_EOF_WHILE_READING，部分包直接装不上；换网络后正常。 | 连续 pip download 同一包，出现 EOF 即命中。 | `docs.dev-guide` | active |

## 已解决（25）

| 严重度 | 坑 | 症状 | 适用 |
|---|---|---|---|
| critical | [备份目录默认在容器可写层，重建容器就没了](../pitfalls/backup-dir-container-layer.md) | Docker 部署后快照「消失」，宿主机找不到备份文件。 | `docs.deploy-windows`, `docs.config-reference` |
| critical | [秒级快照 id 会重复，增量判断与恢复都错](../pitfalls/snapshot-id-collision.md) | 同一秒出现两个 snap-20260731-225755；增量备份变成全量；restore_all 用旧 id 取到被覆盖的新目录。 | `docs.architecture` |
| critical | [快照校验拿自己比自己，篡改永远检测不出来](../pitfalls/snapshot-verify-baseline.md) | 手动改快照里的文件后 verify 仍报 OK。 | `docs.architecture` |
| critical | [单 sqlite 连接跨线程并发 → Linux 段错误](../pitfalls/sqlite-thread-segfault.md) | GitHub Actions 里 pytest 报 Fatal Python error: Segmentation fault（exit 139），栈指向 fts5.py build()；本地 Windows 全绿。 | `docs.architecture` |
| high | [cron 的 0 是周日，Python weekday() 的 0 是周一](../pitfalls/cron-weekday-offset.md) | 配「周一到周五 9:00」的自动备份，周一不执行，周二到周五正常。 | `docs.config-reference` |
| high | [容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的](../pitfalls/docker-host-disks-hidden.md) | iStoreOS + Docker 部署，DirPicker 只能看到挂载点根目录，点进去没有子目录；左侧出现 /mnt、/media 等空目录。 | `docs.deploy-dpanel`, `docs.deploy-windows` |
| high | [jieba 把连字符拆成标点，混进 FTS5 MATCH 会变成 NOT](../pitfalls/jieba-hyphen-token.md) | jieba.lcut("docker-compose") 返回 ['docker','-','compose']；把 token 直接拼进 MATCH 后，"docker -compose" 变成「有 docker 且没有 compose」，本该命中的笔记搜不到。 | `docs.architecture` |
| high | [pydantic-ai 2.x 与 1.x API 差异大，照文档写必然踩空](../pitfalls/pydantic-ai-2x.md) | ImportError / AttributeError：run_with_tool_approval 找不到，OpenAIChatCompatibleProvider 不是类，OpenAIModel 位置变了。 | `docs.architecture` |
| high | [id 带随机后缀后，字典序不再等于时间序](../pitfalls/snapshot-id-ordering.md) | 快照列表顺序错乱；按 id 倒序取到旧快照。 | `docs.architecture` |
| high | [主线程 close 连接时后台索引线程还在跑 → access violation](../pitfalls/sqlite-close-race.md) | pytest 全量跑崩溃：Windows fatal exception: access violation，栈显示 backend.close() 与 _set_meta 同时访问同一连接。 | `docs.architecture` |
| medium | [@agent.tool 默认工具名是函数名，带下划线就会被叫错](../pitfalls/agent-tool-name.md) | 测试或 LLM 调用 write_file 时报 KeyError；工具列表里出现带下划线的名字。 | `docs.architecture`, `docs.mcp-setup` |
| medium | [模块级 create_app() 会让配置错误变成 import 失败](../pitfalls/app-factory-placeholder.md) | import app.main 抛 VaultError；pytest 收集阶段就失败，看不到具体配置问题。 | `docs.architecture`, `docs.dev-guide` |
| medium | [next_run 只扫 25 小时，跨周末就找不到](../pitfalls/cron-nextrun-window.md) | next_run 返回空或抛异常；周一 9:00 的任务在周五晚上算不出来。 | `docs.config-reference` |
| medium | [frontmatter 内联列表 [a, b] 被当成标量](../pitfalls/frontmatter-inline-list.md) | Obsidian 里写的 tags: [docker, obsidian] 读出来是 "docker, obsidian" 一个值，按 tag 筛选失效。 | `docs.feature-overview` |
| medium | [FTS5 空表 count(*) 返回 NULL，不是 0](../pitfalls/fts5-count-null.md) | status() 偶发 TypeError: NoneType not subscriptable，只在索引重建窗口出现。 | `docs.architecture` |
| medium | [只 join 初始线程不够，重建线程会撞上已关闭的库](../pitfalls/index-rebuild-thread-leak.md) | pytest 结束报 PytestUnhandledThreadExceptionWarning：api-rebuild 线程 fts5.build 报 Cannot operate on a closed database。 | `docs.architecture` |
| medium | [只 COPY pyproject.toml 不带 README，pip install . 直接失败](../pitfalls/pip-readme-missing.md) | Actions 构建失败：OSError: Readme file does not exist: README.md。 | `docs.deploy-windows` |
| medium | [tags 预分词后无法还原展示](../pitfalls/tags-pretokenized.md) | 库里 tags 列存 "docker obsidian"（空格连接），_split_tags 去空格后按逗号切得到 ['dockerobsidian']，标签展示与筛选都错。 | `docs.architecture` |
| medium | [TestModel 只生成 dummy 参数，测不了按参数分支的工具](../pitfalls/testmodel-dummy-args.md) | 用 TestModel 测「仅允许 .md」，工具收到的 path 永远是 "a"，用例要么恒失败要么恒通过。 | `docs.dev-guide` |
| medium | [watchdog handler 闭包拿不到外部对象，异常还只在后台线程抛](../pitfalls/watchdog-closure.md) | '_Handler' object has no attribute 'vault'；主流程无异常，测试结束才出现 warning。 | `docs.architecture` |
| medium | [wikilink 正则会误吃 ![[嵌入]]](../pitfalls/wikilink-embed.md) | ![[图片.png]] 被识别为链接 target="图片.png"，嵌入的图片不显示，反链里多出一条不存在的引用。 | `docs.feature-overview` |
| medium | [Windows 上 Path.write_text 会把 \n 变成 \r\n](../pitfalls/write-text-crlf.md) | 同一段 fixture 在 Windows 上断言失败、Linux 通过；文件多出 \r。 | `docs.dev-guide` |
| medium | [路径校验顺序错，越界写返回 403 而不是 422](../pitfalls/write-validation-order.md) | PUT ../逃逸.md 返回 403，与 API 文档约定的 422 不符。 | `docs.api-reference` |
| low | [bytes 字面量不能含中文](../pitfalls/bytes-literal-ascii.md) | SyntaxError: bytes can only contain ASCII literal characters。 | `docs.dev-guide` |
| low | [逐文件推送会制造几十个 commit 和一堆 Actions](../pitfalls/github-per-file-push.md) | 一次上传产生 128 个 workflow run，多数被 concurrency 取消但记录留着。 | `docs.dev-guide` |

## 按适用范围

### `docs.api-reference`

- [路径校验顺序错，越界写返回 403 而不是 422](../pitfalls/write-validation-order.md)（medium）

### `docs.architecture`

- [秒级快照 id 会重复，增量判断与恢复都错](../pitfalls/snapshot-id-collision.md)（critical）
- [快照校验拿自己比自己，篡改永远检测不出来](../pitfalls/snapshot-verify-baseline.md)（critical）
- [单 sqlite 连接跨线程并发 → Linux 段错误](../pitfalls/sqlite-thread-segfault.md)（critical）
- [jieba 把连字符拆成标点，混进 FTS5 MATCH 会变成 NOT](../pitfalls/jieba-hyphen-token.md)（high）
- [pydantic-ai 2.x 与 1.x API 差异大，照文档写必然踩空](../pitfalls/pydantic-ai-2x.md)（high）
- [id 带随机后缀后，字典序不再等于时间序](../pitfalls/snapshot-id-ordering.md)（high）
- [主线程 close 连接时后台索引线程还在跑 → access violation](../pitfalls/sqlite-close-race.md)（high）
- [@agent.tool 默认工具名是函数名，带下划线就会被叫错](../pitfalls/agent-tool-name.md)（medium）
- [模块级 create_app() 会让配置错误变成 import 失败](../pitfalls/app-factory-placeholder.md)（medium）
- [FTS5 空表 count(*) 返回 NULL，不是 0](../pitfalls/fts5-count-null.md)（medium）
- [只 join 初始线程不够，重建线程会撞上已关闭的库](../pitfalls/index-rebuild-thread-leak.md)（medium）
- [tags 预分词后无法还原展示](../pitfalls/tags-pretokenized.md)（medium）
- [watchdog handler 闭包拿不到外部对象，异常还只在后台线程抛](../pitfalls/watchdog-closure.md)（medium）
- [不熟的框架 HITL 别硬上，先用暂存式写操作](../pitfalls/hitl-pending-store.md)（low）

### `docs.config-reference`

- [备份目录默认在容器可写层，重建容器就没了](../pitfalls/backup-dir-container-layer.md)（critical）
- [cron 的 0 是周日，Python weekday() 的 0 是周一](../pitfalls/cron-weekday-offset.md)（high）
- [next_run 只扫 25 小时，跨周末就找不到](../pitfalls/cron-nextrun-window.md)（medium）

### `docs.deploy-dpanel`

- [容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的](../pitfalls/docker-host-disks-hidden.md)（high）

### `docs.deploy-windows`

- [备份目录默认在容器可写层，重建容器就没了](../pitfalls/backup-dir-container-layer.md)（critical）
- [容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的](../pitfalls/docker-host-disks-hidden.md)（high）
- [npm 官方源不可达，构建与安装必须换镜像](../pitfalls/npm-registry-blocked.md)（medium）
- [只 COPY pyproject.toml 不带 README，pip install . 直接失败](../pitfalls/pip-readme-missing.md)（medium）
- [开发沙箱没有 docker，compose 与镜像只能在用户侧验证](../pitfalls/sandbox-no-docker.md)（medium）
- [jieba 首次加载要 0.7 秒，容器里还可能写不了缓存](../pitfalls/jieba-cold-start.md)（low）

### `docs.dev-guide`

- [Git Bash 里 heredoc 的 \n 会变成字面 /n，污染测试数据](../pitfalls/gitbash-heredoc-newline.md)（high）
- [模块级 create_app() 会让配置错误变成 import 失败](../pitfalls/app-factory-placeholder.md)（medium）
- [npm 官方源不可达，构建与安装必须换镜像](../pitfalls/npm-registry-blocked.md)（medium）
- [开发沙箱没有 docker，compose 与镜像只能在用户侧验证](../pitfalls/sandbox-no-docker.md)（medium）
- [TestModel 只生成 dummy 参数，测不了按参数分支的工具](../pitfalls/testmodel-dummy-args.md)（medium）
- [Windows 上 Path.write_text 会把 \n 变成 \r\n](../pitfalls/write-text-crlf.md)（medium）
- [bytes 字面量不能含中文](../pitfalls/bytes-literal-ascii.md)（low）
- [逐文件推送会制造几十个 commit 和一堆 Actions](../pitfalls/github-per-file-push.md)（low）
- [TestClient 的 httpx 弃用警告：先记录，不急着换](../pitfalls/httpx-deprecation.md)（low）
- [PyPI 直连偶发 SSL EOF，安装随机失败](../pitfalls/pypi-ssl-eof.md)（low）

### `docs.feature-overview`

- [frontmatter 内联列表 [a, b] 被当成标量](../pitfalls/frontmatter-inline-list.md)（medium）
- [wikilink 正则会误吃 ![[嵌入]]](../pitfalls/wikilink-embed.md)（medium）

### `docs.mcp-setup`

- [@agent.tool 默认工具名是函数名，带下划线就会被叫错](../pitfalls/agent-tool-name.md)（medium）
