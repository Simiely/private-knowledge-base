// 文件树 + 文档读写 composable（S13：从 App.vue 拆出）
import { ref } from "vue";
import { API } from "./api/endpoints.js";
import { apiGet, apiPut } from "./api.js";

export function useVaultDocs(toast) {
  const treeNodes = ref([]);
  const currentPath = ref("");
  const docContent = ref("");
  const docMeta = ref(null);
  const highlightQuery = ref("");
  const viewMode = ref("doc"); // doc | search | chat | backup

  async function loadTree() {
    try {
      treeNodes.value = await apiGet(API.vaultTree);
    } catch (e) {
      toast("加载目录失败：" + e.message, true);
    }
  }

  async function loadDir(path) {
    try {
      const nodes = await apiGet(`${API.vaultTree}?path=${encodeURIComponent(path)}`);
      const dir = findNode(treeNodes.value, path);
      if (dir) {
        dir.children = nodes;
        dir.childrenLoaded = true; // 标记已加载，避免重复请求
      }
    } catch (e) {
      toast("加载子目录失败：" + e.message, true);
    }
  }

  function findNode(nodes, path) {
    for (const n of nodes) {
      if (n.path === path) return n;
      if (n.children) {
        const hit = findNode(n.children, path);
        if (hit) return hit;
      }
    }
    return null;
  }

  async function openFile(path, query = "") {
    try {
      const data = await apiGet(`${API.vaultFile}?path=${encodeURIComponent(path)}`);
      currentPath.value = path;
      docContent.value = data.content;
      docMeta.value = data.meta;
      highlightQuery.value = query;
      viewMode.value = "doc";
    } catch (e) {
      toast("打开失败：" + e.message, true);
    }
  }

  async function saveDoc(content) {
    try {
      await apiPut(API.vaultFile, { path: currentPath.value, content });
      toast("已保存 ✓");
      await openFile(currentPath.value);
    } catch (e) {
      toast("保存失败：" + e.message, true);
    }
  }

  // 关闭当前文档（删除后回到空状态）
  function closeDoc() {
    currentPath.value = "";
    docContent.value = "";
    docMeta.value = null;
    highlightQuery.value = "";
  }

  return {
    treeNodes,
    currentPath,
    docContent,
    docMeta,
    highlightQuery,
    viewMode,
    loadTree,
    loadDir,
    findNode,
    openFile,
    saveDoc,
    closeDoc,
  };
}
