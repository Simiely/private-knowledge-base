# MCP 接入指南（本地模型）

本项目的 MCP 服务是**只读**知识库接口：模型先模糊搜索，再读取全文，不依赖前端对话框。

## 1. 启动

Docker Compose 会同时启动：

- Web 应用：`http://127.0.0.1:4329`
- MCP 服务：`http://127.0.0.1:8090/mcp`

必须设置两个 token：

```bash
# .env
AUTH_TOKEN=网页/API 的访问口令
MCP_TOKEN=模型连接 MCP 的独立口令
```

`MCP_TOKEN` 为空时 MCP 服务拒绝启动。

## 2. 连接信息

| 项 | 值 |
| --- | --- |
| 传输 | Streamable HTTP |
| URL | `http://127.0.0.1:8090/mcp` |
| 鉴权 | `Authorization: Bearer <MCP_TOKEN>` |
| 监听 | 默认只监听本机；远程用 Tailscale |

如果客户端不支持 HTTP，可用 stdio 桥接（如 `mcp-remote` / `mcp-proxy`）把 stdio 转到上面的 URL。

## 3. 工具列表

| 工具 | 用途 | 关键参数 |
| --- | --- | --- |
| `search_notes` | 模糊/关键词检索 | `query`、`limit`、`mode=or/and` |
| `read_note` | 按路径读全文 | `path`、`offset`、`max_chars` |
| `read_note_by_id` | 按 `doc_id` 读全文 | `doc_id` |
| `read_section` | 按标题读一节 | `path`、`heading` |
| `list_tags` | 列出标签 | 无 |
| `related_notes` | 相关笔记 | `path`、`limit` |
| `get_note_by_path` | 路径直读 | `path` |

## 4. 推荐调用流程

```text
用户问题
  → search_notes(query, limit=5)
  → 选择最相关的 doc_id/path
  → read_note(path, offset=0, max_chars=20000)
  → 若未读完：用 offset 继续读
  → 回答并引用 path/title
```

工具描述已明确要求：**回答前必须读取全文，不能只看搜索片段**。

## 5. 客户端配置示例

不同客户端的配置字段不同，核心是：

```json
{
  "mcpServers": {
    "obsidian-knowledge": {
      "url": "http://127.0.0.1:8090/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_TOKEN>"
      }
    }
  }
}
```

如果客户端只接受 stdio，使用桥接：

```json
{
  "mcpServers": {
    "obsidian-knowledge": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://127.0.0.1:8090/mcp",
        "--header",
        "Authorization: Bearer <MCP_TOKEN>"
      ]
    }
  }
}
```

## 6. 安全注意

- MCP 只读，不提供写入工具。
- `MCP_TOKEN` 与 `AUTH_TOKEN` 分开；不要写进前端。
- 不要把 8090 暴露到公网；远程用 Tailscale。
- 数据本身不加密；磁盘请开 BitLocker。
- 大文件按 `offset/max_chars` 分块读，避免撑爆模型上下文。
