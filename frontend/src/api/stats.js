import client from './client'
import fallbackStats from '../data/stats.json'

export async function getStats() {
  try {
    return await client.get('/stats')
  } catch {
    console.warn('[stats] API unavailable, using static fallback')
    return { data: fallbackStats }
  }
}
