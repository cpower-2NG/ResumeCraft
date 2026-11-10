import { useState } from 'react'
import { ArchiveRestore, ChevronRight, CircleAlert, FilePenLine, LayoutTemplate, Plus, Trash2 } from 'lucide-react'
import { post } from '../api'
import { Empty, Loading, Title, useLoad } from '../components/ui'
import { date, type Pending, type Resume } from '../lib/resume'

export function Resumes({back,open,create,pending,library}:{back:()=>void;open:(id:number)=>void;create:()=>void;pending:Pending[];library:()=>void}){
  const data=useLoad<Resume[]>('/api/resumes',[]),recycled=useLoad<Resume[]>('/api/resumes?status=recycled',[]),[recycle,setRecycle]=useState(false)
  const rows=(recycle?recycled.data:data.data).filter(r=>recycle?r.status==='recycled':r.status==='active')
  const restore=async(id:number)=>{try{await post(`/api/resumes/${id}/restore`);data.reload();recycled.reload()}catch(e){console.error(e)}}
  return <main className="page"><Title crumb="ResumeCraft" title={recycle?'简历回收站':'正式简历'} desc={recycle?'已删除的正式简历仍可查看和恢复。':'同一岗位画像最多保留一份 active 正式简历；每次正式保存追加不可变版本。'} back={back} action={<div className="header-actions">{!recycle&&<><button className="button" onClick={library}><LayoutTemplate size={15}/>模板库</button><button className="button primary" onClick={create}><Plus size={16}/>创建临时简历</button></>}<button className="button" onClick={()=>setRecycle(!recycle)}>{recycle?<ArchiveRestore size={15}/>:<Trash2 size={15}/>} {recycle?'返回正式简历':'回收站'}</button></div>}/>
    {!recycle&&pending.length>0&&<div className="warning-banner"><CircleAlert size={18}/><div><b>{pending.length} 项来源变化待处理</b><span>进入简历后，变化会直接标记在受影响的条目上。</span></div></div>}
    {!recycle&&rows.some(r=>r.content_state!=='clean'||r.warnings>0||r.evidence_sync_state!=='clean'||r.baseline_state==='stale')&&(()=>{const r=rows.find(x=>x.content_state!=='clean'||x.warnings>0||x.evidence_sync_state!=='clean'||x.baseline_state==='stale')!;const state=r.warnings?`${r.warnings} 项来源变化待处理`:r.evidence_sync_state!=='clean'?'证据同步待合并':r.baseline_state==='stale'?'工作副本基线已过期':'工作副本有未保存修改';return <button className="resume-row continue-card" onClick={()=>open(r.id)}><CircleAlert size={18}/><span><b>继续上次工作</b><small>{r.display_name} · {state}</small></span><em>继续 <ChevronRight size={15}/></em></button>})()}
    <section className="list-panel">{(data.loading||recycled.loading)?<Loading/>:rows.length?rows.map(r=><article className="resume-row" key={r.id} onClick={()=>open(r.id)}><FilePenLine size={18}/><span><b>{r.display_name}</b><small>{r.current_version?`v${r.current_version}`:'未保存'} · {date(r.updated_at)}{r.status==='recycled'?' · 已回收':''}</small></span>{r.status==='recycled'?<button className="button" onClick={e=>{e.stopPropagation();restore(r.id)}}><ArchiveRestore size={14}/>恢复</button>:<em>{r.warnings?`${r.warnings} 项来源变化`:'打开工作台'} <ChevronRight size={15}/></em>}</article>):<Empty icon={recycle?Trash2:FilePenLine} title={recycle?'回收站为空':'还没有正式简历'} body={recycle?'已删除的正式简历会保留在这里。':'从岗位画像创建一份临时简历开始。'}/>}</section></main>
}
