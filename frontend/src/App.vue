<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { apiDelete, apiGet, apiPost, apiPut } from "./api.js";
import { renderMarkdown } from "./md.js";

const authed = ref(null);
const loginToken = ref("");
const loginError = ref("");
const view = ref("search");
const query = ref("");
const results = ref([]);
const total = ref(0);
const searching = ref(false);
const error = ref("");
const tags = ref([]);
const recent = ref(JSON.parse(localStorage.getItem("oa_recent") || "[]"));
const note = ref(null);
const noteHtml = ref("");
const draft = ref("");
const editing = ref(false);
const saving = ref(false);
const indexStatus = ref(null);
const snapshots = ref([]);
const snapshotsLoading = ref(false);
const backupBusy = ref(false);
const backupMsg = ref("");
const semanticStatus = ref(null);
const versions = ref([]);
const versionsFor = ref("");
const versionsLoading = ref(false);
const showVersions = ref(false);
let searchTimer = null;

const hasQuery = computed(() => query.value.trim().length > 0);

onMounted(async () => {
  try {
    const me = await apiGet("/api/auth/me");
    authed.value = true;
    if (me && me.authDisabled) loginToken.value = "";
    await loadHome();
  } catch {
    authed.value = false;
  }
});

watch(query, () => {
  clearTimeout(searchTimer);
  if (!query.value.trim()) {
    results.value = [];
    total.value = 0;
    return;
  }
  searchTimer = setTimeout(runSearch, 220);
});

async function login() {
  loginError.value = "";
  try {
    await apiPost("/api/auth/login", { token: loginToken.value });
    authed.value = true;
    await loadHome();
  } catch (e) {
    loginError.value = e.message || "登录失败";
  }
}

async function logout() {
  try { await apiPost("/api/auth/logout", {}); } catch { /* ignore */ }
  authed.value = false;
  view.value = "search";
}

async function loadHome() {
  try {
    const [tagList, status] = await Promise.all([
      apiGet("/api/search/tags"),
      apiGet("/api/index/status"),
    ]);
    tags.value = tagList || [];
    indexStatus.value = status;
  } catch (e) {
    error.value = e.message;
  }
}

async function runSearch() {
  const q = query.value.trim();
  if (!q) return;
  searching.value = true;
  error.value = "";
  try {
    const body = await apiGet(`/api/search?q=${encodeURIComponent(q)}&pageSize=30&mode=or`);
    results.value = body.results || [];
    total.value = body.total || 0;
  } catch (e) {
    error.value = e.message;
    results.value = [];
  } finally {
    searching.value = false;
  }
}

async function openNote(path) {
  if (!path) return;
  error.value = "";
  try {
    const body = await apiGet(`/api/vault/file?path=${encodeURIComponent(path)}`);
    note.value = body;
    const rendered = renderMarkdown(body.content || "", { basePath: path });
    noteHtml.value = rendered.html;
    view.value = "reader";
    remember(path);
  } catch (e) {
    error.value = e.message;
  }
}

function remember(path) {
  const next = [path, ...recent.value.filter((p) => p !== path)].slice(0, 8);
  recent.value = next;
  localStorage.setItem("oa_recent", JSON.stringify(next));
}

function startEdit() {
  draft.value = note.value?.content || "";
  editing.value = true;
  view.value = "editor";
}

async function saveEdit() {
  if (!note.value) return;
  saving.value = true;
  error.value = "";
  try {
    await apiPut("/api/vault/file", { path: note.value.path, content: draft.value });
    note.value.content = draft.value;
    const rendered = renderMarkdown(draft.value, { basePath: note.value.path });
    noteHtml.value = rendered.html;
    editing.value = false;
    view.value = "reader";
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

function cancelEdit() {
  editing.value = false;
  view.value = "reader";
}

// ---- 备份 / 版本历史 ----
function fmtTime(t) {
  if (!t) return "—";
  const d = typeof t === "number" ? new Date(t * 1000) : new Date(t);
  return Number.isNaN(d.getTime()) ? String(t) : d.toLocaleString("zh-CN");
}

async function loadSemanticStatus() {
  try {
    semanticStatus.value = await apiGet("/api/semantic/status");
  } catch (e) {
    semanticStatus.value = { enabled: false, error: e.message };
  }
}

async function rebuildVectors() {
  try {
    await apiPost("/api/semantic/rebuild", {}, { timeoutMs: 30000 });
    backupMsg.value = "向量重建已开始（CPU 上大库需要几分钟，可稍后刷新状态）";
  } catch (e) {
    backupMsg.value = `重建失败：${e.message}`;
  }
}

async function loadSnapshots() {
  snapshotsLoading.value = true;
  try {
    const body = await apiGet("/api/backup/list");
    snapshots.value = body.snapshots || [];
  } catch (e) {
    backupMsg.value = e.message;
  } finally {
    snapshotsLoading.value = false;
  }
}

async function runBackupNow() {
  backupBusy.value = true;
  backupMsg.value = "正在创建快照…（大库可能需要几十秒）";
  try {
    await apiPost("/api/backup/now", { reason: "manual" }, { timeoutMs: 180000 });
    for (let i = 0; i < 90; i++) {
      const st = await apiGet("/api/backup/status");
      if (!st.running) break;
      await new Promise((r) => setTimeout(r, 1000));
    }
    await loadSnapshots();
    backupMsg.value = "快照已创建";
  } catch (e) {
    backupMsg.value = `备份失败：${e.message}`;
  } finally {
    backupBusy.value = false;
  }
}

async function loadVersions(path) {
  versionsFor.value = path;
  versions.value = [];
  showVersions.value = true;
  versionsLoading.value = true;
  try {
    const body = await apiGet(`/api/backup/history?path=${encodeURIComponent(path)}`);
    versions.value = body.versions || [];
  } catch (e) {
    error.value = e.message;
  } finally {
    versionsLoading.value = false;
  }
}

async function restoreVersion(v) {
  if (!versionsFor.value) return;
  const label = v.source === "pre-write" ? "写前备份" : `快照 ${v.snapshotId}`;
  if (!window.confirm(`恢复「${versionsFor.value}」到 ${label}？当前内容会被覆盖（覆盖前会自动备份）。`)) return;
  try {
    await apiPost(
      "/api/backup/restore-file",
      { path: versionsFor.value, snapshotId: v.snapshotId },
      { timeoutMs: 60000 },
    );
    showVersions.value = false;
    await openNote(versionsFor.value);
    backupMsg.value = "已恢复";
  } catch (e) {
    error.value = e.message;
  }
}

async function restoreSnapshot(s) {
  const code = window.prompt(
    `恢复整库到快照 ${s.id}？\n当前整个 vault 会被覆盖（覆盖前自动备份）。\n输入 RESTORE 确认：`,
  );
  if (code === null) return;
  if (code.trim() !== "RESTORE") {
    error.value = "确认码不正确，已取消";
    return;
  }
  try {
    await apiPost(
      "/api/backup/restore",
      { snapshotId: s.id, confirmCode: "RESTORE" },
      { timeoutMs: 30000 },
    );
    backupMsg.value = "整库恢复已开始（后台执行，完成后索引自动重建）";
  } catch (e) {
    error.value = e.message;
  }
}

async function deleteSnapshot(s) {
  if (!window.confirm(`删除快照 ${s.id}？不影响当前笔记内容。`)) return;
  try {
    await apiDelete(`/api/backup/${encodeURIComponent(s.id)}`);
    await loadSnapshots();
  } catch (e) {
    error.value = e.message;
  }
}

async function onDocClick(event) {
  const link = event.target.closest("a.wikilink, a[data-md-path], .md-link");
  if (!link) return;
  const name = link.dataset.path || link.dataset.mdPath;
  if (!name) return;
  event.preventDefault();
  const raw = name.replace(/\.md$/i, "");
  try {
    const found = await apiGet(`/api/vault/resolve-md?name=${encodeURIComponent(raw)}`);
    await openNote(found.path);
  } catch (e) {
    error.value = e.message;
  }
}

function useTag(tag) {
  query.value = tag;
  view.value = "search";
}

function backToSearch() {
  view.value = "search";
}

function openSettings() {
  view.value = "settings";
  loadHome();
  loadSnapshots();
  loadSemanticStatus();
  backupMsg.value = "";
}
</script>

<template>
  <div class="app">
    <header class="topbar">
      <button class="brand" @click="backToSearch">私人知识库</button>
      <div class="search-wrap" v-if="authed">
        <input
          v-model="query"
          class="search-input"
          type="search"
          placeholder="输入一句话、几个词，或拼音，例如：上次那个 docker 部署"
          @focus="view = 'search'"
        />
        <span v-if="searching" class="search-state">搜索中…</span>
      </div>
      <nav class="nav">
        <button class="nav-btn" @click="backToSearch">搜索</button>
        <button class="nav-btn" @click="openSettings">设置</button>
        <button class="nav-btn ghost" @click="logout">退出</button>
      </nav>
    </header>

    <main v-if="authed" class="main">
      <section v-if="view === 'search'" class="search-view">
        <div class="hero" v-if="!hasQuery">
          <h1>快速找到那篇笔记</h1>
          <p>支持中文、拼音、错字和自然语言描述。不需要记文件名。</p>
        </div>

        <div v-if="!hasQuery" class="home-grid">
          <section class="panel">
            <h2>最近打开</h2>
            <ul class="plain-list">
              <li v-for="p in recent" :key="p">
                <button class="link-btn" @click="openNote(p)">{{ p }}</button>
              </li>
              <li v-if="!recent.length" class="muted">还没有打开过笔记</li>
            </ul>
          </section>
          <section class="panel">
            <h2>常用标签</h2>
            <div class="chips">
              <button v-for="t in tags.slice(0, 24)" :key="t.tag" class="chip" @click="useTag(t.tag)">
                {{ t.tag }} <span class="chip-count">{{ t.count }}</span>
              </button>
              <span v-if="!tags.length" class="muted">暂无标签</span>
            </div>
          </section>
        </div>

        <div v-if="hasQuery" class="results-head">
          <span>{{ total }} 条结果</span>
          <span class="muted">模糊模式</span>
        </div>

        <ul class="results">
          <li v-for="item in results" :key="item.doc_id || item.path" class="result-card" @click="openNote(item.path)">
            <div class="result-title">{{ item.title || item.path }}</div>
            <div class="result-path">{{ item.path }}</div>
            <div class="result-snippet" v-if="item.snippets && item.snippets.length">
              {{ item.snippets[0].text }}
            </div>
            <div class="result-tags">
              <span v-for="tag in item.tags" :key="tag" class="tag">#{{ tag }}</span>
            </div>
          </li>
        </ul>
        <div v-if="hasQuery && !searching && !results.length" class="empty">
          没有找到。试试更短的词、拼音，或换个说法。
        </div>
      </section>

      <section v-if="view === 'reader'" class="doc-view">
        <div class="doc-head">
          <button class="back-btn" @click="backToSearch">← 返回搜索</button>
          <div class="head-actions">
            <button class="back-btn" @click="loadVersions(note.path)">版本历史</button>
            <button class="primary-btn" @click="startEdit">编辑</button>
          </div>
        </div>
        <h1 class="doc-title">{{ note?.path }}</h1>
        <div class="doc-meta">{{ note?.meta?.size }} 字节 · {{ note?.meta?.encoding }}</div>
        <article class="markdown-body" v-html="noteHtml" @click="onDocClick"></article>
      </section>

      <section v-if="view === 'editor'" class="editor-view">
        <div class="doc-head">
          <button class="back-btn" @click="cancelEdit">← 取消</button>
          <button class="primary-btn" :disabled="saving" @click="saveEdit">
            {{ saving ? "保存中…" : "保存" }}
          </button>
        </div>
        <h1 class="doc-title">{{ note?.path }}</h1>
        <textarea v-model="draft" class="editor" spellcheck="false"></textarea>
      </section>

      <section v-if="view === 'settings'" class="settings-view">
        <h1>设置</h1>
        <div class="panel">
          <h2>索引状态</h2>
          <dl class="kv">
            <dt>状态</dt><dd>{{ indexStatus?.state || "未知" }}</dd>
            <dt>文档数</dt><dd>{{ indexStatus?.totalFiles ?? "—" }}</dd>
            <dt>最近重建</dt><dd>{{ indexStatus?.lastFullAt || "—" }}</dd>
            <dt>索引后端</dt><dd>{{ indexStatus?.backend || "—" }}</dd>
          </dl>
        </div>
        <div class="panel">
          <div class="panel-head">
            <h2>语义检索</h2>
            <button v-if="semanticStatus?.enabled" class="back-btn small" @click="rebuildVectors">
              重建向量
            </button>
          </div>
          <template v-if="semanticStatus?.enabled">
            <dl class="kv">
              <dt>模型</dt><dd>{{ semanticStatus.model }}</dd>
              <dt>向量数</dt><dd>{{ semanticStatus.vectors }}</dd>
              <dt>状态</dt>
              <dd>{{ semanticStatus.building ? "构建中…" : semanticStatus.ready ? "就绪（参与融合排序）" : "未就绪" }}</dd>
              <dt>最近构建</dt><dd>{{ semanticStatus.lastBuiltAt || "—" }}</dd>
            </dl>
            <p v-if="semanticStatus.error" class="notice">{{ semanticStatus.error }}</p>
          </template>
          <p v-else class="muted">
            未启用。当前只用关键词 + 拼音 + 错字检索。启用需安装 <code>.[semantic]</code> 并设
            <code>SEMANTIC_ENABLED=true</code>。
          </p>
        </div>
        <div class="panel">
          <h2>本地模型连接（MCP）</h2>
          <p class="muted">本程序不提供聊天框。本地模型通过 MCP 只读工具自行搜索和读取。</p>
          <dl class="kv">
            <dt>传输</dt><dd>Streamable HTTP</dd>
            <dt>地址</dt><dd><code>http://127.0.0.1:8090/mcp</code></dd>
            <dt>鉴权</dt><dd><code>Authorization: Bearer &lt;MCP_TOKEN&gt;</code></dd>
            <dt>工具</dt><dd><code>search_notes / read_note / read_section / list_tags</code></dd>
          </dl>
        </div>
        <div class="panel">
          <div class="panel-head">
            <h2>备份与版本</h2>
            <button class="primary-btn small" :disabled="backupBusy" @click="runBackupNow">
              {{ backupBusy ? "备份中…" : "立即备份" }}
            </button>
          </div>
          <p class="muted">整库硬链接快照；恢复前会自动把当前内容再备份一次。</p>
          <div v-if="backupMsg" class="notice">{{ backupMsg }}</div>
          <ul class="snap-list">
            <li v-for="s in snapshots" :key="s.id" class="snap-row">
              <div class="snap-main">
                <span class="snap-id">{{ s.id }}</span>
                <span class="muted">{{ fmtTime(s.createdAt) }} · {{ s.files }} 文件 · {{ s.verify || "—" }}</span>
              </div>
              <div class="snap-actions">
                <button class="back-btn small" @click="restoreSnapshot(s)">恢复</button>
                <button class="back-btn small danger-text" @click="deleteSnapshot(s)">删除</button>
              </div>
            </li>
            <li v-if="snapshotsLoading" class="muted">加载中…</li>
            <li v-else-if="!snapshots.length" class="muted">还没有快照，点「立即备份」创建第一份。</li>
          </ul>
        </div>
        <div class="panel">
          <h2>导出</h2>
          <p class="muted">整库打包为 ZIP，保留目录与附件，可直接用 Obsidian 打开。</p>
          <a class="primary-btn" href="/api/export" download>导出整库 ZIP</a>
        </div>
        <div class="panel danger">
          <h2>安全提醒</h2>
          <p>数据未加密落盘；请开启 BitLocker，并只在本机/局域网使用。生产环境保持 AUTH_DISABLED=false。</p>
        </div>
      </section>

      <div v-if="error" class="error">{{ error }}</div>
    </main>

    <main v-else-if="authed === false" class="login-view">
      <div class="login-card">
        <h1>私人知识库</h1>
        <p class="muted">输入访问口令。数据只在本机。</p>
        <input v-model="loginToken" class="login-input" type="password" placeholder="访问口令" @keyup.enter="login" />
        <button class="primary-btn wide" @click="login">进入</button>
        <div v-if="loginError" class="error">{{ loginError }}</div>
      </div>
    </main>

    <div v-if="showVersions" class="modal-mask" @click.self="showVersions = false">
      <div class="modal">
        <div class="panel-head">
          <h2>版本历史</h2>
          <button class="back-btn small" @click="showVersions = false">关闭</button>
        </div>
        <p class="muted path-line">{{ versionsFor }}</p>
        <ul class="snap-list">
          <li v-for="v in versions" :key="v.snapshotId + v.at" class="snap-row">
            <div class="snap-main">
              <span class="snap-id">{{ v.source === "pre-write" ? "写前备份" : v.snapshotId }}</span>
              <span class="muted">{{ fmtTime(v.at) }}</span>
            </div>
            <div class="snap-actions">
              <button class="back-btn small" @click="restoreVersion(v)">恢复此版本</button>
            </div>
          </li>
          <li v-if="versionsLoading" class="muted">查询中…</li>
          <li v-else-if="!versions.length" class="muted">这篇笔记还没有历史版本（先创建一次快照或编辑一次）。</li>
        </ul>
      </div>
    </div>
  </div>
</template>
