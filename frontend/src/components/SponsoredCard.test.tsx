import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SponsoredCard from './SponsoredCard'
import { ToastProvider } from './ToastProvider'
import type { Ad } from '../api'

const AD: Ad = {
  advertiser: 'PocketPal AI',
  tagline: 'Nobody replying? PocketPal always will.',
  body: 'An AI friend who’s always online and, by design, can never leave you.',
  cta: 'Meet PocketPal',
  mood: 'lonely',
}

describe('SponsoredCard', () => {
  it('states the targeting out loud and renders the ad', () => {
    render(<SponsoredCard ad={AD} />)

    expect(screen.getByText(/sponsored · targeted to your mood: lonely/i)).toBeInTheDocument()
    expect(screen.getByText('PocketPal AI')).toBeInTheDocument()
    expect(screen.getByText('Nobody replying? PocketPal always will.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Meet PocketPal' })).toBeInTheDocument()
  })

  it('the CTA breaks the fourth wall via a toast', async () => {
    render(
      <ToastProvider>
        <SponsoredCard ad={AD} />
      </ToastProvider>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Meet PocketPal' }))
    expect(await screen.findByText("This ad isn't real. The targeting is.")).toBeInTheDocument()
  })
})
