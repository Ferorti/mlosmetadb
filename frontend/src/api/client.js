import axios from 'axios'

// Sits under whatever base the app was built for: '/api' normally, '/v2/api'
// for a sub-path build. BASE_URL always ends in a slash.
//
// Nothing strips the '/api' prefix inside FastAPI — its routes are '/search',
// '/proteins', etc. In development Vite's proxy removes it (see
// vite.config.js); in production nginx does, via a proxy_pass with a trailing
// slash. Point this at a bare uvicorn and every call 404s.
const client = axios.create({
  baseURL: `${import.meta.env.BASE_URL}api`,
  timeout: 20000,
})

client.interceptors.request.use(config => {
  console.log(
    `%c→ ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`,
    'color: #2B7CD8; font-weight: bold',
    config.params ?? ''
  )
  return config
})

client.interceptors.response.use(
  response => {
    console.log(
      `%c← ${response.status} ${response.config.url}`,
      'color: #3B6D11; font-weight: bold',
      { total: response.data?.total ?? response.data?.total_hits ?? '?' }
    )
    return response
  },
  error => {
    console.error(
      `%c✗ ${error.response?.status ?? 'ERR'} ${error.config?.url}`,
      'color: #791F1F; font-weight: bold',
      error.message
    )
    return Promise.reject(error)
  }
)

export default client
