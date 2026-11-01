// 后端 API 端点常量（S8：集中 24 处散落 URL，避免魔法字符串漂移）
export const API = {
  // health / index
  health: "/api/health",
  indexStatus: "/api/index/status",
  indexRebuild: "/api/index/rebuild",
  // vault
  vaultTree: "/api/vault/tree",
  vaultFile: "/api/vault/file",
  vaultResolveMd: "/api/vault/resolve-md",
  // search
  search: "/api/search",
  // settings
  settingsVault: "/api/settings/vault",
  settingsBackupDir: "/api/settings/backupdir",
  settingsBackupDirOpen: "/api/settings/backupdir/open",
  settingsQuickAccess: "/api/settings/quickaccess",
  settingsDetect: "/api/settings/detect",
  settingsAutoBackup: "/api/settings/autobackup",
  // backup
  backupList: "/api/backup/list",
  backupNow: "/api/backup/now",
  backupStatus: "/api/backup/status",
  backupVerify: "/api/backup/verify",
  backupHistory: "/api/backup/history",
  backupRestoreFile: "/api/backup/restore-file",
  backupRestore: "/api/backup/restore",
  backupDelete: (id) => `/api/backup/${id}`,
  backupFiles: (id) => `/api/backup/files?snapshotId=${encodeURIComponent(id)}`,
  // agent
  agentChat: "/api/agent/chat",
  agentConfirm: "/api/agent/confirm",
  agentCancel: "/api/agent/cancel",
};
