// 搜索 composable（S13：从 App.vue 拆出）
import { ref } from "vue";
import { API } from "./api/endpoints.js";
import { apiGet } from "./api.js";

export function useSearch(toast, setViewMode) {
  const searchResults = ref([]);
  const searchTotal = ref(0);
  const searchQuery = ref("");

  async function runSearch() {
    const q = searchQuery.value.trim();
    if (!q) return;
    try {
      const data = await apiGet(`${API.search}?q=${encodeURIComponent(q)}&page=1&pageSize=20`);
      searchResults.value = data.results;
      searchTotal.value = data.total;
      setViewMode("search");
    } catch (e) {
      toast("搜索失败：" + e.message, true);
    }
  }

  function reset() {
    searchResults.value = [];
  }

  return { searchResults, searchTotal, searchQuery, runSearch, reset };
}
