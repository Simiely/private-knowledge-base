# CHANGELOG

版本号遵循语义化版本；未发布内容记在 `Unreleased`，发布时移入具体版本。
逐条原始记录见 [`docs/07-更新日志.md`](docs/07-更新日志.md)，本文件只做摘要。

## Unreleased

### 2026-11-02 · 质量门禁（R6）✅

- 修复 `mypy --strict` 10 个错误：`semantic.py` 的 `array` 补 `array[float]` 泛型、`indexer/service.py` 可选后端方法改用 `cast` 收窄、`vault.py` 的 observer 统一标注 `BaseObserver`
- 新增 `scripts/check.sh`（Linux/CI）与 `scripts/check.ps1`（Windows），一条命令跑 ruff → mypy → pytest，任一失败即非零退出
- 修复后台重建线程未回收：`POST /api/index/rebuild` 与切换库触发的后台重建统一改走 `IndexService.start_rebuild()`，关停时 `shutdown()` 先 join 再关 SQLite——消除 `closed database` 告警与跨线程 close 崩溃风险
- 修复 Linux CI 下 `mypy` 报 `ctypes.windll` / `os.startfile` 不存在：Windows 专有属性改用 `getattr(..., None)` 兜底，Windows/Linux 两种 typeshed 都能通过
- 实测：`ruff` / `mypy` 0 错误，`pytest` **173 passed**（新增后台重建关闭回归用例）

### 2026-11-02 · 版本恢复 UI + 语义检索（P4 补完 / P6）✅

- **P4 补完**：设置页新增「备份与版本」面板（立即备份 / 快照列表 / 整库恢复需输入 RESTORE / 删除）；阅读页新增「版本历史」弹窗，可恢复到任一快照或写前备份
- **P6 语义检索**：新增 `core/semantic.py`（fastembed + `BAAI/bge-small-zh-v1.5`，CPU 上 634 篇约 21s 建完，512 维）；向量存 `{data}/vectors.db`，不引入 numpy；查询用 `query_embed` 加检索指令前缀
- **融合排序**：关键词与向量用 RRF（k=60，语义权重 1.5）合并——自然语言提问（「宝宝辅食怎么吃」）压过「怎么/什么」这类通用词的命中
- **增量维护**：编辑/新建/删除笔记时同步更新该篇向量；启动时仅在向量数与索引文档数不一致时才全量重建
- **可选依赖**：`pyproject` 增加 `[semantic]` extra；Dockerfile 用 `INSTALL_SEMANTIC` 构建参数（默认不装，镜像不膨胀）；未安装/模型下载失败自动降级为关键词检索
- **API**：`GET /api/semantic/status`、`POST /api/semantic/rebuild`
- 实测：真实库 634 篇，搜索「宝宝辅食」「手机照片备份」「成都周边一日游」Top3 均命中预期；查询耗时 30–50ms（模型首次加载除外）
- 测试：`ruff` 全通过；`pytest` **172 passed**

### 2026-11-01 · 私有知识库改造（P0–P5）✅

**前端整体重写为搜索优先界面，不再模仿 Obsidian，移除 AI 对话框。**

- P0 安全：`AUTH_TOKEN` 未配置时 503 拒绝服务；登录口令 → HttpOnly Cookie + `X-Auth-Token` 双通道；CORS 默认关闭（`CORS_ORIGINS` 白名单）；`/api/settings/*`（目录浏览/切换 vault）仅在 `ENABLE_LOCAL_SETTINGS=true` 时注册
- P1 搜索：OR 模式（原词 OR 优先，零结果才展开同义词/拼音/拼音前缀）；FTS5 增加 `doc_id UNINDEXED` 与 `pinyin` 列（旧库自动重建）；`list_tags`、`by-id` 接口；`rapidfuzz` 错字兜底
- P2 MCP：新增 `app/mcp/server.py`（Streamable HTTP + Bearer），7 个只读工具 `search_notes / read_note / read_note_by_id / read_section / list_tags / related_notes / get_note_by_path`，全部走 Web API，不直连 SQLite
- P3 前端：搜索框自动聚焦 + 220ms 防抖；最近打开 / 常用标签首页；结果卡片；独立阅读页（wikilink 可跳转）与编辑页；设置页展示索引状态与 MCP 连接信息
- P4 附件与导出：`/api/vault/attachment` 白名单下载（防同源 HTML XSS）；`/api/export` 整库 ZIP
- P5 部署：`docker-compose.yml` 重写为 web + mcp + caddy，非 root UID 1000；`deploy/Caddyfile` 内部 TLS；新增 `docs/MCP接入.md`、`docs/部署-Windows.md`
- 修复：备份快照 manifest 读取竞态（JSON 解析失败按“创建中”跳过）；watcher 增加 `WATCH_POLLING` 轮询兜底
- 测试：`ruff check app tests` 全通过；`pytest` **167 passed**；浏览器实测登录 / 搜索 / 阅读 / 编辑保存全通过
- 未验证：当前机器无 Docker/WSL2，`docker compose up` 未实机跑

### 2026-08-14 · 修复与平台优化 ✅

- 修复 CI 构建失败：test job 补 `setup-node` + `npm ci && npm run build`；`dist` 缺失时相关用例 `pytest.skip`
- Docker 磁盘过滤：容器内「切换笔记库」只展示 bind 进来的挂载盘（`/vault`、`/data`、额外挂载），不再列出容器内部目录
- 备份目录落挂载盘：`docker-compose.yml` 增加 `BACKUP_DIR=/data/backups`，避免容器重建即丢
- 文档同步（README / 04 配置 / 03 快速开始 / `.env.example`）；全量 `pytest` 156 passed

### 2026-08-02 · 模块化 S25 ✅

- `App.vue` 内联逻辑下沉为 `useHashRouter` / `useVaultSwitcher` / `useCreateDoc`（410→316 行）
- `md.js` 渲染与 DOM 增强分离（`mdEnhance.js`）；`DocView` 的 TOC 抽成 `useToc.js`
- 清理误留的临时脚本；回归验证文档打开 / hash 路由 / TOC 高亮 / 备份 tab 全通过

### 2026-08-01 · 备份管理 ✅

- 默认备份目录改为项目根 `backups/`，Docker 里挂载到 `/app/backups`
- 删除快照改异步：`DELETE` 立即返回 202，后台清理，前端 3s 轮询
- 自动备份间隔默认 30 分钟（可调 1–1440）

## 0.1.0 - 待发布（首个 MVP）

- 里程碑 M0–M6 已落地：Docker 骨架 / Vault 核心 / FTS5 + jieba 检索 / 四路由 API / 前端四视图 / Agent（工具 + HITL + safety）/ 测试补全
- 发布前待办：镜像真机验证（沙箱无 docker，本地未验）、发布说明整理、`pyproject` 版本与本文档对齐

## 相关文档

- [README](README.md) ｜ [DEVELOPMENT](DEVELOPMENT.md) ｜ [AGENTS](AGENTS.md)
- [docs/07-更新日志.md](docs/07-更新日志.md)（原始逐条记录）
