<template>
  <div>
    <h2 class="section-title">Novo Crawl</h2>

    <div class="card">
      <form @submit.prevent="submit">
        <div class="form-grid">
          <div class="field full">
            <label for="source">Fonte</label>
            <select id="source" v-model="form.source">
              <option value="generic">Site genérico</option>
              <option value="central_novel">Central Novel</option>
            </select>
          </div>

          <div v-if="form.source === 'generic'" class="field full">
            <label>Como fornecer a URL</label>
            <div style="display:flex; gap:1rem; flex-wrap:wrap">
              <label style="display:flex; align-items:center; gap:0.4rem; font-weight:normal">
                <input type="radio" value="template" v-model="form.url_mode" /> URL Template
              </label>
              <label style="display:flex; align-items:center; gap:0.4rem; font-weight:normal">
                <input type="radio" value="start_url" v-model="form.url_mode" /> Link de um capítulo
              </label>
            </div>
          </div>

          <div v-if="form.source === 'generic' && form.url_mode === 'template'" class="field full">
            <label for="url_template">URL Template <span style="color:var(--err)">*</span></label>
            <input
              id="url_template"
              v-model="form.url_template"
              placeholder="https://site.com/capitulo-{id}"
            />
            <p class="hint">Use <code>{id}</code> como marcador do número do capítulo.</p>
          </div>

          <div v-else-if="form.source === 'generic'" class="field full">
            <label for="start_url">URL de um capítulo <span style="color:var(--err)">*</span></label>
            <input
              id="start_url"
              v-model="form.start_url"
              placeholder="https://site.com/.../capitulo-736-noite/"
            />
            <p class="hint">
              Cole o link de um capítulo. O número é detectado e o template é deduzido
              automaticamente; capítulos seguintes com slugs diferentes são descobertos
              pelo índice da obra ou pelo link "próximo".
            </p>
          </div>

          <div v-else class="field full">
            <label for="source_url">URL da Central Novel <span style="color:var(--err)">*</span></label>
            <input
              id="source_url"
              v-model="form.source_url"
              placeholder="https://centralnovel.com/series/the-beginning-after-the-end/"
            />
            <p class="hint">
              Aceita a página da série ou de um capítulo. Uma janela do Chromium será
              aberta; conclua manualmente a verificação do site, se ela aparecer.
            </p>
          </div>

          <div class="field" v-if="form.source === 'central_novel' || form.url_mode === 'template'">
            <label for="start">Capítulo inicial</label>
            <input id="start" v-model.number="form.start" type="number" min="1" required />
          </div>
          <div class="field" v-else>
            <label for="start_optional">Capítulo inicial (opcional)</label>
            <input
              id="start_optional"
              v-model.number="form.start"
              type="number"
              min="1"
              placeholder="auto"
            />
            <p class="hint">Se vazio, usa o número detectado na URL.</p>
          </div>
          <div class="field">
            <label for="end">Capítulo final</label>
            <input
              id="end"
              v-model.number="form.end"
              type="number"
              min="1"
              :required="form.source === 'generic'"
              :placeholder="form.source === 'central_novel' ? 'detectar último' : ''"
            />
            <p v-if="form.source === 'central_novel'" class="hint">
              Deixe vazio para detectar o último capítulo numérico do índice.
            </p>
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

          <details v-if="form.source === 'generic'" class="field full">
            <summary>Overrides de URL (opcional)</summary>
            <p class="hint mt1">
              JSON com <code>id do capítulo → URL</code> quando o template não refletir a URL real.
              Ex.: <code>{"477":"https://site/obra/capitulo-477-frenesi/"}</code>
            </p>
            <textarea
              id="url_overrides_json"
              v-model="form.url_overrides_json"
              class="url-overrides-json"
              rows="6"
              placeholder='{
  "477": "https://...",
  "480": "https://..."
}'
            />
          </details>

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

    <!-- Cache -->
    <div class="card mt2">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:0.75rem; flex-wrap:wrap">
        <div>
          <h3 style="font-size:1.05rem; color:var(--sepia); margin:0">Cache de capítulos</h3>
          <p v-if="cacheStats" class="hint" style="margin:0.25rem 0 0">
            HTML: {{ cacheStats.html.count }} arquivo(s) ({{ formatBytes(cacheStats.html.bytes) }})
            · JSON: {{ cacheStats.json.count }} arquivo(s) ({{ formatBytes(cacheStats.json.bytes) }})
          </p>
          <p v-else class="hint" style="margin:0.25rem 0 0">Carregando estatísticas...</p>
        </div>
        <div style="display:flex; gap:0.5rem; flex-wrap:wrap">
          <button class="btn btn-ghost btn-sm" type="button" @click="loadCacheStats" :disabled="cacheBusy">↻ Atualizar</button>
          <button class="btn btn-ghost btn-sm" type="button" @click="confirmClearCache('html')" :disabled="cacheBusy">Apagar HTML</button>
          <button class="btn btn-ghost btn-sm" type="button" @click="confirmClearCache('json')" :disabled="cacheBusy">Apagar JSON</button>
          <button class="btn btn-primary btn-sm" type="button" @click="confirmClearCache('all')" :disabled="cacheBusy">
            <span v-if="cacheBusy" class="spinner"></span>
            <span>{{ cacheBusy ? 'Apagando...' : 'Apagar tudo' }}</span>
          </button>
        </div>
      </div>
      <p v-if="cacheMsg" class="hint mt1" :style="{ color: cacheErr ? 'var(--err)' : 'var(--ok, #2c7)' }">
        {{ cacheMsg }}
      </p>
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
              cap. {{ job.request?.start }}–{{ job.request?.end ?? 'último' }}
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
import { reactive, ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useJobsStore } from '../stores/jobs.js'

const router = useRouter()
const store = useJobsStore()
const loading = ref(false)
const error = ref('')
const cacheStats = ref(null)
const cacheBusy = ref(false)
const cacheMsg = ref('')
const cacheErr = ref(false)

function formatBytes(n) {
  if (!n) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}

async function loadCacheStats() {
  try {
    cacheStats.value = await store.fetchCacheStats()
  } catch (e) {
    cacheErr.value = true
    cacheMsg.value = e.message
  }
}

async function confirmClearCache(kind) {
  const label = kind === 'all' ? 'todo o cache (HTML + JSON)' : `o cache ${kind.toUpperCase()}`
  if (!window.confirm(`Apagar ${label}? Os capítulos serão re-baixados no próximo crawl.`)) {
    return
  }
  cacheBusy.value = true
  cacheMsg.value = ''
  cacheErr.value = false
  try {
    const result = await store.clearCache(kind)
    cacheStats.value = result.stats
    const removed = result.removed || {}
    const total = (removed.html || 0) + (removed.json || 0)
    cacheMsg.value = `Cache apagado: ${total} arquivo(s) removido(s) (HTML: ${removed.html || 0}, JSON: ${removed.json || 0}).`
  } catch (e) {
    cacheErr.value = true
    cacheMsg.value = e.message
  } finally {
    cacheBusy.value = false
  }
}

const defaultForm = () => ({
  source: 'generic',
  source_url: '',
  url_mode: 'template',
  url_template: '',
  start_url: '',
  start: 1,
  end: 10,
  series_title: '',
  author: '',
  output_format: 'epub',
  cover_url: '',
  url_overrides_json: '',
  min_delay: 2.0,
  max_delay: 5.0,
  max_retries: 4,
  strict_ids: true,
})

const form = reactive(defaultForm())

watch(
  () => form.source,
  (source) => {
    form.end = source === 'central_novel' ? null : 10
  }
)

function reset() {
  Object.assign(form, defaultForm())
  error.value = ''
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    let urlOverrides
    const raw =
      form.source === 'generic' ? String(form.url_overrides_json ?? '').trim() : ''
    if (raw) {
      let parsed
      try {
        parsed = JSON.parse(raw)
      } catch {
        error.value = 'JSON inválido em Overrides de URL.'
        return
      }
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
        error.value =
          'Overrides de URL: esperado um objeto, ex.: {"477":"https://..."}.'
        return
      }
      urlOverrides = parsed
    }

    const payload = { ...form }
    delete payload.url_overrides_json
    delete payload.url_mode
    if (form.source === 'central_novel') {
      if (!String(form.source_url || '').trim()) {
        error.value = 'Informe a URL da série ou de um capítulo da Central Novel.'
        return
      }
      delete payload.url_template
      delete payload.start_url
      delete payload.url_overrides
      if (!payload.end) delete payload.end
    } else if (form.url_mode === 'start_url') {
      delete payload.source_url
      if (!String(form.start_url || '').trim()) {
        error.value = 'Informe a URL de um capítulo.'
        return
      }
      delete payload.url_template
      if (!payload.start) delete payload.start
    } else {
      delete payload.source_url
      delete payload.start_url
      if (!String(form.url_template || '').trim()) {
        error.value = 'Informe o URL Template.'
        return
      }
    }
    if (urlOverrides) payload.url_overrides = urlOverrides
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

onMounted(() => {
  store.fetchJobs()
  loadCacheStats()
})
</script>
