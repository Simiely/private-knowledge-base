// 新建笔记 composable：全局"＋ 新建"对话框状态 + 创建逻辑（S25 从 App.vue 抽出）。
// 创建在 vault 根目录，创建后打开并刷新文件树；仅管理对话框与创建，不涉及路由。
import { ref } from "vue";
import { API } from "./api/endpoints.js";
import { apiPost } from "./api.js";

export function useCreateDoc({ openFile, loadTree, toast }) {
  const showCreate = ref(false);
  const createName = ref("");

  function openCreate() {
    createName.value = "";
    showCreate.value = true;
  }

  async function createNewDoc() {
    const name = createName.value.trim();
    if (!name) return toast("请输入文件名", true);
    showCreate.value = false;
    const full = name.toLowerCase().endsWith(".md") ? name : name + ".md";
    try {
      await apiPost(API.vaultFile, { path: full, content: "" });
      toast(`已创建：${full}`);
      await openFile(full);
      await loadTree(); // 刷新文件树（根目录新增节点）
    } catch (e) {
      toast(e.message.includes("409") ? `文件已存在：${full}` : `创建失败：${e.message}`, true);
    }
  }

  return { showCreate, createName, openCreate, createNewDoc };
}
