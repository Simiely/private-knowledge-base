// TOC 滚动高亮 composable（S25 从 DocView 抽出）：点击跳转 + 滚动跟踪当前章节。
// 双机制：IntersectionObserver（标准） + scroll 监听兜底（headless 等环境 IO 不可靠）。
import { ref, onMounted, onUnmounted } from "vue";

export function useToc(headings) {
  const activeToc = ref(""); // 当前高亮的标题 id
  let tocObserver = null;
  let scrollRaf = null;

  // 点击目录项 → 立即高亮 + 平滑滚动（不依赖观察器，反馈可靠）
  function jumpTo(id) {
    activeToc.value = id;
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // 绑定观察器：标题进入视口顶部 25% → 设为当前章节
  function bindTocObserver() {
    if (tocObserver) tocObserver.disconnect();
    const els = headings.value.map((h) => document.getElementById(h.id)).filter(Boolean);
    if (!els.length) {
      activeToc.value = "";
      return;
    }
    tocObserver = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length) {
          let best = null;
          for (const e of visible) {
            if (!best || e.boundingClientRect.top < best.boundingClientRect.top) best = e;
          }
          if (best) activeToc.value = best.target.id;
        }
      },
      { rootMargin: "0px 0px -75% 0px", threshold: 0 }
    );
    els.forEach((el) => tocObserver.observe(el));
  }

  // 滚动兜底：当前章节 = 最后一个顶部 <= 100px 的标题（rAF 节流）
  function onDocScroll() {
    if (scrollRaf) return;
    scrollRaf = requestAnimationFrame(() => {
      scrollRaf = null;
      let cur = "";
      for (const h of headings.value) {
        const el = document.getElementById(h.id);
        if (el && el.getBoundingClientRect().top <= 100) cur = h.id;
      }
      if (cur) activeToc.value = cur;
    });
  }

  onMounted(() => {
    document.addEventListener("scroll", onDocScroll, { passive: true, capture: true });
  });

  onUnmounted(() => {
    if (tocObserver) tocObserver.disconnect();
    if (scrollRaf) cancelAnimationFrame(scrollRaf);
    document.removeEventListener("scroll", onDocScroll, { capture: true });
  });

  return { activeToc, jumpTo, bindTocObserver };
}
