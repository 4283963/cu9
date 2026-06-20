import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
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
