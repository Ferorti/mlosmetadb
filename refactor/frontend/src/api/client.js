import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
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
