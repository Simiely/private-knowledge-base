<script setup>
// 递归文件树（懒加载展开）
import { ref } from "vue";

defineOptions({ name: "FileTree" });
/**
 * 递归懒加载文件树。
 * @prop {Array<{name:string, path:string, type:'dir'|'file', children?:Array}>} nodes 当前层级节点
 * @event open - 点击文件：`(path: string)`
 * @event load-dir - 请求展开目录：`(path: string)`（懒加载，父级负责填充 children）
 */
const props = defineProps({
  nodes: { type: Array, default: () => [] },
});
const emit = defineEmits(["open", "load-dir"]);

const expanded = ref({});

async function toggleDir(node) {
  const key = node.path;
  const willExpand = !expanded.value[key];
  expanded.value = { ...expanded.value, [key]: willExpand };
  // 懒加载：仅当展开且子节点尚未加载时才请求
  if (willExpand && !node.childrenLoaded) {
    emit("load-dir", node.path);
  }
}

function openFile(node) {
  emit("open", node.path);
}
</script>

<template>
  <div class="tree">
    <div v-for="node in nodes" :key="node.path" class="tree-node">
      <div
        v-if="node.type === 'dir'"
        class="tree-row"
        @click="toggleDir(node)"
      >
        <span class="twisty" :class="{ open: expanded[node.path] }">▸</span>
        <span class="tree-name">{{ node.name }}</span>
      </div>
      <div v-else class="tree-row tree-file" @click="openFile(node)">
        <span class="twisty-spacer"></span>
        <span class="tree-name">{{ node.name }}</span>
      </div>
      <div v-if="node.type === 'dir' && expanded[node.path]" class="tree-children">
        <!-- 递归转发事件必须透传 $event（坑：@open="openFile" 会把子层已转成 path 字符串的
             事件当 node 对象再取 .path → undefined → 深层文件 404 打不开） -->
        <FileTree
          :nodes="node.children || []"
          @open="(p) => emit('open', p)"
          @load-dir="(p) => emit('load-dir', p)"
        />
      </div>
    </div>
  </div>
</template>
