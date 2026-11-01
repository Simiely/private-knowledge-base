// 目录选择 composable：封装「磁盘+常用位置+目录树浏览」的全部状态与逻辑。
// 供 App.vue（切换库）与 BackupPanel.vue（更换备份目录）复用，消除重复实现。
import { ref } from "vue";
import { API } from "./api/endpoints.js";
import { apiGet } from "./api.js";

export function useDirPicker() {
  const showDialog = ref(false);
  const inputPath = ref("");       // 输入框当前路径
  const switching = ref(false);    // 确认中（禁用按钮）
  // 快捷位置（磁盘 + 常用）
  const quickDisks = ref([]);
  const quickPlaces = ref([]);
  // 目录浏览
  const browsePath = ref("");
  const browseParent = ref("");
  const browseDirs = ref([]);
  const browseLoading = ref(false);

  async function loadQuickAccess() {
    try {
      const d = await apiGet(API.settingsQuickAccess);
      quickDisks.value = d.disks || [];
      quickPlaces.value = d.places || [];
    } catch (_) {
      quickDisks.value = [];
      quickPlaces.value = [];
    }
  }

  async function browseTo(path) {
    browseLoading.value = true;
    try {
      const data = await apiGet(`/api/settings/browse?path=${encodeURIComponent(path || "")}`);
      browsePath.value = data.path;
      browseParent.value = data.parent;
      browseDirs.value = data.dirs;
    } catch (e) {
      throw e;
    } finally {
      browseLoading.value = false;
    }
  }

  // 打开弹窗：填入当前值并定位到其所在目录
  async function open(currentPath, toastErr) {
    inputPath.value = currentPath || "";
    showDialog.value = true;
    const start = currentPath ? currentPath.replace(/[\\/]+[^\\/]*$/, "") : "";
    try {
      await Promise.all([loadQuickAccess(), browseTo(start)]);
    } catch (e) {
      toastErr && toastErr("浏览目录失败：" + e.message, true);
    }
  }

  function close() {
    showDialog.value = false;
  }

  // 点击快捷位置：进入该目录并同步输入框
  function goQuick(item) {
    inputPath.value = item.path;
    browseTo(item.path).catch(() => {});
  }

  // 点击子目录：进入并同步输入框
  function enterDir(name) {
    const next = browsePath.value
      ? (browsePath.value.endsWith("/") || browsePath.value.endsWith("\\")
          ? browsePath.value + name
          : browsePath.value + "/" + name)
      : name;
    inputPath.value = next;
    browseTo(next).catch(() => {});
  }

  // 选当前浏览目录（双击路径栏 / 选此目录按钮）
  function pickCurrent() {
    if (browsePath.value) inputPath.value = browsePath.value;
  }

  return {
    showDialog,
    inputPath,
    switching,
    quickDisks,
    quickPlaces,
    browsePath,
    browseParent,
    browseDirs,
    browseLoading,
    open,
    close,
    goQuick,
    enterDir,
    pickCurrent,
    setSwitching: (v) => (switching.value = v),
  };
}
