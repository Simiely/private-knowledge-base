#!/bin/sh
# 容器入口：以 root 启动时先修正 bind mount 目录属主，再降权到 appuser 运行。
# 对齐 Radicale / 常见自建镜像的做法，避免 USB/NTFS 挂载目录归 root 时 SQLite 无法建库。
# 需要跳过修正时设 FIX_OWNER_DIRS=""（或只填 /data）。
set -eu

if [ "$(id -u)" = "0" ]; then
    dirs="${FIX_OWNER_DIRS:-/data /vault}"
    # shellcheck disable=SC2086
    for d in $dirs; do
        [ -d "$d" ] || continue
        # exFAT/NTFS 不支持 chown，失败忽略，不阻塞启动
        chown -R appuser:appuser "$d" 2>/dev/null || true
    done
    exec gosu appuser "$@"
fi

exec "$@"
