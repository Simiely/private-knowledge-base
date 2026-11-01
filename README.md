# 私人知识库（obsidian-agent 改造版）

> 单用户的个人知识库 Web 应用：**搜索优先**，中文 / 拼音 / 错字都能模糊定位；网页直接阅读与编辑；本地大模型通过 **MCP** 协议自行检索和读取全文。数据留在你自己的机器上。

---

## 这是什么？

从 `Simiely/obsidian-agent` 后端复用改造而来，前端整体重写。它**不再模仿 Obsidian**，也不再提供 AI 聊天框——它只做三件事：

- 🔍 **快速定位** —— 顶部一个搜索框。支持中文、拼音（`bushu` → 部署）、错字（`docer` → docker）、一句话描述。不需要记文件名。
- 🧠 **语义检索（可选）** —— 本地 CPU 向量模型（bge-small-zh），「手机照片备份到电脑」也能找到 iMazing / GoodSync 这类字面不重合的笔记；与关键词做 RRF 融合排序。
- 📖 **阅读 + 编辑** —— 独立的阅读页和编辑页，Obsidian 语法（frontmatter / `[[]]` 双链 / callout / 高亮 / 表格）正常渲染，附件可下载。
- 🔌 **给本地模型用** —— MCP 只读服务（Streamable HTTP + Bearer），本地模型先 `search_notes` 再 `read_note`，按需精确读取，不会一次性灌满上下文。

另外还有：整库 ZIP 导出、硬链接快照备份（设置页可一键备份/整库恢复/删除）、单篇笔记版本历史与恢复。

不做什么：不做 Obsidian 克隆、不做多用户、不做 AI 对话框、不做数据落盘加密。

---

## 安全模型（先看清）

| 项目 | 现状 |
|---|---|
| 落盘加密 | **无**。数据以明文 Markdown 存放，请自行开启 BitLocker / 文件系统加密 |
| 访问控制 | 登录口令（`AUTH_TOKEN`）→ HttpOnly Cookie；也可用 `X-Auth-Token` 头 |
| 传输加密 | 生产建议前置 Caddy（`deploy/Caddyfile` 已给内部 TLS 配置）或反代 HTTPS |
| MCP | 独立端口 + 独立 `MCP_TOKEN`，默认只监听 `127.0.0.1` |
| 未配口令时 | 直接 **503 拒绝服务**（不再默认放行） |

---

## 快速上手

```bash
# 1. 准备 .env
cp .env.example .env
#    必填：VAULT_PATH（宿主机知识库目录）、AUTH_TOKEN（登录口令）、MCP_TOKEN

# 2. 启动
docker compose up -d

# 3. 打开
#    http://localhost:4329  → 输入访问口令 → 搜索
#    https://localhost:8443 → Caddy 内部 TLS（手机/局域网）
```

详细步骤见 [docs/部署-Windows.md](docs/部署-Windows.md)；本地开发（不用 Docker）见下文「本地开发」。

---

## 本地开发（不用 Docker）

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 后端（Windows PowerShell）
$env:VAULT_PATH="D:\MyVault"
$env:AUTH_TOKEN="test-pass"
.venv\Scripts\python -m uvicorn app.main:app --port 8098

# 前端
cd frontend && npm ci && npm run build     # 构建后由后端同源托管
npm run dev                                # 或开发模式（vite 5173，/api 代理到 8090）
```

MCP 服务单独起：

```bash
$env:MCP_API_BASE="http://127.0.0.1:8098"
$env:MCP_TOKEN="mcp-token"
.venv\Scripts\python -m app.mcp.server     # http://127.0.0.1:8090/mcp
```

---

## 文档导航

| 文档 | 用途 |
|---|---|
| **[docs/部署-Windows.md](docs/部署-Windows.md)** | Windows + Docker/WSL2 部署、端口、权限、备份、常见问题 |
| **[docs/MCP接入.md](docs/MCP接入.md)** | MCP 地址、鉴权、工具清单、本地模型客户端配置 |
| **[AGENTS.md](AGENTS.md)** | 技术栈、关键坑、代码约定、常用命令（改代码前必读） |
| **[CHANGELOG.md](CHANGELOG.md)** | 版本摘要 |
| **[docs/01-功能说明.md](docs/01-功能说明.md)** | 原项目功能基线（部分已被新前端取代） |
| **[docs/02-架构设计.md](docs/02-架构设计.md)** | 模块划分、分层、数据流 |
| **[docs/08-踩坑记录.md](docs/08-踩坑记录.md)** | 实测坑：索引 / 部署 / 前端 |

---

## 项目结构

```
obsidian-agent/
├── app/
│   ├── main.py             # create_app：服务装配 + 路由 + 生命周期
│   ├── config.py           # pydantic-settings（含 AUTH_TOKEN / CORS / watcher 策略）
│   ├── core/
│   │   ├── vault.py        # 路径白名单、原子写、附件白名单、watcher
│   │   ├── search_text.py  # 拼音变体 / 同义词扩展 / doc_id
│   │   ├── indexer/        # base（抽象）→ fts5（FTS5 + jieba + 拼音列）→ service
│   │   ├── search.py       # 搜索编排：原词 OR 优先 → 无结果才拼音/同义词 → rapidfuzz 兜底
│   │   ├── semantic.py     # 可选语义检索：fastembed 向量 + SQLite + RRF 融合
│   │   ├── backup/         # 硬链接快照 / 恢复 / 保留策略
│   │   └── runtime.py      # 服务构建与热切换
│   ├── api/                # routes_auth / routes_vault / routes_search / routes_export /
│   │                       # routes_backup / routes_semantic / deps
│   └── mcp/server.py       # MCP 只读服务（调用 Web API，不开 SQLite）
├── frontend/src/
│   ├── App.vue             # 搜索 / 阅读 / 编辑 / 设置 四视图
│   ├── md.js               # Obsidian 方言渲染 + 附件链接重写
│   └── styles.css          # 暗色默认、移动端单列
├── deploy/Caddyfile        # 内部 TLS 反代
├── docker-compose.yml      # web + mcp + caddy
└── tests/                  # 167 个用例（含拼音/错字/MCP/认证/导出）
```

---

## 状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| P0 | 鉴权、CORS 收紧、危险路由下线、附件白名单 | ✅ |
| P1 | 模糊搜索：OR 优先 / 拼音 / 错字 / 同义词 | ✅ |
| P2 | MCP 只读服务（7 个工具） | ✅ |
| P3 | 搜索优先新前端（阅读页 / 编辑页 / 设置页） | ✅ |
| P4 | 附件下载 / 整库导出 / 快照备份与版本恢复 UI | ✅ |
| P5 | Docker + Caddy 部署文件 | ✅ 文件就绪；**当前机器无 Docker，未实机验证** |
| P6 | 语义检索（bge-small-zh 向量 + RRF 融合） | ✅ 本机实测通过 |

---

## License

MIT（沿用原项目）
