<script setup>
// 文档视图：阅读（渲染）/ 编辑（纯文本原样保存，坑 #1：不做 WYSIWYG）
import { ref, watch, nextTick, computed } from "vue";
import { renderMarkdown } from "../md.js";
import { enhanceDom } from "../mdEnhance.js";
import { useToc } from "../useToc.js";
import ConfirmDialog from "./ConfirmDialog.vue";

/**
 * 文档视图：阅读（渲染）/ 编辑（纯文本原样保存）。
 * @prop {string} path 文件相对路径
 * @prop {string} content 文档内容
 * @prop {string} highlightQuery 搜索词（打开后正文高亮 + 滚动定位）
 * @event save - 保存编辑内容：`(content: string)`
 * @event open-path - 点击文档内链接请求打开目标：`({ path: string, wikilink: boolean })`
 * @event delete-doc - 确认删除当前文档：`(path: string)`
 */
const props = defineProps({
  path: { type: String, default: "" },
  content: { type: String, default: "" },
  highlightQuery: { type: String, default: "" },
});
const emit = defineEmits(["save", "open-path", "delete-doc"]);

const mode = ref("read");
const draft = ref("");
const viewEl = ref(null);
const showDelete = ref(false); // 删除确认对话框
const showTocSheet = ref(false); // 移动端底部抽屉目录

const rendered = computed(() =>
  props.content ? renderMarkdown(props.content, { basePath: props.path }) : { html: "", headings: [] }
);
const html = computed(() => rendered.value.html);
const headings = computed(() => rendered.value.headings || []);

// TOC 滚动高亮（点击跳转 + 当前章节跟踪）
const { activeToc, jumpTo, bindTocObserver } = useToc(headings);

// 打开新文档/内容变化 → 回到阅读模式
watch(
  () => [props.path, props.content],
  () => {
    mode.value = "read";
    draft.value = props.content;
  },
  { immediate: true }
);

// 渲染完成后：DOM 增强 + 绑定 TOC 观察器
watch(
  () => html.value,
  async () => {
    await nextTick();
    if (viewEl.value) {
      enhanceDom(viewEl.value, props.highlightQuery);
      bindTocObserver();
    }
  }
);

function startEdit() {
  draft.value = props.content;
  mode.value = "edit";
}

// 删除文档：打开确认对话框（危险操作）
function askDelete() {
  showDelete.value = true;
}

function doDelete() {
  showDelete.value = false;
  emit("delete-doc", props.path);
}

function cancel() {
  mode.value = "read";
}

function save() {
  if (draft.value !== props.content) emit("save", draft.value);
  else mode.value = "read";
}

function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "s") {
    e.preventDefault();
    save();
  }
}

// 点击委托：代码块复制按钮 / wikilink / md 链接；外部链接不拦截
function onDocClick(e) {
  // 代码块复制
  const copyBtn = e.target.closest(".code-copy");
  if (copyBtn) {
    const code = copyBtn.closest(".code-wrap")?.querySelector("pre.code-block code");
    if (code) {
      copyText(code.textContent).then((ok) => {
        copyBtn.textContent = ok ? "✓" : "✕";
        copyBtn.title = ok ? "已复制" : "复制失败";
        setTimeout(() => {
          copyBtn.textContent = "⧉";
          copyBtn.title = "复制代码";
        }, 1500);
      });
    }
    return;
  }
  const a = e.target.closest("a");
  if (!a) return;
  if (a.classList.contains("wikilink")) {
    e.preventDefault();
    const p = a.dataset.path; // 文件名（Obsidian 全库匹配）
    if (p) emit("open-path", { path: p, wikilink: true });
  } else if (a.classList.contains("md-link")) {
    e.preventDefault();
    const p = a.dataset.mdPath; // 已解析的 vault 相对路径
    if (p) emit("open-path", { path: p, wikilink: false });
  }
}

// 复制文本到剪贴板（优先 Clipboard API，降级 execCommand）
function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text).then(() => true, () => false);
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return Promise.resolve(ok);
  } catch (_) {
    return Promise.resolve(false);
  }
}
</script>

<template>
  <div class="doc" @click="onDocClick">
    <div class="doc-header">
      <span class="doc-path" :title="path">{{ path }}</span>
      <div class="actions">
        <button v-if="mode === 'read'" class="btn primary" @click="startEdit">编辑</button>
        <button v-if="mode === 'read'" class="btn" title="删除当前文档" @click="askDelete">删除</button>
        <template v-else>
          <button class="btn primary" @click="save">保存</button>
          <button class="btn" @click="cancel">取消</button>
        </template>
      </div>
    </div>
    <div class="doc-body">
      <article v-if="mode === 'read'" ref="viewEl" class="markdown-body" v-html="html"></article>
      <textarea
        v-else
        v-model="draft"
        class="editor"
        spellcheck="false"
        @keydown="onKeydown"
      ></textarea>
      <!-- 右侧标题导航（大纲）：仅阅读模式 + 有标题时显示 -->
      <nav v-if="mode === 'read' && headings.length" class="doc-toc" aria-label="目录">
        <div class="doc-toc-title">目录</div>
        <a
          v-for="h in headings"
          :key="h.id"
          class="doc-toc-item"
          :class="['lvl-' + h.level, { active: activeToc === h.id }]"
          :title="h.text"
          @click.prevent="jumpTo(h.id)"
        >{{ h.text }}</a>
      </nav>
    </div>

    <!-- 移动端悬浮"目录"按钮（<1000px 显示，标题 >=3 条时可用），纯图标无文字 -->
    <button
      v-if="mode === 'read' && headings.length >= 3"
      class="toc-fab"
      title="目录"
      @click.stop="showTocSheet = true"
    ><span class="toc-fab-icon">☰</span></button>

    <!-- 移动端底部抽屉目录 -->
    <div v-if="showTocSheet" class="toc-mask" @click.self="showTocSheet = false">
      <div class="toc-sheet" role="dialog" aria-label="目录">
        <div class="toc-sheet-title">目录</div>
        <div class="toc-sheet-list">
          <a
            v-for="h in headings"
            :key="h.id"
            class="doc-toc-item"
            :class="['lvl-' + h.level, { active: activeToc === h.id }]"
            :title="h.text"
            @click.prevent="jumpTo(h.id); showTocSheet = false"
          >{{ h.text }}</a>
        </div>
      </div>
    </div>

    <!-- 删除确认对话框 -->
    <ConfirmDialog
      :show="showDelete"
      title="删除文档"
      :message="`确定删除「${path}」？此操作不可恢复。`"
      confirm-text="删除"
      danger
      @confirm="doDelete"
      @cancel="showDelete = false"
    />
  </div>
</template>
