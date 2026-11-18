---
id: "docs.pitfalls.backup-dir-container-layer"
title: "备份目录默认在容器可写层，重建容器就没了"
summary: "没配 BACKUP_DIR 时快照落在 /app/backups，容器一删备份全丢。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/backup/engine.py"
last_reviewed: "2026-08-01"
related: []
applies_to: ["docs.deploy-windows", "docs.config-reference"]
severity: "critical"
symptom: "Docker 部署后快照「消失」，宿主机找不到备份文件。"
cause: "resolved_backup_dir 默认 {项目根}/backups（容器内 /app/backups），不在任何 volume 上。"
detect: "docker inspect 看 Mounts 是否包含备份目录；或在容器内 ls /app/backups 后重建容器再查。"
avoid: "compose environment 显式配 BACKUP_DIR=/data/backups（挂载盘内），或把宿主目录挂到 /app/backups。"
recover: "已丢失的备份无法恢复；立即改配置并重建一份快照。"
---

# 备份目录默认在容器可写层，重建容器就没了

## 影响

备份目录必须在持久卷上，且不在 vault 内（避免递归）。
