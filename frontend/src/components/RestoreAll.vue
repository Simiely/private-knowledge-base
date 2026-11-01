<script setup>
// 整库恢复子组件（S12：从 BackupPanel 拆出，危险操作）
import { ref } from "vue";
import { API } from "../api/endpoints.js";
import { apiPost } from "../api.js";
import { fmtTime, reasonLabel } from "../format.js";
import ConfirmDialog from "./ConfirmDialog.vue";

/**
 * @prop {Array} backups 快照列表（供选择恢复源）
 * @event toast - `(msg, isError?)`
 * @event restored - 恢复任务启动后请求刷新
 */
const props = defineProps({
  backups: { type: Array, default: () => [] },
});
const emit = defineEmits(["toast", "restored"]);

function toast(msg, isError = false) {
  emit("toast", msg, isError);
}

const restoreTarget = ref("");
const restoreCode = ref("");
const restoring = ref(false);
const confirmAll = ref(false); // 整库恢复确认框开关（替代原生 confirm）

async function restoreAll() {
  if (!restoreTarget.value) return toast("请选择要恢复的快照", true);
  if (restoreCode.value !== "RESTORE") return toast("确认码错误：请输入 RESTORE", true);
  confirmAll.value = true; // 打开居中确认框
}

async function onConfirmAll() {
  confirmAll.value = false;
  restoring.value = true;
  try {
    const r = await apiPost(API.backupRestore, {
      snapshotId: restoreTarget.value,
      confirmCode: restoreCode.value,
    });
    toast(`恢复任务已启动（${r.snapshotId}）`);
    emit("restored");
  } catch (e) {
    toast("恢复失败：" + e.message, true);
  } finally {
    restoring.value = false;
  }
}
</script>

<template>
  <div class="bp-section bp-danger">
    <h3 class="bp-section-title">整库恢复 <span class="bp-danger-tag">危险</span></h3>
    <div class="bp-inline">
      <select v-model="restoreTarget" class="modal-input">
        <option value="">选择要恢复的快照…</option>
        <option v-for="s in backups" :key="s.id" :value="s.id">
          {{ fmtTime(s.createdAt) }} · {{ reasonLabel(s.reason) }} · {{ s.files }} 文件
        </option>
      </select>
      <input
        v-model="restoreCode"
        class="modal-input bp-code"
        placeholder="输入确认码 RESTORE"
      />
      <button class="btn danger" :disabled="restoring" @click="restoreAll">
        {{ restoring ? "恢复中…" : "整库恢复" }}
      </button>
    </div>
    <div class="bp-warn">⚠️ 将用所选快照覆盖 vault 全部文件；恢复前系统会自动创建一份「恢复前快照」以便反悔。</div>

    <!-- 整库恢复确认（居中弹窗，替代原生 confirm） -->
    <ConfirmDialog
      :show="confirmAll"
      title="整库恢复"
      message="整库恢复将用所选快照覆盖 vault 全部文件，且恢复前会自动建快照。\n确认继续？"
      confirm-text="确认恢复"
      danger
      @confirm="onConfirmAll"
      @cancel="confirmAll = false"
    />
  </div>
</template>
