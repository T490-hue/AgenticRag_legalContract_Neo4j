import { useState, useEffect } from "react"
const API = "http://localhost:8000"

const SEV_COLOR  = { high:"#ef4444", medium:"#f59e0b", low:"#22c55e" }
const SEV_BG     = { high:"#1a0808", medium:"#1a0e00", low:"#071a0e" }
const SEV_BORDER = { high:"#7f1d1d", medium:"#78350f", low:"#14532d" }

export default function Risks() {
  const [flags,  setFlags]  = useState([])
  const [filter, setFilter] = useState("all")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/risks`)
      .then(r => r.json())
      .then(d => { setFlags(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const filtered = filter === "all" ? flags :
    flags.filter(f => f.severity === filter)

  const counts = {
    all:    flags.length,
    high:   flags.filter(f=>f.severity==="high").length,
    medium: flags.filter(f=>f.severity==="medium").length,
    low:    flags.filter(f=>f.severity==="low").length,
  }

  return (
    <div>
      <div style={{marginBottom:"1.5rem"}}>
        <div style={{fontSize:"1.5rem",fontWeight:700,color:"#f1f5f9",marginBottom:"0.3rem"}}>
          Risk Flags
        </div>
        <div style={{color:"#64748b",fontSize:"0.85rem"}}>
          LLM-extracted risks across all contracts — stored in PostgreSQL, linked in Neo4j
        </div>
      </div>

      {/* Summary cards */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",
        gap:"0.8rem",marginBottom:"1.5rem"}}>
        {[
          {label:"Total Flags",   value:counts.all,    color:"#94a3b8"},
          {label:"High Severity", value:counts.high,   color:"#ef4444"},
          {label:"Medium",        value:counts.medium, color:"#f59e0b"},
          {label:"Low",           value:counts.low,    color:"#22c55e"},
        ].map(s=>(
          <div key={s.label} style={{background:"#0d1117",border:"1px solid #1e2433",
            borderRadius:"10px",padding:"1rem",textAlign:"center"}}>
            <div style={{fontSize:"1.8rem",fontWeight:700,color:s.color,
              fontFamily:"'JetBrains Mono',monospace"}}>{s.value}</div>
            <div style={{color:"#475569",fontSize:"0.75rem"}}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div style={{display:"flex",gap:"0.5rem",marginBottom:"1.2rem"}}>
        {["all","high","medium","low"].map(f=>(
          <button key={f} onClick={()=>setFilter(f)} style={{
            background: filter===f ? "#1e2433" : "none",
            border:`1px solid ${filter===f?"#334155":"#1e2433"}`,
            color: filter===f
              ? (SEV_COLOR[f]||"#f1f5f9")
              : "#64748b",
            borderRadius:"8px",padding:"0.4rem 1rem",cursor:"pointer",
            fontSize:"0.82rem",fontFamily:"'Inter',sans-serif",
            textTransform:"capitalize",
          }}>
            {f} {counts[f] > 0 && `(${counts[f]})`}
          </button>
        ))}
      </div>

      {loading && (
        <div style={{color:"#475569",textAlign:"center",padding:"3rem"}}>
          Loading risks…
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div style={{color:"#334155",textAlign:"center",padding:"3rem",
          border:"1px dashed #1e2433",borderRadius:"10px"}}>
          {flags.length === 0
            ? "No risk flags yet — upload contracts first"
            : `No ${filter} severity flags found`}
        </div>
      )}

      <div>
        {filtered.map((f, i) => (
          <div key={i} style={{
            background: SEV_BG[f.severity]   || "#0d1117",
            border:    `1px solid ${SEV_BORDER[f.severity]||"#1e2433"}`,
            borderLeft:`4px solid ${SEV_COLOR[f.severity]||"#475569"}`,
            borderRadius:"10px",padding:"1rem 1.2rem",marginBottom:"0.7rem",
          }}>
            <div style={{display:"flex",alignItems:"center",gap:"0.7rem",
              marginBottom:"0.5rem",flexWrap:"wrap"}}>
              <span style={{color:SEV_COLOR[f.severity]||"#94a3b8",
                fontWeight:700,fontSize:"0.82rem",textTransform:"uppercase"}}>
                {f.severity}
              </span>
              <span style={{background:"#0d1117",border:"1px solid #1e2433",
                color:"#94a3b8",fontSize:"0.72rem",padding:"0.15rem 0.55rem",
                borderRadius:"4px",fontFamily:"'JetBrains Mono',monospace"}}>
                {f.flag_type}
              </span>
              {(f.filename || f.title) && (
                <span style={{color:"#f59e0b",fontSize:"0.75rem"}}>
                  📄 {(f.title || f.filename || "").slice(0, 50)}
                </span>
              )}
            </div>
            <div style={{color:"#e2e8f0",fontSize:"0.88rem",marginBottom:"0.4rem"}}>
              {f.description}
            </div>
            {f.clause_ref && (
              <div style={{color:"#64748b",fontSize:"0.78rem"}}>
                Clause: {f.clause_ref}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
