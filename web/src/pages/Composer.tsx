import { useEffect, useState } from 'react'
import { ChevronRight, CircleAlert, LayoutTemplate } from 'lucide-react'
import { patch, post } from '../api'
import { BenchHead } from '../components/BenchHead'
import { Canvas } from '../components/Canvas'
import { Picker } from '../components/Picker'
import { StageToolbar } from '../components/StageToolbar'
import { TemplateModal } from '../components/TemplateModal'
import { useLoad } from '../components/ui'
import { factCategories, labels, layoutBudget, layoutMainIds, streamItems, type Content, type Fact, type Profile } from '../lib/resume'
import type { TemplateDescriptor } from '../lib/templates'

export function Composer({id,profile,back,open,error}:{id:number;profile:Profile;back:()=>void;open:(id:number)=>void;error:(s:string)=>void}){
  const linked=useLoad<{selection:Record<string,number[]>;preview:Content;template?:TemplateDescriptor}>(`/api/linked-resumes/${id}`,{selection:{},preview:{sections:[]}})
  const facts=useLoad<Fact[]>('/api/facts',[])
  const templates=useLoad<TemplateDescriptor[]>('/api/templates',[])
  const [sectionId,setSectionId]=useState<string|null>(null)
  const [convertLoading,setConvertLoading]=useState(false)
  const [templateOpen,setTemplateOpen]=useState(false)
  const [zoom,setZoom]=useState(1)
  const [compact,setCompact]=useState(false)
  useEffect(()=>{const h=()=>setCompact(window.scrollY>150);window.addEventListener('scroll',h);return()=>window.removeEventListener('scroll',h)},[])
  const toggle=async(fid:number)=>{if(!sectionId)return;const old=linked.data.selection[sectionId]||[],next={...linked.data.selection,[sectionId]:old.includes(fid)?old.filter(x=>x!==fid):[...old,fid]};try{await patch(`/api/linked-resumes/${id}`,{selection:next});linked.reload()}catch(e){error((e as Error).message)}}
  const chooseTemplate=async(tvId:number)=>{try{await patch(`/api/linked-resumes/${id}`,{template_version_id:tvId});setTemplateOpen(false);linked.reload()}catch(e){error((e as Error).message)}}
  const convert=async()=>{if(convertLoading)return;setConvertLoading(true);try{open((await post<{resume_id:number}>(`/api/linked-resumes/${id}/convert`)).resume_id)}catch(e){error((e as Error).message)}finally{setConvertLoading(false)}}
  const missing=Object.values(linked.data.selection).flat().filter(fid=>!facts.data.some(f=>f.id===fid)).length
  const layout=linked.data.template?.layout||'sidebar'
  return <main className="workbench">
    <BenchHead title="临时简历" subtitle={`${profile.name} · ${profile.core_requirements.join('、')||'未设置核心要求'}`} back={back} compact={compact}/>
    {missing>0&&<div className="warning-banner compact"><CircleAlert size={17}/><div><b>{missing} 条已选资料不可用</b><span>它们已归档或被删除，不会出现在预览中；点击对应栏目可重新选择。</span></div></div>}
    <p className="canvas-hint">初始画布只显示栏目；点击栏目选择事实资料，内容增加后自动续为 A4 页面。转换正式简历时会使用当前所选模板。</p>
    <StageToolbar zoom={zoom} setZoom={setZoom} pageCount={streamItems(linked.data.preview,layoutMainIds(layout),layoutBudget(layout),false).length}/>
    <div className="stage-zoom" style={{zoom}}><Canvas content={linked.data.preview} mode="select" template={linked.data.template} select={id=>factCategories(id).length&&setSectionId(id)}/></div>
    <footer className="actionbar">
      <button className="button" onClick={back}>退出选择</button>
      <button className="button" onClick={()=>setTemplateOpen(true)}><LayoutTemplate size={15}/>模板 · {linked.data.template?.name||'默认模板'}</button>
      <button className="button primary" disabled={linked.loading||convertLoading} onClick={convert}>{convertLoading?'正在生成…':'生成格式化简历'} {!convertLoading&&<ChevronRight size={16}/>}</button>
    </footer>
    {sectionId&&<Picker title={labels[sectionId]} facts={facts.data.filter(f=>factCategories(sectionId).includes(f.category))} chosen={linked.data.selection[sectionId]||[]} toggle={toggle} close={()=>setSectionId(null)}/>}
    {templateOpen&&<TemplateModal current={linked.data.template?.template_version_id} templates={templates.data} loading={templates.loading} onChoose={chooseTemplate} close={()=>setTemplateOpen(false)}/>}
  </main>
}
