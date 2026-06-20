import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 600000,
})

export async function fetchParams() {
  const { data } = await api.get('/params')
  return data
}

export async function runSimulationFull(params) {
  const { data } = await api.post('/simulate_full', params)
  return data
}

export async function runSimulation(params) {
  const { data } = await api.post('/simulate', params)
  return data
}

export async function submitAsyncSimulation(params) {
  const { data } = await api.post('/simulate_async', params)
  return data
}

export async function fetchTask(taskId, includeViews = true) {
  const { data } = await api.get(`/task/${taskId}`, {
    params: { include_views: includeViews ? 1 : 0 },
  })
  return data
}

export async function cancelTask(taskId) {
  const { data } = await api.post(`/task/${taskId}/cancel`)
  return data
}

export async function fetchView(view, queryParams = {}) {
  const { data } = await api.get(`/view/${view}`, { params: queryParams })
  return data
}

export async function fetchAllViews() {
  const { data } = await api.get('/views')
  return data
}

export async function checkHealth() {
  try {
    const { data } = await api.get('/health')
    return data.status === 'ok'
  } catch {
    return false
  }
}

export async function pollTaskUntilDone(
  taskId,
  onProgress,
  intervalMs = 400,
  maxPolls = 10000,
) {
  for (let i = 0; i < maxPolls; i++) {
    const t = await fetchTask(taskId, false)
    if (onProgress) {
      const stop = onProgress(t)
      if (stop === false) return t
    }
    if (t.status === 'done') return fetchTask(taskId, true)
    if (t.status === 'error' || t.status === 'cancelled') return t
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error(`Polling timed out after ${maxPolls} attempts`)
}
