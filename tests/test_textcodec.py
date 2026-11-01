"""textcodec 统一解码测试（S5：vault 与 indexer 共用）。"""

from __future__ import annotations

from app.core.textcodec import safe_decode


def test_safe_decode_utf8() -> None:
    # utf-8-sig 解码 UTF-8 字节总是成功（仅去 BOM），故编码名固定为 utf-8-sig
    text, enc = safe_decode("中文内容".encode())
    assert text == "中文内容"
    assert enc == "utf-8-sig"


def test_safe_decode_utf8_sig_strips_bom() -> None:
    text, enc = safe_decode("\ufeff# BOM 开头".encode("utf-8"))
    assert text == "# BOM 开头"
    assert enc == "utf-8-sig"


def test_safe_decode_gb18030_fallback() -> None:
    text, enc = safe_decode("中文".encode("gb18030"))
    assert text == "中文"
    assert enc == "gb18030"


def test_safe_decode_returns_none_on_garbage() -> None:
    assert safe_decode(b"\xff\xfe\x00\xff\x01") is None
