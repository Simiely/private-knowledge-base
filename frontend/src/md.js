// Markdown 渲染：markdown-it + Obsidian 方言（wikilink / callout / 高亮 / frontmatter）
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({
  html: false,
  linkify: false,
  breaks: true,
  // 无语法高亮库：代码块渲染由自定义 fence 规则负责（含复制按钮）
});

// ---- 代码块渲染：包复制按钮（Obsidian 同款：hover 右上角 ⧉ 复制） ----
// 用自定义 fence 规则而非 highlight 选项——highlight 返回值不以 <pre 开头时
// 会被 markdown-it 再包一层 <pre><code>，导致结构错乱。
md.renderer.rules.fence = function (tokens, idx, options, env, self) {
  const token = tokens[idx];
  const info = token.info ? md.utils.unescapeAll(token.info).trim() : "";
  const lang = info.split(/\s+/g)[0] || "";
  const code = md.utils.escapeHtml(token.content);
  const langAttr = lang ? ` data-lang="${md.utils.escapeHtml(lang)}"` : "";
  return `<div class="code-wrap"><button type="button" class="code-copy" title="复制代码">⧉</button><pre class="code-block"${langAttr}><code>${code}</code></pre></div>`;
};

// ---- 插件：wikilink [[目标|别名]] ----
md.inline.ruler.before("link", "wikilink", (state, silent) => {
  const m = state.src.slice(state.pos).match(/^\[\[([^\]|#]+?)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]/);
  if (!m) return false;
  if (silent) return true;
  const target = m[1].replace(/\.md$/i, "");
  const label = m[2] || target;
  const open = state.push("wikilink_open", "a", 1);
  open.attrSet("class", "wikilink");
  open.attrSet("data-path", target + ".md");
  const text = state.push("text", "", 0);
  text.content = label;
  state.push("wikilink_close", "a", -1);
  state.pos += m[0].length;
  return true;
});

// ---- 插件：图片 wikilink ![[目标.png|别名]]（Obsidian 图片引用） ----
md.inline.ruler.before("link", "image_wikilink", (state, silent) => {
  const m = state.src.slice(state.pos).match(/^!\[\[([^\]|#]+?)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]/);
  if (!m) return false;
  if (silent) return true;
  const target = m[1].replace(/^\.\//, "");
  const alt = m[2] || "";
  const token = state.push("image", "img", 0);
  token.attrSet("src", target);
  if (alt) token.attrSet("alt", alt);
  token.meta = { wikilink: true }; // 全库文件名匹配（Obsidian 语义），不做目录拼接
  token.children = []; // markdown-it image renderer 依赖 children（renderInlineAsText），缺了会崩
  state.pos += m[0].length;
  return true;
});

// ---- 图片 src 重写：相对路径 → /api/vault/asset?path= ----
// - markdown 形式 ![](相对路径)：基于当前文档路径（env.basePath）解析
// - wikilink 形式 ![[文件名.png]]：按文件名全库匹配（后端 find_asset_by_name）
// 直接自渲染 img 标签：绕开 markdown-it 默认 image rule 对 alt/children 的假设
//（token 手动构造时缺 alt 会导致默认规则崩溃）。
md.renderer.rules.image = function (tokens, idx, options, env, self) {
  const token = tokens[idx];
  const src = resolveAssetSrc(
    token.attrGet("src") || "",
    (env && env.basePath) || "",
    !!(token.meta && token.meta.wikilink)
  );
  const alt = token.attrGet("alt") || "";
  const esc = md.utils.escapeHtml;
  return `<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy" />`;
};

export function resolveAssetSrc(src, basePath, isWikilink = false) {
  if (!src) return src;
  const lower = src.toLowerCase();
  // 网络图片 / 内嵌 base64 / 绝对 URL 原样保留
  if (lower.startsWith("http://") || lower.startsWith("https://") || lower.startsWith("data:")) return src;
  // markdown-it 已把空格/中文编码，先解码再按原始路径解析
  let raw = src;
  try { raw = decodeURIComponent(src); } catch (_) { /* 保留原样 */ }  if (isWikilink) {
  // Obsidian wikilink：按文件名全库匹配，不做目录拼接
  const name = raw.replace(/\\/g, "/").split("/").pop();
  if (!name) return src;
  return `/api/vault/asset?path=${encodeURIComponent(name)}`;
  }
  const rel = resolveRelPath(raw, basePath);
  return rel ? `/api/vault/asset?path=${encodeURIComponent(rel)}` : src;
}

// 相对路径 → vault 内规范 posix 路径（基于当前文档目录解析，防越出 vault 根）
export function resolveRelPath(raw, basePath) {
  // markdown-it 会把空格/中文编码，先解码再按原始路径解析
  let src = raw;
  try { src = decodeURIComponent(raw); } catch (_) { /* 保留原样 */ }
  let rel = src.replace(/\\/g, "/").replace(/^\.\//, "").replace(/^\/+/, "");
  if (!rel) return null;
  if (basePath) {
    const dir = basePath.includes("/") ? basePath.slice(0, basePath.lastIndexOf("/")) : "";
    rel = (dir ? dir + "/" : "") + rel;
    const parts = [];
    for (const seg of rel.split("/")) {
      if (seg === "..") {
        if (!parts.length) return null; // 越出 vault 根
        parts.pop();
      } else if (seg && seg !== ".") {
        parts.push(seg);
      }
    }
    rel = parts.join("/");
    if (!rel) return null;
  }
  return rel;
}

// ---- md 文档链接：.md 结尾的内部链接 → 可点击打开（md-link） ----
const _linkOpenRender = md.renderer.rules.link_open || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const token = tokens[idx];
  const href = token.attrGet("href") || "";
  if (_isInternalMd(href)) {
    const rel = resolveRelPath(href.split("#")[0], (env && env.basePath) || ""); // 剥离 #锚点
    if (rel) {
      const cls = token.attrGet("class") || "";
      token.attrSet("class", (cls + " md-link").trim());
      token.attrSet("data-md-path", rel);
    }
  } else if (_isInternalAttachment(href)) {
    const rel = resolveRelPath(href, (env && env.basePath) || "");
    if (rel) {
      token.attrSet("href", `/api/vault/attachment?path=${encodeURIComponent(rel)}`);
      token.attrSet("target", "_blank");
    }
  }
  return _linkOpenRender(tokens, idx, options, env, self);
};

function _isInternalMd(href) {
  const h = href.toLowerCase();
  if (h.startsWith("http://") || h.startsWith("https://") || h.startsWith("mailto:") || h.startsWith("#")) return false;
  return /\.md($|[?#])/i.test(href);
}

const ATTACHMENT_EXT_RE = /\.(pdf|pptx?|docx?|xlsx?|csv|zip|rar|7z|mp4|mov|webm|mp3|wav|blend|ttf|otf|json|ya?ml|xml|base|canvas|html)($|[?#])/i;

function _isInternalAttachment(href) {
  const h = href.toLowerCase();
  if (h.startsWith("http://") || h.startsWith("https://") || h.startsWith("mailto:") || h.startsWith("#")) return false;
  return ATTACHMENT_EXT_RE.test(href);
}

// ---- 插件：高亮 ==文字== ----
md.inline.ruler.before("emphasis", "highlight", (state, silent) => {
  const m = state.src.slice(state.pos).match(/^==([^=]+)==/);
  if (!m) return false;
  if (silent) return true;
  state.push("highlight_open", "mark", 1);
  const t = state.push("text", "", 0);
  t.content = m[1];
  state.push("highlight_close", "mark", -1);
  state.pos += m[0].length;
  return true;
});

// ---- 标题导航（TOC）：给 h1-h6 加唯一 id，并把标题收集到 env.headings ----
// 结构：heading_open → inline（content 为纯文本标题）→ heading_close
// 标题文本需清洗 wikilink/markdown 链接语法（正文标题仍渲染为可点击链接，TOC 只取显示文本）
function cleanHeadingText(s) {
  return String(s)
    .replace(/!\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]/g, (_m, t, a) => a || t || "") // 图片 wikilink
    .replace(/\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]/g, (_m, t, a) => a || t || "") // 文本 wikilink [[目标|别名]]→别名
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, (_m, alt) => alt || "") // markdown 图片 ![alt](url)
    .replace(/\[([^\]]+)\]\([^)]*\)/g, (_m, label) => label || "") // markdown 链接 [文字](url)
    .replace(/[*_`]/g, "") // 残留强调/代码标记（# 是合法字符，保留）
    .replace(/\s+/g, " ")
    .trim();
}
const _headingOpenRender = md.renderer.rules.heading_open || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));
md.renderer.rules.heading_open = function (tokens, idx, options, env, self) {
  const token = tokens[idx];
  const inline = tokens[idx + 1];
  const text = inline ? cleanHeadingText(inline.content) : "";
  if (text && env) {
    env.headings = env.headings || [];
    const id = "toc-" + env.headings.length;
    token.attrSet("id", id);
    env.headings.push({ text, level: Number(token.tag.slice(1)), id });
  }
  return _headingOpenRender(tokens, idx, options, env, self);
};

// ---- 渲染入口 ----
// opts.basePath: 当前文档路径（用于解析 md 里相对路径图片）
// 返回 { html, headings }，headings = [{ text, level, id }]（标题导航用）
export function renderMarkdown(src, opts = {}) {
  let text = String(src);
  text = text.replace(/%%[\s\S]*?%%/g, ""); // Obsidian 注释
  text = _wrapBracketImageUrls(text); // 图片路径含括号 → 尖括号包裹（markdown-it 限制）
  const fm = extractFrontmatter(text);
  const env = { basePath: opts.basePath || "" };
  const bodyHtml = md.render(fm.body, env);
  let html = "";
  // 最上方：frontmatter 提取的标签（tags）→ 标签 chip 行
  const tags = extractTags(fm.data);
  if (tags.length) {
    html += `<div class="doc-tags">${tags.map((t) => `<span class="doc-tag">#${esc(t)}</span>`).join("")}</div>`;
  }
  // frontmatter 其余字段（折叠展示；tags 已在上方展示，跳过避免重复）
  if (fm.data && Object.keys(fm.data).length) {
    const rows = Object.entries(fm.data)
      .filter(([k]) => k.toLowerCase() !== "tags")
      .map(([k, v]) => `<div class="fm-row"><span class="fm-key">${esc(k)}</span><span class="fm-val">${esc(Array.isArray(v) ? v.join(", ") : String(v))}</span></div>`)
      .join("");
    if (rows) {
      html += `<details class="frontmatter"><summary>frontmatter (${Object.keys(fm.data).length})</summary>${rows}</details>`;
    }
  }
  html += bodyHtml;
  return { html, headings: env.headings || [] };
}

// 提取 frontmatter 中的 tags（支持 tags: [a, b] / tags: a, b / tags:\n  - a 等形式，容忍 # 前缀）
function extractTags(data) {
  if (!data || data.tags === undefined || data.tags === null || data.tags === "") return [];
  const raw = data.tags;
  const arr = Array.isArray(raw)
    ? raw.map((t) => String(t))
    : String(raw).split(/[,，\s]+/).filter(Boolean);
  return arr.map((t) => t.replace(/^#+/, "")).filter(Boolean);
}

// 预处理：markdown 图片语法 ![](url) 的 url 含括号时，用 < > 包裹。
// markdown-it 的 image 规则按括号配对解析 URL，含未转义括号（如 Windows 文件名
// "(第 1 天)x.png"）会导致整条语法不匹配 → 渲染成纯文本。`![](<url>)` 形式
// 允许括号/空格，是 markdown-it 标准支持。用状态机配对扫描，避免破坏嵌套括号。
function _wrapBracketImageUrls(src) {
  let out = "";
  let i = 0;
  const re = /!\[[^\]]*\]\(/g;
  while (i < src.length) {
    re.lastIndex = i;
    const m = re.exec(src);
    if (!m) {
      out += src.slice(i);
      break;
    }
    out += src.slice(i, m.index + m[0].length); // 含 ![alt](
    let depth = 0;
    let j = m.index + m[0].length;
    let end = -1;
    while (j < src.length) {
      if (src[j] === "(") depth++;
      else if (src[j] === ")") {
        if (depth === 0) { end = j; break; }
        depth--;
      }
      j++;
    }
    if (end === -1) { out += src.slice(m.index + m[0].length); break; }
    const url = src.slice(m.index + m[0].length, end);
    out += /[()]/.test(url) && !url.startsWith("<") ? `<${url}>` : url;
    i = end; // 保留 ')'，由 markdown-it 消费
  }
  return out;
}

function extractFrontmatter(src) {  const lines = src.split(/\r?\n/);
  if (lines[0] && lines[0].trim() === "---") {
    const end = lines.slice(1).findIndex((l) => l.trim() === "---");
    if (end >= 0) {
      return { data: parseFm(lines.slice(1, end + 1)), body: lines.slice(end + 2).join("\n") };
    }
  }
  return { data: null, body: src };
}

function parseFm(lines) {
  const fm = {};
  let key = null, list = [];
  const flush = () => {
    if (key !== null) {
      fm[key] = list.length ? list : "";
      key = null;
      list = [];
    }
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("- ")) {
      if (key !== null) list.push(line.slice(2).replace(/^["']|["']$/g, ""));
      continue;
    }
    const i = line.indexOf(":");
    if (i > 0) {
      flush();
      key = line.slice(0, i).trim();
      let v = line.slice(i + 1).trim();
      if (v.startsWith("[") && v.endsWith("]")) {
        fm[key] = v.slice(1, -1).split(",").map((s) => s.trim()).filter(Boolean);
        key = null;
      } else if (v) {
        fm[key] = v.replace(/^["']|["']$/g, "");
        key = null;
      }
    }
  }
  flush();
  return fm;
}

export function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
