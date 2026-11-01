// 活跃式自动备份 composable（重构计划 T3）
// 需求：打开页面（登录）后，设置间隔 N 分钟；只要还在页面且有操作，每隔 N 分钟自动备份一次；
//      只是挂着页面没有任何操作 → 不备份。
// 实现：前端监听用户活动（click/键盘/滚动/触摸）更新时间戳；每 30s 检查一次——
//      距上次备份 ≥ 间隔 且 距上次操作 ≤ 间隔（活跃）→ 调 /api/backup/now (reason=auto)。
//      页面关闭/刷新 → 计时自然停止（= 不再备份）。间隔可修改并持久化到 settings.json。
import { ref } from "vue";
import { API } from "./api/endpoints.js";
import { apiGet, apiPut, apiPost } from "./api.js";
import { pollBackupDone } from "./useBackupStatus.js"; // 自动备份完成后同步侧栏状态

const intervalMinutes = ref(30); // 间隔（分钟）
const enabled = ref(true);       // 自动备份总开关
const lastBackupAt = ref(0);     // 上次自动备份时间戳

let lastActivity = 0;            // 上次用户操作时间戳
let timer = null;
const EVENTS = ["click", "keydown", "mousemove", "scroll", "touchstart"];

function onActivity() {
  lastActivity = Date.now();
}

export function useAutoBackup(toast) {
  // 读取配置（间隔/开关）
  async function loadConfig() {
    try {
      const d = await apiGet(API.settingsAutoBackup);
      intervalMinutes.value = d.intervalMinutes || 30;
      enabled.value = d.enabled !== false;
    } catch (_) { /* 后端未就绪时保持默认 */ }
  }

  // 保存配置（间隔/开关，只传要更新的键）并持久化
  async function saveConfig({ intervalMinutes: minutes, enabled: en } = {}) {
    const payload = {};
    if (minutes !== undefined) {
      payload.intervalMinutes = Math.max(1, Math.min(Math.round(minutes) || 30, 1440));
    }
    if (en !== undefined) payload.enabled = !!en;
    const r = await apiPut(API.settingsAutoBackup, payload);
    intervalMinutes.value = r.intervalMinutes;
    enabled.value = r.enabled;
    return r;
  }

  // 每 30s 检查：活跃且到间隔 → 自动备份
  async function tick() {
    if (!enabled.value) return;
    const now = Date.now();
    const interval = intervalMinutes.value * 60000;
    const idleMs = now - lastActivity;
    const sinceBackup = now - lastBackupAt.value;
    // 关键：距上次操作 ≤ 间隔（有操作，未空闲）且距上次备份 ≥ 间隔 → 备份
    if (idleMs <= interval && sinceBackup >= interval) {
      try {
        await apiPost(API.backupNow, { reason: "auto" });
        lastBackupAt.value = now;
        pollBackupDone(); // 自动备份完成 → 同步侧栏"备份：N 份快照"（静默，不打扰）
      } catch (e) {
        if (e.message.startsWith("409")) return; // 已有备份/恢复任务进行中，静默跳过
        if (toast) toast("自动备份失败：" + e.message, true);
      }
    }
  }

  function start() {
    lastActivity = Date.now();      // 登录/打开页面即活跃起点
    lastBackupAt.value = Date.now(); // 登录起点（首次自动备份发生在登录后满间隔且有操作时）
    EVENTS.forEach((ev) => window.addEventListener(ev, onActivity, { passive: true }));
    timer = setInterval(tick, 30000);
    loadConfig();
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    EVENTS.forEach((ev) => window.removeEventListener(ev, onActivity));
  }

  return { intervalMinutes, enabled, lastBackupAt, loadConfig, saveConfig, start, stop };
}
