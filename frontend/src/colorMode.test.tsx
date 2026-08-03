import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ColorModeProvider, getInitialMode, useColorMode } from './colorMode'

function ModeProbe() {
  const { mode, toggle } = useColorMode()
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <button onClick={toggle}>toggle</button>
    </div>
  )
}

describe('getInitialMode', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.unstubAllGlobals())

  it('honors a previously saved choice over everything else', () => {
    localStorage.setItem('faceplant-color-mode', 'dark')
    expect(getInitialMode()).toBe('dark')
  })

  it('falls back to the OS preference when nothing is saved', () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true }))
    expect(getInitialMode()).toBe('dark')
  })

  it('defaults to light when there is no saved choice and no dark OS preference', () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false }))
    expect(getInitialMode()).toBe('light')
  })
})

describe('ColorModeProvider', () => {
  beforeEach(() => localStorage.clear())

  it('toggles the mode and persists the new choice', async () => {
    render(
      <ColorModeProvider>
        <ModeProbe />
      </ColorModeProvider>,
    )

    expect(screen.getByTestId('mode')).toHaveTextContent('light')

    await userEvent.click(screen.getByRole('button', { name: 'toggle' }))

    expect(screen.getByTestId('mode')).toHaveTextContent('dark')
    expect(localStorage.getItem('faceplant-color-mode')).toBe('dark')
  })

  it('useColorMode throws outside a provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ModeProbe />)).toThrow(/ColorModeProvider/)
    spy.mockRestore()
  })
})
