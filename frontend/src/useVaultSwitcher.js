// Vault 切换 composable：当前库路径 + 检测 + 切换（S25 从 App.vue 抽出）。
// 与 useDirPicker（目录浏览 UI）配合：切换走同一个对话框。
// onSwitched 回调：切换成功后由调用方做视图重置（清空文档/搜索/视图模式等）。
import { ref } from "vue";
import { API } from "./api/endpoints.js";
import { apiGet, apiPost } from "./api.js";

export function useVaultSwitcher(picker, { loadTree, openFile, toast, onSwitched }) {
  const vaultPath = ref("");
  const detectedVaults = ref([]);
  const detectLoading = ref(false);

  async function loadVaultPath() {
    try {
      const s = await apiGet(API.settingsVault);
      vaultPath.value = s.path || "";
    } catch (_) {
      /* ignore */
    }
  }

  // 打开弹窗：并行加载自动检测库 + 目录选择器初始化
  async function openVaultDialog() {
    picker.setSwitching(false);
    picker.open(vaultPath.value, toast);
    await detectVaultsNow();
  }

  // 自动检测本机 Obsidian 库
  async function detectVaultsNow() {
    detectLoading.value = true;
    try {
      const d = await apiGet(API.settingsDetect);
      detectedVaults.value = d.vaults || [];
    } catch (_) {
      detectedVaults.value = [];
    } finally {
      detectLoading.value = false;
    }
  }

  // 点击检测到的库：填入路径并立即切换（一步到位）
  function pickVault(v) {
    picker.inputPath.value = v.path;
    switchVault();
  }

  async function switchVault() {
    const path = picker.inputPath.value.trim();
    if (!path) return toast("请选择或输入库路径", true);
    picker.setSwitching(true);
    try {
      const r = await apiPost(API.settingsVault, { path });
      toast(`已切换到：${r.path}，正在重建索引…`);
      picker.close();
      await Promise.all([loadTree(), loadVaultPath()]);
      await openFile(""); // 重置文档视图
      onSwitched && onSwitched();
    } catch (e) {
      toast("切换失败：" + e.message, true);
    } finally {
      picker.setSwitching(false);
    }
  }

  return {
    vaultPath,
    detectedVaults,
    detectLoading,
    loadVaultPath,
    openVaultDialog,
    detectVaultsNow,
    pickVault,
    switchVault,
  };
}
