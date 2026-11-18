---
id: "docs.pitfalls.docker-host-disks-hidden"
title: "容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的"
summary: "只挂载 /vault 与 /data 时，容器内的 /mnt、/media 是空目录，切库时看不到盘。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/platform.py"
last_reviewed: "2026-08-01"
related: []
applies_to: ["docs.deploy-dpanel", "docs.deploy-windows"]
severity: "high"
symptom: "iStoreOS + Docker 部署，DirPicker 只能看到挂载点根目录，点进去没有子目录；左侧出现 /mnt、/media 等空目录。"
cause: "容器文件系统只包含 compose volumes 声明的路径；代码兜底枚举的 /mnt、/media 在容器内为空。另：platform.linux_disks() 会过滤 fuse 类型挂载（exFAT/ntfs-3g）。"
detect: "进容器 ls /mnt /media，为空即说明没有 bind mount。"
avoid: "在 compose volumes 里显式挂载需要的宿主路径（如 - /mnt/usb1:/mnt/usb1）；linux_disks() 在容器内只展示真实 bind 挂载。"
recover: "改 compose 后重建容器；先确保宿主挂载源有内容再 up -d，否则 Docker 会用空目录占位。"
---

# 容器只能看到挂载点，宿主机磁盘在 DirPicker 里是空的

## 影响

挂载时序：容器启动时磁盘未挂载会被空目录占位，看起来像「盘丢了」。
