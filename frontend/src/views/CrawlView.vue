<template>
  <div>
    <h2 class="section-title">Novo Crawl</h2>

    <div class="card">
      <form @submit.prevent="submit">
        <div class="form-grid">
          <div class="field full">
            <label for="url_template">URL Template <span style="color:var(--err)">*</span></label>
            <input
              id="url_template"
              v-model="form.url_template"
              placeholder="https://site.com/capitulo-{id}"
              required
            />
            <p class="hint">Use <code>{id}</code> como marcador do número do capítulo.</p>
          </div>

          <div class="field">
            <label for="start">Capítulo inicial</label>
            <input id="start" v-model.number="form.start" type="number" min="1" required />
          </div>
          <div class="field">
            <label for="end">Capítulo final</label>
            <input id="end" v-model.number="form.end" type="number" min="1" required />
          </div>

          <div class="field">
            <label for="series_title">Título da série</label>
            <input id="series_title" v-model="form.series_title" placeholder="Minha Série" />
          </div>
          <div class="field">
            <label for="author">Autor</label>
            <input id="author" v-model="form.author" placeholder="Nome do Autor" />
          </div>

          <div class="field">
            <label for="output_format">Formato de saída</label>
            <select id="output_format" v-model="form.output_format">
              <option value="epub">EPUB</option>
              <option value="txt">TXT</option>
            </select>
          </div>

          <div class="field full">
            <label for="cover_url">URL da capa (opcional)</label>
            <input id="cover_url" v-model="form.cover_url" placeholder="https://..." />
          </div>

          <div class="field">
            <label for="min_delay">Delay mínimo (s)</label>
            <input id="min_delay" v-model.number="form.min_delay" type="number" step="0.5" min="0" />
          </div>
          <div class="field">
            <label for="max_delay">Delay máximo (s)</label>
            <input id="max_delay" v-model.number="form.max_delay" type="number" step="0.5" min="0" />
          </div>
          <div class="field">
            <label for="max_retries">Máx. tentativas</label>
            <input id="max_retries" v-model.number="form.max_retries" type="number" min="1" max="10" />
          </div>
        </div>

        <p v-if="error" class="hint mt1" style="color:var(--err)">{{ error }}</p>

        <div class="mt2" style="display:flex; gap:0.75rem; align-items:center">
          <button class="btn btn-primary" type="submit" :disabled="loading">
            <span v-if="loading" class="spinner"></span>
            <span>{{ loading ? 'Iniciando...' : 'Iniciar Crawl' }}</span>
          </button>
          <button class="btn btn-ghost" type="button" @click="reset">Limpar</button>
        </div>
      </form>
    </div>

    <!-- Jobs recentes -->
    <div class="mt2">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem">
        <h3 style="font-size:1.1rem; color:var(--sepia)">Jobs recentes</h3>
        <button class="btn btn-ghost btn-sm" @click="store.fetchJobs()">↻ Atualizar</button>
      </div>

      <div v-if="store.loading" class="empty-state">
        <span class="spinner" style="width:24px;height:24px"></span>
      </div>
      <div v-else-if="!store.jobs.length" class="empty-state">
        <span class="emoji">🔍</span>
        Nenhum job ainda. Inicie um crawl acima.
      </div>
      <div v-else>
        <div
          v-for="job in store.jobs"
          :key="job.id"
          class="card"
          style="cursor:pointer"
          @click="$router.push(`/jobs/${job.id}`)"
        >
          <div style="display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap">
            <span :class="`badge badge-${job.status}`">{{ job.status }}</span>
            <span style="font-size:0.9rem; font-weight:600; color:var(--sepia)">
              {{ job.request?.series_title || 'Job' }}
            </span>
            <span style="font-size:0.8rem; color:var(--text-dim); margin-left:auto">
              cap. {{ job.request?.start }}–{{ job.request?.end }}
            </span>
          </div>
          <div class="progress-wrap mt1">
            <div
              class="progress-bar"
              :style="{ width: progressPct(job) + '%' }"
            ></div>
          </div>
          <p class="hint">{{ job.created_at?.slice(0, 19).replace('T', ' ') }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useJobsStore } from '../stores/jobs.js'

const router = useRouter()
const store = useJobsStore()
const loading = ref(false)
const error = ref('')

const defaultForm = () => ({
  url_template: '',
  start: 1,
  end: 10,
  series_title: '',
  author: '',
  output_format: 'epub',
  cover_url: '',
  min_delay: 2.0,
  max_delay: 5.0,
  max_retries: 4,
  strict_ids: true,
})

const form = reactive(defaultForm())

function reset() {
  Object.assign(form, defaultForm())
  error.value = ''
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const payload = { ...form }
    if (!payload.author) delete payload.author
    if (!payload.cover_url) delete payload.cover_url
    if (!payload.series_title) payload.series_title = 'Livro'
    const { job_id } = await store.createJob(payload)
    router.push(`/jobs/${job_id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function progressPct(job) {
  if (!job.total) return 0
  return Math.round((job.progress / job.total) * 100)
}

onMounted(() => store.fetchJobs())
</script>
