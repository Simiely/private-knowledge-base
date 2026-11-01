// 备份状态单例（S14 统一 /api/backup/list 数据源；S18 统一"启动备份+完成检测"）
//
// 设计：状态只存一份（runner/backups），侧栏 StatusBar 与备份页 BackupPanel 共享。
//      启动备份（startBackup）也统一在此：乐观置忙 → 轮询检测完成 → toast 反馈，
//      杜绝"点击侧栏备份、右侧界面不同步"的两套状态问题。
import { ref } from "vue";
import { API } from "./api/endpoints.js";
import { apiGet, apiPost } from "./api.js";

const backupText = ref("备份：-");
const backupBusy = ref(false);
const runner = ref({});
const backups = ref([]);

let doneTimer = null; // 备份完成检测轮询（模块级，单例生命周期）

export function updateBackupState(data) {
  const r = data.runner || {};
  runner.value = r;
  backups.value = data.snapshots || [];
  backupBusy.value = !!r.running;
  backupText.value = r.running ? "备份：进行中…" : `备份：${backups.value.length} 份快照`;
}

// 备份完成检测：2s 主动轮询 /api/backup/list，直到 running=false。
// 手动备份（startBackup）与自动备份（useAutoBackup.tick）共用；
// toast 可选——自动备份静默更新状态，不打扰用户。
export function pollBackupDone(toast) {
  if (doneTimer) clearInterval(doneTimer);
  doneTimer = setInterval(async () => {
    try {
      const data = await apiGet(API.backupList);
      updateBackupState(data);
      if (!runner.value.running) {
        clearInterval(doneTimer);
        doneTimer = null;
        if (toast) toast("备份完成 ✓");
      }
    } catch (_) { /* 瞬时错误忽略，下轮再试 */ }
  }, 2000);
}

// 统一"立即备份"入口：侧栏与备份页按钮共用。
// toast: (msg, isError?) => void（由调用方传入，UI 层解耦）
export function startBackup(toast) {
  if (backupBusy.value) {
    if (toast) toast("已有备份/恢复任务进行中，请稍候");
    return;
  }
  // 乐观置忙：所有订阅者（侧栏 + 备份页）立即显示"备份中…"
  updateBackupState({ runner: { running: true }, snapshots: backups.value });
  (async () => {
    try {
      await apiPost(API.backupNow, { reason: "manual" });
      if (toast) toast("备份任务已启动…");
      pollBackupDone(toast); // 完成检测
    } catch (e) {
      // 失败：恢复状态（重新拉真实状态覆盖乐观值）
      try {
        const data = await apiGet(API.backupList);
        updateBackupState(data);
      } catch (_) {
        updateBackupState({ runner: { running: false }, snapshots: backups.value });
      }
      if (toast) {
        toast(e.message.includes("409") ? "已有备份/恢复任务进行中，请稍候" : "备份失败：" + e.message, true);
      }
    }
  })();
}

export function useBackupStatus() {
  return { backupText, backupBusy, runner, backups, updateBackupState, pollBackupDone, startBackup };
}
