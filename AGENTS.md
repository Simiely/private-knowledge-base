# AGENTS.md · 项目规则

> 📌 **文档基线**：2026-11-03 · 私有知识库改造版 · 搜索优先前端 + MCP + 鉴权 + 语义检索 + 质量门禁 + 容器入口降权
> **更新文档/代码后，请更新此行**（日期 + 版本 + 摘要），并在 CHANGELOG 追加版本

## 技术栈

- 后端：**Python 3.11+ / FastAPI + uvicorn**，`pydantic-settings` 读 `.env`
- 鉴权：口令 → HttpOnly Cookie（`oa_session`）+ `X-Auth-Token` 头双通道；未配 `AUTH_TOKEN` 直接 503
- 索引：**SQLite FTS5 + jieba 预分词** + `pinyin` 列（pypinyin）；`rapidfuzz` 做错字兜底
- 搜索：**原词 OR 优先**，无结果才展开同义词 / 拼音 / 拼音前缀（顺序不能反，否则短拼音会抢结果）
- 本地模型：**MCP 2.x**，`mcp/server.py` 独立进程，只调 Web API，**不直接开 SQLite**
- 语义检索（可选）：**fastembed + bge-small-zh ONNX**，向量存 `{data}/vectors.db`（`array('f')` BLOB，不依赖 numpy），与关键词做 **RRF 融合**（语义权重 1.5）
- 前端：**Vue 3 + Vite**，markdown-it + 自研 Obsidian 方言插件（`frontend/src/md.js`）；无聊天框
- 部署：Docker / compose（web + mcp + caddy），非 root UID 1000；mount `/vault` 与 `/data`

## 关键坑（改代码前必看）

- **SQLite 连接不能跨线程共用**：CI 实测 Linux 段错误；Windows 上并发关闭连接会 access violation → 每线程独立连接，用完即关
- **jieba 分词结果不能直接拼进 FTS5 MATCH**：连字符会被拆成独立标点 token，混入后可能变成 NOT 运算符 → 分词后过滤标点，必要时给 token 加引号
- **FTS5 空表 `count(*)` 返回 NULL 而不是 0** → 一律 `COALESCE(..., 0)`
- **`Path.write_text` 在 Windows 会做 `\n` → `\r\n` 转换** → 需要逐字节一致时用 `newline=""` 或二进制写
- **Docker 里的默认备份目录是容器可写层**，重建容器即丢 → compose 显式 `BACKUP_DIR=/data/backups`
- **`core/` 与 `agent/` 禁止 import FastAPI**：分层单向 `api → agent → core`，否则单测与替换框架都会被绑死
- **前端 dist 不入库**：CI 必须先 `npm ci && npm run build`，否则 `test_static_index_served` 会在干净环境 404
- **FTS5 拼音前缀不能滥用**：`bushu*` 会误命中 `you*` 之类的短前缀 → 拼音只作“原词零结果”后的兜底
- **MCP 不能直连索引库**：SQLite 单写者，MCP 与 Web 抢连接会锁库 → MCP 一律走 HTTP API
- **附件必须白名单 + `FileResponse` 下载**：否则同源 HTML 会在本站上下文执行脚本（XSS）

## 约定

- 中文注释；公共 API 必须写 docstring（含参数），工具 docstring 会被 Pydantic AI 直接当 schema 用
- 提交信息用 `feat(scope) / fix(scope) / docs / test / chore` 前缀
- 任何写操作都经过 `agent/safety.py`：路径必须在 vault 内、禁写 `.obsidian/` 等目录、写前备份
- 新增功能必须有测试；修 bug 先写复现用例
- 未发布内容记 `Unreleased`，发布时才移动为具体版本号

## 常用命令

```bash
# 后端（在 obsidian-agent 根目录）
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
pytest tests/ -q
ruff check app tests

# 前端
cd frontend && npm ci && npm run build

# 部署
docker compose up -d
```

## 详细规则（按需 @引用）

- @docs/02-架构设计.md（分层、模块职责、数据流、选型依据）
- @docs/08-踩坑记录.md（40+ 条实测坑，按索引/部署/Agent/前端分区）
- @docs/部署-DPanel.md（DPanel + USB 部署、GHCR 镜像、入口降权与排障）
- @docs/06-开发指南.md ｜ @docs/04-配置参考.md ｜ @docs/05-API参考.md
