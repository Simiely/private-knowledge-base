// Hash 路由 composable：视图与当前文档进 URL，支持浏览器前进/后退。
// 从 App.vue 抽出（S25 模块化）：parseHash / syncHash / onHashChange / 监听注册。
// 格式：#/doc、#/search、#/chat、#/backup、#/doc/<encodeURIComponent(路径)>
import { watch } from "vue";

const VIEW_HASH = { doc: "#/doc", search: "#/search", chat: "#/chat", backup: "#/backup" };

function parseHash() {
  const raw = (location.hash || "#/doc").replace(/^#\/?/, ""); // "doc/路径" | "doc" | ""
  const seg = raw.split("/");
  const mode = VIEW_HASH[seg[0]] ? seg[0] : "doc";
  const path = seg.length > 1 ? decodeURIComponent(seg.slice(1).join("/")) : "";
  return { mode, path };
}

export function useHashRouter({ viewMode, currentPath, openFile }) {
  let syncing = false; // 防循环：hashchange 与 watch 互斥

  // viewMode / currentPath → 更新 hash（产生历史记录，供前进/后退）
  function syncHash() {
    const target =
      viewMode.value === "doc" && currentPath.value
        ? `#/doc/${encodeURIComponent(currentPath.value)}`
        : VIEW_HASH[viewMode.value] || "#/doc";
    if (location.hash !== target && !syncing) {
      syncing = true;
      location.hash = target;
      syncing = false;
    }
  }

  // hash 变化（浏览器前进/后退/手改地址）→ 更新视图与文档
  async function onHashChange() {
    const { mode, path } = parseHash();
    if (viewMode.value !== mode) viewMode.value = mode;
    if (mode === "doc" && path && path !== currentPath.value) {
      await openFile(path);
    }
  }

  function start() {
    watch([viewMode, currentPath], syncHash, { flush: "sync" });
    window.addEventListener("hashchange", onHashChange);
  }

  function stop() {
    window.removeEventListener("hashchange", onHashChange);
  }

  // 初始化：读 hash 恢复视图（供 onMounted 调用，返回 {mode, path} 供恢复文档）
  function init() {
    return parseHash();
  }

  return { init, start, stop };
}
