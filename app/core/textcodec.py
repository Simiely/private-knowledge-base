"""文本解码工具（S5：统一 vault 与 indexer 的解码降级逻辑）。

解码顺序：utf-8-sig（自动去 BOM）→ utf-8 → gb18030（坑 #6 编码容错）。
vault 层失败抛 VaultError（读文件必须成功），indexer 层失败返回 None（索引跳过）。
"""

from __future__ import annotations


def safe_decode(data: bytes) -> tuple[str, str] | None:
    """按 utf-8-sig → utf-8 → gb18030 依次尝试解码。

    返回 (text, encoding)；全部失败返回 None（调用方决定如何处理）。
    """
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return None
