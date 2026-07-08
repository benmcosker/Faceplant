import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CostMeter from './CostMeter'

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return { ...actual, fetchCosts: vi.fn() }
})
import { type CostSummary, fetchCosts } from '../api'

const SUMMARY: CostSummary = {
  total_cost_usd: 0.0234,
  total_calls: 12,
  input_tokens: 9000,
  output_tokens: 1500,
  by_source: {
    bot_reaction: { cost_usd: 0.02, calls: 10 },
    ad_tagline: { cost_usd: 0.0034, calls: 2 },
  },
  per_human_user: [
    { username: 'maya', cost_usd: 0.0184, calls: 8 },
    { username: 'jordan', cost_usd: 0.005, calls: 4 },
  ],
  human_user_count: 2,
  cost_per_human_user_avg: 0.0117,
  cost_per_post_usd: 0.0039,
  rate_per_min_usd: 0.0021,
  recent: [
    { source: 'ad_tagline', actor: 'Evergreen Farewell Plans', human_username: 'maya', cost_usd: 0.0007, created_at: '2026-07-08T00:00:00Z' },
    { source: 'bot_reaction', actor: 'gifgremlin', human_username: 'jordan', cost_usd: 0.0006, created_at: '2026-07-08T00:00:01Z' },
  ],
  spend_per_min: [0, 0, 0.001, 0.003, 0.0007, 0, 0.002, 0, 0, 0.0005, 0, 0, 0.001, 0.004, 0.0021],
}

describe('CostMeter', () => {
  it('shows the running total and, on click, the swarm/ads + per-human breakdown', async () => {
    vi.mocked(fetchCosts).mockResolvedValue(SUMMARY)

    render(<CostMeter />)

    const pill = await screen.findByRole('button', { name: 'AI cost meter' })
    expect(pill).toHaveTextContent('$0.0234')

    await userEvent.click(pill)

    expect(screen.getByText('The cost of manufactured engagement')).toBeInTheDocument()
    expect(screen.getByText('Bot swarm')).toBeInTheDocument()
    expect(screen.getByText('Ad targeting')).toBeInTheDocument()
    expect(screen.getByText(/across 2 humans/)).toBeInTheDocument()
    expect(screen.getByText('maya')).toBeInTheDocument()
    expect(screen.getByText('jordan')).toBeInTheDocument()

    // Phase 2 storytelling layer: derived stats + recent-spend ticker.
    expect(screen.getByText('per post')).toBeInTheDocument()
    expect(screen.getByText('$0.0039')).toBeInTheDocument()
    expect(screen.getByText('spend rate')).toBeInTheDocument()
    expect(screen.getByText('Recent activity')).toBeInTheDocument()
    expect(screen.getByText('Evergreen Farewell Plans targeted maya')).toBeInTheDocument()
    expect(screen.getByText('gifgremlin reacted to jordan')).toBeInTheDocument()
    expect(screen.getByText('+$0.0007')).toBeInTheDocument()
  })

  it('renders $0.0000 before any data arrives', () => {
    vi.mocked(fetchCosts).mockReturnValue(new Promise(() => {})) // never resolves

    render(<CostMeter />)
    expect(screen.getByRole('button', { name: 'AI cost meter' })).toHaveTextContent('$0.0000')
  })
})
