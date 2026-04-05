import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Extrai mensagem legível (com código KM-*) da resposta da API.
 * Aceita corpo já parseado ou texto cru; trata detail em array (validação FastAPI).
 */
export function formatApiError(body, status, statusText) {
  const httpBit =
    status != null
      ? `HTTP ${status}${statusText ? ` ${statusText}` : ''}`
      : ''

  if (body == null || body === '') {
    return httpBit
      ? `${httpBit}: resposta vazia — confira se a API está rodando (ex.: uvicorn em :8000 e, no dev, proxy do Vite).`
      : 'Resposta vazia da API.'
  }

  if (typeof body === 'object' && body._raw != null) {
    const raw = String(body._raw).replace(/\s+/g, ' ').trim().slice(0, 400)
    return httpBit
      ? `${httpBit}: ${raw || '(sem detalhe)'}`
      : raw || 'Resposta não-JSON do servidor.'
  }

  if (typeof body !== 'object') {
    return httpBit ? `${httpBit}: ${String(body)}` : String(body)
  }

  if (body.code && body.message) {
    return `[${body.code}] ${body.message}`
  }

  const d = body.detail

  if (d && typeof d === 'object' && !Array.isArray(d) && d.code && d.message) {
    return `[${d.code}] ${d.message}`
  }

  if (typeof d === 'string') {
    return httpBit ? `${httpBit}: ${d}` : d
  }

  if (Array.isArray(d)) {
    const msgs = d
      .map((item) => {
        if (item && typeof item === 'object' && item.msg) {
          const loc = Array.isArray(item.loc) ? item.loc.filter(Boolean).join('.') : ''
          return loc ? `${loc}: ${item.msg}` : item.msg
        }
        return JSON.stringify(item)
      })
      .join('; ')
    const out = msgs || 'Dados inválidos'
    return body.code ? `[${body.code}] ${out}` : httpBit ? `${httpBit}: ${out}` : out
  }

  if (body.message) {
    return httpBit ? `${httpBit}: ${body.message}` : body.message
  }

  return httpBit
    ? `${httpBit}: não foi possível interpretar a resposta do servidor.`
    : 'Erro na requisição (resposta sem código nem mensagem conhecida).'
}

export async function readJsonBody(res) {
  const text = await res.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text)
  } catch {
    return { _raw: text }
  }
}

export const useJobsStore = defineStore('jobs', () => {
  const jobs = ref([])
  const loading = ref(false)

  async function fetchJobs() {
    loading.value = true
    try {
      const res = await fetch('/api/jobs')
      const body = await readJsonBody(res)
      if (!res.ok) {
        console.warn('GET /api/jobs', res.status, body)
        jobs.value = []
        return
      }
      if (Array.isArray(body)) {
        jobs.value = body
      } else {
        jobs.value = []
      }
    } catch (e) {
      console.warn('fetchJobs rede:', e)
      jobs.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchJob(id) {
    const res = await fetch(`/api/jobs/${id}`)
    const body = await readJsonBody(res)
    if (!res.ok) {
      throw new Error(formatApiError(body, res.status, res.statusText))
    }
    return body
  }

  async function createJob(payload) {
    let res
    try {
      res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    } catch (e) {
      throw new Error(
        `Falha de rede: ${e.message}. Verifique se o backend está ativo (uvicorn :8000) e, no modo dev, se o Vite está proxyando /api.`
      )
    }
    const body = await readJsonBody(res)
    if (!res.ok) {
      console.warn('POST /api/jobs', res.status, body)
      throw new Error(formatApiError(body, res.status, res.statusText))
    }
    await fetchJobs()
    return body
  }

  return { jobs, loading, fetchJobs, fetchJob, createJob }
})
