<template>
  <div
    ref="consoleEl"
    class="log-console"
    role="log"
    aria-live="polite"
    aria-label="Console de logs"
  >
    <div v-if="!lines.length" style="color:var(--text-muted); padding:0.5rem 0">
      Aguardando logs...
    </div>
    <div
      v-for="(line, i) in lines"
      :key="i"
      :class="['log-line', line.level]"
    >
      <span class="ts">{{ line.ts ? line.ts.slice(11, 19) : '' }}</span>
      <span class="lvl">{{ line.level }}</span>
      <span v-if="line.error_code" class="ecode">{{ line.error_code }}</span>
      <span class="msg">{{ line.message }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  jobId: { type: String, required: true },
  jobStatus: { type: String, default: 'queued' },
})

const emit = defineEmits(['done'])
const lines = ref([])
const consoleEl = ref(null)
let ws = null

function scrollBottom() {
  nextTick(() => {
    if (consoleEl.value) {
      consoleEl.value.scrollTop = consoleEl.value.scrollHeight
    }
  })
}

function connect() {
  if (ws) ws.close()
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws/logs/${props.jobId}`)

  ws.onmessage = (e) => {
    const event = JSON.parse(e.data)
    if (event.level === 'PING') return
    lines.value.push(event)
    scrollBottom()
    if (event.level === 'DONE') {
      emit('done', event)
      ws?.close()
    }
  }

  ws.onerror = () => {
    lines.value.push({
      level: 'ERROR',
      error_code: 'KM-WS-002',
      message: 'Erro na conexão WebSocket.',
      ts: new Date().toISOString(),
    })
  }
}

onMounted(() => {
  if (props.jobStatus !== 'done' && props.jobStatus !== 'error') {
    connect()
  }
})

watch(() => props.jobId, () => {
  lines.value = []
  connect()
})

onUnmounted(() => ws?.close())
</script>
