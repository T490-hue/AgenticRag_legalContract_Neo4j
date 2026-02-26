import { useState, useEffect, useRef } from "react"
const API = "http://localhost:8000"

const RISK_COLOR = { high:"#ef4444", medium:"#f59e0b", low:"#22c55e" }
const STATUS_COLOR = { pending:"#d97706", processing:"#0284c7", complete:"#22c55e", failed:"#ef4444" }

function ContractCard({ c, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const [detail,   setDetail]   = useState(null)

  const fetchDetail = async () => {
    const r = await fetch(`${API}/contracts/${c.id}/status`)
    setDetail(await r.json())
  }

  const highRisks = detail?.risk_flags?.filter(f => f.severity === "high") || []
  const riskScore = c.risk_score || 0

  return (
    <div style={{background:"#0d1117",border:"1px solid #1e2433",borderRadius:"10px",
      padding:"1.2rem",marginBottom:"0.8rem"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div style={{flex:1}}>
          {/* Title row */}
          <div style={{display:"flex",alignItems:"center",gap:"0.6rem",marginBottom:"0.5rem",flexWrap:"wrap"}}>
            <span style={{color:"#f1f5f9",fontSize:"0.92rem",fontWeight:500}}>
              📄 {c.title || c.filename}
            </span>
            <span style={{background:"#1e2433",color:STATUS_COLOR[c.status]||"#64748b",
              fontSize:"0.68rem",fontWeight:700,padding:"0.15rem 0.55rem",
              borderRadius:"4px",fontFamily:"'JetBrains Mono',monospace"}}>
              {c.status}
            </span>
            {c.contract_type && (
              <span style={{background:"#1e2433",color:"#94a3b8",fontSize:"0.68rem",
                padding:"0.15rem 0.55rem",borderRadius:"4px"}}>
                {c.contract_type}
              </span>
            )}
          </div>

          {/* Meta row */}
          <div style={{display:"flex",gap:"1.2rem",color:"#475569",fontSize:"0.75rem",marginBottom:"0.5rem",flexWrap:"wrap"}}>
            {c.jurisdiction   && <span>⚖ {c.jurisdiction}</span>}
            {c.effective_date && <span>📅 {c.effective_date}</span>}
            {c.chunk_count > 0  && <span>{c.chunk_count} chunks</span>}
            {c.clause_count > 0 && <span>{c.clause_count} clauses</span>}
            {c.file_size        && <span>{(c.file_size/1024).toFixed(1)} KB</span>}
          </div>

          {/* Parties */}
          {c.parties?.length > 0 && (
            <div style={{display:"flex",gap:"0.4rem",flexWrap:"wrap",marginBottom:"0.5rem"}}>
              {c.parties.map(p => (
                <span key={p} style={{background:"#0f172a",border:"1px solid #1e2433",
                  color:"#94a3b8",fontSize:"0.72rem",padding:"0.15rem 0.5rem",
                  borderRadius:"12px"}}>
                  👤 {p}
                </span>
              ))}
            </div>
          )}

          {/* Risk score bar */}
          {c.status === "complete" && (
            <div style={{display:"flex",alignItems:"center",gap:"0.8rem",marginBottom:"0.4rem"}}>
              <span style={{color:"#475569",fontSize:"0.72rem"}}>Risk score</span>
              <div style={{flex:1,maxWidth:"120px",height:"4px",background:"#1e2433",borderRadius:"2px"}}>
                <div style={{
                  width:`${riskScore*100}%`,
                  height:"100%",borderRadius:"2px",
                  background: riskScore > 0.5 ? "#ef4444" : riskScore > 0.2 ? "#f59e0b" : "#22c55e"
                }}/>
              </div>
              <span style={{color:riskScore>0.5?"#ef4444":riskScore>0.2?"#f59e0b":"#22c55e",
                fontSize:"0.72rem",fontFamily:"'JetBrains Mono',monospace"}}>
                {(riskScore*100).toFixed(0)}%
              </span>
            </div>
          )}

          {c.error_msg && (
            <div style={{color:"#ef4444",fontSize:"0.78rem"}}>⚠ {c.error_msg}</div>
          )}

          {/* Expand button */}
          {c.status === "complete" && (
            <button onClick={()=>{ setExpanded(!expanded); if(!expanded) fetchDetail() }}
              style={{background:"none",border:"none",color:"#475569",cursor:"pointer",
                fontSize:"0.75rem",padding:"0.2rem 0",fontFamily:"'Inter',sans-serif"}}>
              {expanded ? "▲ Hide details" : "▼ Show processing log & risks"}
            </button>
          )}

          {/* Expanded detail */}
          {expanded && detail && (
            <div style={{marginTop:"0.8rem",borderTop:"1px solid #1e2433",paddingTop:"0.8rem"}}>
              {/* Processing log */}
              <div style={{color:"#475569",fontSize:"0.7rem",marginBottom:"0.5rem"}}>
                PROCESSING LOG
              </div>
              {detail.processing_log?.map((l,i) => (
                <div key={i} style={{fontSize:"0.75rem",color:"#64748b",
                  marginBottom:"0.2rem",fontFamily:"'JetBrains Mono',monospace"}}>
                  <span style={{color:l.status==="complete"?"#22c55e":l.status==="failed"?"#ef4444":"#0284c7"}}>
                    [{l.status}]
                  </span>{" "}{l.stage}: {l.message}
                </div>
              ))}

              {/* High risk flags */}
              {highRisks.length > 0 && (
                <>
                  <div style={{color:"#475569",fontSize:"0.7rem",
                    marginTop:"0.8rem",marginBottom:"0.5rem"}}>HIGH RISK FLAGS</div>
                  {highRisks.map((f,i) => (
                    <div key={i} style={{background:"#1a0a0a",border:"1px solid #7f1d1d",
                      borderRadius:"6px",padding:"0.5rem 0.7rem",marginBottom:"0.4rem",
                      fontSize:"0.78rem"}}>
                      <span style={{color:"#ef4444",fontWeight:600}}>{f.flag_type}</span>
                      <span style={{color:"#94a3b8",marginLeft:"0.5rem"}}>{f.description}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>

        <button onClick={() => onDelete(c.id)} style={{
          background:"none",border:"1px solid #7f1d1d",color:"#ef4444",
          borderRadius:"6px",padding:"0.3rem 0.7rem",cursor:"pointer",
          fontSize:"0.75rem",marginLeft:"1rem",fontFamily:"'Inter',sans-serif",flexShrink:0}}>
          Delete
        </button>
      </div>
    </div>
  )
}

export default function Contracts() {
  const [contracts, setContracts] = useState([])
  const [drag,      setDrag]      = useState(false)
  const [uploading, setUploading] = useState(false)
  const [msg,       setMsg]       = useState("")
  const fileRef = useRef()

  const fetchContracts = async () => {
    try {
      const r = await fetch(`${API}/contracts`)
      setContracts(await r.json())
    } catch {}
  }

  useEffect(() => {
    fetchContracts()
    const iv = setInterval(fetchContracts, 3000)
    return () => clearInterval(iv)
  }, [])

  const upload = async (file) => {
    if (!file) return
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase()
    if (![".pdf",".txt",".md"].includes(ext)) {
      setMsg("❌ Only PDF, TXT, MD supported"); return
    }
    setUploading(true)
    setMsg(`Uploading ${file.name}…`)
    const form = new FormData()
    form.append("file", file)
    try {
      const r = await fetch(`${API}/contracts/upload`, { method:"POST", body:form })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || "Upload failed")
      setMsg(`✓ ${file.name} uploaded — processing in background…`)
      fetchContracts()
    } catch(e) { setMsg(`❌ ${e.message}`) }
    finally { setUploading(false) }
  }

  const del = async (id) => {
    if (!window.confirm("Delete contract and all graph data?")) return
    await fetch(`${API}/contracts/${id}`, { method:"DELETE" })
    fetchContracts()
  }

  const stats = {
    total: contracts.length,
    complete: contracts.filter(c=>c.status==="complete").length,
    processing: contracts.filter(c=>c.status==="processing").length,
    high_risk: contracts.filter(c=>c.risk_score>0.5).length,
  }

  return (
    <div>
      <div style={{marginBottom:"1.5rem"}}>
        <div style={{fontSize:"1.5rem",fontWeight:700,color:"#f1f5f9",marginBottom:"0.3rem"}}>
          Contracts
        </div>
        <div style={{color:"#64748b",fontSize:"0.85rem"}}>
          Upload contracts — Celery processes them async, building the knowledge graph
        </div>
      </div>

      {/* Drop zone */}
      <div
        style={{border:`2px dashed ${drag?"#f59e0b":"#1e2433"}`,borderRadius:"12px",
          padding:"2.5rem 2rem",textAlign:"center",cursor:"pointer",
          background:drag?"#1a0e00":"#0d1117",transition:"all 0.2s",marginBottom:"1.5rem"}}
        onClick={() => fileRef.current.click()}
        onDragOver={e=>{e.preventDefault();setDrag(true)}}
        onDragLeave={()=>setDrag(false)}
        onDrop={e=>{e.preventDefault();setDrag(false);upload(e.dataTransfer.files[0])}}
      >
        <div style={{fontSize:"2rem",marginBottom:"0.6rem"}}>📂</div>
        <div style={{color:"#94a3b8",fontSize:"0.9rem"}}>
          {uploading ? "Uploading…" : "Drag & drop or click to upload"}
        </div>
        <div style={{color:"#475569",fontSize:"0.78rem",marginTop:"0.3rem"}}>
          .pdf · .txt · .md
        </div>
        <input ref={fileRef} type="file" accept=".pdf,.txt,.md"
          style={{display:"none"}} onChange={e=>upload(e.target.files[0])}/>
      </div>

      {msg && (
        <div style={{background:"#0d1117",border:"1px solid #1e2433",borderRadius:"8px",
          padding:"0.8rem 1rem",color:msg.startsWith("❌")?"#ef4444":"#22c55e",
          fontSize:"0.85rem",marginBottom:"1.2rem"}}>{msg}</div>
      )}

      {/* Stats bar */}
      {contracts.length > 0 && (
        <div style={{display:"flex",gap:"0.8rem",marginBottom:"1.2rem",flexWrap:"wrap"}}>
          {[
            {label:"Total",      value:stats.total,      color:"#94a3b8"},
            {label:"Complete",   value:stats.complete,   color:"#22c55e"},
            {label:"Processing", value:stats.processing, color:"#0284c7"},
            {label:"High Risk",  value:stats.high_risk,  color:"#ef4444"},
          ].map(s=>(
            <div key={s.label} style={{background:"#0d1117",border:"1px solid #1e2433",
              borderRadius:"8px",padding:"0.6rem 1.2rem",textAlign:"center"}}>
              <div style={{color:s.color,fontSize:"1.3rem",fontWeight:700}}>{s.value}</div>
              <div style={{color:"#475569",fontSize:"0.7rem"}}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{color:"#334155",fontSize:"0.78rem",marginBottom:"0.8rem"}}>
        CONTRACTS ({contracts.length})
      </div>

      {contracts.length === 0 ? (
        <div style={{color:"#334155",textAlign:"center",padding:"3rem",
          border:"1px dashed #1e2433",borderRadius:"10px"}}>
          No contracts yet — upload one above
        </div>
      ) : (
        contracts.map(c => <ContractCard key={c.id} c={c} onDelete={del}/>)
      )}
    </div>
  )
}
