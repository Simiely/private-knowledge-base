<script setup>
// 通用确认对话框（替代浏览器原生 confirm）：
// 居中显示、主题一致、支持危险操作样式。用法：
//   <ConfirmDialog :show="flag" title="删除快照" :message="msg"
//                  confirm-text="删除" danger @confirm="..." @cancel="..." />
defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: "请确认" },
  message: { type: String, default: "" },
  confirmText: { type: String, default: "确认" },
  cancelText: { type: String, default: "取消" },
  danger: { type: Boolean, default: false }, // 危险操作（删除/覆盖）：确认按钮红色
});
const emit = defineEmits(["confirm", "cancel"]);
</script>

<template>
  <div v-if="show" class="modal-mask confirm-mask" @click.self="emit('cancel')">
    <div class="modal confirm-modal" role="alertdialog" aria-modal="true">
      <h3>{{ title }}</h3>
      <p class="modal-hint confirm-message">{{ message }}</p>
      <div class="confirm-actions">
        <button class="btn" @click="emit('cancel')">{{ cancelText }}</button>
        <button class="btn" :class="{ danger }" @click="emit('confirm')" autofocus>
          {{ confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>
