<script setup>
// 快照列表子组件（S12：从 BackupPanel 拆出）：列表 + 校验 + 删除 + 文件列表
import { ref } from "vue";
import { API } from "../api/endpoints.js";
import { apiDelete, apiGet, apiPost } from "../api.js";
import { fmtSize, fmtTime, reasonLabel } from "../format.js";
import ConfirmDialog from "./ConfirmDialog.vue";

/**
 * @prop {Array} backups 快照列表（父组件维护，删除后由父刷新）
 * @prop {boolean} loading 加载中
 * @prop {string|null} deletingSnap 正在删除的快照 id（按钮禁用）
 * @event toast - `(msg, isError?)`
 * @event refresh - 请求父组件刷新列表
 * @event delete - 请求删除快照：`(id)`
 * @event files-loaded - 文件列表加载完成：`(id, files)`
 */
const props = defineProps({
  backups: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  deletingSnap: { type: String, default: null },
});
const emit = defineEmits(["toast", "refresh", "delete", "files-loaded"]);

const showFiles = ref(null);   // 当前查看文件列表的快照 id
const confirmDel = ref(null);  // 待确认删除的快照 id（自定义确认框，替代原生 confirm）

function toast(msg, isError = false) {
  emit("toast", msg, isError);
}

async function verifySnap(id) {
  try {
    const r = await apiPost(API.backupVerify + "/" + id);
    toast(r.ok ? `校验通过：${r.detail}` : `校验失败：${r.detail}`, !r.ok);
    emit("refresh");
  } catch (e) {
    toast("校验失败：" + e.message, true);
  }
}

function delSnap(id) {
  if (props.deletingSnap) return; // 防重复点击
  confirmDel.value = id; // 打开居中确认框（替代原生 confirm，位置/样式可控）
}

function onConfirmDel() {
  emit("delete", confirmDel.value);
  confirmDel.value = null;
}

async function toggleFiles(id) {
  showFiles.value = showFiles.value === id ? null : id;
  if (showFiles.value) {
    try {
      const r = await apiGet(API.backupFiles(id));
      emit("files-loaded", id, r.files || []);
    } catch (e) {
      toast("加载文件列表失败：" + e.message, true);
      showFiles.value = null;
    }
  }
}
</script>

<template>
  <div class="bp-section">
    <h3 class="bp-section-title">快照列表</h3>
    <div v-if="loading" class="dir-empty">加载中…</div>
    <div v-else-if="!backups.length" class="dir-empty">暂无快照，点击「立即备份」创建第一份</div>
    <div v-else class="bp-table">
      <div class="bp-tr bp-th">
        <span>时间</span><span>原因</span><span>文件数</span><span>大小</span><span>校验</span><span>操作</span>
      </div>
      <div v-for="s in backups" :key="s.id" class="bp-tr">
        <span data-label="时间">{{ fmtTime(s.createdAt) }}</span>
        <span data-label="原因">{{ reasonLabel(s.reason) }}</span>
        <span data-label="文件数">{{ s.files }}</span>
        <span data-label="大小">{{ fmtSize(s.bytes) }}</span>
        <span data-label="校验">
          <span
            class="bp-verify"
            :class="s.verify === 'ok' ? 'ok' : s.verify && s.verify.startsWith('fail') ? 'fail' : 'pending'"
          >{{ s.verify === "ok" ? "✓ 通过" : s.verify && s.verify.startsWith("fail") ? "✗ 失败" : "未校验" }}</span>
        </span>
        <span data-label="操作" class="bp-ops">
          <button class="btn small" @click="verifySnap(s.id)">校验</button>
          <button class="btn small" @click="toggleFiles(s.id)">
            {{ showFiles === s.id ? "收起" : "文件" }}
          </button>
          <button class="btn small danger" :disabled="deletingSnap === s.id" @click="delSnap(s.id)">
            {{ deletingSnap === s.id ? "删除中…" : "删除" }}
          </button>
        </span>
      </div>
    </div>
    <!-- 快照文件列表 -->
    <div v-if="showFiles" class="bp-files">
      <div v-for="f in (backups.find((s) => s.id === showFiles) || {})._files || []" :key="f" class="bp-file">
        <span class="bp-file-icon">📄</span>
        <span class="bp-file-name">{{ f }}</span>
      </div>
      <div v-if="!((backups.find((s) => s.id === showFiles) || {})._files || []).length" class="dir-empty">
        文件列表加载中…
      </div>
    </div>

    <!-- 删除确认（居中弹窗，替代原生 confirm） -->
    <ConfirmDialog
      :show="!!confirmDel"
      title="删除快照"
      :message="`确定删除快照 ${confirmDel}？\n此操作不可恢复。`"
      confirm-text="删除"
      danger
      @confirm="onConfirmDel"
      @cancel="confirmDel = null"
    />
  </div>
</template>
