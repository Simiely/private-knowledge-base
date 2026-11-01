<script setup>
// 通用目录选择弹窗：磁盘 + 常用位置 + 目录树 + 输入框（v-model 双向绑定路径）
// 用法：<DirPicker v-model:show="show" v-model="path" title="..." @confirm="..." />
// 状态逻辑来自 useDirPicker（与 useDirPicker.js 配套使用），本组件只负责渲染。
/**
 * 通用目录选择弹窗（纯渲染组件）：磁盘 + 常用位置 + 目录树 + 输入框。
 * 状态逻辑来自 useDirPicker（配套使用），本组件只负责渲染与事件转发。
 * @prop {boolean} show 弹窗开关（v-model:show）
 * @prop {string} title / hint 标题与提示
 * @prop {string} modelValue 当前路径（v-model 双向绑定）
 * @prop {boolean} switching 确认按钮加载态
 * @prop {Array} quickDisks / quickPlaces 快捷位置（磁盘 + 常用）
 * @prop {string} browsePath / browseParent 当前浏览目录与上级
 * @prop {Array} browseDirs 子目录列表
 * @prop {boolean} browseLoading 目录加载中
 * @event confirm - 点击确认：`(path: string)`
 * @event browse - 进入目录：`(path: string)`
 * @event quick - 点击快捷位置：`(item: {path:string})`
 * @event enter - 点击子目录：`(name: string)`
 * @event pick - 选择当前目录：`()`
 */
defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: "选择目录" },
  hint: { type: String, default: "" },
  modelValue: { type: String, default: "" },
  switching: { type: Boolean, default: false },
  quickDisks: { type: Array, default: () => [] },
  quickPlaces: { type: Array, default: () => [] },
  browsePath: { type: String, default: "" },
  browseParent: { type: String, default: "" },
  browseDirs: { type: Array, default: () => [] },
  browseLoading: { type: Boolean, default: false },
});
const emit = defineEmits(["update:show", "update:modelValue", "confirm", "browse", "quick", "enter", "pick"]);

function onInput(e) {
  emit("update:modelValue", e.target.value);
}
</script>

<template>
  <div v-if="show" class="modal-mask" @click.self="emit('update:show', false)">
    <div class="modal vault-modal">
      <h3>{{ title }}</h3>
      <p v-if="hint" class="modal-hint">{{ hint }}</p>

      <div class="dir-browser" style="height: 280px">
        <div class="dir-side">
          <div class="dir-side-title">💾 磁盘</div>
          <div
            v-for="item in quickDisks"
            :key="item.path"
            class="quick-item"
            :title="item.path"
            @click="emit('quick', item)"
          >
            <span class="dir-icon">{{ item.icon }}</span>
            <span class="dir-name">{{ item.name }}</span>
          </div>
          <div class="dir-side-title" style="margin-top: 8px">📌 常用</div>
          <div
            v-for="item in quickPlaces"
            :key="item.path"
            class="quick-item"
            :title="item.path"
            @click="emit('quick', item)"
          >
            <span class="dir-icon">{{ item.icon }}</span>
            <span class="dir-name">{{ item.name }}</span>
          </div>
        </div>
        <div class="dir-main">
          <div class="dir-toolbar">
            <button class="btn small" :disabled="!browseParent" @click="emit('browse', browseParent)">⬆ 上级</button>
            <span class="dir-current" :title="browsePath || '根目录'" @dblclick="emit('pick')">{{ browsePath || "根目录" }}</span>
            <button class="btn small" @click="emit('pick')">选此目录</button>
          </div>
          <div class="dir-list">
            <div v-if="browseLoading" class="dir-empty">加载中…</div>
            <div v-else-if="!browseDirs.length" class="dir-empty">（无子目录）</div>
            <div
              v-for="d in browseDirs"
              :key="d"
              class="dir-item"
              @click="emit('enter', d)"
            >
              <span class="dir-icon">📁</span>
              <span class="dir-name">{{ d }}</span>
            </div>
          </div>
        </div>
      </div>

      <input
        :value="modelValue"
        class="modal-input"
        style="margin-top: 12px"
        placeholder="目录路径（可手动输入）…"
        @input="onInput"
        @keydown.enter="emit('confirm')"
      />
      <div class="modal-actions">
        <button class="btn" @click="emit('update:show', false)">取消</button>
        <button class="btn primary" :disabled="switching" @click="emit('confirm')">
          {{ switching ? "切换中…" : "确认" }}
        </button>
      </div>
    </div>
  </div>
</template>
