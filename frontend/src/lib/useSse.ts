import { useEffect, useRef, useState } from 'react'
import type { SseState } from './types'
import { apiBaseUrl } from './api'

const TERMINAL: SseState[] = ['done', 'failed']

export function useTaskSse(taskId?: string) {
  const [states, setStates] = useState<SseState[]>([])
  const [error, setError] = useState<string>('')
  const sourceRef = useRef<EventSource | null>(null)
  const terminalRef = useRef(false)

  useEffect(() => {
    if (!taskId) return

    setStates([])
    setError('')
    terminalRef.current = false

    const es = new EventSource(`${apiBaseUrl}/api/generate/${taskId}/events`)
    sourceRef.current = es

    es.onmessage = (e) => {
      const msg = (e.data || '').toString().trim() as SseState
      if (!msg) return

      setStates((prev) => (prev.includes(msg) ? prev : [...prev, msg]))

      if (TERMINAL.includes(msg)) {
        terminalRef.current = true
        es.close()
      }
    }

    es.onerror = () => {
      // EventSource will fire onerror when server closes stream.
      // If task already reached terminal state, this is expected.
      if (!terminalRef.current) {
        setError('SSE 连接异常，请稍后重试。')
      }
      es.close()
    }

    return () => {
      es.close()
    }
  }, [taskId])

  return { states, error }
}
