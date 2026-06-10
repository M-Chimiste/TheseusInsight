import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { SnackbarProvider, useSnackbar } from './SnackbarContext'

const Trigger: React.FC = () => {
  const { showError, showSuccess } = useSnackbar()
  return (
    <>
      <button onClick={() => showError('boom')}>err</button>
      <button onClick={() => showSuccess('yay')}>ok</button>
    </>
  )
}

describe('SnackbarProvider', () => {
  it('shows messages with the right severity', async () => {
    render(
      <SnackbarProvider>
        <Trigger />
      </SnackbarProvider>,
    )
    screen.getByText('err').click()
    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveClass('MuiAlert-standardError')

    screen.getByText('ok').click()
    await waitFor(() => expect(screen.getByText('yay')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveClass('MuiAlert-standardSuccess')
  })
})
