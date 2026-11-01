"""应用配置：全部环境变量在 pydantic-settings 中声明，字段名大写即环境变量名。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 核心 ----
    vault_path: Path = Path("/vault")
    port: int = 8080
    data_dir: Path = Path("/data")
    index_backend: str = "fts5"  # fts5 | meili
    meili_url: str = "http://meilisearch:7700"
    meili_master_key: str = ""

    # ---- LLM ----
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.2
    ollama_host: str = "http://host.docker.internal:11434"

    # ---- Vault 行为 ----
    ignore_dirs: str = ".obsidian,.trash,.git,node_modules,.stfolder"
    ignore_files: str = ""
    max_file_bytes: int = 5 * 1024 * 1024
    watch_enabled: bool = True
    watch_debounce_seconds: int = 2
    # Windows bind mount / Docker Desktop 上 inotify 可能收不到宿主事件，改用轮询。
    watch_polling: bool = False

    # ---- 安全 ----
    auth_token: str = ""
    # 默认必须配置 AUTH_TOKEN 才能访问 API；仅本地开发/测试显式关闭。
    auth_disabled: bool = False
    # 允许浏览器跨源访问时填逗号分隔来源；默认空 = 不启用 CORS（同源部署）。
    cors_origins: str = ""
    # 本地开发用的目录浏览/切换 vault/切换备份目录接口；生产默认关闭。
    enable_local_settings: bool = False
    # 通过 HTTPS 访问时置 true，让登录 Cookie 带 Secure。
    cookie_secure: bool = False
    disallowed_write_dirs: str = ".obsidian,.trash,.git"

    # ---- 备份 ----
    backup_enabled: bool = True
    # 默认 {项目根}/backups —— 项目内新目录，Docker 部署时挂载宿主卷到 /app/backups 即可
    backup_dir: Path | None = None
    backup_schedule: str = ""  # cron 定时备份（已废弃，改为前端活跃式自动备份；保留字段兼容旧配置）
    backup_retention: str = "7d,4w,3m"
    backup_max_bytes: int = 10 * 1024 * 1024
    backup_verify: bool = True
    auto_backup_interval_minutes: int = 30  # 活跃式自动备份间隔（默认 30 分钟，可前端修改）
    auto_backup_enabled: bool = True  # 活跃式自动备份开关（前端滑动开关，持久化到 settings.json）

    # ---- 索引性能 ----
    index_batch_size: int = 200
    index_workers: int = 2
    jieba_userdict: str = ""  # jieba 自定义词典路径（如 data/userdict.txt，空 = 不加载）

    # ---- 语义检索（可选）----
    # 依赖 fastembed（pip install .[semantic]）；未安装或模型下载失败时自动降级为关键词检索
    semantic_enabled: bool = False
    semantic_model: str = "BAAI/bge-small-zh-v1.5"
    semantic_cache_dir: str = ""  # 空 = {data_dir}/models
    semantic_max_chars: int = 800  # 每篇参与向量化的正文字符数（标题+标签始终包含）
    semantic_top_k: int = 20
    # RRF 融合权重：语义 1.5 > 关键词 1.0，保证自然语言提问时语义排序压过“怎么/什么”这类词的命中
    semantic_weight: float = 1.5

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        """逗号分隔配置 → 去空白列表（S7：三段 split 收敛为公共方法）。"""
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def ignore_dirs_list(self) -> list[str]:
        return self._split_csv(self.ignore_dirs)

    @property
    def ignore_files_list(self) -> list[str]:
        return self._split_csv(self.ignore_files)

    @property
    def disallowed_write_dirs_list(self) -> list[str]:
        return self._split_csv(self.disallowed_write_dirs)

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS 白名单；空列表 = 不启用跨源中间件（同源部署）。"""
        return self._split_csv(self.cors_origins)

    @property
    def resolved_backup_dir(self) -> Path:
        """默认 {项目根}/backups（Docker 部署把宿主卷挂到 /app/backups 即可）。"""
        if self.backup_dir:
            return self.backup_dir
        project_root = Path(__file__).resolve().parent.parent
        return project_root / "backups"

    @property
    def resolved_semantic_cache_dir(self) -> Path:
        """向量模型缓存目录：显式配置优先，否则放 data_dir（随数据卷持久化）。"""
        if self.semantic_cache_dir:
            return Path(self.semantic_cache_dir)
        return self.data_dir / "models"

    @property
    def llm_resolved_model(self) -> str:
        """按 provider 回退默认模型，避免未配置时启动即崩。"""
        if self.llm_model:
            return self.llm_model
        defaults = {
            "deepseek": "deepseek-chat",
            "openai": "gpt-4o-mini",
            "kimiapi": "moonshot-v1-8k",
            "ollama": "qwen2.5:7b",
        }
        return defaults.get(self.llm_provider, "deepseek-chat")

    def validate_paths(self) -> None:
        """启动前路径校验。

        坑 #11：备份目录若位于 vault 内部，会被索引、被递归备份、被恢复覆盖
        → 直接报错拒绝启动（防备份链断裂）。
        """
        vault = self.vault_path.expanduser().resolve()
        backup = self.resolved_backup_dir.expanduser().resolve()
        try:
            backup.relative_to(vault)
        except ValueError:
            pass
        else:
            raise ValueError(
                f"配置错误：BACKUP_DIR({backup}) 不能位于 vault({vault}) 内部。"
                f"请将备份目录放到 vault 之外的路径（如 {self.data_dir / 'backups'}）。"
            )

    def redacted(self) -> dict[str, Any]:
        """脱敏后的配置视图（日志/`--check` 用），key 打码。"""
        data = self.model_dump()
        if data.get("llm_api_key"):
            data["llm_api_key"] = data["llm_api_key"][:4] + "****"
        if data.get("auth_token"):
            data["auth_token"] = "****"
        if data.get("meili_master_key"):
            data["meili_master_key"] = "****"
        return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
