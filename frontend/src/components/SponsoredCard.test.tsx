import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import SponsoredCard from './SponsoredCard'
import type { Ad } from '../api'

const AD: Ad = {
  advertiser: 'PocketPal AI',
  tagline: 'Nobody replying? PocketPal always will.',
  body: 'An AI friend who’s always online and, by design, can never leave you.',
  cta: 'Meet PocketPal',
  mood: 'lonely',
  url: 'https://en.wikipedia.org/wiki/Chatbot',
}

describe('SponsoredCard', () => {
  it('states the targeting out loud and renders the ad', () => {
    render(<SponsoredCard ad={AD} />)

    expect(screen.getByText(/sponsored · targeted to your mood: lonely/i)).toBeInTheDocument()
    expect(screen.getByText('PocketPal AI')).toBeInTheDocument()
    expect(screen.getByText('Nobody replying? PocketPal always will.')).toBeInTheDocument()
  })

  it('links the CTA out with safe rel attributes', () => {
    render(<SponsoredCard ad={AD} />)

    const cta = screen.getByRole('link', { name: 'Meet PocketPal' })
    expect(cta).toHaveAttribute('href', 'https://en.wikipedia.org/wiki/Chatbot')
    expect(cta).toHaveAttribute('target', '_blank')
    expect(cta).toHaveAttribute('rel', 'sponsored nofollow noopener noreferrer')
  })

  it('disclaims the placement so a real brand is not implicated', () => {
    render(<SponsoredCard ad={AD} />)

    expect(screen.getByText(/didn't target you, Faceplant did/i)).toBeInTheDocument()
  })
})
