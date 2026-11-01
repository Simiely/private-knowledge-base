#!/usr/bin/env bash
# ===== 构建并推送 obsidian-agent 镜像到 GHCR =====
# 用法：
#   1. 首次先登录 GHCR（GitHub PAT，权限勾选 write:packages + read:packages）：
#      echo "<PAT>" | docker login ghcr.io -u simiely --password-stdin
#   2. 构建并推送（在项目根目录执行）：
#      bash scripts/build-push.sh
#
# 想换成 Docker Hub：把 IMAGE 改为 simiely/obsidian-agent:latest，
#   并用 docker login -u simiely 登录 Docker Hub 后执行即可（同时改 compose 里的 image）。

set -euo pipefail

IMAGE="ghcr.io/simiely/obsidian-agent:latest"

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> 构建 $IMAGE"
docker build -t "$IMAGE" .

echo "==> 推送 $IMAGE"
docker push "$IMAGE"

echo ""
echo "✅ 完成。服务器更新步骤："
echo "   docker compose pull && docker compose up -d"
echo "   （或用 Dpanel 面板点「更新」，pull_policy: always 会自动拉新镜像）"
