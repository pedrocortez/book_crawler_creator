<template>
  <div>
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:1.2rem">
      <h2 class="section-title" style="margin-bottom:0">Biblioteca</h2>
      <button class="btn btn-ghost btn-sm" @click="load">↻ Atualizar</button>
    </div>

    <div v-if="loading" class="empty-state">
      <span class="spinner" style="width:24px;height:24px"></span>
    </div>
    <div v-else-if="error" class="empty-state" style="color:var(--err)">
      <span class="emoji">⚠️</span>
      {{ error }}
    </div>
    <div v-else-if="!files.length" class="empty-state">
      <span class="emoji">📚</span>
      Nenhum arquivo ainda. Inicie um crawl para gerar EPUBs ou TXTs.
    </div>
    <div v-else>
      <!-- Filtros -->
      <div style="display:flex; gap:0.5rem; margin-bottom:1rem; flex-wrap:wrap">
        <button
          v-for="fmt in ['todos', 'epub', 'txt']"
          :key="fmt"
          :class="['btn', 'btn-sm', filter === fmt ? 'btn-primary' : 'btn-ghost']"
          @click="filter = fmt"
        >
          {{ fmt === 'todos' ? 'Todos' : fmt.toUpperCase() }}
          <span style="opacity:.65">({{ counts[fmt] }})</span>
        </button>
      </div>

      <div class="file-grid">
        <FileCard
          v-for="file in filtered"
          :key="file.filename"
          :file="file"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import FileCard from '../components/FileCard.vue'

const files = ref([])
const loading = ref(false)
const error = ref('')
const filter = ref('todos')

const filtered = computed(() => {
  if (filter.value === 'todos') return files.value
  return files.value.filter(f => f.format === filter.value)
})

const counts = computed(() => ({
  todos: files.value.length,
  epub: files.value.filter(f => f.format === 'epub').length,
  txt: files.value.filter(f => f.format === 'txt').length,
}))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/library')
    if (!res.ok) throw new Error('Erro ao carregar biblioteca')
    files.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
