<script setup>
// 自动备份设置子组件（v3：局部状态，彻底隔离外部干扰）
// 设计：UI 状态用组件内部 ref（点击/输入立即响应，无任何轮询/共享状态覆盖）；
//       保存时调用 useAutoBackup.saveConfig 同步后端（失败回滚本地）。
import { ref, watch, onMounted } from "vue";
import { API } from "../api/endpoints.js";
import { apiGet, apiPut } from "../api.js";
import { useAutoBackup } from "../useAutoBackup.js";

/**
 * @event toast - `(msg, isError?)`
 */
const emit = defineEmits(["toast"]);

function toast(msg, isError = false) {
  emit("toast", msg, isError);
}

// 模块级单例（供 App.vue 自动备份定时器 tick 使用）；本组件只做单向写入同步，不读取
const autoBackup = useAutoBackup();

// ---- 局部状态（与模块级 useAutoBackup 完全独立，杜绝覆盖） ----
const enabled = ref(true);       // 开关
const intervalMinutes = ref(30); // 间隔（分钟）
const autoIntervalInput = ref(30);
const autoDetail = ref(false);

// 挂载时读一次后端配置
onMounted(async () => {
  try {
    const d = await apiGet(API.settingsAutoBackup);
    enabled.value = d.enabled !== false;
    intervalMinutes.value = d.intervalMinutes || 30;
    autoIntervalInput.value = intervalMinutes.value;
  } catch (_) { /* 后端未就绪保持默认 */ }
});

// ---- 开关：立即本地翻转 + 后台保存，失败回滚 ----
let savingSwitch = false;
async function onToggle() {
  if (savingSwitch) return;
  savingSwitch = true;
  const next = !enabled.value;
  enabled.value = next; // 视觉立即响应
  try {
    const r = await apiPut(API.settingsAutoBackup, { enabled: next });
    autoBackup.enabled.value = r.enabled; // 单向同步模块级（供 tick 判断）
  } catch (e) {
    enabled.value = !next; // 仅真正保存失败才回滚
    toast("保存失败：" + e.message, true);
    return;
  } finally {
    savingSwitch = false;
  }
  // 提示放 try 外：toast 属 UI 层，失败不得回滚已保存的状态
  toast(next ? "自动备份已开启" : "自动备份已关闭");
}

// ---- 间隔：停止输入 800ms 自动保存 ----
let saveTimer = null;
watch(autoIntervalInput, (val) => {
  clearTimeout(saveTimer);
  const n = Number(val);
  if (!n || n < 1) return;
  saveTimer = setTimeout(async () => {
    try {
      const r = await apiPut(API.settingsAutoBackup, { intervalMinutes: n });
      intervalMinutes.value = r.intervalMinutes;
      autoIntervalInput.value = r.intervalMinutes; // 同步钳制后的值
      autoBackup.intervalMinutes.value = r.intervalMinutes; // 单向同步模块级
    } catch (e) {
      toast("保存失败：" + e.message, true);
      return;
    }
    toast(`自动备份间隔已设为 ${intervalMinutes.value} 分钟`);
  }, 800);
});
</script>

<template>
  <div class="bp-card">
    <div class="bp-card-title">⏱️ 自动备份</div>
    <div class="bp-card-body">
      <!-- iOS 风格滑动开关 -->
      <div class="bp-auto-switch-row">
        <span class="bp-label">自动备份</span>
        <button
          class="switch"
          :class="{ on: enabled, off: !enabled }"
          role="switch"
          :aria-checked="enabled"
          @click="onToggle"
        >
          <span class="switch-knob"></span>
        </button>
      </div>
      <!-- 间隔输入（自动应用，防抖 800ms） -->
      <div class="bp-auto-row">
        <label class="bp-auto-field">
          <span class="bp-label">间隔</span>
          <input
            v-model.number="autoIntervalInput"
            type="number"
            min="1"
            max="1440"
            class="modal-input bp-num"
            :disabled="!enabled"
          />
          <span class="bp-unit">分钟</span>
        </label>
        <button class="btn small" @click="autoDetail = !autoDetail">
          {{ autoDetail ? "收起 ▲" : "详情 ▼" }}
        </button>
      </div>
      <div v-if="autoDetail" class="bp-auto-hint">
        每 {{ intervalMinutes }} 分钟自动备份一次，规则：<br />
        · 仅当页面活跃（有操作）时触发<br />
        · 只是挂着不动 → 不备份<br />
        · 关闭页面即停止
      </div>
      <div v-else class="bp-auto-hint bp-auto-oneline">
        {{ enabled ? `每 ${intervalMinutes} 分钟自动备份（活跃时触发）` : "自动备份已关闭" }}
      </div>
    </div>
  </div>
</template>
