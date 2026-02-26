import { useEffect, useRef, useState } from "react"
const API = "http://localhost:8000"

const NODE_COLORS = {
  Contract:     "#f59e0b",
  Party:        "#0284c7",
  Clause:       "#7c3aed",
  Jurisdiction: "#059669",
  RiskFlag:     "#ef4444",
  Obligation:   "#64748b",
}

const REL_COLORS = {
  HAS_PARTY:      "#0284c7",
  PARTY_TO:       "#0284c7",
  CONTAINS:       "#7c3aed",
  GOVERNED_BY:    "#059669",
  CONFLICTS_WITH: "#ef4444",
  RELATED_TO:     "#f59e0b",
  HAS_RISK:       "#ef4444",
  IMPOSES:        "#64748b",
}

export default function Graph() {
  const svgRef = useRef()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [tip,     setTip]     = useState(null)
  const [filter,  setFilter]  = useState("all")

  useEffect(() => {
    fetch(`${API}/graph/entities?limit=120`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!data || !svgRef.current) return
    import("d3").then(d3 => {
      const el     = svgRef.current
      const width  = el.clientWidth  || 900
      const height = el.clientHeight || 540

      d3.select(el).selectAll("*").remove()
      const svg = d3.select(el)
      const g   = svg.append("g")

      svg.call(d3.zoom().scaleExtent([0.2, 4])
        .on("zoom", e => g.attr("transform", e.transform)))

      // Filter nodes
      const nodes = data.nodes
        .filter(n => filter === "all" || n.type === filter)
        .map(n => ({ ...n, id_str: String(n.id) }))

      const nodeSet = new Set(nodes.map(n => n.id_str))
      const edges = data.edges
        .map(e => ({ ...e, source: String(e.source), target: String(e.target) }))
        .filter(e => nodeSet.has(e.source) && nodeSet.has(e.target))

      const sim = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(edges).id(d => d.id_str).distance(100))
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width/2, height/2))
        .force("collision", d3.forceCollide(22))

      // Arrow markers
      const rels = [...new Set(edges.map(e => e.relation))]
      svg.append("defs").selectAll("marker")
        .data(rels).join("marker")
        .attr("id", d => `arrow-${d}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 20).attr("refY", 0)
        .attr("markerWidth", 6).attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", d => REL_COLORS[d] || "#1e2433")

      const link = g.append("g").selectAll("line").data(edges).join("line")
        .attr("stroke", d => REL_COLORS[d.relation] || "#1e2433")
        .attr("stroke-width", d => d.relation === "CONFLICTS_WITH" ? 2.5 : 1.2)
        .attr("stroke-opacity", 0.6)
        .attr("stroke-dasharray", d => d.relation === "CONFLICTS_WITH" ? "4,3" : null)
        .attr("marker-end", d => `url(#arrow-${d.relation})`)

      const linkLabel = g.append("g").selectAll("text").data(edges).join("text")
        .attr("fill", d => REL_COLORS[d.relation] || "#334155")
        .attr("font-size", "7px")
        .attr("text-anchor", "middle")
        .attr("opacity", 0.7)
        .text(d => d.relation)

      const node = g.append("g").selectAll("g").data(nodes).join("g")
        .attr("cursor", "pointer")
        .call(d3.drag()
          .on("start", (e,d) => { if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y })
          .on("drag",  (e,d) => { d.fx=e.x; d.fy=e.y })
          .on("end",   (e,d) => { if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null })
        )
        .on("mouseover", (e,d) => setTip({ x:e.offsetX+12, y:e.offsetY-8,
          label:d.label||d.name, type:d.type, risk:d.severity||d.risk_level }))
        .on("mouseout", () => setTip(null))

      node.append("circle")
        .attr("r", d => d.type==="Contract" ? 12 : d.type==="Party" ? 9 : 7)
        .attr("fill", d => NODE_COLORS[d.type] || "#475569")
        .attr("stroke", "#080b12").attr("stroke-width", 2)

      // RiskFlag pulsing ring
      node.filter(d => d.type==="RiskFlag").append("circle")
        .attr("r", 11).attr("fill","none")
        .attr("stroke","#ef4444").attr("stroke-width",1.5)
        .attr("opacity", 0.4)

      node.append("text")
        .attr("dx", 14).attr("dy", 4)
        .attr("fill","#64748b").attr("font-size","9px")
        .text(d => (d.label||"").slice(0,22))

      sim.on("tick", () => {
        link
          .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x).attr("y2", d => d.target.y)
        linkLabel
          .attr("x", d => ((d.source.x||0)+(d.target.x||0))/2)
          .attr("y", d => ((d.source.y||0)+(d.target.y||0))/2)
        node.attr("transform", d => `translate(${d.x},${d.y})`)
      })
    })
  }, [data, filter])

  const nodeTypes = data ? [...new Set(data.nodes.map(n => n.type))] : []

  return (
    <div>
      <div style={{marginBottom:"1rem"}}>
        <div style={{fontSize:"1.5rem",fontWeight:700,color:"#f1f5f9",marginBottom:"0.3rem"}}>
          Knowledge Graph
        </div>
        <div style={{color:"#64748b",fontSize:"0.85rem"}}>
          Contracts · Parties · Clauses · Risk Flags — drag nodes, scroll to zoom
        </div>
      </div>

      {/* Node type filters */}
      <div style={{display:"flex",gap:"0.5rem",marginBottom:"1rem",flexWrap:"wrap"}}>
        {["all",...nodeTypes].map(t => (
          <button key={t} onClick={()=>setFilter(t)} style={{
            background: filter===t ? "#1e2433" : "none",
            border:`1px solid ${filter===t ? (NODE_COLORS[t]||"#334155") : "#1e2433"}`,
            color: filter===t ? (NODE_COLORS[t]||"#f1f5f9") : "#64748b",
            borderRadius:"8px",padding:"0.3rem 0.8rem",cursor:"pointer",
            fontSize:"0.78rem",fontFamily:"'Inter',sans-serif",
          }}>{t}</button>
        ))}
      </div>

      <div style={{background:"#0d1117",border:"1px solid #1e2433",
        borderRadius:"12px",overflow:"hidden",position:"relative"}}>

        {loading && (
          <div style={{textAlign:"center",padding:"4rem",color:"#475569"}}>
            Loading graph…
          </div>
        )}
        {!loading && (!data || data.nodes.length===0) && (
          <div style={{textAlign:"center",padding:"4rem",color:"#334155"}}>
            No entities yet — upload contracts first
          </div>
        )}

        <svg ref={svgRef} width="100%" height="560" style={{display:"block"}}/>

        {/* Legend */}
        {data && data.nodes.length > 0 && (
          <div style={{position:"absolute",top:"1rem",left:"1rem",
            background:"#080b12cc",border:"1px solid #1e2433",
            borderRadius:"8px",padding:"0.8rem"}}>
            {Object.entries(NODE_COLORS).map(([type,color])=>(
              <div key={type} style={{display:"flex",alignItems:"center",
                gap:"0.5rem",fontSize:"0.72rem",color:"#94a3b8",marginBottom:"0.3rem"}}>
                <div style={{width:10,height:10,borderRadius:"50%",
                  background:color,flexShrink:0}}/>
                {type}
              </div>
            ))}
            <div style={{borderTop:"1px solid #1e2433",marginTop:"0.5rem",
              paddingTop:"0.5rem",fontSize:"0.68rem",color:"#475569"}}>
              <div style={{color:"#ef4444",marginBottom:"0.2rem"}}>
                ╌╌ CONFLICTS_WITH
              </div>
              Drag to rearrange
            </div>
          </div>
        )}

        {tip && (
          <div style={{position:"absolute",top:tip.y,left:tip.x,
            background:"#0d1117",border:"1px solid #1e2433",
            borderRadius:"6px",padding:"0.5rem 0.8rem",
            fontSize:"0.78rem",color:"#e2e8f0",
            pointerEvents:"none",zIndex:20,maxWidth:"200px"}}>
            <div style={{color:NODE_COLORS[tip.type]||"#94a3b8",
              fontSize:"0.65rem",marginBottom:"0.2rem"}}>{tip.type}</div>
            <div>{tip.label}</div>
            {tip.risk && (
              <div style={{color:tip.risk==="high"?"#ef4444":"#f59e0b",
                fontSize:"0.7rem",marginTop:"0.2rem"}}>
                risk: {tip.risk}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
