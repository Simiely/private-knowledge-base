# DEVELOPMENT.md · 架构说明与问题记录

## 项目概览

Docker 化的 Obsidian 知识库 AI 工作台：指定 vault 路径后，可在浏览器里浏览、编辑、
全文检索所有 Markdown，并用自然语言让 Agent 操作笔记。

- **形态**：自托管 Web 应用，FastAPI 后端 + Vue 3 前端，`docker compose up` 即用
- **数据**：笔记只在宿主机 vault 内；索引与备份落在 `/data`
- **不做的事**：不替代 Obsidian 桌面端，不接管插件生态（想要原版体验可并行部署 Ignis 指向同一 vault）

## 架构说明

```
浏览器（目录树 / 阅读 / 编辑 / 搜索 / Agent 面板）
        │ HTTP + SSE
API 层（FastAPI）  /api/vault /search /index /agent
        │  分层单向：api → agent → core
core/    vault(树/读写/监听) · markdown(解析) · indexer(FTS5 抽象) · search · backup(快照)
agent/   llm(模型串) · tools(类型化工具) · loop(会话+HITL) · safety(路径/备份/diff)
        │
宿主机挂载  /vault ← Obsidian 库    /data ← 索引 + 备份
```

**分层铁律**：`core/` 与 `agent/` 是纯领域逻辑，不 import FastAPI；`api/` 只做 HTTP 适配。
这条保证了核心逻辑可单测、可换框架、可复用。

### 关键数据流

| 链路 | 流程 |
|---|---|
| 索引 | 启动扫描（忽略规则过滤）→ 逐文件解析 → 分批写索引（可续传）→ watchdog 监听，变更 debounce 2s 后只重索引该文件 |
| 检索 | query 解析（可选 `path:` / `tag:`）→ 分词 → FTS5 → `{路径, 高亮片段, 命中偏移}` → 前端跳转定位 |
| Agent 编辑 | 指令 → LLM 调 `write_file` → HITL 批准 + safety 校验（vault 内 / 非禁写 / 写前备份）→ 原子写 → 返回 diff → 增量索引 |
| 备份 | 定时 / 手动 / 批量前 → 硬链接增量快照 + manifest → 保留策略清理；恢复前强制再快照 |

### 技术选型要点

- **FTS5 + jieba** 而非 Meilisearch：实测命中率与延迟更好，且零额外容器；接口抽象保留逃生通道
- **Pydantic AI v1.x**：类型安全 + 内置 HITL；换厂商只改模型串（DeepSeek / OpenAI / Kimi / Ollama）
- **硬链接快照** 而非 Restic：零外部依赖、快照就是普通目录，可人工读取

## 关键问题与方案

### 已拆成独立坑页的问题

下面四条都已按 `kind: pitfall` 一坑一篇（症状 / 根因 / 怎么发现 / 怎么避免 / 怎么退出），
这里只留入口，避免同一结论写两遍：

- [单 sqlite 连接跨线程并发 → Linux 段错误](docs/pitfalls/sqlite-thread-segfault.md)
- [jieba 把连字符拆成标点，混进 FTS5 MATCH 会变成 NOT](docs/pitfalls/jieba-hyphen-token.md)
- [FTS5 空表 count(*) 返回 NULL，不是 0](docs/pitfalls/fts5-count-null.md)
- [备份目录默认在容器可写层，重建容器就没了](docs/pitfalls/backup-dir-container-layer.md)

全部 32 条的入口见 [docs/08-踩坑记录.md](docs/08-踩坑记录.md)。

### 问题：干净环境 CI 里首页测试 404

**TL;DR**：前端 `dist` 不入库，测试却依赖它。

- 问题：CI 的 test job 失败，`GET /` 返回 404；build job 被跳过
- 根因：`test_static_index_served` 依赖 `frontend/dist`，而 CI 从不构建前端
- 解决：test job 增加 `setup-node` + `npm ci && npm run build`；`dist` 缺失时该用例 `pytest.skip`
- 预防：测试依赖构建产物时，要么在流水线里构建，要么显式 skip，不要默认它存在

## 规划期风险与对策（未发生）

> 从 `docs/08-踩坑记录.md` 的「预判风险清单」迁入；原 #15/#16 已实际发生，改为坑页：
> [容器看不到宿主磁盘](docs/pitfalls/docker-host-disks-hidden.md)、[备份目录在容器可写层](docs/pitfalls/backup-dir-container-layer.md)。
> 以下 14 条是设计期预判，逐条在对应里程碑验证；验证后若真发生，迁成 `kind: pitfall` 页。

### 1. Obsidian 特殊语法被编辑器破坏
- **风险**：md 含 frontmatter、`[[]]`、callout（`> [!note]`）、`==高亮==`、内嵌 LaTeX。若编辑/保存时做任何"规范化"重写，会毁掉整个库。
- **对策**：编辑视图 = 纯文本原样保存（不 WYSIWYG）；渲染只发生在阅读视图；保存逻辑对内容零改写。测试用例锁死「读入 → 写出 → 字节一致」。

### 2. 中文全文检索命中率差
- **风险**：SQLite FTS5 默认 unicode61 tokenizer 对中文按字切分，搜"分词"可能搜不到"分词方案"中的连续词，且无词义。
- **对策**：jieba 分词后入库（内容存一份分词串 + 保留原文做高亮）；检索时同样分词；`fts5` 用 `tokenize='unicode61'` + 自定义预分词。用例：搜「docker」命中 "Docker 部署"，搜「分词」命中 "中文分词方案"。

### 3. 容器写权限（PUID/PGID）
- **风险**：容器内非 root 用户与宿主机 uid 不一致 → vault 写入"权限拒绝"。
- **对策**：支持 `PUID/PGID` 环境变量切换运行用户；Linux 部署文档明确说明 `id -u` 步骤。测试：以非 root 用户写入挂载目录。

### 4. watchdog 事件风暴
- **风险**：大库首次启动时文件系统事件堆积，或 Obsidian 批量保存触发大量事件 → 索引疯狂重建。
- **对策**：debounce（默认 2s）+ 每文件去重（按 mtime+size 判断是否真变更）+ 增量队列上限。

### 5. Agent 误操作破坏笔记
- **风险**：LLM 生成的写入内容可能有误（删错段落、截断文件、编码混乱）。
- **对策**：写前强制备份到 `data/backups/`；写操作必须用户确认（SSE `tool` 事件 + `/api/agent/confirm`）；`MAX_FILE_BYTES` 以上禁止重写；禁写 `.obsidian/` 等目录。测试：模拟工具调用全链路。

### 6. 编码与换行符（Windows 历史文件）
- **风险**：部分 md 可能是 GBK / UTF-8 带 BOM；LF/CRLF 混用。读错乱码，写错破坏全文。
- **对策**：读取用 `utf-8-sig`（自动去 BOM）→ 解码失败回退 GBK；**写入恒为 UTF-8 无 BOM**，换行保留原文件风格（检测首个换行符）。测试：造 GBK/带 BOM/CRLF 三种 fixture。

### 7. 路径穿越（安全）
- **风险**：API 参数 `path=../../etc/passwd` 越界读、写任意文件。
- **对策**：后端统一 `core/vault.py` 的 `resolve_safe_path()`，`pathlib.resolve()` 后必须仍位于 vault 根内；拒绝绝对路径/盘符/`..`；API 层一律走该校验函数。测试：路径穿越用例必须覆盖。

### 8. markdown 渲染库对 Obsidian 语法支持不全
- **风险**：渲染库默认不支持 callout / wikilink / 高亮 / 嵌入。
- **对策**：直接用 `@quartz-community/obsidian-flavored-markdown`（Quartz 官方插件包，remark 生态）+ Mermaid 懒加载。阅读视图 CSS 尽量贴近 Obsidian 观感（深色/浅色跟随）。

### 9. LLM API key 泄漏
- **风险**：key 写进代码 / 镜像 / 前端 bundle。
- **对策**：key 只进 `.env`（compose `env_file`）；前端不接触 key（Agent 调用全在后端）；日志脱敏（`LOG_LEVEL=debug` 时 key 打码）。检查项：`docker history` 无 key、`grep -r key frontend/dist` 为空。

### 10. 大库全量索引慢 / 中断
- **风险**：数万文件首次索引分钟级，中途崩溃则白干。
- **对策**：分批（`INDEX_BATCH_SIZE`）+ 事务提交 + 断点续传（记录已索引文件 mtime 快照，重启后跳过未变更文件）；进度经 `/api/index/status` 上报。

### 11. 备份目录放错位置（自我递归/污染）
- **风险**：备份目录若建在 vault 内部，会被索引、被下一个快照再次备份、甚至被"整库恢复"覆盖自身 → 备份链断裂。
- **对策**：强制 `BACKUP_DIR` 位于 vault 之外（默认 `{项目根}/backups`，Docker 内 `/app/backups`）；启动时校验若在 vault 内直接报错退出；`IGNORE_DIRS` 永远包含备份目录。测试：误配置在 vault 内 → 启动失败提示。

### 12. 快照一致性（文件写入中）
- **风险**：快照扫描时 Obsidian/用户正在写文件 → 快照里出现半截文件。
- **对策**：快照对单个文件先复制到临时再置位（或对 >1MB 文件做双读校验）；失败重试 3 次仍不一致则跳过并记 warning。测试：快照过程中并发修改文件。

### 13. 硬链接增量在跨卷/部分文件系统失效
- **风险**：NTFS/APFS/ext4 支持硬链接，但 FAT32/exFAT、跨 volume 挂载时硬链接会失败或静默复制。
- **对策**：`os.link` 失败自动降级为复制；快照 manifest 记录"链接/复制"方式，校验时按 manifest 处理。测试：临时目录用不支持硬链接的挂载点（或 mock link 抛错）验证降级。

### 14. 整库恢复误操作
- **风险**：恢复方向反了 / 选错快照 / 恢复中中断 → vault 数据比恢复前更糟。
- **对策**：恢复前**强制先建"恢复前快照"**；双确认（UI 输入 `RESTORE` 确认码）；恢复期间服务进入只读模式；支持恢复任务中断后的继续/回滚。测试：恢复流程全链路 + 中断恢复。

## 相关文档

- [README](README.md) ｜ [CHANGELOG](CHANGELOG.md)
- [docs/02-架构设计.md](docs/02-架构设计.md) ｜ [docs/08-踩坑记录.md](docs/08-踩坑记录.md)
- [docs/07-更新日志.md](docs/07-更新日志.md)（原始逐条记录）
