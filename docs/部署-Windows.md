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

- 容器入口以 root 启动：先对 `/data`、`/vault` 执行 `chown -R appuser:appuser`，再用 `gosu` 降权到 appuser（UID 1000）运行主进程（同 Radicale 的做法）。
- 因此 USB/NTFS 等挂载目录归 root 时，一般不需要再手动改 `user` 或 `chown`。
- 如果目录在 **exFAT/FAT32** 上，`chown` 本身无效，入口会忽略失败继续启动；此时若仍报 `unable to open database file` / 无法写 vault：
  1. 临时把 compose 的 `user` 设为 `"0:0"` 验证；
  2. 长期方案：挂载时指定属主（`uid=1000,gid=1000`），或把 `/data` 放到内置 ext4 盘。
- 目录很大时 `chown -R /vault` 会拖慢启动，可用 `FIX_OWNER_DIRS=/data` 只修数据目录。

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
