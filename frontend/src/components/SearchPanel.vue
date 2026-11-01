<script setup>
// 搜索结果面板：片段内命中词用 <mark> 高亮（英文大小写不敏感，保留原文大小写）
import { esc } from "../md.js";
import { escapeRegex } from "../mdEnhance.js";

/**
 * 搜索结果面板：片段内命中词用 <mark> 高亮（英文大小写不敏感，保留原文大小写）。
 * @prop {Array<{path:string, title:string, snippets:Array<{text:string, hitWords:Array<string>}>}>} results
 * @prop {number} total 命中总数
 * @prop {string} query 当前搜索词
 * @event select - 点击结果：`(path: string, query: string)`
 */
const props = defineProps({
  results: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  query: { type: String, default: "" },
});
const emit = defineEmits(["select"]);

// 将片段文本中的命中词包上 <mark>：先转义再替换（防 XSS），gi 匹配保留原文大小写
function highlight(text, hitWords) {
  let html = esc(text);
  const words = [...new Set((hitWords || []).filter((w) => w && w.length))];
  if (!words.length) return html;
  // 按长度降序替换，避免短词先命中破坏长词匹配
  words.sort((a, b) => b.length - a.length);
  for (const w of words) {
    const safe = esc(w);
    html = html.replace(new RegExp(escapeRegex(safe), "gi"), (m) => `<mark>${m}</mark>`);
  }
  return html;
}
</script>

<template>
  <section class="search-panel">
    <div v-if="total === 0" class="empty">未找到与「{{ query }}」相关的结果</div>
    <template v-else>
      <div class="search-meta">共 {{ total }} 条结果（{{ query }}）</div>
      <div
        v-for="r in results"
        :key="r.path"
        class="search-hit"
        @click="emit('select', r.path)"
      >
        <div class="hit-title">{{ r.title }}</div>
        <div class="hit-path">{{ r.path }}</div>
        <div v-if="r.snippets && r.snippets[0]" class="hit-snippet" v-html="highlight(r.snippets[0].text, r.snippets[0].hitWords)"></div>
        <span v-for="t in r.tags" :key="t" class="tag">#{{ t }}</span>
      </div>
    </template>
  </section>
</template>
