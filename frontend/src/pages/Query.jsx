import { useState } from "react"
const API = "http://localhost:8000"

const METHOD_COLORS = {
  vector:"#0284c7", clause:"#f59e0b", graph_expand:"#7c3aed",
  structured:"#059669", sequential:"#475569"
}

const EXAMPLES = [
  "Which contracts have indemnification clauses?",
  "What are the termination conditions?",
  "Are there any conflicting clauses?",
  "Which party has the most obligations?",
  "What contracts have no liability caps?",
  "What jurisdiction governs these agreements?",
  "Find all contracts involving CloudBase",
]

const tag = (label, color="#475569") => (
  <span key={label} style={{
    background:"#0d1117", border:`1px solid ${color}30`,
    color, fontSize:"0.7rem", padding:"0.2rem 0.6rem",
    borderRadius:"4px", fontFamily:"'JetBrains Mono',monospace",
    marginRight:"0.4rem"
  }}>{label}</span>
)

export default function Query() {
  const [q,       setQ]       = useState("")
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState("")
  const [showSrc, setShowSrc] = useState(false)

  const search = async (text) => {
    const question = (text || q).trim()
    if (!question) return
    setLoading(true); setError(""); setResult(null); setShowSrc(false)
    try {
      const r = await fetch(`${API}/query`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ question }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setResult(await r.json())
    } catch(e) {
      setError(`Error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const AnswerCard = ({ accent, label, badge, answer, meta }) => (
    <div style={{
      background:"#0d1117",
      border:`1px solid ${accent}25`,
      borderTop:`3px solid ${accent}`,
      borderRadius:"12px", padding:"1.4rem", flex:1
    }}>
      {/* Header */}
      <div style={{display:"flex",alignItems:"center",
        gap:"0.5rem",marginBottom:"1rem",flexWrap:"wrap"}}>
        <span style={{
          color:accent, fontWeight:700, fontSize:"0.72rem",
          fontFamily:"'JetBrains Mono',monospace",
          letterSpacing:"0.08em"
        }}>{label}</span>
        {badge && (
          <span style={{
            background:`${accent}18`, color:accent,
            fontSize:"0.65rem", padding:"0.15rem 0.5rem",
            borderRadius:"3px", fontFamily:"'JetBrains Mono',monospace"
          }}>{badge}</span>
        )}
      </div>

      {/* Answer text */}
      <div style={{
        color:"#e2e8f0", fontSize:"0.88rem", lineHeight:1.75,
        marginBottom:"1rem", minHeight:"100px",
        whiteSpace:"pre-wrap"
      }}>
        {answer || <span style={{color:"#334155"}}>—</span>}
      </div>

      {/* Meta chips */}
      <div style={{display:"flex",gap:"0.4rem",flexWrap:"wrap"}}>
        {meta}
      </div>
    </div>
  )

  return (
    <div>
      {/* Header */}
      <div style={{textAlign:"center",marginBottom:"2rem"}}>
        <div style={{fontSize:"1.8rem",fontWeight:700,
          color:"#f1f5f9",marginBottom:"0.4rem"}}>
          Contract Intelligence
        </div>
        <div style={{color:"#64748b",fontSize:"0.85rem"}}>
          Graph RAG vs Flat Baseline — same LLM, same prompt, different retrieval
        </div>
      </div>

      {/* Search bar */}
      <div style={{display:"flex",gap:"1rem",marginBottom:"1.2rem"}}>
        <input
          style={{
            flex:1, background:"#0d1117",
            border:"1px solid #1e2433",
            borderRadius:"10px", padding:"0.9rem 1.2rem",
            color:"#f1f5f9", fontSize:"0.95rem",
            fontFamily:"'Inter',sans-serif", outline:"none"
          }}
          placeholder="Ask a question about your contracts…"
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => e.key==="Enter" && search()}
        />
        <button onClick={() => search()} disabled={loading} style={{
          background: loading ? "#1e2433" : "#f59e0b",
          color:      loading ? "#64748b" : "#000",
          border:"none", borderRadius:"10px",
          padding:"0 2rem", fontSize:"0.9rem", fontWeight:700,
          cursor: loading ? "not-allowed" : "pointer",
          whiteSpace:"nowrap"
        }}>
          {loading ? "Searching…" : "Search →"}
        </button>
      </div>

      {/* Example questions */}
      {!result && !loading && (
        <div style={{marginBottom:"2rem"}}>
          <div style={{color:"#334155",fontSize:"0.75rem",
            marginBottom:"0.6rem"}}>Try an example:</div>
          <div style={{display:"flex",gap:"0.5rem",flexWrap:"wrap"}}>
            {EXAMPLES.map(ex => (
              <button key={ex}
                onClick={() => { setQ(ex); search(ex) }}
                style={{
                  background:"#0d1117",
                  border:"1px solid #1e2433", color:"#64748b",
                  borderRadius:"20px", padding:"0.35rem 0.9rem",
                  fontSize:"0.76rem", cursor:"pointer",
                  fontFamily:"'Inter',sans-serif"
                }}>
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div style={{
          color:"#ef4444", background:"#1a0808",
          border:"1px solid #7f1d1d", borderRadius:"8px",
          padding:"0.9rem 1rem", marginBottom:"1rem",
          fontSize:"0.85rem"
        }}>{error}</div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div style={{display:"flex",gap:"1.2rem",marginBottom:"1.5rem"}}>
          {["#f59e0b","#475569"].map((a,i) => (
            <div key={i} style={{
              flex:1, background:"#0d1117",
              border:`1px solid ${a}25`,
              borderTop:`3px solid ${a}`,
              borderRadius:"12px", padding:"1.4rem", opacity:0.4
            }}>
              <div style={{height:"14px",background:"#1e2433",
                borderRadius:"4px",marginBottom:"1rem",width:"40%"}}/>
              <div style={{height:"100px",background:"#1e2433",borderRadius:"4px"}}/>
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Two answer columns */}
          <div style={{display:"flex",gap:"1.2rem",
            marginBottom:"1.2rem",flexWrap:"wrap"}}>

            <AnswerCard
              accent="#f59e0b"
              label="GRAPH RAG"
              badge={`${result.graph_only_chunks} graph-only chunks`}
              answer={result.graph_answer}
              meta={[
                tag(`${result.graph_latency}s`, "#f59e0b"),
                tag(`${result.graph_chunks} chunks retrieved`, "#f59e0b"),
                result.graph_only_chunks > 0 && (
                  <span key="go" style={{
                    background:"#f59e0b18", color:"#f59e0b",
                    fontSize:"0.7rem", padding:"0.2rem 0.6rem",
                    borderRadius:"4px",
                    fontFamily:"'JetBrains Mono',monospace"
                  }}>
                    ✦ graph traversal found extra context
                  </span>
                )
              ]}
            />

            <AnswerCard
              accent="#475569"
              label="FLAT BASELINE"
              badge="vector only"
              answer={result.baseline_answer}
              meta={[
                tag(`${result.baseline_latency}s`, "#475569"),
                tag("cosine similarity", "#475569"),
                tag("no graph", "#475569"),
              ]}
            />
          </div>

          {/* What this comparison shows */}
          {result.graph_only_chunks > 0 && (
            <div style={{
              background:"#0a0f05",
              border:"1px solid #14532d",
              borderLeft:"3px solid #22c55e",
              borderRadius:"8px", padding:"0.8rem 1.1rem",
              marginBottom:"1.2rem", fontSize:"0.82rem"
            }}>
              <span style={{color:"#22c55e",fontWeight:600}}>
                Graph advantage:{" "}
              </span>
              <span style={{color:"#86efac"}}>
                Graph RAG found {result.graph_only_chunks} passage(s) via
                graph traversal that vector search would have missed —
                clause nodes, CONFLICTS_WITH edges, or cross-contract
                RELATED_TO links.
              </span>
            </div>
          )}

          {/* Sources */}
          <div style={{
            background:"#0d1117",
            border:"1px solid #1e2433",
            borderRadius:"10px", padding:"1rem 1.4rem"
          }}>
            <button
              onClick={() => setShowSrc(!showSrc)}
              style={{
                background:"none", border:"none",
                color:"#475569", cursor:"pointer",
                fontSize:"0.83rem", padding:0,
                fontFamily:"'Inter',sans-serif"
              }}>
              {showSrc ? "▾" : "▸"}{" "}
              Retrieved Sources ({result.sources.length})
              {" — "}
              <span style={{color:"#334155",fontSize:"0.75rem"}}>
                click to see which passages each answer was grounded in
              </span>
            </button>

            {showSrc && (
              <div style={{marginTop:"0.8rem"}}>
                {result.sources.map((src, i) => (
                  <div key={i} style={{
                    borderTop:"1px solid #1e2433",
                    padding:"0.8rem 0",
                    fontSize:"0.8rem", color:"#94a3b8"
                  }}>
                    <div style={{
                      display:"flex", gap:"0.5rem",
                      alignItems:"center", marginBottom:"0.35rem",
                      flexWrap:"wrap"
                    }}>
                      <span style={{
                        fontFamily:"'JetBrains Mono',monospace",
                        fontSize:"0.65rem",
                        color: METHOD_COLORS[src.method] || "#64748b",
                        background:"#1e2433",
                        padding:"0.15rem 0.5rem", borderRadius:"3px"
                      }}>{src.method}</span>
                      <span style={{color:"#334155",fontSize:"0.72rem"}}>
                        score {src.score}
                      </span>
                      {src.contract_title && (
                        <span style={{color:"#f59e0b",fontSize:"0.72rem"}}>
                          📄 {src.contract_title.slice(0,55)}
                        </span>
                      )}
                    </div>
                    <div style={{lineHeight:1.5}}>{src.text}</div>
                    {src.clause_context && (
                      <div style={{
                        color:"#059669", fontSize:"0.72rem",
                        marginTop:"0.3rem"
                      }}>
                        🔗 via clause: {src.clause_context}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
