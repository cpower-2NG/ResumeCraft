import { useState } from 'react'
import { ChevronRight, Plus } from 'lucide-react'
import { patch, post } from '../api'
import { Empty, Field, Loading, Modal, Title, useLoad } from '../components/ui'
import { date, type Profile } from '../lib/resume'

export function Profiles({back,create,open,error}:{back:()=>void;create:(p:Profile)=>void;open:(id:number)=>void;error:(s:string)=>void}){
  const data=useLoad<Profile[]>('/api/requirement-profiles',[]),[edit,setEdit]=useState<Profile|null>(null)
  return <main className="page"><Title crumb="岗位画像" title="岗位画像" desc="先整理岗位要求，再选择最适合呈现的事实资料。" back={back} action={<button className="button primary" onClick={()=>setEdit({id:0,name:'',role_direction:'',core_requirements:[],resume_strategy:'',raw_jd:'',status:'active',updated_at:''})}><Plus size={16}/>新建岗位画像</button>}/>
    <section className="profile-list">{data.loading?<Loading/>:data.data.map(p=><article className="profile-card" key={p.id}><div><p className="eyebrow">{p.role_direction||'岗位方向待补充'}</p><h2>{p.name}</h2><div className="chips">{p.core_requirements.map(x=><span key={x}>{x}</span>)}</div><p>{p.resume_strategy||'尚未设置简历强调方向。'}</p><small className="profile-meta">{date(p.updated_at)} · {p.opportunity_count||0} 个招聘机会{p.active_resume_id?' · 已关联正式简历':''}</small></div><div className="card-actions"><button className="button" onClick={()=>setEdit(p)}>编辑</button>{p.active_resume_id?<><button className="button" onClick={async()=>{try{const r=await post<{resume_id:number}>(`/api/resumes/${p.active_resume_id}/fork`);open(r.resume_id)}catch(e){error((e as Error).message)}}}>新简历身份</button><button className="button primary" onClick={()=>open(p.active_resume_id!)}>打开正式简历 <ChevronRight size={15}/></button></>:<button className="button primary" onClick={()=>create(p)}>创建临时简历 <ChevronRight size={15}/></button>}</div></article>)}</section>
    {edit&&<ProfileModal profile={edit.id?edit:undefined} close={()=>setEdit(null)} done={()=>{setEdit(null);data.reload()}} create={create} error={error}/>}
  </main>
}

function ProfileModal({profile,close,done,create,error}:{profile?:Profile;close:()=>void;done:()=>void;create:(p:Profile)=>void;error:(s:string)=>void}){
  const[name,setName]=useState(profile?.name||''),[role,setRole]=useState(profile?.role_direction||''),[req,setReq]=useState(profile?.core_requirements.join('、')||''),[strategy,setStrategy]=useState(profile?.resume_strategy||''),[jd,setJd]=useState(profile?.raw_jd||'')
  const save=async(start=false)=>{try{const body={name,role_direction:role,core_requirements:req.split(/[、，,]/).map(x=>x.trim()).filter(Boolean),resume_strategy:strategy,raw_jd:jd};const item=profile?await patch<Profile>(`/api/requirement-profiles/${profile.id}`,body):await post<Profile>('/api/requirement-profiles',body);done();if(start)create(item)}catch(e){error((e as Error).message)}}
  return <Modal title={profile?'编辑岗位画像':'新建岗位画像'} close={close}><Field label="画像名称"><input autoFocus value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="岗位方向"><input value={role} onChange={e=>setRole(e.target.value)}/></Field><Field label="核心技术要求" hint="使用顿号或逗号分隔多条要求。"><input value={req} onChange={e=>setReq(e.target.value)} placeholder="Python、ROS2、数据标注"/></Field><Field label="简历强调方向"><textarea value={strategy} onChange={e=>setStrategy(e.target.value)}/></Field><details><summary>原始 JD 与来源</summary><textarea value={jd} onChange={e=>setJd(e.target.value)}/></details><div className="modal-actions"><button className="button" onClick={close}>取消</button><button className="button" disabled={!name.trim()} onClick={()=>save(false)}>保存画像</button><button className="button primary" disabled={!name.trim()} onClick={()=>save(true)}>保存并选择资料</button></div></Modal>
}
