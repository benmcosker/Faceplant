import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ColorModeProvider } from '../colorMode'
import ThemeToggle from './ThemeToggle'

function renderToggle() {
  return render(
    <ColorModeProvider>
      <ThemeToggle />
    </ColorModeProvider>,
  )
}

describe('ThemeToggle', () => {
  beforeEach(() => localStorage.clear())

  it('labels itself by the mode it would switch to, and flips on click', async () => {
    renderToggle()

    // Starts in light mode → the control offers the switch *to* dark.
    const toDark = screen.getByRole('button', { name: 'Switch to dark mode' })
    await userEvent.click(toDark)

    // Now in dark mode → the control offers the switch back to light.
    expect(screen.getByRole('button', { name: 'Switch to light mode' })).toBeInTheDocument()
    expect(localStorage.getItem('faceplant-color-mode')).toBe('dark')
  })
})
