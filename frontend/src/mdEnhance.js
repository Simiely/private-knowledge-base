// 渲染后 DOM 增强（S25 从 md.js 拆出）：与纯渲染（md.js）分离。
// callout 转换 + 任务列表 + 搜索高亮。只操作已渲染的 DOM，不参与 markdown 解析。

// 正则特殊字符转义（用于把用户输入的搜索词安全地拼进 RegExp）
export function escapeRegex(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function enhanceDom(root, query) {
  // callout：blockquote 首行 [!type]
  root.querySelectorAll("blockquote").forEach((bq) => {
    const first = bq.firstElementChild;
    if (!first) return;
    const m = first.textContent.match(/^\[!(\w+)\]([+-]?)\s*(.*)$/);
    if (!m) return;
    const type = m[1].toLowerCase();
    const title = m[3] || m[1];
    if (first.tagName === "P") first.remove();
    bq.classList.add("callout", `callout-${type}`);
    const titleDiv = document.createElement("div");
    titleDiv.className = "callout-title";
    titleDiv.textContent = title;
    bq.prepend(titleDiv);
  });

  // 任务列表 - [ ] / - [x]
  root.querySelectorAll("li").forEach((li) => {
    const m = li.textContent.match(/^\[([ xX])\]\s+(.*)$/);
    if (!m) return;
    li.classList.add("task-item");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = m[1].toLowerCase() === "x";
    cb.disabled = true;
    li.textContent = m[2];
    li.prepend(cb);
  });

  // 搜索高亮 + 滚动定位（英文大小写不敏感，所有命中都高亮）
  if (query) {
    const lowerQuery = query.toLowerCase();
    const re = new RegExp(escapeRegex(query), "gi");
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) {
      if (n.textContent.toLowerCase().includes(lowerQuery)) nodes.push(n);
    }
    if (nodes.length) {
      // 逐个文本节点：把命中词拆包成 <mark>（保留原文大小写）
      nodes.forEach((node) => {
        const text = node.textContent;
        const frag = document.createDocumentFragment();
        let last = 0;
        let m;
        re.lastIndex = 0;
        while ((m = re.exec(text)) !== null) {
          if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
          const mark = document.createElement("mark");
          mark.textContent = m[0];
          frag.appendChild(mark);
          last = m.index + m[0].length;
          if (m[0].length === 0) re.lastIndex++; // 空匹配防死循环
        }
        if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
        node.parentNode.replaceChild(frag, node);
      });
      // 滚动定位到第一个命中
      const first = root.querySelector("mark");
      if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }
}
