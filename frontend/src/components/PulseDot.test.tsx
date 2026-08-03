import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import PulseDot from './PulseDot'

describe('PulseDot', () => {
  it('renders a decorative, animated indicator that is hidden from assistive tech', () => {
    const { container } = render(<PulseDot />)
    const dot = container.firstElementChild as HTMLElement
    expect(dot).toBeTruthy()
    // Decorative only — screen readers should skip it.
    expect(dot).toHaveAttribute('aria-hidden', 'true')
    // The pulse animation is wired up (emotion emits it as a class-based style).
    expect(dot.className).toBeTruthy()
  })
})
