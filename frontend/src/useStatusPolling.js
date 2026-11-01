// 索引状态轮询（模块级单例，S17 优化）
// 设计：refs 定义在模块顶层，App.vue 与 StatusBar 共享同一份状态；
//      轮询定时器只启动一次（start），更新只触发订阅者（StatusBar）重渲染，
//      避免整个 App.vue 因 5s 轮询频繁重渲染（大文档页面卡顿的根源）。
import { ref } from "vue";
import { API } from "./api/endpoints.js";
import { apiGet } from "./api.js";

const indexStatus = ref("索引：-");
const indexOk = ref(false);
const version = ref("");

let timer = null;
let started = false;

async function refreshStatus() {
  try {
    const st = await apiGet(API.indexStatus);
    if (st.state === "ready") {
      indexStatus.value = st.vaultFiles
        ? `索引：就绪 (${st.totalFiles} md · ${st.vaultFiles} 文件)`
        : `索引：就绪 (${st.totalFiles})`;
    } else {
      indexStatus.value = "索引：构建中…";
    }
    indexOk.value = st.state === "ready";
  } catch (_) { /* ignore */ }
}

async function loadVersion() {
  try {
    const h = await apiGet(API.health);
    version.value = h.version;
  } catch (_) { /* ignore */ }
}

export function startStatusPolling(pollMs = 5000) {
  if (started) return;
  started = true;
  refreshStatus();
  loadVersion();
  timer = setInterval(refreshStatus, pollMs);
}

export function stopStatusPolling() {
  if (timer) clearInterval(timer);
  timer = null;
  started = false;
}

export function useStatusPolling() {
  return { indexStatus, indexOk, version, refreshStatus };
}
