"""agent/llm.py 模型配置映射单测（重构计划 B4）。

覆盖：is_configured 判定（ollama 免 key）、build_model_id 的 provider 映射与环境变量注入。
"""

from __future__ import annotations

import os

from app.agent import llm
from app.config import Settings


def _settings(**kw) -> Settings:
    """构造最小 Settings（默认 ollama，避免依赖真实 API key）。"""
    base = dict(
        vault_path=".",
        llm_provider="ollama",
        llm_model="qwen3:8b",
        ollama_host="http://localhost:11434",
    )
    base.update(kw)
    return Settings(**base)


def test_is_configured_ollama_without_key() -> None:
    """ollama 无需 api_key 即可用。"""
    s = _settings(llm_api_key="")
    assert llm.is_configured(s) is True


def test_is_configured_deepseek_needs_key() -> None:
    """deepseek 无 api_key 不可用，有则可用。"""
    assert llm.is_configured(_settings(llm_provider="deepseek", llm_api_key="")) is False
    assert llm.is_configured(_settings(llm_provider="deepseek", llm_api_key="sk-x")) is True


def test_build_model_id_ollama(monkeypatch) -> None:
    """ollama：模型 id 为 ollama:<model>，并注入 OLLAMA_HOST。"""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    s = _settings(llm_model="qwen3:8b")
    assert llm.build_model_id(s) == "ollama:qwen3:8b"
    assert os.environ.get("OLLAMA_HOST") == "http://localhost:11434"


def test_build_model_id_deepseek(monkeypatch) -> None:
    """deepseek：模型 id 为 deepseek:<model>，api_key 注入 DEEPSEEK_API_KEY。"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    s = _settings(llm_provider="deepseek", llm_api_key="sk-secret", llm_model="deepseek-chat")
    assert llm.build_model_id(s) == "deepseek:deepseek-chat"
    assert os.environ.get("DEEPSEEK_API_KEY") == "sk-secret"


def test_build_model_id_kimiapi_maps_to_moonshot(monkeypatch) -> None:
    """kimiapi → moonshotai 内置 provider，env 用 MOONSHOT_API_KEY。"""
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    s = _settings(llm_provider="kimiapi", llm_api_key="sk-kimi", llm_model="kimi-k2")
    assert llm.build_model_id(s) == "moonshotai:kimi-k2"
    assert os.environ.get("MOONSHOT_API_KEY") == "sk-kimi"


def test_build_model_id_openai(monkeypatch) -> None:
    """openai：env 用 OPENAI_API_KEY。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = _settings(llm_provider="openai", llm_api_key="sk-oa", llm_model="gpt-4o-mini")
    assert llm.build_model_id(s) == "openai:gpt-4o-mini"
    assert os.environ.get("OPENAI_API_KEY") == "sk-oa"


def test_build_model_id_env_already_set_not_overwritten(monkeypatch) -> None:
    """已有环境变量时不覆盖（setdefault 语义）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "existing")
    s = _settings(llm_provider="deepseek", llm_api_key="sk-new", llm_model="deepseek-chat")
    llm.build_model_id(s)
    assert os.environ["DEEPSEEK_API_KEY"] == "existing"
