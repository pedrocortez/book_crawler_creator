<template>
  <article class="file-card">
    <span class="file-icon">{{ icon }}</span>
    <p class="file-name">{{ file.filename }}</p>
    <p class="file-meta">{{ sizeLabel }} · {{ dateLabel }}</p>
    <div class="file-actions">
      <a
        :href="`/api/library/${file.filename}`"
        :download="file.filename"
        class="btn btn-primary btn-sm"
      >
        ⬇ Baixar
      </a>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  file: { type: Object, required: true },
})

const icon = computed(() => props.file.format === 'epub' ? '📕' : '📄')

const sizeLabel = computed(() => {
  const bytes = props.file.size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(2)} MB`
})

const dateLabel = computed(() => {
  return props.file.modified_at?.slice(0, 10) ?? ''
})
</script>
