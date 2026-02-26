import { useState, useEffect } from "react"
const API = "http://localhost:8000"

const NODE_COLORS = {
  Contract:"#f59e0b", Party:"#0284c7", Clause:"#7c3aed",
  Jurisdiction:"#059669", RiskFlag:"#ef4444", Chunk:"#475569",
}
const REL_COLORS = {
  HAS_PARTY:"#0284c7", PARTY_TO:"#0284c7", CONTAINS:"#7c3aed",
  GOVERNED_BY:"#059669", CONFLICTS_WITH:"#ef4444",
  RELATED_TO:"#f59e0b", SIMILAR_TO:"#334155", NEXT:"#1e2433",
  HAS_CHUNK:"#334155", HAS_RISK:"#ef4444", IMPOSES:"#64748b",
}

export default function Stats() {
  const [stats,   setStats]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    const load = () =>
      fetch(`${API}/graph/stats`).then(r=>r.json()).then(d=>{setStats(d);setLoading(false)}).catch(()=>{})
    load()
    const iv = setInterval(load, 10000)
    return ()=>clearInterval(iv)
  },[])

  if (loading) return <div style={{color:"#475569",textAlign:"center",padding:"4rem"}}>Loading…</div>
  if (!stats) return null

  const nodes = stats.neo4j?.nodes || {}
  const rels  = stats.neo4j?.relationships || {}
  const maxN  = Math.max(...Object.values(nodes),1)
  const maxR  = Math.max(...Object.values(rels),1)

  const Bar = ({val,max,color}) => (
    <div style={{flex:1,height:"4px",background:"#1e2433",borderRadius:"2px",marginBottom:"0.8rem"}}>
      <div style={{width:`${Math.round((val/max)*100)}%`,height:"100%",
        background:color,borderRadius:"2px",transition:"width 0.5s"}}/>
    </div>
  )

  return (
    <div>
      <div style={{marginBottom:"1.5rem"}}>
        <div style={{fontSize:"1.5rem",fontWeight:700,color:"#f1f5f9",marginBottom:"0.3rem"}}>
          System Statistics
        </div>
        <div style={{color:"#64748b",fontSize:"0.85rem"}}>
          Live counts from Neo4j and PostgreSQL — refreshes every 10s
        </div>
      </div>

      {/* Summary */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",
        gap:"1rem",marginBottom:"1.5rem"}}>
        {[
          {label:"Contracts", value:stats.postgres?.contracts||0, color:"#f59e0b"},
          {label:"Queries",   value:stats.postgres?.queries||0,   color:"#0284c7"},
          {label:"Risk Flags",value:stats.postgres?.risks||0,     color:"#ef4444"},
          {label:"Chunks",    value:nodes.Chunk||0,               color:"#7c3aed"},
        ].map(s=>(
          <div key={s.label} style={{background:"#0d1117",
            border:`1px solid ${s.color}30`,borderRadius:"10px",
            padding:"1rem",textAlign:"center"}}>
            <div style={{fontSize:"2rem",fontWeight:700,color:s.color,
              fontFamily:"'JetBrains Mono',monospace"}}>
              {s.value.toLocaleString()}
            </div>
            <div style={{color:"#475569",fontSize:"0.78rem"}}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:"1.2rem"}}>
        {/* Nodes */}
        <div style={{background:"#0d1117",border:"1px solid #1e2433",
          borderRadius:"12px",padding:"1.4rem"}}>
          <div style={{fontSize:"0.72rem",fontWeight:700,color:"#475569",
            letterSpacing:"0.1em",marginBottom:"1rem",
            fontFamily:"'JetBrains Mono',monospace"}}>NEO4J NODES</div>
          {Object.entries(nodes).filter(([l])=>l!=="null").map(([label,count])=>(
            <div key={label}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:"0.2rem"}}>
                <span style={{color:"#94a3b8",fontSize:"0.85rem"}}>{label}</span>
                <span style={{color:NODE_COLORS[label]||"#94a3b8",
                  fontFamily:"'JetBrains Mono',monospace",fontWeight:600}}>
                  {count.toLocaleString()}
                </span>
              </div>
              <Bar val={count} max={maxN} color={NODE_COLORS[label]||"#475569"}/>
            </div>
          ))}
        </div>

        {/* Relationships */}
        <div style={{background:"#0d1117",border:"1px solid #1e2433",
          borderRadius:"12px",padding:"1.4rem"}}>
          <div style={{fontSize:"0.72rem",fontWeight:700,color:"#475569",
            letterSpacing:"0.1em",marginBottom:"1rem",
            fontFamily:"'JetBrains Mono',monospace"}}>NEO4J RELATIONSHIPS</div>
          {Object.entries(rels).filter(([t])=>t!=="null").map(([type,count])=>(
            <div key={type}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:"0.2rem"}}>
                <span style={{color:"#94a3b8",fontSize:"0.82rem"}}>{type}</span>
                <span style={{color:REL_COLORS[type]||"#94a3b8",
                  fontFamily:"'JetBrains Mono',monospace",fontWeight:600}}>
                  {count.toLocaleString()}
                </span>
              </div>
              <Bar val={count} max={maxR} color={REL_COLORS[type]||"#475569"}/>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
