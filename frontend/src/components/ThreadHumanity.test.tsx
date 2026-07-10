import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ThreadHumanity from './ThreadHumanity'

describe('ThreadHumanity', () => {
  it('shows a percentage when at least one human is present', () => {
    render(<ThreadHumanity share={0.25} human={1} total={4} />)
    expect(screen.getByText('25% human')).toBeInTheDocument()
  })

  it('reads "dead internet" when there are no humans at all', () => {
    render(<ThreadHumanity share={0} human={0} total={8} />)
    expect(screen.getByText('dead internet')).toBeInTheDocument()
    expect(screen.queryByText(/human/)).not.toBeInTheDocument()
  })

  it('rounds the share to a whole percent', () => {
    render(<ThreadHumanity share={0.048} human={1} total={21} />)
    expect(screen.getByText('5% human')).toBeInTheDocument()
  })
})
