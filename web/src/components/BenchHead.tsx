import { ArrowLeft } from 'lucide-react'

export function BenchHead({title,subtitle,back,compact=false}:{title:string;subtitle:string;back:()=>void;compact?:boolean}){
  return <header className={`workbench-head${compact?' compact':''}`}>
    <button className="back-btn" onClick={back}><ArrowLeft size={15}/>返回</button>
    <div><p className="eyebrow">{title}</p><h1>{subtitle}</h1></div>
    <span className="a4-state">固定 A4</span>
  </header>
}
