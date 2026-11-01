<script setup>
// 侧栏状态栏（S17 优化）：独立订阅轮询状态，只重渲染自身，
// 避免 indexStatus/backupText 更新导致整个 App.vue 重渲染（大文档卡顿根源）。
import { onMounted } from "vue";
import { API } from "../api/endpoints.js";
import { apiGet, apiPost } from "../api.js";
import { useStatusPolling } from "../useStatusPolling.js";
import { useBackupStatus } from "../useBackupStatus.js";

/**
 * @event toast - 提示消息：`(msg, isError?)`
 */
const emit = defineEmits(["toast"]);

const { indexStatus, indexOk, version } = useStatusPolling();
// 备份状态与"立即备份"统一走单例（S18）：与备份页 BackupPanel 共享同一状态/同一入口
const { backupText, backupBusy, updateBackupState, startBackup } = useBackupStatus();

function backupNow() {
  startBackup((msg, isErr) => emit("toast", msg, isErr));
}

// 首次挂载即初始化备份状态：备份状态唯一数据源是 BackupPanel.load()，
// 若用户未进入备份管理页则永远不刷新（侧栏显示"备份：-"）。此处初始化一次。
onMounted(async () => {
  try {
    const data = await apiGet(API.backupList);
    updateBackupState(data);
  } catch (_) { /* 后端未就绪保持默认 */ }
});
</script>

<template>
  <footer id="status-bar">
    <div class="status-line">
      <span class="dot" :class="indexOk ? 'ok' : 'busy'"></span>
      <span>{{ indexStatus }}</span>
    </div>
    <div class="status-line">
      <span class="dot" :class="backupBusy ? 'busy' : 'ok'"></span>
      <span>{{ backupText }}</span>
      <button
        class="btn small"
        :class="{ loading: backupBusy }"
        :disabled="backupBusy"
        @click="backupNow"
      >{{ backupBusy ? "备份中…" : "备份" }}</button>
    </div>
  </footer>
</template>
