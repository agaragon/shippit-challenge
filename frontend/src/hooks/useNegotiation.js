import { useCallback, useRef, useState } from 'react'

const WS_URL =
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/negotiate`

export function useNegotiation() {
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('idle')   // idle | negotiating | done
  const [statusText, setStatusText] = useState('')
  const [error, setError] = useState(null)
  const [decision, setDecision] = useState(null)
  const wsRef = useRef(null)

  const startNegotiation = useCallback((quantities, note) => {
    // Reset state
    setMessages([])
    setDecision(null)
    setStatusText('')
    setError(null)
    setStatus('negotiating')

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start_negotiation', quantities, note: note || undefined }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'message':
          setMessages((prev) => [
            ...prev,
            {
              supplier_id: data.supplier_id,
              role: data.role,
              content: data.content,
              round: data.round ?? 0,
            },
          ])
          break

        case 'status':
          setStatusText(data.message)
          break

        case 'decision':
          setDecision({
            winner_supplier_id: data.winner_supplier_id,
            winner_name: data.winner_name,
            reasoning: data.reasoning,
            comparison: data.comparison,
          })
          break

        case 'done':
          setStatus('done')
          setStatusText('')
          ws.close()
          break

        case 'error':
          setError(data.message)
          setStatus('idle')
          ws.close()
          break

        default:
          break
      }
    }

    ws.onerror = () => {
      setError('Could not connect to backend — is the server running on port 8000?')
      setStatus('idle')
    }

    ws.onclose = () => {
      wsRef.current = null
    }
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return { messages, status, statusText, error, clearError, decision, startNegotiation }
}
