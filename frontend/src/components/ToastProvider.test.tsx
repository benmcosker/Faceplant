import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider, useToast } from './ToastProvider'

function Boom() {
  const toast = useToast()
  return <button onClick={() => toast.error('the server exploded')}>break</button>
}

describe('ToastProvider', () => {
  it('surfaces a toast message when an action reports a failure', async () => {
    render(
      <ToastProvider>
        <Boom />
      </ToastProvider>,
    )

    expect(screen.queryByText('the server exploded')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'break' }))
    expect(await screen.findByText('the server exploded')).toBeInTheDocument()
  })

  it('useToast is a no-op without a provider (does not throw)', async () => {
    render(<Boom />)
    await userEvent.click(screen.getByRole('button', { name: 'break' }))
    expect(screen.queryByText('the server exploded')).toBeNull()
  })
})
