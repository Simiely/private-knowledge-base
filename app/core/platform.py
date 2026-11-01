"""平台探测层：磁盘枚举 / 特殊文件夹 / Obsidian 库检测（纯逻辑，无 Web 依赖）。

职责（从 api/routes_settings.py 拆分而来）：
- win_special_folder / win_disks / linux_disks / list_roots：磁盘与系统目录枚举
- detect_vaults：以 .obsidian 标志扫描本机 Obsidian 库
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Windows CSIDL 常量（SHGetFolderPathW 用，见 MSDN）
_CSIDL_DESKTOP = 0
_CSIDL_PERSONAL = 5  # 我的文档
_CSIDL_DOWNLOADS = 0x374  # 下载
_CSIDL_MYPICTURES = 0x27
_CSIDL_MYMUSIC = 0xD
_CSIDL_MYVIDEO = 0xE

# Linux 伪文件系统类型（/proc/mounts 过滤，避免把内存/虚拟文件系统当磁盘）
_PSEUDO_FS = {
    "proc",
    "sysfs",
    "devtmpfs",
    "devpts",
    "tmpfs",
    "overlay",
    "cgroup",
    "cgroup2",
    "efivarfs",
    "squashfs",
    "debugfs",
    "tracefs",
    "securityfs",
    "pstore",
    "bpf",
    "autofs",
    "ramfs",
    "hugetlbfs",
    "rpc_pipefs",
    "fusectl",
    "mqueue",
    "configfs",
    "binfmt_misc",
    "nsfs",
    "selinuxfs",
    "fuse.portal",
}

# /proc/mounts 路径（提取为常量便于单测 monkeypatch）
_PROC_MOUNTS = "/proc/mounts"


def win_special_folder(csidl: int) -> str | None:
    """通过 Windows API 获取特殊文件夹真实路径（正确处理 OneDrive 重定向/非英文系统）。"""
    try:
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        fn = ctypes.windll.shell32.SHGetFolderPathW
        fn.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPCWSTR,
        ]
        if fn(0, csidl, 0, 0, buf) == 0:
            return buf.value
    except Exception:  # pragma: no cover - 非 Windows 或 API 不可用
        pass
    return None


def win_disks() -> list[dict[str, str]]:
    """枚举 Windows 存在的盘符（C:/、D:/…）。"""
    disks: list[dict[str, str]] = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:"
        if os.path.exists(drive + os.sep):
            disks.append({"name": drive + "\\", "path": drive + "/", "icon": "💾", "kind": "disk"})
    return disks


def _running_in_docker() -> bool:
    """是否运行在容器内：Docker 必有 /.dockerenv，podman 有 /run/.containerenv。"""
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def linux_disks() -> list[dict[str, str]]:
    """枚举 Linux 真实磁盘挂载点（读 /proc/mounts）。

    - 过滤伪文件系统（overlay/tmpfs/proc 等），只留真实磁盘
    - 顶层挂载点（如 /mnt、/media、/volume1）与磁盘挂载点（如 /mnt/sda1、/volume1/vault）
      都返回；名称取最后一段，路径过长时前端会截断
    - Docker 容器内（/.dockerenv 存在）：只展示通过 volumes bind 进来的业务盘
      （如 /vault、/data、/mnt/usb1），排除根挂载 / 与常见目录兜底——
      避免「切换笔记库」列出一堆容器内部挂载；本地裸机部署仍保留全量枚举 + 兜底
    """
    in_docker = _running_in_docker()
    disks: list[dict[str, str]] = []
    mounts: list[tuple[Path, str]] = []
    try:
        with open(_PROC_MOUNTS, encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                _, mnt, fstype = parts[0], parts[1], parts[2]
                if fstype in _PSEUDO_FS:
                    continue
                if fstype.startswith("fuse"):
                    continue
                mnt_path = Path(mnt)
                if not mnt_path.is_dir():
                    continue
                if in_docker and mnt_path == Path("/"):
                    continue  # Docker 模式：排除根挂载，只留 bind 进来的业务盘
                mounts.append((mnt_path, fstype))
    except OSError:  # pragma: no cover - 非 Linux
        return disks
    if not mounts:
        return disks
    # 排序：顶层（深度小）优先，同级按名称
    mounts.sort(key=lambda x: (len(x[0].parts), x[0].as_posix()))
    seen: set[str] = set()
    for mnt_path, fstype in mounts:
        name = mnt_path.name or "/"
        display = name if len(name) <= 24 else "…" + name[-23:]
        disks.append(
            {
                "name": f"{display} ({fstype})",
                "path": str(mnt_path),
                "icon": "💾",
                "kind": "disk",
            }
        )
        seen.add(str(mnt_path))
    # 常见数据挂载父目录兜底（仅本地裸机；Docker 内只认 /proc/mounts 里的真实挂载点）
    if not in_docker:
        for extra in ("/mnt", "/media", "/volume1", "/volume2", "/share", "/data", "/userdisk"):
            p = Path(extra)
            if p.is_dir() and str(p) not in seen:
                disks.append({"name": extra, "path": extra, "icon": "💾", "kind": "disk"})
    return disks


def list_roots() -> dict[str, Any]:
    """根列表：Windows 返回存在的盘符（C:/、D:/…），其他系统返回 /。"""
    roots: list[str] = []
    if os.name == "nt":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:"
            if os.path.exists(drive + os.sep):
                roots.append(drive + "/")
    else:
        roots.append("/")
    return {"path": "", "parent": "", "dirs": roots}


def browse_dirs(path: str) -> dict[str, Any]:
    """浏览指定目录：返回父目录 + 子目录名列表（供前端逐级导航）。

    - path 为空 → list_roots()（盘符/根）
    - 只列目录不列文件；无权限/不存在的目录自动跳过，不报错（S11：从 API 层收敛到 core）。
    """
    if not path:
        return list_roots()
    p = Path(path).expanduser()
    if not p.is_dir():
        raise FileNotFoundError(f"目录不存在或不是目录: {path}")
    parent = str(p.parent) if p.parent != p else ""
    dirs: list[str] = []
    try:
        for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.is_dir():
                dirs.append(entry.name)
    except OSError:  # pragma: no cover - 权限受限目录
        pass
    return {"path": str(p), "parent": parent, "dirs": dirs}


def open_in_file_manager(path: str | Path) -> bool:
    """用系统默认文件管理器打开目录（跨平台）。

    - Windows: os.startfile（Explorer）
    - macOS: open
    - Linux（含 iStoreOS 桌面环境）: xdg-open
    返回是否成功；失败时抛 RuntimeError 携带原因。
    """
    import subprocess

    p = str(path)
    if not os.path.isdir(p):
        raise RuntimeError(f"目录不存在: {p}")
    try:
        if os.name == "nt":
            os.startfile(p)  # Windows 专有
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
    except OSError as e:
        raise RuntimeError(f"打开目录失败: {e}") from e
    return True


def detect_vaults(start: Path, max_depth: int = 5, limit: int = 50) -> list[dict[str, Any]]:
    """在 start 目录树内扫描 Obsidian 库（含 .obsidian 标志的目录）。

    - max_depth 限制递归深度，防止全盘扫描卡顿
    - 返回 [{path, name, mdCount}]，按 mdCount 降序
    - 无权限目录容错跳过（Windows 常见于 System Volume Information 等）
    """
    if not start.is_dir():
        return []
    found: list[tuple[Path, int]] = []

    def _walk(dirp: Path, depth: int) -> None:
        if depth > max_depth or len(found) >= limit:
            return
        try:
            entries = sorted(dirp.iterdir(), key=lambda e: e.name.lower())
        except OSError:
            return
        for entry in entries:
            if len(found) >= limit:  # limit 在循环内也生效（同层多个库时限制数量）
                return
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            try:
                if (entry / ".obsidian").is_dir():
                    md = sum(1 for _ in entry.rglob("*.md"))
                    found.append((entry, md))
                    continue  # 库内子目录不再递归（避免嵌套库重复/深层扫描）
            except OSError:
                continue
            _walk(entry, depth + 1)

    _walk(start, 1)
    found.sort(key=lambda x: x[1], reverse=True)
    return [{"path": str(p.resolve()), "name": p.name, "mdCount": n} for p, n in found]


def quick_access() -> dict[str, Any]:
    """快捷位置：disks = 磁盘/挂载点，places = 常用文件夹（前端侧边栏分组显示）。

    - Windows：SHGetFolderPathW 取真实路径（兼容 OneDrive 重定向）+ 枚举盘符
    - Linux（含 iStoreOS/群晖）：读 /proc/mounts 枚举真实磁盘挂载点
    - 非 Windows 平台常用文件夹回退 ~/Desktop、~/Documents 等约定位置
    """
    places: list[dict[str, str]] = []

    def _add(name: str, path: str | None, icon: str) -> None:
        if path and Path(path).is_dir():
            places.append(
                {"name": name, "path": str(Path(path).resolve()), "icon": icon, "kind": "place"}
            )

    if os.name == "nt":
        disks = win_disks()
        _add("桌面", win_special_folder(_CSIDL_DESKTOP), "🖥️")
        _add("文档", win_special_folder(_CSIDL_PERSONAL), "📄")
        _add("下载", win_special_folder(_CSIDL_DOWNLOADS), "⬇️")
        _add("图片", win_special_folder(_CSIDL_MYPICTURES), "🖼️")
        _add("音乐", win_special_folder(_CSIDL_MYMUSIC), "🎵")
        _add("视频", win_special_folder(_CSIDL_MYVIDEO), "🎬")
    else:
        disks = linux_disks()
        home = Path.home()
        for name, sub, icon in (
            ("桌面", "Desktop", "🖥️"),
            ("文档", "Documents", "📄"),
            ("下载", "Downloads", "⬇️"),
            ("图片", "Pictures", "🖼️"),
            ("音乐", "Music", "🎵"),
            ("视频", "Videos", "🎬"),
        ):
            _add(name, str(home / sub), icon)

    _add("用户目录", str(Path.home()), "🏠")
    return {"disks": disks, "places": places}


def detect_local_vaults() -> dict[str, Any]:
    """自动检测本机 Obsidian 库：常见位置（用户目录/桌面/文档/下载）+ 全盘根目录浅扫。"""
    home = Path.home()
    candidates: list[Path] = [home]
    for sub in ("Desktop", "Documents", "OneDrive", "Downloads", "Obsidian"):
        p = home / sub
        if p.is_dir():
            candidates.append(p)
    # Linux/macOS 常规位置（Windows 上跳过，避免 /Users 被解析成相对路径产生重复项）
    if os.name != "nt":
        for p in (Path("/home"), Path("/Users"), Path("/root")):
            if p.is_dir() and p != home:
                candidates.append(p)

    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for base in candidates:
        for item in detect_vaults(base, max_depth=5):
            if item["path"] not in seen:
                seen.add(item["path"])
                results.append(item)
    # 当前正在使用的库永远排最前
    results.sort(key=lambda x: (x["path"] != str(Path.home()), -x["mdCount"]))
    return {"vaults": results, "scanBase": [str(p) for p in candidates]}
