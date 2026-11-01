<script setup>
// Agent 对话面板：SSE 流式 + 写操作确认（diff 展示）
import { ref, nextTick } from "vue";
import { API } from "../api/endpoints.js";
import { apiPost } from "../api.js";

const messages = ref([]); // {role: 'user'|'assistant'|'tool', content, opId?, path?, diff?}
const input = ref("");
const busy = ref(false);
const listEl = ref(null);
let sessionId = null;

function push(msg) {
  messages.value.push(msg);
  nextTick(() => listEl.value?.scrollTo({ top: listEl.value.scrollHeight }));
}

async function send() {
  const text = input.value.trim();
  if (!text || busy.value) return;
  push({ role: "user", content: text });
  input.value = "";
  busy.value = true;
  try {
    const res = await fetch(API.agentChat, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, sessionId }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || res.statusText);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let assistantText = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const part of parts) {
        const evtLine = part.split("\n").find((l) => l.startsWith("event:"));
        const dataLine = part.split("\n").find((l) => l.startsWith("data:"));
        if (!dataLine) continue;
        const type = evtLine ? evtLine.slice(6).trim() : "message";
        const data = JSON.parse(dataLine.slice(5).trim());
        if (type === "session") {
          sessionId = data.sessionId;
        } else if (type === "text") {
          assistantText += data.content;
        } else if (type === "tool") {
          push({ role: "tool", content: `写入操作待确认：${data.path}`, opId: data.opId, diff: data.diff });
        } else if (type === "error") {
          push({ role: "assistant", content: "⚠️ " + (data.message || "未知错误") });
        } else if (type === "done") {
          // 流结束，确保文本消息已入列
        }
      }
    }
    if (assistantText) push({ role: "assistant", content: assistantText });
    if (!assistantText && !messages.value.some((m) => m.role === "tool" && m.opId)) {
      push({ role: "assistant", content: "（Agent 未返回内容）" });
    }
  } catch (e) {
    push({ role: "assistant", content: "⚠️ " + e.message });
  } finally {
    busy.value = false;
  }
}

async function confirmOp(opId, approve) {
  try {
    const r = await apiPost(approve ? API.agentConfirm : API.agentCancel, {
      sessionId: sessionId || "anon",
      opId,
    });
    const msg = messages.value.find((m) => m.opId === opId);
    if (msg) msg.resolved = approve ? "✓ 已写入" : "✕ 已取消";
    push({ role: "assistant", content: approve ? `已确认写入 ${r.path} ✓` : `已取消操作 ${opId}` });
  } catch (e) {
    push({ role: "assistant", content: "⚠️ 确认失败：" + e.message });
  }
}
</script>

<template>
  <div class="chat-panel">
    <div ref="listEl" class="chat-list">
      <div
        v-for="(m, i) in messages"
        :key="i"
        class="chat-msg"
        :class="'chat-' + m.role"
      >
        <div class="msg-content">{{ m.content }}</div>
        <div v-if="m.role === 'tool'" class="tool-box">
          <pre class="diff">{{ m.diff }}</pre>
          <div v-if="!m.resolved" class="tool-actions">
            <button class="btn primary" @click="confirmOp(m.opId, true)">确认写入</button>
            <button class="btn" @click="confirmOp(m.opId, false)">取消</button>
          </div>
          <div v-else class="resolved">{{ m.resolved }}</div>
        </div>
      </div>
    </div>
    <div class="chat-input">
      <input
        v-model="input"
        placeholder="问 Agent：例如「总结当前文档」「在笔记里追加待办」"
        :disabled="busy"
        @keydown.enter="send"
      />
      <button class="btn primary" :disabled="busy || !input.trim()" @click="send">
        {{ busy ? "思考中…" : "发送" }}
      </button>
    </div>
  </div>
</template>
