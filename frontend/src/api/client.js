import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 20000,
})

export default client
