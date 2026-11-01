<script setup>
// 单文件历史恢复子组件（S12：从 BackupPanel 拆出）
import { ref } from "vue";
import { API } from "../api/endpoints.js";
import { apiGet, apiPost } from "../api.js";
import { fmtTime } from "../format.js";
import ConfirmDialog from "./ConfirmDialog.vue";

/**
 * @event toast - `(msg, isError?)`
 */
const emit = defineEmits(["toast"]);

function toast(msg, isError = false) {
  emit("toast", msg, isError);
}

const historyPath = ref("");
const history = ref([]);
const historyLoading = ref(false);
const showHistory = ref(false);
const confirmRestore = ref(null); // 待确认恢复的快照 id（自定义确认框）

async function loadHistory() {
  const p = historyPath.value.trim();
  if (!p) return toast("请输入要查询的文件相对路径", true);
  historyLoading.value = true;
  showHistory.value = true;
  try {
    const r = await apiGet(API.backupHistory + "?path=" + encodeURIComponent(p));
    history.value = r.versions || [];
  } catch (e) {
    toast("查询历史失败：" + e.message, true);
  } finally {
    historyLoading.value = false;
  }
}

function restoreFile(snapId) {
  const p = historyPath.value.trim();
  if (!p) return;
  confirmRestore.value = snapId; // 打开居中确认框
}

async function onConfirmRestore() {
  const snapId = confirmRestore.value;
  confirmRestore.value = null;
  const p = historyPath.value.trim();
  try {
    const r = await apiPost(API.backupRestoreFile, { path: p, snapshotId: snapId });
    toast(`已恢复：${r.path}`);
    loadHistory();
  } catch (e) {
    toast("恢复失败：" + e.message, true);
  }
}
</script>

<template>
  <div class="bp-section">
    <h3 class="bp-section-title">单文件历史恢复</h3>
    <div class="bp-inline">
      <input
        v-model="historyPath"
        class="modal-input"
        placeholder="输入 vault 内文件相对路径，如 日记/2026-08-01.md"
        @keydown.enter="loadHistory"
      />
      <button class="btn" :disabled="historyLoading" @click="loadHistory">查询版本</button>
    </div>
    <div v-if="showHistory" class="bp-history">
      <div v-if="historyLoading" class="dir-empty">查询中…</div>
      <div v-else-if="!history.length" class="dir-empty">该文件暂无历史版本（没有备份过或文件从未变更）</div>
      <div v-else class="bp-table">
        <div class="bp-tr bp-th">
          <span>时间</span><span>来源</span><span>快照 ID</span><span></span>
        </div>
        <div v-for="v in history" :key="v.snapshotId" class="bp-tr">
          <span data-label="时间">{{ fmtTime(v.at) }}</span>
          <span data-label="来源">{{ v.source === "pre-write" ? "写前备份" : "快照" }}</span>
          <span data-label="快照 ID" class="bp-mono">{{ v.snapshotId }}</span>
          <span data-label="操作">
            <button class="btn small" @click="restoreFile(v.snapshotId)">恢复此版本</button>
          </span>
        </div>
      </div>
    </div>

    <!-- 恢复确认（居中弹窗，替代原生 confirm） -->
    <ConfirmDialog
      :show="!!confirmRestore"
      title="恢复文件"
      :message="`用快照 ${confirmRestore} 恢复文件「${historyPath.trim()}」？\n当前内容会被覆盖（恢复前自动备份）。`"
      confirm-text="恢复"
      danger
      @confirm="onConfirmRestore"
      @cancel="confirmRestore = null"
    />
  </div>
</template>
