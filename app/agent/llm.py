"""LLM 模型配置层：把项目配置映射为 pydantic-ai 2.x 的模型 id。

pydantic-ai 2.x 内置 provider（deepseek / openai / moonshotai / ollama / litellm ...），
模型 id 格式 `<provider>:<model>`；api_key 通过环境变量（DEEPSEEK_API_KEY 等）注入。
"""

from __future__ import annotations

import os

from app.config import Settings

# provider 名映射（项目配置 → pydantic-ai 内置）
_PROVIDER_MAP = {
    "deepseek": "deepseek",
    "openai": "openai",
    "kimiapi": "moonshotai",  # Kimi
    "ollama": "ollama",
    "custom": "litellm",  # 通用 OpenAI 兼容网关
}

# provider → 环境变量名（api_key 注入用）
_API_KEY_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "moonshotai": "MOONSHOT_API_KEY",
}


def is_configured(settings: Settings) -> bool:
    """LLM 是否可用：ollama 无需 key；其余需 api_key。"""
    if settings.llm_provider == "ollama":
        return True
    return bool(settings.llm_api_key)


def build_model_id(settings: Settings) -> str:
    """构造 pydantic-ai 模型 id 并把 api_key/ollama host 注入环境变量。"""
    pid = _PROVIDER_MAP.get(settings.llm_provider, settings.llm_provider)
    if settings.llm_provider == "ollama":
        # ollama host 注入（pydantic-ai 内置 ollama provider 读取）
        os.environ.setdefault("OLLAMA_HOST", settings.ollama_host)
    elif settings.llm_api_key:
        env_name = _API_KEY_ENV.get(pid, f"{pid.upper()}_API_KEY")
        os.environ.setdefault(env_name, settings.llm_api_key)
    return f"{pid}:{settings.llm_resolved_model}"
