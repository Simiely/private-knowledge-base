"""统一 API Schemas：请求/响应模型集中定义（重构计划 R1）。

原则：
- 所有路由的请求体（Body）与响应（response_model）模型都在此定义，
  不再内联在 routes 中，便于跨端对齐与 OpenAPI 文档生成。
- 保持字段与历史 API 完全一致（兼容前端，不破坏现有调用）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------- 通用 ----------


class PathResult(BaseModel):
    """写/删操作的标准返回。"""

    path: str
    ok: bool = True


# ---------- vault: 文件读写 ----------


class FileWrite(BaseModel):
    """写入已有文件（不存在则 404）。"""

    path: str
    content: str


class FileCreate(BaseModel):
    """新建文件（已存在则 409）。"""

    path: str
    content: str = ""


class FileMetaOut(BaseModel):
    """文件元信息。"""

    size: int
    mtime: float
    encoding: str
    newline: str


class FileReadOut(BaseModel):
    """读文件响应。"""

    path: str
    content: str
    meta: FileMetaOut


class TreeNode(BaseModel):
    """目录树节点。dir 无 size/mtime；file 无 children。"""

    name: str
    path: str
    type: Literal["dir", "file"]
    size: int | None = None
    mtime: float | None = None
    children: list[TreeNode] = Field(default_factory=list)


# ---------- vault: 元信息 ----------


class FileMetaOutFlat(BaseModel):
    """GET /api/vault/meta 响应（扁平结构，兼容前端）。"""

    path: str
    size: int
    mtime: float
    encoding: str
    newline: str


# ---------- search ----------


class SearchSnippet(BaseModel):
    """搜索结果片段（含高亮定位信息）。"""

    text: str
    offset: int = 0
    length: int = 0
    hitWords: list[str] = Field(default_factory=list)


class SearchHit(BaseModel):
    """单条搜索结果。"""

    doc_id: str = ""
    path: str
    title: str = ""
    score: float | None = None
    snippets: list[SearchSnippet] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SearchOut(BaseModel):
    """搜索响应（含分页字段，兼容前端）。"""

    total: int
    page: int = 1
    pageSize: int = 20
    results: list[SearchHit] = Field(default_factory=list)


# ---------- backup ----------


class RestoreFileBody(BaseModel):
    """单文件恢复请求。"""

    path: str
    snapshotId: str


class RestoreAllBody(BaseModel):
    """整库恢复请求（需确认码）。"""

    snapshotId: str
    confirmCode: str


class BackupNowBody(BaseModel):
    """立即备份请求。reason: manual（手动，默认）/ auto（前端活跃式自动备份）。"""

    reason: str = "manual"


# ---------- agent ----------


class ChatBody(BaseModel):
    """Agent 对话请求。"""

    message: str
    contextPath: str | None = None
    sessionId: str | None = None


class ConfirmBody(BaseModel):
    """Agent 操作确认/取消请求。"""

    sessionId: str
    opId: str


# ---------- settings ----------


class VaultPathBody(BaseModel):
    """切换 vault / 备份目录的路径请求。"""

    path: str


class AutoBackupBody(BaseModel):
    """活跃式自动备份设置（间隔分钟 + 开关，均可选——只更新传入的键）。"""

    intervalMinutes: int | None = None
    enabled: bool | None = None


# ---------- settings / index / filesystem 响应 ----------


class VaultInfoOut(BaseModel):
    """GET /api/settings/vault 响应。"""

    path: str
    dataDir: str


class BackupDirOut(BaseModel):
    """GET /api/settings/backupdir 响应。"""

    path: str
    enabled: bool
    retention: str


class AutoBackupOut(BaseModel):
    """GET /api/settings/autobackup 响应。"""

    intervalMinutes: int
    enabled: bool


class IndexStatusOut(BaseModel):
    """GET /api/index/status 响应。"""

    state: str
    totalFiles: int = 0
    vaultFiles: int = 0  # vault 全部文件数（含附件，供侧栏状态显示）
    lastFullAt: str | None = None
    backend: str | None = None


class OpOkOut(BaseModel):
    """通用操作成功响应（ok + 可选字段）。"""

    ok: bool = True
    message: str | None = None


# ---------- backup 响应 ----------


class SnapshotOut(BaseModel):
    """快照摘要（list_snapshots 条目）。"""

    id: str
    createdAt: str
    reason: str
    files: int = 0
    bytes: int = 0
    skipped: list[str] = Field(default_factory=list)
    verify: str = "pending"


class RunnerStatusOut(BaseModel):
    """GET /api/backup/status 响应。"""

    running: bool
    kind: str | None = None
    lastAt: str | None = None
    lastReason: str | None = None
    error: str | None = None
    snapshots: int = 0


class RetentionOut(BaseModel):
    """保留策略对象（前端按 days/weeks/months 展示）。"""

    days: int
    weeks: int
    months: int


class BackupListOut(BaseModel):
    """GET /api/backup/list 响应。"""

    snapshots: list[SnapshotOut] = Field(default_factory=list)
    retention: RetentionOut | None = None
    runner: RunnerStatusOut | None = None


class BackupNowOut(BaseModel):
    """POST /api/backup/now 响应。"""

    ok: bool
    taskId: str
    reason: str = "manual"


class VerifyOut(BaseModel):
    """POST /api/backup/verify/{id} 响应。"""

    snapshotId: str
    ok: bool
    detail: str = ""


class SnapshotFilesOut(BaseModel):
    """GET /api/backup/files 响应。"""

    snapshotId: str
    files: list[str] = Field(default_factory=list)


class DeleteOut(BaseModel):
    """DELETE /api/backup/{id} 响应（异步删除）。"""

    ok: bool
    deleting: str
    async_: bool = Field(default=True, alias="async")

    model_config = {"populate_by_name": True}
