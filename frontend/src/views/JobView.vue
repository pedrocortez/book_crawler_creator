<template>
  <div>
    <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1.2rem">
      <RouterLink to="/crawl" class="btn btn-ghost btn-sm">← Voltar</RouterLink>
      <h2 class="section-title" style="margin-bottom:0">
        {{ jobId ? 'Detalhes do Job' : 'Todos os Jobs' }}
      </h2>
    </div>

    <!-- Listagem de todos os jobs -->
    <template v-if="!jobId">
      <div v-if="store.loading" class="empty-state">
        <span class="spinner" style="width:24px;height:24px"></span>
      </div>
      <div v-else-if="!store.jobs.length" class="empty-state">
        <span class="emoji">📭</span>
        Nenhum job encontrado.
      </div>
      <div v-else>
        <div
          v-for="job in store.jobs"
          :key="job.id"
          class="card"
          style="cursor:pointer; margin-bottom:0.75rem"
          @click="$router.push(`/jobs/${job.id}`)"
        >
          <div style="display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap">
            <span :class="`badge badge-${job.status}`">{{ job.status }}</span>
            <span style="font-weight:600; color:var(--sepia)">
              {{ job.request?.series_title || 'Job' }}
            </span>
            <span style="margin-left:auto; font-size:0.8rem; color:var(--text-dim)">
              cap. {{ job.request?.start }}–{{ job.request?.end }}
            </span>
          </div>
          <div class="progress-wrap mt1">
            <div class="progress-bar" :style="{ width: pct(job) + '%' }"></div>
          </div>
          <p class="hint">{{ job.created_at?.slice(0, 19).replace('T', ' ') }}</p>
        </div>
      </div>
    </template>

    <!-- Detalhe de um job específico -->
    <template v-else>
      <div v-if="loadingJob" class="empty-state">
        <span class="spinner" style="width:24px;height:24px"></span>
      </div>
      <div v-else-if="!job" class="empty-state">
        <span class="emoji">❌</span>
        Job não encontrado.
      </div>
      <template v-else>
        <!-- Header do Job -->
        <div class="card" style="margin-bottom:1rem">
          <div style="display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap">
            <span :class="`badge badge-${job.status}`">{{ job.status }}</span>
            <span style="font-size:1.1rem; font-weight:700; color:var(--sepia)">
              {{ job.request?.series_title || 'Job' }}
            </span>
            <span style="font-size:0.85rem; color:var(--text-dim); margin-left:auto">
              cap. {{ job.request?.start }}–{{ job.request?.end }}
              · {{ job.request?.output_format?.toUpperCase() }}
            </span>
          </div>

          <!-- Progresso -->
          <div class="mt1">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px">
              <span class="hint">Progresso</span>
              <span class="hint">{{ job.progress }} / {{ job.total }}</span>
            </div>
            <div class="progress-wrap">
              <div class="progress-bar" :style="{ width: pct(job) + '%' }"></div>
            </div>
          </div>

          <!-- Arquivo gerado -->
          <div v-if="job.output_file" class="mt1">
            <a
              :href="`/api/library/${job.output_file}`"
              class="btn btn-primary btn-sm"
              :download="job.output_file"
            >
              ⬇ Baixar {{ job.output_file }}
            </a>
          </div>
        </div>

        <!-- Console de Logs -->
        <div class="card">
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.75rem">
            <span style="font-size:0.85rem; font-weight:600; color:var(--text-dim); text-transform:uppercase; letter-spacing:.06em">Logs em tempo real</span>
            <button class="btn btn-ghost btn-sm" @click="refresh">↻</button>
          </div>
          <LogStream
            :job-id="jobId"
            :job-status="job.status"
            @done="onDone"
          />
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useJobsStore } from '../stores/jobs.js'
import LogStream from '../components/LogStream.vue'

const route = useRoute()
const store = useJobsStore()

const jobId = computed(() => route.params.id || null)
const job = ref(null)
const loadingJob = ref(false)

async function loadJob() {
  if (!jobId.value) return
  loadingJob.value = true
  try {
    job.value = await store.fetchJob(jobId.value)
  } catch {
    job.value = null
  } finally {
    loadingJob.value = false
  }
}

async function onDone() {
  await loadJob()
}

async function refresh() {
  await loadJob()
}

function pct(j) {
  if (!j.total) return 0
  return Math.round((j.progress / j.total) * 100)
}

onMounted(async () => {
  if (jobId.value) {
    await loadJob()
  } else {
    await store.fetchJobs()
  }
})

watch(jobId, async (val) => {
  if (val) await loadJob()
  else await store.fetchJobs()
})
</script>
