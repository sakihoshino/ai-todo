<script setup>
import { CalendarDays, Layers2, Clock3, CircleCheck, History, X, LaptopMinimal } from '@lucide/vue'
import { legacy, publicBase } from '../workspace'
import { categories } from '../tasks.js'

defineProps({ active: String, counts: Object, mobile: Boolean })
const emit = defineEmits(['select', 'close'])
const views = [
  ['today', '今日任务', CalendarDays], ['all', '全部任务', Layers2],
  ['upcoming', '即将到期', Clock3], ['completed', '已完成', CircleCheck],
]
</script>

<template>
  <div class="navigation">
    <div class="brand flex items-center">
      <img width="35" height="35" :src="publicBase + 'favicon.svg'" alt="">
      <span>AI-Todo</span>
      <button v-if="mobile" type="button" aria-label="关闭导航" class="icon-btn ml-auto" @click="emit('close')"><X :size="20"/></button>
    </div>
    <nav class="navigation-scroll" aria-label="任务导航">
      <h2 class="nav-label">工作空间</h2>
      <button v-for="[key, label, icon] in views" :key="key" class="nav-item" :class="{ active: active === key }" :aria-current="active === key ? 'page' : undefined" :aria-label="label" @click="emit('select', key)">
        <component :is="icon" :size="18" :stroke-width="1.65"/><span>{{ label }}</span><span class="nav-count">{{ counts[key] }}</span>
      </button>
      <button v-if="!legacy" class="nav-item" :class="{active: active === 'history'}" :aria-current="active === 'history' ? 'page' : undefined" @click="emit('select','history')"><History :size="18" :stroke-width="1.65"/>操作历史</button>
      <div class="nav-rule"></div>
      <h2 class="nav-label">任务分类</h2>
      <button v-for="[name, color] in categories" :key="name" class="nav-item category-nav" :class="{ active: active === name }" :aria-current="active === name ? 'page' : undefined" @click="emit('select', name)">
        <i class="category-dot" :style="{ background: color }"></i>{{ name }}
      </button>
    </nav>
    <div class="local-space"><LaptopMinimal :size="18"/><span>本地工作区</span><small>{{ legacy ? 'V0.1' : 'V0.3' }}</small></div>
  </div>
</template>
