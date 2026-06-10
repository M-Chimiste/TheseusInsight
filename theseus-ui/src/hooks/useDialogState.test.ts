import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useDialogState } from './useDialogState'

describe('useDialogState', () => {
  it('starts closed with no data', () => {
    const { result } = renderHook(() => useDialogState<{ id: number }>())
    expect(result.current.open).toBe(false)
    expect(result.current.data).toBeNull()
  })

  it('openWith stores the payload and opens', () => {
    const { result } = renderHook(() => useDialogState<{ id: number }>())
    act(() => result.current.openWith({ id: 7 }))
    expect(result.current.open).toBe(true)
    expect(result.current.data).toEqual({ id: 7 })
  })

  it('close keeps data for exit animations; openEmpty clears it', () => {
    const { result } = renderHook(() => useDialogState<{ id: number }>())
    act(() => result.current.openWith({ id: 7 }))
    act(() => result.current.close())
    expect(result.current.open).toBe(false)
    expect(result.current.data).toEqual({ id: 7 })
    act(() => result.current.openEmpty())
    expect(result.current.open).toBe(true)
    expect(result.current.data).toBeNull()
  })
})
