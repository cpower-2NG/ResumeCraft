import { BriefcaseBusiness, ChevronRight, FilePenLine, Library } from 'lucide-react'
import { useLoad } from '../components/ui'
import { date, type Resume } from '../lib/resume'

// 首页固定三个主要入口并列展示；简历工作台是主入口，以深色卡片突出。
// 模板从简历工作台/编辑器内进入，不作为首页独立模块。
const MODULES=[[FilePenLine,'简历工作台','在 A4 简历上直接工作','resumes',true],[Library,'资料库','按分类维护事实与证据','facts',false],[BriefcaseBusiness,'岗位画像','组织招聘要求和简历策略','profiles',false]] as const

export function Home({go,openResume}:{go:(p:any)=>void;openResume:(id:number)=>void}){
  const data=useLoad<{stats:Record<string,number>;recent_resumes:Resume[]}>('/api/overview',{stats:{facts:0,profiles:0,resumes:0,working_copies:0},recent_resumes:[]})
  return <main className="page home">
    <p className="eyebrow">PERSONAL RESUME SYSTEM</p>
    <h1>让经历沉淀为<br/><em>可持续维护的简历</em></h1>
    <p className="lead">资料保持真实中立，岗位决定表达重点，版本记录每次正式交付。</p>
    <section className="module-grid">{MODULES.map(([I,t,d,k,dark])=><button className={`module-card${dark?' dark':''}`} key={k} onClick={()=>go(k)}><I size={22}/><h2>{t}</h2><p>{d}</p><ChevronRight size={16}/></button>)}</section>
    <section className="stat-row">{[['事实资料',data.data.stats.facts],['岗位画像',data.data.stats.profiles],['正式简历',data.data.stats.resumes],['工作副本',data.data.stats.working_copies]].map(x=><div key={String(x[0])}><b>{x[1]}</b><span>{x[0]}</span></div>)}</section>
    {data.data.recent_resumes.length>0&&<section className="list-panel recent-panel">
      <div className="table-head"><span>近期正式简历</span><span></span></div>
      {data.data.recent_resumes.map(r=><button className="resume-row" key={r.id} onClick={()=>openResume(r.id)}><FilePenLine size={18}/><span><b>{r.display_name}</b><small>{r.profile_name} · {r.current_version?`v${r.current_version}`:'未保存'} · {date(r.updated_at)}</small></span><em>打开工作台 <ChevronRight size={15}/></em></button>)}
    </section>}
  </main>
}
