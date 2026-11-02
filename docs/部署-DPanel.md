# DPanel + USB 部署

> 适用场景：Linux 宿主机 + DPanel（直接粘贴 compose 文本）+ 外置 USB 盘放笔记库。
> 镜像由 GitHub Actions 构建并推到 GHCR，部署端只拉镜像、不本地构建。

---

## 1. 目录布局

```
/mnt/usb2/Configs/obsidian-agent/
├── vault/        # 笔记库（Obsidian 目录，可含子目录/附件）
└── data/         # 索引 / 向量 / 备份；必须与 vault 平级，不能嵌进 vault
```

建目录：

```bash
mkdir -p /mnt/usb2/Configs/obsidian-agent/{vault,data}
```

宿主机目录归 root 也没关系：容器入口会以 root 启动并 `chown` 后再降权（见第 4 节）。

---

## 2. DPanel Compose（完整版）

镜像 `ghcr.io/simiely/private-knowledge-base:latest` 为公开包，可直接匿名拉取。

```yaml
services:
  web:
    image: ghcr.io/simiely/private-knowledge-base:latest
    container_name: obsidian-knowledge
    restart: unless-stopped
    ports:
      - "4329:8080"
    environment:
      - VAULT_PATH=/vault
      - DATA_DIR=/data
      - BACKUP_DIR=/data/backups
      - AUTH_TOKEN=请改成你的网页访问口令
      - AUTH_DISABLED=false
      - COOKIE_SECURE=false
      - CORS_ORIGINS=
      - ENABLE_LOCAL_SETTINGS=false
      - WATCH_ENABLED=true
      - WATCH_POLLING=true
      - SEMANTIC_ENABLED=false
      - HF_ENDPOINT=https://hf-mirror.com
      - TZ=Asia/Shanghai
    volumes:
      - /mnt/usb2/Configs/obsidian-agent/vault:/vault
      - /mnt/usb2/Configs/obsidian-agent/data:/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

  mcp:
    image: ghcr.io/simiely/private-knowledge-base:latest
    container_name: obsidian-knowledge-mcp
    restart: unless-stopped
    command: ["python", "-m", "app.mcp.server"]
    ports:
      - "127.0.0.1:8090:8090"
    environment:
      - MCP_API_BASE=http://web:8080
      - AUTH_TOKEN=请改成你的网页访问口令
      - MCP_TOKEN=请改成与网页口令不同的 MCP 口令
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8090
    depends_on:
      - web
```

说明：

- **不要**再写 `user: "1000:1000"`。写了会跳过入口里的 chown，回到“UID 1000 无写权限”的老问题。
- `SEMANTIC_ENABLED=false` 对应 CI 默认构建的精简镜像（不含 fastembed）。需要语义检索时把 [.github/workflows/build.yml](../.github/workflows/build.yml) 里 `INSTALL_SEMANTIC=false` 改成 `true` 重跑 Actions，再改这里为 `true`。
- 不用 MCP 时整段删除；MCP 只监听宿主机本地，局域网访问需改端口绑定。
- DPanel 若用 HTTPS 域名反代，把 `COOKIE_SECURE` 设为 `true`。

---

## 3. 启动与验证

DPanel 里粘贴 compose → 拉取镜像 → 启动。然后在**宿主机**（不是 DPanel 的 shell 容器）验证：

```bash
curl -i http://127.0.0.1:4329/
curl -s http://127.0.0.1:4329/api/health
docker logs --tail 40 obsidian-knowledge
```

期望：

- `/` 返回 200 `text/html`（Vue 页面）
- `/api/health` 返回 `{"status":"ok","version":"0.1.0",...}`
- 日志没有 `应用初始化失败`

首次启动会在后台索引整库，`/api/index/status` 的 `state` 变 `ready` 后搜索才完整。

---

## 4. 权限模型（为什么不需要手动 chown）

镜像入口 [docker-entrypoint.sh](../docker-entrypoint.sh)：

1. 以 root 启动；
2. 对 `/data`、`/vault` 执行 `chown -R appuser:appuser`；
3. 用 `gosu` 降权到 appuser（UID 1000）启动 uvicorn。

因此 USB 盘、NTFS、Docker 自动创建的目录归 root 时，SQLite 也能正常建 `index.db`。

例外：

- **exFAT/FAT32** 不支持 `chown`，入口会忽略失败继续启动；若仍报 `unable to open database file`：
  1. compose 里临时加 `user: "0:0"` 验证；
  2. 长期方案：重新挂载时指定 `uid=1000,gid=1000`，或把 `/data` 放内置 ext4 盘。
- 笔记库特别大时每次启动 `chown -R /vault` 可能拖慢启动，可设 `FIX_OWNER_DIRS=/data` 只修数据目录。

---

## 5. 关键坑：`data/settings.json` 覆盖 VAULT_PATH

应用启动时会优先读取 `{DATA_DIR}/settings.json`，其中 `vault_path` **覆盖 compose 的环境变量**。

如果这个文件里残留了旧路径（例如 `/vault/baba/light-alchemy-main`），而该目录不存在，应用会降级为占位应用：

- `/api/health` → 500
- 其他所有路径（含 `/`）→ `{"detail":"Not Found"}`

处理：

```bash
cat /mnt/usb2/Configs/obsidian-agent/data/settings.json
rm /mnt/usb2/Configs/obsidian-agent/data/settings.json   # 改用 compose 的 VAULT_PATH
docker restart obsidian-knowledge
```

`ENABLE_LOCAL_SETTINGS=true` 时网页端“切换笔记库”会写这个文件；生产建议保持 `false`。

---

## 6. 端口与访问

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| Web | `http://<宿主机IP>:4329/` | 搜索 / 阅读 / 编辑 / 设置 |
| MCP | `http://127.0.0.1:8090/mcp` | Streamable HTTP + Bearer；根路径 404 属正常 |
| 前端路由 | `http://<IP>:4329/#/doc/...` | hash 路由，路径里没有 `#` 会 404 JSON |

---

## 7. 更新流程

1. 本地改代码 → push `main`
2. GitHub Actions 自动执行 `test → build & push`，更新 `ghcr.io/simiely/private-knowledge-base:latest`（另有 `sha-<short>` 标签）
3. 部署端 `docker compose pull && docker compose up -d`，或 DPanel 点“更新/重建”

查看构建：`https://github.com/Simiely/private-knowledge-base/actions`

---

## 8. 排障速查

| 现象 | 根因 / 处理 |
| --- | --- |
| 浏览器 `{"detail":"Not Found"}` | 先看 `/api/health`：500 说明应用降级，查 `docker logs` 的“应用初始化失败”；200 则是访问路径错（用 `/#/`） |
| `unable to open database file` | data 目录不可写；确认入口未被 `user:` 覆盖、USB 文件系统是否支持 chown（见第 4 节） |
| `vault 路径不存在` | `data/settings.json` 旧路径覆盖，见第 5 节 |
| GHCR `unauthorized` | 镜像包被改为 private；部署机 `docker login ghcr.io` 或把包改回 public |
| 搜索不更新 | 确认 `WATCH_POLLING=true`，或手动 `POST /api/index/rebuild` |
| `curl 127.0.0.1:4329` 失败 | 你是否在 DPanel 的 shell 容器里执行？那里的 loopback 不是宿主机 |

---

## 9. GHCR 可见性

- 当前 `private-knowledge-base` 包为 **public**，可匿名 pull。
- 若改回 private：部署机执行 `echo <PAT> | docker login ghcr.io -u simiely --password-stdin`（PAT 需 `read:packages`）。
- 个人账号的包可见性**没有 REST API**，只能在网页 `Package settings → Danger Zone → Change visibility` 修改。
