# Windows / Docker 部署

## 1. 前置

- Windows 11 + WSL2 + Docker Desktop
- 虚拟化已开启；Docker Desktop 使用 WSL2 后端
- 建议把 vault 放在 NTFS 盘；`/data` 使用命名卷或独立目录

## 2. 配置

```bash
copy .env.example .env
```

`.env` 至少设置：

```ini
AUTH_TOKEN=你的网页访问口令
MCP_TOKEN=你的模型连接口令
VAULT_HOST_PATH=C:/Users/you/Documents/obsidian/simiely - 隐私
DATA_HOST_PATH=C:/Users/you/Documents/obsidian-agent-data
WATCH_POLLING=true
TZ=Asia/Shanghai
```

注意：

- Compose 路径用**正斜杠**；不要用反斜杠。
- `DATA_HOST_PATH` 不要放在 vault 里面，否则备份/索引会递归。
- `AUTH_TOKEN` 与 `MCP_TOKEN` 必须不同。

## 3. 启动

```bash
docker compose up -d --build
```

入口：

| 服务 | 地址 |
| --- | --- |
| Web（HTTP） | `http://127.0.0.1:4329` |
| Web（HTTPS） | `https://127.0.0.1:8443`（Caddy 自签证书） |
| MCP | `http://127.0.0.1:8090/mcp` |

手机访问用局域网 IP + `8443`，首次需信任 Caddy 内部证书。

## 4. 权限

- 容器以 UID 1000 运行；Windows Docker Desktop 的 bind mount 权限模型不同。
- 如果出现 `attempt to write a readonly database` 或无法写 vault：
  1. 确认 `DATA_HOST_PATH` 可写；
  2. 临时把 compose 的 `user` 改为 `root` 仅用于验证；
  3. 长期仍建议非 root，或改用 WSL2 内的 gocryptfs/卷。

## 5. 文件监听

Windows bind mount 上 inotify 可能收不到宿主 Obsidian 的改动：

- 默认 `WATCH_POLLING=false`；
- 如果宿主改文件后搜索不更新，设 `WATCH_POLLING=true` 重启；
- 轮询间隔由 watchdog 默认值决定，注意大库 CPU 占用。

## 6. 备份与导出

- 备份目录：`/data/backups`，对应宿主 `DATA_HOST_PATH/backups`
- 硬链接失败会自动降级为复制（空间会变大，但可用）
- 网页「设置 → 导出」可下载整库 ZIP

## 7. MCP

见 [MCP接入.md](MCP接入.md)。MCP 只监听 `127.0.0.1:8090`，手机/其他机器通过 Tailscale 访问时再调整绑定地址。

## 8. 常见问题

| 现象 | 处理 |
| --- | --- |
| 页面 401 | 先登录；或检查 `AUTH_TOKEN` |
| 页面 503 | 没配 `AUTH_TOKEN`，且没有 `AUTH_DISABLED=true` |
| 搜索不更新 | 开 `WATCH_POLLING=true`，或手动重建索引 |
| 图片 401 | 确认已登录；图片走 Cookie |
| PDF/PPTX 打不开 | 使用附件路由 `/api/vault/attachment?path=...` |
| MCP 连不上 | 检查 `MCP_TOKEN`、8090 是否监听、`MCP_API_BASE` 是否指向 web |
