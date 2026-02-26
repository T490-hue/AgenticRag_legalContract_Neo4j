import { useState, useEffect } from "react"
const API = "http://localhost:8000"

export default function History() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/history?limit=30`)
      .then(r=>r.json()).then(d=>{setHistory(d);setLoading(false)})
      .catch(()=>setLoading(false))
  }, [])

  if (loading) return <div style={{color:"#475569",textAlign:"center",padding:"4rem"}}>Loading…</div>

  return (
    <div>
      <div style={{marginBottom:"1.5rem"}}>
        <div style={{fontSize:"1.5rem",fontWeight:700,color:"#f1f5f9",marginBottom:"0.3rem"}}>
          Query History
        </div>
        <div style={{color:"#64748b",fontSize:"0.85rem"}}>
          Stored in PostgreSQL — persists across sessions
        </div>
      </div>

      {history.length === 0 ? (
        <div style={{color:"#334155",textAlign:"center",padding:"3rem",
          border:"1px dashed #1e2433",borderRadius:"10px"}}>
          No queries yet
        </div>
      ) : history.map(q => (
        <div key={q.id} style={{background:"#0d1117",border:"1px solid #1e2433",
          borderRadius:"10px",padding:"1.2rem",marginBottom:"0.8rem"}}>
          <div style={{color:"#f59e0b",fontSize:"0.95rem",fontWeight:600,marginBottom:"0.8rem"}}>
            "{q.question}"
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:"0.8rem"}}>
            {[
              {label:"EXTRACTIVE", color:"#22c55e", answer:q.extractive_answer,
               extra:q.extractive_confidence>0 ? `conf ${q.extractive_confidence?.toFixed(2)}`:""},
              {label:"GRAPH RAG",  color:"#f59e0b", answer:q.graph_answer,
               extra:`${q.graph_latency}s`},
              {label:"BASELINE",   color:"#94a3b8", answer:q.baseline_answer,
               extra:`${q.baseline_latency}s`},
            ].map(col=>(
              <div key={col.label} style={{background:"#080b12",border:`1px solid ${col.color}20`,
                borderRadius:"8px",padding:"0.8rem"}}>
                <div style={{color:col.color,fontSize:"0.65rem",fontWeight:700,
                  fontFamily:"'JetBrains Mono',monospace",marginBottom:"0.4rem"}}>
                  {col.label}
                </div>
                <div style={{color:"#94a3b8",fontSize:"0.82rem",lineHeight:1.5}}>
                  {(col.answer||"—").slice(0,200)}
                  {(col.answer||"").length>200 && "…"}
                </div>
                {col.extra && (
                  <div style={{color:"#475569",fontSize:"0.7rem",marginTop:"0.4rem",
                    fontFamily:"'JetBrains Mono',monospace"}}>{col.extra}</div>
                )}
              </div>
            ))}
          </div>
          <div style={{color:"#334155",fontSize:"0.72rem",marginTop:"0.8rem",
            fontFamily:"'JetBrains Mono',monospace"}}>
            {new Date(q.created_at).toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  )
}
