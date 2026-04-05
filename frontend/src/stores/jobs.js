import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useJobsStore = defineStore('jobs', () => {
  const jobs = ref([])
  const loading = ref(false)

  async function fetchJobs() {
    loading.value = true
    try {
      const res = await fetch('/api/jobs')
      jobs.value = await res.json()
    } finally {
      loading.value = false
    }
  }

  async function fetchJob(id) {
    const res = await fetch(`/api/jobs/${id}`)
    if (!res.ok) throw new Error('Job não encontrado')
    return res.json()
  }

  async function createJob(payload) {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Erro ao criar job')
    }
    const data = await res.json()
    await fetchJobs()
    return data
  }

  return { jobs, loading, fetchJobs, fetchJob, createJob }
})
