# 05 - API 参考

> 后端 REST API 说明。框架为 FastAPI，启动后亦可访问 `http://localhost:8080/docs` 查看自动生成的交互式文档（Swagger UI）。
> 若配置了 `AUTH_TOKEN`，所有请求需带请求头 `X-Auth-Token: <token>`。

---

## 1. 通用约定

- Base URL：`http://<host>:<port>/api`
- 请求/响应：JSON（`Content-Type: application/json`）
- 错误格式：`{ "detail": "错误信息" }`，HTTP 状态码见各端点
- 时间格式：ISO 8601（如 `2026-07-31T21:00:00+08:00`）
- 文件路径一律使用 vault 内**相对路径**，分隔符 `/`，如 `Projects/Obsidian/插件开发.md`

## 2. 端点总览

| 方法 | 路径 | 用途 | 状态码 |
|---|---|---|---|
| GET | `/api/vault/tree` | 获取目录树 | 200 |
| GET | `/api/vault/file` | 读取文件内容 | 200 / 404 / 422 |
| PUT | `/api/vault/file` | 写入文件 | 200 / 403 / 404 / 422 |
| POST | `/api/vault/file` | 新建文件 | 201 / 409 / 422 |
| DELETE | `/api/vault/file` | 删除文件（进回收站语义需二次确认） | 200 / 404 |
| GET | `/api/vault/meta` | 文件元信息（大小/时间/frontmatter） | 200 / 404 |
| GET | `/api/search` | 全文检索 | 200 |
| GET | `/api/index/status` | 索引状态与进度 | 200 |
| POST | `/api/index/rebuild` | 触发全量重建 | 202 |
| GET | `/api/agent/session` | 当前会话历史 | 200 |
| POST | `/api/agent/chat` | 发送 Agent 指令（SSE 流式回复） | 200 / 401 |
| POST | `/api/agent/confirm` | 确认待执行的写操作（写入生效） | 200 |
| POST | `/api/agent/cancel` | 取消待执行的写操作 | 200 |
| GET | `/api/backup/list` | 快照列表（含保留策略状态） | 200 |
| POST | `/api/backup/now` | 立即创建整库快照 | 202 |
| GET | `/api/backup/status` | 当前备份任务进度 | 200 |
| GET | `/api/backup/history` | 单文件版本历史 | 200 |
| POST | `/api/backup/restore-file` | 恢复单个文件到指定版本 | 200 / 404 |
| POST | `/api/backup/restore` | 整库恢复（危险，需确认码） | 202 |
| DELETE | `/api/backup/{id}` | 删除指定快照 | 200 / 404 |

## 3. 端点详解

### 3.1 目录树

```
GET /api/vault/tree?depth=3
```
响应：

```json
{
  "root": [
    {
      "name": "Projects",
      "path": "Projects",
      "type": "dir",
      "children": [
        { "name": "插件开发.md", "path": "Projects/插件开发.md", "type": "file", "size": 2048,
          "mtime": "2026-07-31T21:00:00+08:00", "tags": ["obsidian", "dev"] }
      ]
    },
    { "name": "日记.md", "path": "日记.md", "type": "file", "size": 512, "mtime": "2026-07-31T20:00:00+08:00" }
  ]
}
```

### 3.2 读取文件

```
GET /api/vault/file?path=Projects/插件开发.md
```
响应：`{ "path": "...", "content": "...原始 md 文本...", "meta": { "size": 2048, "mtime": "...", "frontmatter": {...} } }`

### 3.3 写入文件

```
PUT /api/vault/file
Body: { "path": "Projects/插件开发.md", "content": "新的原始 md 文本" }
```
写入为**原子操作**（临时文件 + rename），成功后触发该文件增量重索引。
- 403：路径在白名单外（如 `.obsidian/`）或超过 `MAX_FILE_BYTES`（Agent 重写被拒）
- 422：路径非法（`..`、绝对路径、非 `.md`）

### 3.4 全文检索

```
GET /api/search?q=中文分词&page=1&pageSize=20
```
响应：

```json
{
  "total": 12, "page": 1, "pageSize": 20,
  "results": [
    {
      "path": "Projects/检索方案.md",
      "title": "检索方案",
      "score": 0.98,
      "snippets": [
        { "text": "…中文<mark>分词</mark>方案对比…", "offset": 128, "length": 60 }
      ],
      "tags": ["search"]
    }
  ]
}
```
前端点击结果 → 打开文档并滚动到第一个 `offset` 位置（后端可附 `?locate=path&pos=128`）。

### 3.5 索引状态

```
GET /api/index/status
```
响应：`{ "state": "building" | "ready", "totalFiles": 12345, "indexed": 12000, "percent": 97.2, "lastFullAt": "...", "lastDeltaAt": "...", "backend": "fts5" }`

### 3.6 Agent 对话（SSE 流式）

```
POST /api/agent/chat
Body: { "message": "在今天的日记里追加：- [ ] 复习 Docker 网络", "contextPath": "日记.md" }
```
响应：`text/event-stream`，事件类型：

| 事件 | 数据 | 说明 |
|---|---|---|
| `text` | `{ "delta": "…" }` | LLM 回复增量 |
| `tool` | `{ "name": "write_file", "args": {...}, "diff": "...", "backupPath": "..." }` | Agent 请求执行写操作（**需用户确认**） |
| `confirm_required` | `{}` | 前端弹出 diff 确认框，用户确认后调 `/api/agent/confirm` |
| `done` | `{ "summary": "…" }` | 本轮结束 |
| `error` | `{ "message": "…" }` | 出错 |

> **安全设计**：所有写操作（`write_file`/`delete_file`）一律先返回 `tool` 事件等待用户确认，Agent 无法绕过确认直接落盘。确认接口需携带本轮 `sessionId` 与 `toolId`。

### 3.7 备份快照

```
GET /api/backup/list
```
响应：

```json
{
  "snapshots": [
    { "id": "snap-20260731-0200", "createdAt": "2026-07-31T02:00:00+08:00",
      "files": 12345, "sizeBytes": 482000000, "type": "scheduled", "verifyStatus": "ok" }
  ],
  "retention": "7d,4w,3m", "nextScheduledAt": "2026-08-01T02:00:00+08:00"
}
```

```
POST /api/backup/now
```
- 后台执行，202 + `{ "taskId": "...", "snapshotId": "..." }`；进度查 `/api/backup/status`。

### 3.8 单文件版本历史与恢复

```
GET /api/backup/history?path=Projects/插件开发.md
```
响应：

```json
{ "versions": [
  { "snapshotId": "snap-20260731-0200", "at": "2026-07-31T02:00:00+08:00",
    "size": 2048, "source": "snapshot" },
  { "snapshotId": "write-backup", "at": "2026-07-31T01:30:00+08:00",
    "size": 2030, "source": "pre-write" }
]}
```

```
POST /api/backup/restore-file
Body: { "path": "Projects/插件开发.md", "snapshotId": "snap-20260731-0200" }
```
- 恢复前自动将当前文件再备份一份（pre-restore），保证可回退。
- 404：该版本在指定快照中不存在。

### 3.9 整库恢复（危险操作）

```
POST /api/backup/restore
Body: { "snapshotId": "snap-20260731-0200", "confirmCode": "RESTORE" }
```
- 强制流程：① 先自动创建"恢复前快照"；② 校验 confirmCode 必须为 `RESTORE`；③ 异步执行整库还原。
- 202 + `{ "taskId": "..." }`；执行中服务进入只读模式（写操作返回 409）。

## 4. 路径安全校验规则（后端强制）

1. 解码后使用 `pathlib` 规范化，禁止 `..` 越界到 vault 之外
2. 拒绝绝对路径与盘符（`C:\...`）
3. 写入目标禁止位于 `DISALLOWED_WRITE_DIRS`（`.obsidian/.trash/.git` 等）
4. 只允许 `.md` 扩展名文件写入
