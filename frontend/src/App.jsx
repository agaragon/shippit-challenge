import { useEffect, useRef, useState } from 'react'
import { useNegotiation } from './hooks/useNegotiation'

const PRODUCTS = [
  { code: 'FSH013', name: 'Pulse Pro High-Top', defaultQty: 10000 },
  { code: 'FSH014', name: 'Drift Aero High-Top', defaultQty: 5000 },
  { code: 'FSH016', name: 'Vibe City High-Top', defaultQty: 5000 },
  { code: 'FSH019', name: 'Edge Urban High-Top', defaultQty: 5000 },
  { code: 'FSH021', name: 'City Rise High-Top', defaultQty: 5000 },
]

const SUPPLIERS = [
  { id: 1, name: 'Supplier A' },
  { id: 2, name: 'Supplier B' },
  { id: 3, name: 'Supplier C' },
]

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------
function Spinner() {
  return (
    <span
      className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"
      role="status"
      aria-label="Loading"
    />
  )
}

// ---------------------------------------------------------------------------
// ErrorBanner
// ---------------------------------------------------------------------------
function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div className="flex items-start gap-3 bg-red-50 border border-red-300 text-red-800 text-sm px-4 py-3 rounded-lg">
      <span className="text-red-500 mt-0.5">⚠</span>
      <span className="flex-1">{message}</span>
      <button
        onClick={onDismiss}
        className="text-red-400 hover:text-red-600 font-bold leading-none"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// RoundDivider
// ---------------------------------------------------------------------------
function RoundDivider({ round }) {
  return (
    <div className="flex items-center gap-2 my-2">
      <div className="flex-1 h-px bg-gray-200" />
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">
        Round {round}
      </span>
      <div className="flex-1 h-px bg-gray-200" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// ChatColumn — one supplier's conversation thread
// ---------------------------------------------------------------------------
function ChatColumn({ supplierId, supplierName, messages }) {
  const filtered = messages.filter((m) => m.supplier_id === supplierId)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [filtered.length])

  return (
    <div className="flex flex-col flex-1 min-w-0 bg-white rounded-xl shadow border border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 rounded-t-xl">
        <h3 className="font-semibold text-gray-700 text-sm">{supplierName}</h3>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1 min-h-0" style={{ maxHeight: '480px' }}>
        {filtered.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-8">Waiting for messages…</p>
        )}

        {filtered.map((msg, i) => {
          const prevRound = i > 0 ? filtered[i - 1].round : null
          const showDivider = msg.round !== prevRound
          return (
            <div key={i}>
              {showDivider && <RoundDivider round={msg.round} />}
              <ChatBubble role={msg.role} content={msg.content} />
            </div>
          )
        })}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function ChatBubble({ role, content }) {
  const isBrand = role === 'brand'
  return (
    <div className={`flex ${isBrand ? 'justify-start' : 'justify-end'} mb-1`}>
      <div
        className={`max-w-[85%] px-3 py-2 rounded-lg text-xs leading-relaxed whitespace-pre-wrap ${
          isBrand
            ? 'bg-blue-100 text-blue-900 rounded-bl-none'
            : 'bg-gray-100 text-gray-800 rounded-br-none'
        }`}
      >
        <span className={`block font-semibold mb-1 ${isBrand ? 'text-blue-700' : 'text-gray-500'}`}>
          {isBrand ? 'Brand' : 'Supplier'}
        </span>
        {content}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DecisionPanel — shown when negotiation is done
// ---------------------------------------------------------------------------
function DecisionPanel({ decision }) {
  if (!decision) return null

  return (
    <section className="bg-white rounded-xl shadow border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 bg-green-50 border-b border-green-200">
        <h2 className="text-lg font-bold text-green-800">
          Decision — Winner: {decision.winner_name}
        </h2>
      </div>

      <div className="p-6 space-y-6">
        {/* Comparison table */}
        {decision.comparison && Object.keys(decision.comparison).length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-3 uppercase tracking-wide">
              Supplier Comparison
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-50">
                    {['Supplier', 'Cost', 'Quality', 'Lead Time', 'Payment Terms', 'Overall'].map((h) => (
                      <th key={h} className="text-left px-3 py-2 border border-gray-200 text-gray-600 font-semibold">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(decision.comparison).map(([name, data]) => {
                    const isWinner = name === decision.winner_name
                    return (
                      <tr key={name} className={isWinner ? 'bg-green-50 font-medium' : 'bg-white'}>
                        <td className="px-3 py-2 border border-gray-200">
                          {isWinner && <span className="mr-1">🏆</span>}
                          {name}
                        </td>
                        <td className="px-3 py-2 border border-gray-200 text-gray-700">{data.cost_assessment ?? '—'}</td>
                        <td className="px-3 py-2 border border-gray-200 text-gray-700">{data.quality_assessment ?? '—'}</td>
                        <td className="px-3 py-2 border border-gray-200 text-gray-700">{data.lead_time_assessment ?? '—'}</td>
                        <td className="px-3 py-2 border border-gray-200 text-gray-700">{data.payment_terms_assessment ?? '—'}</td>
                        <td className="px-3 py-2 border border-gray-200 text-gray-700">{data.overall_score ?? '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Reasoning */}
        <div>
          <h3 className="text-sm font-semibold text-gray-600 mb-2 uppercase tracking-wide">
            AI Reasoning
          </h3>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap bg-gray-50 rounded-lg p-4 border border-gray-200">
            {decision.reasoning}
          </p>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
export default function App() {
  const { messages, status, statusText, error, clearError, decision, startNegotiation } =
    useNegotiation()

  const [quantities, setQuantities] = useState(
    Object.fromEntries(PRODUCTS.map((p) => [p.code, p.defaultQty]))
  )
  const [note, setNote] = useState('')

  const isNegotiating = status === 'negotiating'

  function handleQtyChange(code, value) {
    setQuantities((prev) => ({ ...prev, [code]: Number(value) || 0 }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    startNegotiation(quantities, note.trim())
  }

  return (
    <div className="min-h-screen bg-gray-100 text-gray-900">
      <header className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
        <h1 className="text-xl font-bold tracking-tight">Supplier Negotiation</h1>
        <p className="text-xs text-gray-500 mt-0.5">AI-powered multi-supplier negotiation</p>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">

        {/* Error banner */}
        <ErrorBanner message={error} onDismiss={clearError} />

        {/* ---------------------------------------------------------------- */}
        {/* Controls                                                          */}
        {/* ---------------------------------------------------------------- */}
        <section className="bg-white rounded-xl shadow border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-700 mb-4">Order Configuration</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {PRODUCTS.map((p) => (
                <div key={p.code} className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-gray-600">
                    {p.name}
                    <span className="block text-gray-400 font-normal">{p.code}</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={quantities[p.code]}
                    onChange={(e) => handleQtyChange(p.code, e.target.value)}
                    disabled={isNegotiating}
                    className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-gray-100 disabled:text-gray-400"
                  />
                </div>
              ))}
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">
                Additional note for the brand negotiator{' '}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={isNegotiating}
                rows={2}
                placeholder="e.g. Prioritise lead time over cost. Avoid Supplier A if possible."
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-gray-100 disabled:text-gray-400"
              />
            </div>

            <div className="flex items-center gap-4">
              <button
                type="submit"
                disabled={isNegotiating}
                className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-sm font-semibold rounded-lg transition-colors"
              >
                {isNegotiating && <Spinner />}
                {isNegotiating ? 'Negotiating…' : 'Start Negotiation'}
              </button>
              {isNegotiating && statusText && (
                <span className="text-xs text-gray-500 italic">{statusText}</span>
              )}
            </div>
          </form>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Conversations                                                     */}
        {/* ---------------------------------------------------------------- */}
        {(isNegotiating || status === 'done') && (
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-gray-700">Conversations</h2>
              {isNegotiating && (
                <span className="inline-flex items-center gap-1.5 text-xs text-blue-600 font-medium">
                  <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                  Live
                </span>
              )}
            </div>
            <div className="flex gap-4">
              {SUPPLIERS.map((s) => (
                <ChatColumn
                  key={s.id}
                  supplierId={s.id}
                  supplierName={s.name}
                  messages={messages}
                />
              ))}
            </div>
          </section>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Decision                                                          */}
        {/* ---------------------------------------------------------------- */}
        {status === 'done' && <DecisionPanel decision={decision} />}

      </main>
    </div>
  )
}
