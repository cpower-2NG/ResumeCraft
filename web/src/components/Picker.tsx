import { useState } from 'react'
import { Search, X } from 'lucide-react'
import type { Fact } from '../lib/resume'
import { brief } from '../lib/resume'

export function Picker({title,facts,chosen,toggle,close}:{title:string;facts:Fact[];chosen:number[];toggle:(id:number)=>void;close:()=>void}){
  const[q,setQ]=useState('')
  const shown=facts.filter(f=>`${f.title} ${brief(f)}`.toLowerCase().includes(q.toLowerCase()))
  return <div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)close()}}>
    <section className="selection-modal">
      <header><div><p className="eyebrow">选择事实资料</p><h2>{title}</h2></div><button className="icon-btn" onClick={close}><X size={18}/></button></header>
      <div className="filterbar"><Search size={16}/><input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="搜索资料名称或详情"/></div>
      <div className="selection-list">{shown.map(f=><label key={f.id}><input type="checkbox" checked={chosen.includes(f.id)} onChange={()=>toggle(f.id)}/><span><b>{f.title}</b><small>{brief(f)}</small></span></label>)}</div>
      <footer><span>已选择 {chosen.length} 条</span><button className="button primary" onClick={close}>完成选择</button></footer>
    </section>
  </div>
}
