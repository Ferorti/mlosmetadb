import statsData from '../data/stats.json'

// Replace import + return with client.get('/stats') when the API is ready.
export async function getStats() {
  return { data: statsData }
}
