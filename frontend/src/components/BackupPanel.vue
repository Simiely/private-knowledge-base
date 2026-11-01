<script setup>
// 备份管理面板（编排层，S12 拆分）：概览卡片 + 备份目录管理 + 子组件编排
import { ref, onMounted, onUnmounted } from "vue";
import { API } from "../api/endpoints.js";
import DirPicker from "./DirPicker.vue";
import SnapshotList from "./SnapshotList.vue";
import AutoBackupSettings from "./AutoBackupSettings.vue";
import HistoryRestore from "./HistoryRestore.vue";
import RestoreAll from "./RestoreAll.vue";
import { apiGet, apiPost, apiDelete } from "../api.js";
import { useDirPicker } from "../useDirPicker.js";
import { useBackupStatus } from "../useBackupStatus.js";
import { fmtTime, reasonLabel } from "../format.js";

/**
 * 备份管理面板：概览 / 备份目录管理 / 快照列表 / 自动备份 / 历史恢复 / 整库恢复。
 * 逻辑按领域拆到子组件（S12），本组件只做数据编排与状态共享。
 * @prop {string} vault 当前库绝对路径
 * @event toast - 提示消息：`(msg: string, isError?: boolean)`
 */
const props = defineProps({
  vault: { type: String, default: "" },
});

const emit = defineEmits(["toast"]);

// S14/S18：备份状态统一读单例（runner/backups 与侧栏共享一份，杜绝两套状态不同步）
const { runner, backups, updateBackupState, startBackup } = useBackupStatus();

const loading = ref(false);
const retention = ref(null);    // 保留策略
const backupDir = ref("");      // 当前备份目录
const deletingSnap = ref(null); // 正在删除的快照 id
let deletingSnapTimer = null;
let timer = null;

function toast(msg, isError = false) {
  emit("toast", msg, isError);
}

async function load() {
  loading.value = true;
  try {
    const data = await apiGet(API.backupList);
    updateBackupState(data); // 单例统一更新（runner/backups/backupText 全同步）
    retention.value = data.retention || null;
  } catch (e) {
    toast("加载备份列表失败：" + e.message, true);
  } finally {
    loading.value = false;
  }
  try {
    const bd = await apiGet(API.settingsBackupDir);
    backupDir.value = bd.path || "";
  } catch (_) { /* ignore */ }
  // 注意：不再在此处同步自动备份配置（AutoBackupSettings 挂载时自己同步一次）。
  // 轮询若覆盖 enabled/intervalMinutes，会回弹用户刚切换的开关（状态延迟 bug）。
}

// ---------- 备份目录管理 ----------

const picker = useDirPicker();
const { showDialog: showDirDialog, inputPath: dirInput, switching: dirSwitching } = picker;

function openDirDialog() {
  picker.open(backupDir.value, toast);
}

async function openBackupDir() {
  try {
    const r = await apiPost(API.settingsBackupDirOpen);
    toast(`已打开备份目录：${r.opened}`);
  } catch (e) {
    toast("打开失败：" + e.message, true);
  }
}

async function switchBackupDir() {
  const path = dirInput.value.trim();
  if (!path) return toast("请选择或输入备份目录路径", true);
  dirSwitching.value = true;
  try {
    const r = await apiPost(API.settingsBackupDir, { path });
    toast(`备份目录已切换：${r.path}`);
    picker.close();
    backupDir.value = r.path;
    load();
  } catch (e) {
    toast("切换失败：" + e.message, true);
  } finally {
    dirSwitching.value = false;
  }
}

// 立即备份：统一走单例 startBackup（乐观置忙 + 完成检测 + toast），
// 与侧栏 StatusBar 按钮共用同一入口/同一状态 → 右侧与侧栏始终同步
function backupNow() {
  startBackup(toast);
}

// ---------- 快照操作（子组件事件处理） ----------

async function onDeleteSnap(id) {
  if (deletingSnap.value) return;
  deletingSnap.value = id;
  try {
    await apiDelete(API.backupDelete(id));
    toast("正在删除快照…（大快照后台清理约需几秒）");
    load();
    // 主动轮询刷新列表检测删除完成——不能只查本地 backups.value：
    // 它只在 load() 时更新，若依赖 10s 主轮询，删除完成后还要干等最多 10s。
    deletingSnapTimer = setInterval(async () => {
      await load(); // 每 2s 主动请求最新列表
      const still = backups.value.some((s) => s.id === id);
      if (!still) {
        clearInterval(deletingSnapTimer);
        deletingSnapTimer = null;
        deletingSnap.value = null;
        toast("快照已删除 ✓");
      }
    }, 2000);
  } catch (e) {
    deletingSnap.value = null;
    toast("删除失败：" + e.message, true);
  }
}

function onFilesLoaded(id, files) {
  backups.value = backups.value.map((s) => (s.id === id ? { ...s, _files: files } : s));
}

// ---------- 生命周期 ----------

onMounted(() => {
  load();
  timer = setInterval(load, 10000); // 10s 轮询，捕获定时备份/运行中状态变化
});
onUnmounted(() => {
  clearInterval(timer);
  if (deletingSnapTimer) clearInterval(deletingSnapTimer);
  // 备份完成检测由单例 startBackup 管理（模块级，无需组件清理）
});
</script>

<template>
  <section class="backup-panel">
    <!-- 概览卡片 + 备份目录管理 -->
    <div class="bp-overview">
      <div class="bp-card">
        <div class="bp-card-title">备份状态</div>
        <div class="bp-card-body">
          <div class="bp-stat">
            <span class="dot" :class="runner.running ? 'busy' : 'ok'"></span>
            <span>{{ runner.running ? "备份进行中…" : "空闲" }}</span>
          </div>
          <div class="bp-sub">上次：{{ fmtTime(runner.lastAt) }}（{{ reasonLabel(runner.lastReason) }}）</div>
        </div>
      </div>
      <div class="bp-card">
        <div class="bp-card-title">快照统计</div>
        <div class="bp-card-body">
          <div class="bp-stat big">{{ backups.length }} <span class="bp-unit">份快照</span></div>
          <div class="bp-sub">保留策略：{{ retention ? `${retention.days}d / ${retention.weeks}w / ${retention.months}m` : "-" }}</div>
        </div>
      </div>
      <div class="bp-card">
        <div class="bp-card-title">当前库</div>
        <div class="bp-card-body">
          <div class="bp-vault" :title="vault">{{ vault || "-" }}</div>
          <div class="bp-sub">备份目录位于库外（data/backups）</div>
        </div>
      </div>
      <div class="bp-card">
        <div class="bp-card-title">🗂️ 备份目录</div>
        <div class="bp-card-body">
          <div class="bp-vault" :title="backupDir">{{ backupDir || "-" }}</div>
          <div class="bp-sub">
            <button class="btn small" @click="openBackupDir">📂 打开目录</button>
            <button class="btn small" @click="openDirDialog">📝 修改目录</button>
          </div>
        </div>
      </div>

      <!-- 自动备份设置（子组件） -->
      <AutoBackupSettings @toast="toast" />

      <div class="bp-card bp-action-card">
        <div class="bp-card-title">操作</div>
        <div class="bp-card-body">
          <button class="btn primary" :class="{ loading: runner.running }" :disabled="runner.running" @click="backupNow">
            {{ runner.running ? "备份中…" : "立即备份" }}
          </button>
          <button class="btn" @click="load">刷新列表</button>
        </div>
      </div>
    </div>

    <!-- 单文件历史恢复（子组件） -->
    <HistoryRestore @toast="toast" />

    <!-- 快照列表（子组件） -->
    <SnapshotList
      :backups="backups"
      :loading="loading"
      :deleting-snap="deletingSnap"
      @toast="toast"
      @refresh="load"
      @delete="onDeleteSnap"
      @files-loaded="onFilesLoaded"
    />

    <!-- 整库恢复（子组件） -->
    <RestoreAll :backups="backups" @toast="toast" @restored="() => setTimeout(load, 1500)" />

    <!-- 更换备份目录：通用目录选择器 -->
    <DirPicker
      :show="showDirDialog"
      title="更换备份目录"
      hint="选择或输入备份目录路径（需位于当前库之外）"
      :model-value="dirInput"
      :switching="dirSwitching"
      :quick-disks="picker.quickDisks.value"
      :quick-places="picker.quickPlaces.value"
      :browse-path="picker.browsePath.value"
      :browse-parent="picker.browseParent.value"
      :browse-dirs="picker.browseDirs.value"
      :browse-loading="picker.browseLoading.value"
      @update:model-value="(v) => (dirInput = v)"
      @update:show="picker.close"
      @browse="(p) => picker.browseTo(p)"
      @quick="(item) => picker.goQuick(item)"
      @enter="(d) => picker.enterDir(d)"
      @pick="picker.pickCurrent"
      @confirm="switchBackupDir"
    />
  </section>
</template>
