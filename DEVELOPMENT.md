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

### 问题：单条 SQLite 连接跨线程使用导致段错误

**TL;DR**：`sqlite3` 连接不是线程安全的，并发关闭更危险。

- 问题：CI 在 Linux 上偶发段错误；Windows 上并发关闭连接报 access violation
- 根因：同一连接被多个线程共用，且关闭时机与查询竞争
- 解决：每线程独立连接，用完即关；写操作集中到单一执行点
- 预防：任何 `sqlite3.connect` 都不要跨线程传递

### 问题：中文检索偶发「一个词都搜不到」

**TL;DR**：jieba 分出的标点 token 混进 FTS5 MATCH，语义被改写。

- 问题：带连字符或特殊符号的关键词，命中率突然变成 0
- 根因：jieba 把连字符拆成独立标点 token，而 FTS5 MATCH 里某些符号是运算符（如 NOT）
- 解决：分词结果先过滤标点，再拼查询；必要时对 token 加引号
- 预防：分词输出永远不要直接拼进查询串

### 问题：空库统计不是 0 而是「空」

**TL;DR**：FTS5 空表 `count(*)` 返回 NULL。

- 问题：新库首屏统计显示异常或前端拿到 null 崩掉
- 根因：FTS5 对空表的聚合返回 NULL，不是 0
- 解决：查询侧统一 `COALESCE(count(*), 0)`
- 预防：所有 FTS5 聚合都按「可能返回 NULL」处理

### 问题：容器重建后备份全丢

**TL;DR**：默认备份目录在容器可写层。

- 问题：`docker compose down && up` 之后，备份列表空了
- 根因：默认 `{项目根}/backups` 在镜像可写层，容器重建即销毁
- 解决：compose 显式 `BACKUP_DIR=/data/backups`（挂载盘）
- 预防：任何「需要持久化」的路径都要显式落在 volume 上，不依赖默认值

### 问题：干净环境 CI 里首页测试 404

**TL;DR**：前端 `dist` 不入库，测试却依赖它。

- 问题：CI 的 test job 失败，`GET /` 返回 404；build job 被跳过
- 根因：`test_static_index_served` 依赖 `frontend/dist`，而 CI 从不构建前端
- 解决：test job 增加 `setup-node` + `npm ci && npm run build`；`dist` 缺失时该用例 `pytest.skip`
- 预防：测试依赖构建产物时，要么在流水线里构建，要么显式 skip，不要默认它存在

## 相关文档

- [README](README.md) ｜ [CHANGELOG](CHANGELOG.md)
- [docs/02-架构设计.md](docs/02-架构设计.md) ｜ [docs/08-踩坑记录.md](docs/08-踩坑记录.md)
- [docs/07-更新日志.md](docs/07-更新日志.md)（原始逐条记录）
