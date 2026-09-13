import { useEffect, useState, type ReactNode } from 'react'
import { ArrowLeft, LoaderCircle, X } from 'lucide-react'
import { api } from '../api'

export function useLoad<T>(path:string, initial:T){ const [data,setData]=useState<T>(initial); const [loading,setLoading]=useState(true); const [tick,setTick]=useState(0); useEffect(()=>{let live=true;if(!path)return;setLoading(true);api<T>(path).then(v=>live&&setData(v)).catch(()=>{}).finally(()=>live&&setLoading(false));return()=>{live=false}},[path,tick]); return {data,loading,reload:()=>setTick(v=>v+1)} }

export function Field({label,hint,children}:{label:string;hint?:string;children:ReactNode}){return <label className="field"><b>{label}</b>{hint&&<small>{hint}</small>}{children}</label>}

export function Title({crumb,title,desc,back,action}:{crumb:string;title:string;desc:string;back:()=>void;action?:ReactNode}){return <><div className="breadcrumb"><button className="back-btn" onClick={back}><ArrowLeft size={15}/>返回概览</button><span>/ {crumb}</span></div><header className="page-title"><div><p className="eyebrow">{crumb}</p><h1>{title}</h1><p>{desc}</p></div>{action}</header></>}

export function Modal({title,close,children,className}:{title:string;close:()=>void;children:ReactNode;className?:string}){
  useEffect(()=>{const h=(e:KeyboardEvent)=>{if(e.key==='Escape')close()};window.addEventListener('keydown',h);return()=>window.removeEventListener('keydown',h)},[close])
  return <div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)close()}}><section className={`modal${className?` ${className}`:''}`}><header><h2>{title}</h2><button className="icon-btn" onClick={close}><X size={18}/></button></header><div className="modal-body">{children}</div></section></div>
}

export function Loading(){return <div className="loading"><LoaderCircle size={18}/>正在加载</div>}
export function Empty({icon:Icon,title,body}:{icon:any;title:string;body:string}){return <div className="empty"><Icon size={25}/><h3>{title}</h3><p>{body}</p></div>}
