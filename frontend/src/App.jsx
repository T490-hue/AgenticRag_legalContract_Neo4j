import { useState } from "react"
import Query from "./pages/Query"
import Contracts from "./pages/Contracts"
import Graph from "./pages/Graph"
import Risks from "./pages/Risks"
import History from "./pages/History"
import Stats from "./pages/Stats"

const NAV = [
  { id:"query",     label:"🔍 Query" },
  { id:"contracts", label:"📄 Contracts" },
  { id:"graph",     label:"🕸 Graph" },
  { id:"risks",     label:"⚠ Risks" },
  { id:"history",   label:"🕐 History" },
  { id:"stats",     label:"📊 Stats" },
]

export default function App() {
  const [page, setPage] = useState("query")
  const pages = { query:<Query/>, contracts:<Contracts/>, graph:<Graph/>,
                  risks:<Risks/>, history:<History/>, stats:<Stats/> }

  return (
    <div style={{minHeight:"100vh",background:"#080b12",color:"#e2e8f0",
      fontFamily:"'Inter',sans-serif"}}>
      <nav style={{background:"#0d1117",borderBottom:"1px solid #1e2433",
        padding:"0 2rem",display:"flex",alignItems:"center",
        gap:"1.5rem",height:"56px",position:"sticky",top:0,zIndex:100}}>
        <span style={{fontFamily:"'JetBrains Mono',monospace",fontSize:"0.85rem",
          color:"#f59e0b",fontWeight:700,marginRight:"0.5rem",letterSpacing:"0.05em"}}>
          ⚖ LegalGraphRAG
        </span>
        {NAV.map(n => (
          <button key={n.id} onClick={() => setPage(n.id)} style={{
            background:"none",border:"none",
            color: page===n.id ? "#f59e0b" : "#64748b",
            cursor:"pointer",fontSize:"0.83rem",padding:"0.4rem 0.6rem",
            borderRadius:"6px",fontFamily:"'Inter',sans-serif",
            fontWeight: page===n.id ? 600 : 400,
            borderBottom: page===n.id ? "2px solid #f59e0b" : "2px solid transparent",
          }}>
            {n.label}
          </button>
        ))}
      </nav>
      <main style={{maxWidth:"1400px",margin:"0 auto",padding:"2rem"}}>
        {pages[page]}
      </main>
    </div>
  )
}
