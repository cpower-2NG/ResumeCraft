import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react'
import { AlertTriangle, ArchiveRestore, ArrowLeft, BookOpen, BriefcaseBusiness, ChevronRight, CircleAlert, Download, FilePenLine, FileUp, History, LayoutTemplate, Library, LoaderCircle, Plus, Search, Trash2, X } from 'lucide-react'
import { api, del, patch, post, upload } from './api'

type CustomField = { key:string; label:string; value:string; displayable:boolean; sort_order:number }
type Fact = { id:number; category:string; title:string; content:Record<string,string>; details:Record<string,string>; custom_fields:CustomField[]; display_fields:string[]; tags:string[]; status:string; updated_at:string; evidence_count:number }
type Profile = { id:number; name:string; role_direction:string; core_requirements:string[]; resume_strategy:string; raw_jd:string; status:string; updated_at:string; active_resume_id?:number; opportunity_count?:number }
export type Block = { id:string; title:string; content:string; fields?:Record<string,string>; field_labels?:Record<string,string>; display_fields?:string[]; source_refs:number[]; origin:string; fragment_index?:number; continuation?:boolean }
type Section = { id:string; title:string; visibility:boolean; blocks:Block[] }
export type Content = { sections:Section[] }
type Resume = { id:number; display_name:string; profile_name:string; current_version:number; updated_at:string; dirty:boolean; warnings:number; status:string }
type Pending = { id:number; resume_id:number; fact_id:number; message:string; kind:string; created_at:string; affected:{section_id:string;block_id:string}[] }
type BlockRef = { sectionId:string; blockId:string; fragmentIndex:number }
type BlockMenu = BlockRef & { x:number; y:number }
type UpdateBlock = (sectionId:string, blockId:string, value:string, key?:'content'|'title'|'field', fieldKey?:string, fragmentIndex?:number)=>void
type SearchResult = { type:'fact'|'evidence'|'profile'|'opportunity'|'resume'; id:number; title:string; subtitle:string; status:string; updated_at:string; payload:any }

const labels:Record<string,string> = { basics:'基本信息', target:'求职目标', profile:'个人简介', education:'教育经历', experience:'项目与实践', skills:'技能', awards:'成果', links:'链接与作品集' }
const categories = ['basics','education','experience','skills','awards','links']
const fieldLabels:Record<string,string> = { name:'姓名', phone:'电话', email:'邮箱', city:'所在地', desired_city:'目标城市', birth_date:'出生日期', age:'年龄', hometown:'籍贯', status:'身份状态', graduation:'毕业时间', availability:'到岗安排', bio:'个人简介', school:'学校', major:'专业', degree:'学历', start_date:'入学时间', end_date:'毕业时间', period:'时间', gpa:'GPA', ranking:'专业排名', achievement:'成绩与成果', courses:'相关课程', kind:'经历类型', organization:'组织/公司', role:'角色', team_size:'团队规模', context:'背景/使用场景', work:'具体工作', tools:'工具与技术', outcome:'结果', challenge:'挑战', solution:'解决方案', public_note:'公开说明', skill_category:'技能分类', proficiency:'熟练程度', issuer:'颁发方', result:'结果', note:'说明', link_type:'链接类型', url:'地址', label:'显示名称' }
const searchTypeLabels:Record<string,string> = { fact:'事实资料', evidence:'证据', profile:'岗位画像', opportunity:'招聘机会', resume:'正式简历' }
const pendingKindLabels:Record<string,string> = { source_changed:'来源资料变化', source_recycled:'来源移入回收站' }
const date = (v?:string) => v ? new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium'}).format(new Date(v)) : '—'
const brief = (f:Fact) => Object.values(f.details || f.content || {}).filter(Boolean).slice(0,3).join(' · ') || '尚未补充详细信息'
const section = (content:Content,id:string):Section => content.sections.find(s=>s.id===id) || {id,title:labels[id],visibility:true,blocks:[]}
const sourceIdOf = (b:Block) => b.id.split('--fragment-')[0]
const factCategories = (id:string) => id === 'basics' || id === 'profile' ? ['basics'] : id === 'target' ? [] : [id]

export default function App(){
  const [page,setPage] = useState<'home'|'facts'|'profiles'|'resumes'|'compose'|'editor'|'templates'>('home')
  const [error,setError] = useState(''); const [profile,setProfile] = useState<Profile|null>(null); const [linked,setLinked] = useState<number|null>(null); const [resume,setResume] = useState<number|null>(null)
  const [focusFact,setFocusFact] = useState<Fact|null>(null)
  const [focusBlock,setFocusBlock] = useState<{sectionId:string;blockId:string}|null>(null)
  const [pendingOpen,setPendingOpen] = useState(false)
  const [insufficient,setInsufficient] = useState<Profile|null>(null)
  const pending = useLoad<Pending[]>('/api/pending-items',[])
  const startCompose = async (p:Profile) => { try { const r=await post<{id:number}>(`/api/linked-resumes?profile_id=${p.id}`); setProfile(p); setLinked(r.id); setPage('compose') } catch(e) { setError((e as Error).message) } }
  const create = async (p:Profile) => {
    try {
      const facts = await api<Fact[]>('/api/facts')
      if (facts.length < 3) { setInsufficient(p); return }
      await startCompose(p)
    } catch(e) { setError((e as Error).message) }
  }
  const openResume = (id:number) => { setResume(id); setPage('editor') }
  const openPending = (item:Pending) => {
    setPendingOpen(false)
    const target = item.affected[0]
    setFocusBlock(target ? {sectionId:target.section_id, blockId:target.block_id} : null)
    openResume(item.resume_id)
  }
  return <div className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={()=>setPage('home')}><span>R</span>ResumeCraft</button>
      <TopSearch go={setPage} openResume={openResume} setFocusFact={setFocusFact}/>
      <span className="topbar-spacer"/>
    </header>
    {error&&<div className="flash"><AlertTriangle size={16}/>{error}<button onClick={()=>setError('')}><X size={15}/></button></div>}
    {page==='home'&&<Home go={setPage} openResume={openResume}/>}
    {page==='facts'&&<Facts back={()=>setPage('home')} error={setError} focus={focusFact} onFocusHandled={()=>setFocusFact(null)}/>}
    {page==='profiles'&&<Profiles back={()=>setPage('home')} create={create} open={openResume} error={setError}/>}
    {page==='resumes'&&<Resumes back={()=>setPage('home')} open={openResume} create={()=>setPage('profiles')} pending={pending.data} library={()=>setPage('templates')}/>}
    {page==='compose'&&profile&&linked&&<Composer id={linked} profile={profile} back={()=>setPage('profiles')} open={openResume} error={setError}/>}
    {page==='editor'&&resume&&<Editor id={resume} back={()=>setPage('resumes')} error={setError} refresh={pending.reload} focusBlock={focusBlock} onFocusLocated={()=>setFocusBlock(null)}/>}
    {page==='templates'&&<TemplateLibrary back={()=>setPage('home')} go={setPage}/>}
    {pending.data.length>0&&<button className="pending-fab" onClick={()=>setPendingOpen(v=>!v)} title="待处理事项"><CircleAlert size={18}/><i>{pending.data.length}</i></button>}
    {pendingOpen&&<aside className="pending-panel">
      <header><h2>待处理事项</h2><button className="icon-btn" onClick={()=>setPendingOpen(false)}><X size={16}/></button></header>
      <div className="pending-body">
        {Object.keys(pendingKindLabels).map(kind=>{
          const rows=pending.data.filter(x=>x.kind===kind)
          if(!rows.length)return null
          return <div key={kind}>
            <p className="pending-group">{pendingKindLabels[kind]}</p>
            {rows.map(item=><button key={item.id} className="pending-row" onClick={()=>openPending(item)}><b>{item.message}</b><small>{date(item.created_at)} · 点击定位受影响条目</small></button>)}
          </div>
        })}
      </div>
    </aside>}
    {insufficient&&<Modal title="资料偏少" close={()=>setInsufficient(null)}>
      <p className="modal-note">当前资料库只有少量事实资料。可以先去资料库补充，也可以继续制作——简历中会留出空缺栏目，之后再补。</p>
      <div className="modal-actions">
        <button className="button" onClick={()=>{const p=insufficient;setInsufficient(null);setPage('facts')}}>去资料库补充</button>
        <button className="button primary" onClick={()=>{const p=insufficient;setInsufficient(null);startCompose(p)}}>继续制作</button>
      </div>
    </Modal>}
  </div>
}

function useLoad<T>(path:string, initial:T){ const [data,setData]=useState<T>(initial); const [loading,setLoading]=useState(true); const [tick,setTick]=useState(0); useEffect(()=>{let live=true;setLoading(true);api<T>(path).then(v=>live&&setData(v)).catch(()=>{}).finally(()=>live&&setLoading(false));return()=>{live=false}},[path,tick]); return {data,loading,reload:()=>setTick(v=>v+1)} }

function TopSearch({go,openResume,setFocusFact}:{go:(p:any)=>void;openResume:(id:number)=>void;setFocusFact:(f:Fact)=>void}){
  const [q,setQ]=useState(''); const [items,setItems]=useState<SearchResult[]|null>(null); const [open,setOpen]=useState(false)
  const box=useRef<HTMLDivElement|null>(null)
  useEffect(()=>{ if(!q.trim()){setItems(null);setOpen(false);return}
    let live=true; const t=window.setTimeout(()=>{ api<SearchResult[]>(`/api/search?q=${encodeURIComponent(q.trim())}`).then(v=>{if(live){setItems(v);setOpen(true)}}).catch(()=>{if(live)setItems([])}) },250)
    return ()=>{live=false;clearTimeout(t)}
  },[q])
  useEffect(()=>{ const h=(e:MouseEvent)=>{ if(box.current&&!box.current.contains(e.target as Node))setOpen(false) }; document.addEventListener('mousedown',h); return ()=>document.removeEventListener('mousedown',h) },[])
  const nav=(r:SearchResult)=>{ setOpen(false); setQ('')
    if(r.type==='resume')openResume(r.id)
    else if(r.type==='profile'||r.type==='opportunity')go('profiles')
    else if(r.type==='fact'&&r.payload){setFocusFact(r.payload as Fact);go('facts')}
    else if(r.type==='evidence'&&r.payload?.fact){setFocusFact(r.payload.fact as Fact);go('facts')}
  }
  return <div className="top-search" ref={box}>
    <Search size={15}/><input placeholder="全局搜索：资料、证据、画像、机会、简历" value={q} onChange={e=>setQ(e.target.value)}/>
    {open&&items&&<div className="search-pop">{items.length?items.map(r=><button key={`${r.type}-${r.id}`} onClick={()=>nav(r)}><b>{r.title}</b><small>{searchTypeLabels[r.type]} · {r.subtitle}</small></button>):<p className="search-empty">没有匹配结果</p>}</div>}
  </div>
}

function Home({go,openResume}:{go:(p:any)=>void;openResume:(id:number)=>void}){
  const data=useLoad<{stats:Record<string,number>;recent_resumes:Resume[]}>('/api/overview',{stats:{facts:0,profiles:0,resumes:0,working_copies:0},recent_resumes:[]})
  const modules=[[Library,'资料库','按分类维护事实与证据','facts'],[BriefcaseBusiness,'岗位画像','组织招聘要求和简历策略','profiles'],[FilePenLine,'ResumeCraft','在 A4 简历上直接工作','resumes'],[LayoutTemplate,'模板库','浏览模板并为简历选择版式','templates']] as const
  return <main className="page home">
    <p className="eyebrow">PERSONAL RESUME SYSTEM</p>
    <h1>让经历沉淀为<br/><em>可持续维护的简历</em></h1>
    <p className="lead">资料保持真实中立，岗位决定表达重点，版本记录每次正式交付。</p>
    <section className="module-grid">{modules.map(([I,t,d,k])=><button className="module-card" key={k} onClick={()=>go(k)}><I size={22}/><h2>{t}</h2><p>{d}</p><ChevronRight size={16}/></button>)}</section>
    <section className="stat-row">{[['事实资料',data.data.stats.facts],['岗位画像',data.data.stats.profiles],['正式简历',data.data.stats.resumes],['工作副本',data.data.stats.working_copies]].map(x=><div key={String(x[0])}><b>{x[1]}</b><span>{x[0]}</span></div>)}</section>
    {data.data.recent_resumes.length>0&&<section className="list-panel recent-panel">
      <div className="table-head"><span>近期正式简历</span><span></span></div>
      {data.data.recent_resumes.map(r=><button className="resume-row" key={r.id} onClick={()=>openResume(r.id)}><FilePenLine size={18}/><span><b>{r.display_name}</b><small>{r.profile_name} · {r.current_version?`v${r.current_version}`:'未保存'} · {date(r.updated_at)}</small></span><em>打开工作台 <ChevronRight size={15}/></em></button>)}
    </section>}
  </main>
}

function Facts({back,error,focus,onFocusHandled}:{back:()=>void;error:(s:string)=>void;focus:Fact|null;onFocusHandled:()=>void}){
  const facts=useLoad<Fact[]>('/api/facts',[]), recycled=useLoad<Fact[]>('/api/facts?include_recycled=true',[])
  const [cat,setCat]=useState<string|null>(null),[q,setQ]=useState(''),[edit,setEdit]=useState<Fact|null>(null),[recycle,setRecycle]=useState(false)
  useEffect(()=>{ if(focus){ setEdit(focus); onFocusHandled() } },[focus])
  const list=(recycle?recycled.data.filter(f=>f.status==='recycled'):facts.data).filter(f=>(!cat||f.category===cat)&&`${f.title} ${brief(f)}`.toLowerCase().includes(q.toLowerCase()))
  const count=(k:string)=>facts.data.filter(f=>f.category===k).length
  const noEvidence=facts.data.filter(f=>!f.evidence_count).length,noTags=facts.data.filter(f=>!f.tags.length).length
  return <main className="page">
    <Title crumb="资料库" title={cat?labels[cat]:'资料库'} desc={cat?'点击条目审阅详情、编辑分类字段或补充证据。':'按类别沉淀事实，所有详细字段都会保留。'} back={back} action={<div className="header-actions"><button className="button" onClick={()=>{setRecycle(!recycle);setCat(null)}}>{recycle?<ArchiveRestore size={15}/>:<Trash2 size={15}/>} {recycle?'返回资料库':'回收站'}</button><button className="button primary" onClick={()=>setEdit({id:0,category:cat||'experience',title:'',content:{},details:{},custom_fields:[],display_fields:[],tags:[],status:'active',updated_at:'',evidence_count:0})}><Plus size={16}/>新增资料</button></div>}/>
    <div className="filterbar"><Search size={16}/><input placeholder="搜索资料名称、详情或关键词" value={q} onChange={e=>setQ(e.target.value)}/></div>
    {!cat&&!q&&!recycle?<><section className="library-grid">{categories.map(k=><button className="library-card" key={k} onClick={()=>setCat(k)}><BookOpen size={18}/><span><b>{labels[k]}</b><small>{count(k)} 条资料</small></span><ChevronRight size={15}/></button>)}</section><div className="home-extras"><section className="list-panel mini-panel"><div className="table-head"><span>最近修改</span></div>{facts.data.slice(0,5).map(f=><button className="table-row" key={f.id} onClick={()=>setEdit(f)}><span><b>{f.title}</b><small>{labels[f.category]}</small></span><time>{date(f.updated_at)}</time></button>)}</section><aside className="quality-hints"><b>质量提示</b>{facts.data.length===0?<p>还没有事实资料，先从基本信息开始沉淀。</p>:<>{noEvidence>0&&<p>{noEvidence} 条资料还没有关联证据。</p>}{noTags>0&&<p>{noTags} 条资料缺少标签。</p>}{noEvidence===0&&noTags===0&&<p>资料状态良好，继续保持。</p>}</>}</aside></div></>:<><nav className="category-tabs"><button className={!cat?'active':''} onClick={()=>setCat(null)}>全部</button>{categories.map(k=><button key={k} className={cat===k?'active':''} onClick={()=>setCat(k)}>{labels[k]}</button>)}</nav><section className="data-table"><div className="table-head"><span>资料名称</span><span>摘要</span><span>证据</span><span>更新时间</span></div>{(recycle?recycled.loading:facts.loading)?<Loading/>:list.length?list.map(f=><button className="table-row" key={f.id} onClick={()=>setEdit(f)}><span><b>{f.title}</b><small>{labels[f.category]}{f.status==='recycled'?' · 已回收':''}</small></span><span>{brief(f)}</span><span>{f.evidence_count?`${f.evidence_count} 份`:'未添加'}</span><time>{date(f.updated_at)}</time></button>):<Empty icon={BookOpen} title="没有匹配资料" body="可以新增资料，或调整搜索条件。"/>}</section></>}
    {edit&&<FactModal fact={edit} close={()=>setEdit(null)} done={()=>{setEdit(null);facts.reload();recycled.reload()}} error={error}/>}
  </main>
}

function FactModal({fact,close,done,error}:{fact?:Fact;close:()=>void;done:()=>void;error:(s:string)=>void}){
  const [title,setTitle]=useState(fact?.title||''),[cat,setCat]=useState(fact?.category||'experience'),[details,setDetails]=useState<Record<string,string>>(fact?.details||fact?.content||{}),[custom,setCustom]=useState<CustomField[]>(fact?.custom_fields||[]),[evidence,setEvidence]=useState(false),[saving,setSaving]=useState(false),audits=useLoad<{id:number;action:string;summary:string;created_at:string}[]>(fact?.id?`/api/facts/${fact.id}/audits`:'',[])
  useEffect(()=>{setTitle(fact?.title||'');setCat(fact?.category||'experience');setDetails(fact?.details||fact?.content||{});setCustom(fact?.custom_fields||[])},[fact])
  const schema=useLoad<{key:string;label:string;type:string;required:boolean}[]>(`/api/fact-schemas/${cat}`,[])
  const set=(key:string,value:string)=>setDetails(v=>({...v,[key]:value}))
  const save=async()=>{setSaving(true);try{const body={title,category:cat,details,content:details,custom_fields:custom.filter(x=>x.key.trim()),tags:fact?.tags||[],status:fact?.status==='recycled'?'recycled':'active'};fact&&fact.id?await patch(`/api/facts/${fact.id}`,body):await post('/api/facts',body);done()}catch(e){error((e as Error).message)}finally{setSaving(false)}}
  const remove=async()=>{if(!fact||!confirm('确认删除？正式简历引用过的资料会进入回收站。'))return;try{await del(`/api/facts/${fact.id}`);done()}catch(e){error((e as Error).message)}}
  const addCustom=()=>setCustom(v=>[...v,{key:`custom_${v.length+1}`,label:'自定义字段',value:'',displayable:true,sort_order:v.length}])
  return <Modal title={fact?.id?`编辑资料 · ${fact.title}`:'新增资料'} close={close}><Field label="资料分类"><select value={cat} onChange={e=>{setCat(e.target.value);setDetails({});setCustom([])}}>{categories.map(k=><option key={k} value={k}>{labels[k]}</option>)}</select></Field><Field label="资料名称" hint="用于列表识别，不替代分类详情。"><input value={title} onChange={e=>setTitle(e.target.value)} placeholder="例如：越疆 X-Trainer 数据采集项目"/></Field><div className="fact-fields">{schema.loading?<Loading/>:schema.data.map(f=><Field key={f.key} label={`${f.label}${f.required?' *':''}`}>{f.type==='textarea'?<textarea value={details[f.key]||''} onChange={e=>set(f.key,e.target.value)} placeholder={`填写${f.label}，没有内容可以留空`}/>:<input type={f.type==='email'?'email':f.type==='url'?'url':'text'} value={details[f.key]||''} onChange={e=>set(f.key,e.target.value)} placeholder={`填写${f.label}，没有内容可以留空`}/>}</Field>)}</div><div className="custom-fields"><div className="custom-fields-head"><b>扩展字段</b><button className="mini-button" type="button" onClick={addCustom}><Plus size={13}/>添加字段</button></div>{custom.map((item,index)=><div className="custom-field-row" key={`${item.key}-${index}`}><input value={item.label} onChange={e=>setCustom(v=>v.map((x,i)=>i===index?{...x,label:e.target.value}:x))} placeholder="字段名称"/><input value={item.value} onChange={e=>setCustom(v=>v.map((x,i)=>i===index?{...x,value:e.target.value}:x))} placeholder="字段内容"/><button className="icon-btn" type="button" onClick={()=>setCustom(v=>v.filter((_,i)=>i!==index))}><X size={14}/></button></div>)}</div>{fact?.id&&<details className="audit-box"><summary>修改记录（{audits.data.length}）</summary>{audits.data.map(a=><p key={a.id} className="audit-row"><b>{a.summary}</b><small>{date(a.created_at)}</small></p>)}</details>}{fact?.id&&<button className="evidence-link" onClick={()=>setEvidence(true)}><FileUp size={16}/>证据材料 <span>{fact.evidence_count} 份</span><ChevronRight size={15}/></button>}<div className="modal-actions">{fact?.status==='recycled'?<button className="button" onClick={async()=>{await post(`/api/facts/${fact.id}/restore`);done()}}><ArchiveRestore size={15}/>恢复资料</button>:fact?.id&&<button className="button danger" onClick={remove}><Trash2 size={15}/>删除</button>}<button className="button primary" disabled={!title.trim()||saving} onClick={save}>{saving?'保存中…':'保存资料'}</button></div>{evidence&&fact?.id&&<EvidenceModal fact={fact} close={()=>setEvidence(false)} error={error}/>}</Modal>
}

function EvidenceModal({fact,close,error}:{fact:Fact;close:()=>void;error:(s:string)=>void}){const list=useLoad<any[]>(`/api/facts/${fact.id}/evidence`,[]),[title,setTitle]=useState(''),[url,setUrl]=useState(''),[note,setNote]=useState(''),[file,setFile]=useState<File|null>(null);const save=async()=>{try{if(file){const fd=new FormData();fd.set('fact_id',String(fact.id));fd.set('title',title);fd.set('note',note);fd.set('file',file);await upload('/api/evidence/upload',fd)}else await post('/api/evidence',{fact_id:fact.id,title,url,note});setTitle('');setUrl('');setNote('');setFile(null);list.reload()}catch(e){error((e as Error).message)}};const archive=async(id:number)=>{try{await del(`/api/evidence/${id}`);list.reload()}catch(e){error((e as Error).message)}};return <Modal title={`证据 · ${fact.title}`} close={close}><p className="modal-note">上传 PDF、PNG、JPEG、WEBP，或添加可验证链接。证据不会自动出现在简历正文。</p>{list.data.map(e=><div className="evidence-row" key={e.id}><FileUp size={15}/><span><b>{e.title}</b><small>{e.kind==='link'?e.url:e.filename}</small></span>{e.status==='active'&&<button className="mini-button" onClick={()=>archive(e.id)}>标记失效</button>}{e.status!=='active'&&<small className="evidence-state">已失效</small>}</div>)}<Field label="证据名称"><input value={title} onChange={e=>setTitle(e.target.value)}/></Field><Field label="上传文件或填写链接"><input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" onChange={e=>setFile(e.target.files?.[0]||null)}/><input value={url} disabled={!!file} onChange={e=>setUrl(e.target.value)} placeholder="https://..."/></Field><Field label="说明"><input value={note} onChange={e=>setNote(e.target.value)}/></Field><button className="button primary" disabled={!file&&!url.trim()} onClick={save}>添加证据</button></Modal> }

function Profiles({back,create,open,error}:{back:()=>void;create:(p:Profile)=>void;open:(id:number)=>void;error:(s:string)=>void}){
  const data=useLoad<Profile[]>('/api/requirement-profiles',[]),[edit,setEdit]=useState<Profile|null>(null)
  return <main className="page"><Title crumb="岗位画像" title="岗位画像" desc="先整理岗位要求，再选择最适合呈现的事实资料。" back={back} action={<button className="button primary" onClick={()=>setEdit({id:0,name:'',role_direction:'',core_requirements:[],resume_strategy:'',raw_jd:'',status:'active',updated_at:''})}><Plus size={16}/>新建岗位画像</button>}/>
    <section className="profile-list">{data.loading?<Loading/>:data.data.map(p=><article className="profile-card" key={p.id}><div><p className="eyebrow">{p.role_direction||'岗位方向待补充'}</p><h2>{p.name}</h2><div className="chips">{p.core_requirements.map(x=><span key={x}>{x}</span>)}</div><p>{p.resume_strategy||'尚未设置简历强调方向。'}</p><small className="profile-meta">{date(p.updated_at)} · {p.opportunity_count||0} 个招聘机会{p.active_resume_id?' · 已关联正式简历':''}</small></div><div className="card-actions"><button className="button" onClick={()=>setEdit(p)}>编辑</button>{p.active_resume_id?<><button className="button" onClick={async()=>{try{const r=await post<{resume_id:number}>(`/api/resumes/${p.active_resume_id}/fork`);open(r.resume_id)}catch(e){error((e as Error).message)}}}>新简历身份</button><button className="button primary" onClick={()=>open(p.active_resume_id!)}>打开正式简历 <ChevronRight size={15}/></button></>:<button className="button primary" onClick={()=>create(p)}>创建临时简历 <ChevronRight size={15}/></button>}</div></article>)}</section>
    {edit&&<ProfileModal profile={edit.id?edit:undefined} close={()=>setEdit(null)} done={()=>{setEdit(null);data.reload()}} create={create} error={error}/>}
  </main>
}
function ProfileModal({profile,close,done,create,error}:{profile?:Profile;close:()=>void;done:()=>void;create:(p:Profile)=>void;error:(s:string)=>void}){const[name,setName]=useState(profile?.name||''),[role,setRole]=useState(profile?.role_direction||''),[req,setReq]=useState(profile?.core_requirements.join('、')||''),[strategy,setStrategy]=useState(profile?.resume_strategy||''),[jd,setJd]=useState(profile?.raw_jd||'');const save=async(start=false)=>{try{const body={name,role_direction:role,core_requirements:req.split(/[、，,]/).map(x=>x.trim()).filter(Boolean),resume_strategy:strategy,raw_jd:jd};const item=profile?await patch<Profile>(`/api/requirement-profiles/${profile.id}`,body):await post<Profile>('/api/requirement-profiles',body);done();if(start)create(item)}catch(e){error((e as Error).message)}};return <Modal title={profile?'编辑岗位画像':'新建岗位画像'} close={close}><Field label="画像名称"><input autoFocus value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="岗位方向"><input value={role} onChange={e=>setRole(e.target.value)}/></Field><Field label="核心技术要求" hint="使用顿号或逗号分隔多条要求。"><input value={req} onChange={e=>setReq(e.target.value)} placeholder="Python、ROS2、数据标注"/></Field><Field label="简历强调方向"><textarea value={strategy} onChange={e=>setStrategy(e.target.value)}/></Field><details><summary>原始 JD 与来源</summary><textarea value={jd} onChange={e=>setJd(e.target.value)}/></details><div className="modal-actions"><button className="button" onClick={close}>取消</button><button className="button" disabled={!name.trim()} onClick={()=>save(false)}>保存画像</button><button className="button primary" disabled={!name.trim()} onClick={()=>save(true)}>保存并选择资料</button></div></Modal> }

function Resumes({back,open,create,pending,library}:{back:()=>void;open:(id:number)=>void;create:()=>void;pending:Pending[];library:()=>void}){const data=useLoad<Resume[]>('/api/resumes',[]),recycled=useLoad<Resume[]>('/api/resumes?include_recycled=true',[]),[recycle,setRecycle]=useState(false);const rows=(recycle?recycled.data:data.data).filter(r=>recycle?r.status==='recycled':r.status==='active');const restore=async(id:number)=>{try{await post(`/api/resumes/${id}/restore`);data.reload();recycled.reload()}catch(e){console.error(e)}};return <main className="page"><Title crumb="ResumeCraft" title={recycle?'简历回收站':'正式简历'} desc={recycle?'已删除的正式简历仍可查看和恢复。':'每次正式保存都会增加一个不可变版本。'} back={back} action={<div className="header-actions">{!recycle&&<><button className="button" onClick={library}><LayoutTemplate size={15}/>模板库</button><button className="button primary" onClick={create}><Plus size={16}/>创建临时简历</button></>}<button className="button" onClick={()=>setRecycle(!recycle)}>{recycle?<ArchiveRestore size={15}/>:<Trash2 size={15}/>} {recycle?'返回正式简历':'回收站'}</button></div>}/>{!recycle&&pending.length>0&&<div className="warning-banner"><CircleAlert size={18}/><div><b>{pending.length} 项来源变化待处理</b><span>进入简历后，变化会直接标记在受影响的条目上。</span></div></div>}{!recycle&&rows.some(r=>r.dirty||r.warnings>0)&&(()=>{const r=rows.find(x=>x.dirty||x.warnings>0)!;return <button className="resume-row continue-card" onClick={()=>open(r.id)}><CircleAlert size={18}/><span><b>继续上次工作</b><small>{r.display_name} · {r.warnings?`${r.warnings} 项来源变化待处理`:'工作副本有未保存修改'}</small></span><em>继续 <ChevronRight size={15}/></em></button>})()}<section className="list-panel">{(data.loading||recycled.loading)?<Loading/>:rows.length?rows.map(r=><article className="resume-row" key={r.id} onClick={()=>open(r.id)}><FilePenLine size={18}/><span><b>{r.display_name}</b><small>{r.current_version?`v${r.current_version}`:'未保存'} · {date(r.updated_at)}{r.status==='recycled'?' · 已回收':''}</small></span>{r.status==='recycled'?<button className="button" onClick={e=>{e.stopPropagation();restore(r.id)}}><ArchiveRestore size={14}/>恢复</button>:<em>{r.warnings?`${r.warnings} 项来源变化`:'打开工作台'} <ChevronRight size={15}/></em>}</article>):<Empty icon={recycle?Trash2:FilePenLine} title={recycle?'回收站为空':'还没有正式简历'} body={recycle?'已删除的正式简历会保留在这里。':'从岗位画像创建一份临时简历开始。'}/>}</section></main> }

// Sample facts used only by the template library previews: one compact entry
// per section so every template shows its real layout, colours and typography.
const SAMPLE_CONTENT:Content={sections:[
  {id:'basics',title:'基本信息',visibility:true,blocks:[{id:'sample-basics',title:'陈晓萌',content:'',fields:{phone:'138 0000 0000',email:'chenxiaomeng@example.com',city:'上海',desired_city:'上海',status:'应届毕业生',graduation:'2026年6月'},display_fields:['phone','email','city','desired_city','status','graduation'],source_refs:[],origin:'fact'}]},
  {id:'target',title:'求职目标',visibility:true,blocks:[{id:'sample-target',title:'机器人数据采集工程师',content:'突出数据采集流水线与标注质量管理的工程实践，强调跨团队协作。',fields:{role_direction:'机器人 · 数据工程'},display_fields:['role_direction'],source_refs:[],origin:'profile'}]},
  {id:'profile',title:'个人简介',visibility:true,blocks:[{id:'sample-profile',title:'个人简介',content:'三年机器人数据采集与标注经验，熟悉采集规范制定、质量抽检与交付复盘。',fields:{},display_fields:[],source_refs:[],origin:'fact'}]},
  {id:'experience',title:'项目与实践',visibility:true,blocks:[
    {id:'sample-exp1',title:'越疆 X-Trainer 数据采集项目',content:'搭建 12 台机械臂的采集流水线，制定场景脚本与异常回传机制，累计交付 4.2 万条有效轨迹。',fields:{period:'2024.03 – 2025.06',organization:'智能机器人实验室',role:'数据采集负责人'},display_fields:['period','organization','role'],source_refs:[],origin:'fact'},
    {id:'sample-exp2',title:'标注质量管理专项',content:'设计三级抽检流程，把标注一致率从 86% 提升到 97%，沉淀质量手册并被两个团队复用。',fields:{period:'2023.09 – 2024.02',role:'质量组长'},display_fields:['period','role'],source_refs:[],origin:'fact'}]},
  {id:'education',title:'教育经历',visibility:true,blocks:[{id:'sample-edu',title:'华东理工大学 · 自动化',content:'主修控制理论与机器人学，毕业设计方向为遥操作数据合成。',fields:{period:'2022.09 – 2026.06',degree:'本科',gpa:'3.7/4.0'},display_fields:['period','degree','gpa'],source_refs:[],origin:'fact'}]},
  {id:'skills',title:'技能',visibility:true,blocks:[
    {id:'sample-skill1',title:'数据工具链',content:'ROS2 采集节点、标注平台管理、Python 数据清洗脚本。',fields:{skill_category:'工程工具',proficiency:'熟练'},display_fields:['skill_category','proficiency'],source_refs:[],origin:'fact'},
    {id:'sample-skill2',title:'质量管理',content:'抽检设计、一致性度量、标注规范撰写。',fields:{skill_category:'方法论',proficiency:'熟练'},display_fields:['skill_category','proficiency'],source_refs:[],origin:'fact'}]},
  {id:'awards',title:'成果',visibility:true,blocks:[{id:'sample-award',title:'校级优秀毕业设计',content:'遥操作数据合成方向，评级 A。',fields:{period:'2026.06',issuer:'华东理工大学'},display_fields:['period','issuer'],source_refs:[],origin:'fact'}]},
  {id:'links',title:'链接与作品集',visibility:true,blocks:[{id:'sample-link',title:'个人作品集',content:'采集规范、质量手册与项目复盘节选。',fields:{link_type:'作品集',url:'https://example.com/portfolio',label:'example.com/portfolio'},display_fields:['link_type','label'],source_refs:[],origin:'fact'}]},
]}

function TemplateLibrary({back,go}:{back:()=>void;go:(p:any)=>void}){
  const templates=useLoad<{slug:string;name:string;description:string;layout:string;template_version_id:number}[]>('/api/templates',[])
  return <main className="page">
    <Title crumb="模板库" title="简历模板库" desc="所有模板用同一份样例资料实时渲染，版式、配色与字体的差异即最终导出效果。选择后可在临时简历与正式简历中随时切换。" back={back} action={<button className="button primary" onClick={()=>go('profiles')}><Plus size={16}/>创建简历选用模板</button>}/>
    <section className="template-library-grid">{templates.loading?<Loading/>:templates.data.map(t=><article className="template-library-card" key={t.slug}>
      <div className="template-preview"><div className="template-preview-stage" style={{zoom:.34}}><Canvas content={SAMPLE_CONTENT} mode="select" template={t}/></div></div>
      <div className="template-info"><b>{t.name}</b><small>{t.description}</small><em>{layoutLabel(t.layout)} · 模板 #{t.template_version_id}</em></div>
      <div className="template-actions"><button className="button primary" onClick={()=>go('profiles')}>用此模板创建简历</button></div>
    </article>)}</section>
  </main>
}

function Composer({id,profile,back,open,error}:{id:number;profile:Profile;back:()=>void;open:(id:number)=>void;error:(s:string)=>void}){const linked=useLoad<{selection:Record<string,number[]>;preview:Content;template?:TemplateInfo}>(`/api/linked-resumes/${id}`,{selection:{},preview:{sections:[]}}),facts=useLoad<Fact[]>('/api/facts',[]),templates=useLoad<{slug:string;name:string;description:string;layout:string;template_version_id:number}[]>('/api/templates',[]),[sectionId,setSectionId]=useState<string|null>(null),[convertLoading,setConvertLoading]=useState(false),[templateOpen,setTemplateOpen]=useState(false),[zoom,setZoom]=useState(1),[compact,setCompact]=useState(false);useEffect(()=>{const h=()=>setCompact(window.scrollY>150);window.addEventListener('scroll',h);return()=>window.removeEventListener('scroll',h)},[]);const toggle=async(fid:number)=>{if(!sectionId)return;const old=linked.data.selection[sectionId]||[],next={...linked.data.selection,[sectionId]:old.includes(fid)?old.filter(x=>x!==fid):[...old,fid]};try{await patch(`/api/linked-resumes/${id}`,{selection:next});linked.reload()}catch(e){error((e as Error).message)}};const chooseTemplate=async(tvId:number)=>{try{await patch(`/api/linked-resumes/${id}`,{template_version_id:tvId});setTemplateOpen(false);linked.reload()}catch(e){error((e as Error).message)}};const convert=async()=>{if(convertLoading)return;setConvertLoading(true);try{open((await post<{resume_id:number}>(`/api/linked-resumes/${id}/convert`)).resume_id)}catch(e){error((e as Error).message)}finally{setConvertLoading(false)}};const missing=Object.values(linked.data.selection).flat().filter(fid=>!facts.data.some(f=>f.id===fid)).length;const layout=linked.data.template?.layout||'sidebar';return <main className="workbench"><BenchHead title="临时简历" subtitle={`${profile.name} · ${profile.core_requirements.join('、')||'未设置核心要求'}`} back={back} compact={compact}/>{missing>0&&<div className="warning-banner compact"><CircleAlert size={17}/><div><b>{missing} 条已选资料不可用</b><span>它们已归档或被删除，不会出现在预览中；点击对应栏目可重新选择。</span></div></div>}<p className="canvas-hint">初始画布只显示栏目；点击栏目选择事实资料，内容增加后自动续为 A4 页面。转换正式简历时会使用当前所选模板。</p><StageToolbar zoom={zoom} setZoom={setZoom} pageCount={streamItems(linked.data.preview,layoutMainIds(layout),layoutBudget(layout),false).length}/><div className="stage-zoom" style={{zoom}}><Canvas content={linked.data.preview} mode="select" template={linked.data.template} select={id=>factCategories(id).length&&setSectionId(id)}/></div><footer className="actionbar"><button className="button" onClick={back}>退出选择</button><button className="button" onClick={()=>setTemplateOpen(true)}><LayoutTemplate size={15}/>模板 · {linked.data.template?.name||'默认模板'}</button><button className="button primary" disabled={linked.loading||convertLoading} onClick={convert}>{convertLoading?'正在生成…':'生成格式化简历'} {!convertLoading&&<ChevronRight size={16}/>}</button></footer>{sectionId&&<Picker title={labels[sectionId]} facts={facts.data.filter(f=>factCategories(sectionId).includes(f.category))} chosen={linked.data.selection[sectionId]||[]} toggle={toggle} close={()=>setSectionId(null)}/>}{templateOpen&&<TemplateModal current={linked.data.template?.template_version_id} templates={templates.data} loading={templates.loading} onChoose={chooseTemplate} close={()=>setTemplateOpen(false)}/>}</main> }
function Picker({title,facts,chosen,toggle,close}:{title:string;facts:Fact[];chosen:number[];toggle:(id:number)=>void;close:()=>void}){const[q,setQ]=useState('');const shown=facts.filter(f=>`${f.title} ${brief(f)}`.toLowerCase().includes(q.toLowerCase()));return <div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)close()}}><section className="selection-modal"><header><div><p className="eyebrow">选择事实资料</p><h2>{title}</h2></div><button className="icon-btn" onClick={close}><X size={18}/></button></header><div className="filterbar"><Search size={16}/><input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="搜索资料名称或详情"/></div><div className="selection-list">{shown.map(f=><label key={f.id}><input type="checkbox" checked={chosen.includes(f.id)} onChange={()=>toggle(f.id)}/><span><b>{f.title}</b><small>{brief(f)}</small></span></label>)}</div><footer><span>已选择 {chosen.length} 条</span><button className="button primary" onClick={close}>完成选择</button></footer></section></div> }

function Editor({id,back,error,refresh,focusBlock,onFocusLocated}:{id:number;back:()=>void;error:(s:string)=>void;refresh:()=>void;focusBlock:{sectionId:string;blockId:string}|null;onFocusLocated:()=>void}){
  const resume=useLoad<any>(`/api/resumes/${id}`,null)
  const versions=useLoad<any[]>(`/api/resumes/${id}/versions`,[])
  const facts=useLoad<Fact[]>('/api/facts',[])
  const pending=useLoad<Pending[]>('/api/pending-items',[])
  const templates=useLoad<{slug:string;name:string;description:string;layout:string;template_version_id:number}[]>('/api/templates',[])
  const [content,setContent]=useState<Content|null>(null)
  const baseline=useRef('')
  const [restore,setRestore]=useState<number|null>(null)
  const [pick,setPick]=useState<string|null>(null)
  const [saving,setSaving]=useState(false)
  const [editing,setEditing]=useState<BlockRef|null>(null)
  const [menu,setMenu]=useState<BlockMenu|null>(null)
  const [confirmLeave,setConfirmLeave]=useState(false)
  const [diffWith,setDiffWith]=useState<number|null>(null)
  const [templateOpen,setTemplateOpen]=useState(false)
  const [zoom,setZoom]=useState(1)
  const [compact,setCompact]=useState(false)
  useEffect(()=>{const h=()=>setCompact(window.scrollY>150);window.addEventListener('scroll',h);return()=>window.removeEventListener('scroll',h)},[])
  useEffect(()=>{if(resume.data){setContent(resume.data.working_copy.content);baseline.current=JSON.stringify(resume.data.working_copy.content)}},[resume.data])
  // Locate and flash the block affected by a pending item after navigation.
  useEffect(()=>{
    if(!content||!focusBlock)return
    const el=document.querySelector(`[data-block-key="${focusBlock.sectionId}:${focusBlock.blockId}"]`) as HTMLElement|null
    if(!el)return
    el.scrollIntoView({behavior:'smooth',block:'center'})
    el.classList.remove('flash-highlight');void el.offsetWidth;el.classList.add('flash-highlight')
    // Clear the focus target only after the flash finishes: clearing earlier
    // re-renders the canvas and would wipe the manually added class.
    window.setTimeout(()=>{el.classList.remove('flash-highlight');onFocusLocated()},3500)
  },[content,focusBlock])
  // Only edits that diverge from the loaded baseline count as unsaved changes;
  // merely opening a resume must never mark the working copy dirty. A template
  // switch or server-side draft (working_copy.dirty) also counts as unsaved.
  const localDirty=(!!content&&baseline.current!==''&&JSON.stringify(content)!==baseline.current)||!!resume.data?.working_copy.dirty
  useEffect(()=>{if(!content||!resume.data||resume.data.status==='recycled')return;const payload=JSON.stringify(content);if(payload===baseline.current)return;const t=window.setTimeout(()=>{patch(`/api/resumes/${id}/working-copy`,{content}).catch(e=>error(e.message))},500);return()=>clearTimeout(t)},[content,id,resume.data])
  if(!content||!resume.data)return <Loading/>
  const readOnly=resume.data.status==='recycled'
  const changed=pending.data.filter(x=>x.resume_id===id).flatMap(x=>x.affected.map(a=>`${a.section_id}:${a.block_id}`))
  const update:UpdateBlock=(sid,bid,value,key='content',fieldKey,fragmentIndex)=>setContent(old=>{
    if(!old)return old
    return {sections:old.sections.map(s=>{
      if(s.id!==sid)return s
      return {...s,blocks:s.blocks.map(b=>{
        if(b.id!==bid)return b
        const next={...b,origin:'user'} as Block
        if(key==='field'&&fieldKey){next.fields={...b.fields,[fieldKey]:value};return next}
        if(key==='title'){next.title=value;return next}
        if(fragmentIndex===undefined){next.content=value;return next}
        const chunks=splitText(b.content||'',fragmentLimit(sid))
        chunks[fragmentIndex]=value
        // splitText slices by position, so reassembly must be a plain concat;
        // joining with '\n' would inject newlines at every fragment boundary.
        next.content=chunks.join('')
        return next
      })}
    })}
  })
  const removeBlock=(sid:string,bid:string)=>setContent(old=>old?{sections:old.sections.map(s=>s.id!==sid?s:{...s,blocks:s.blocks.filter(b=>b.id!==bid)})}:old)
  const moveBlock=(sid:string,bid:string,dir:1|-1)=>setContent(old=>{
    if(!old)return old
    return {sections:old.sections.map(s=>{
      if(s.id!==sid)return s
      const index=s.blocks.findIndex(b=>b.id===bid),target=index+dir
      if(index<0||target<0||target>=s.blocks.length)return s
      const blocks=[...s.blocks];[blocks[index],blocks[target]]=[blocks[target],blocks[index]]
      return {...s,blocks}
    })}
  })
  const addFact=(fact:Fact)=>{
    if(!pick)return
    const block=factBlock(fact,pick)
    setContent(old=>old?{sections:old.sections.map(s=>s.id===pick?{...s,blocks:[...s.blocks,block]}:s)}:old)
    setPick(null)
  }
  const save=async()=>{
    if(saving||readOnly)return
    setSaving(true)
    try{await post(`/api/resumes/${id}/save`,{change_summary:'用户保存正式版本'});resume.reload();versions.reload();refresh()}
    catch(e){error((e as Error).message)}
    finally{setSaving(false)}
  }
  const discard=async()=>{
    try{await post(`/api/resumes/${id}/versions/${resume.data.current_version}/restore`);resume.reload();versions.reload();refresh()}
    catch(e){error((e as Error).message)}
  }
  const exportVersion=async(v:number)=>{try{await downloadExport(id,v)}catch(e){error((e as Error).message)}}
  const openEdit=(target:BlockRef)=>{setMenu(null);setEditing(target)}
  const openMenu=(target:BlockRef,x:number,y:number)=>{setEditing(null);setMenu({...target,x,y})}
  const addSource=(sid:string)=>{setMenu(null);setPick(sid)}
  const requestBack=()=>{if(localDirty&&!readOnly)setConfirmLeave(true);else back()}
  const activeMenu=menu
  const versionLabel=resume.data.current_version?`v${resume.data.current_version}`:'未保存'
  const menuSection=activeMenu?section(content,activeMenu.sectionId):null
  const menuBlock=activeMenu&&menuSection?menuSection.blocks.find(b=>b.id===activeMenu.blockId)||null:null
  const menuIndex=menuSection&&menuBlock?menuSection.blocks.indexOf(menuBlock):-1
  return <main className="workbench">
    <BenchHead title={`正式简历 · ${versionLabel}`} subtitle={`${resume.data.profile_name} · ${readOnly?'已移入回收站':localDirty?'工作副本有未保存修改':'工作副本已同步'}`} back={requestBack} compact={compact}/>
    {changed.length>0&&!readOnly&&<div className="warning-banner compact"><CircleAlert size={17}/><div><b>来源资料已变化</b><span>受影响条目已标记；正文没有被自动改写。</span></div></div>}
    <StageToolbar zoom={zoom} setZoom={setZoom} pageCount={streamItems(content,layoutMainIds(resume.data.template?.layout||'sidebar'),layoutBudget(resume.data.template?.layout||'sidebar'),false).length}/>
    <div className="stage-zoom" style={{zoom}}>
      <Canvas content={content} mode={readOnly?'select':'edit'} template={resume.data.template} changed={changed} addFact={setPick} onEdit={openEdit} onContext={openMenu}/>
    </div>
    <section className="version-panel">
      <header><History size={17}/><h2>版本历史</h2></header>
      {versions.data.map(v=><div className="version-row" key={v.id}><span><b>v{v.version_number}</b><small>{v.reason==='format_conversion'?'格式化简历、未润色':v.reason==='rollback'?'历史版本回退':v.reason==='evidence_sync'?'证据同步':v.change_summary} · {date(v.created_at)}</small></span><div className="card-actions">{v.version_number!==resume.data.current_version&&<button className="button" onClick={()=>setDiffWith(v.version_number)}>对比当前</button>}<button className="button" onClick={()=>exportVersion(v.version_number)}><Download size={14}/>导出 HTML</button>{!readOnly&&v.version_number!==resume.data.current_version&&<button className="button" onClick={()=>setRestore(v.version_number)}>以 v{v.version_number} 创建工作副本</button>}</div></div>)}
    </section>
    <footer className="actionbar">
      {readOnly
        ? <button className="button primary" onClick={async()=>{try{await post(`/api/resumes/${id}/restore`);resume.reload();versions.reload()}catch(e){error((e as Error).message)}}}><ArchiveRestore size={15}/>恢复简历</button>
        : <button className="button danger" onClick={async()=>{if(confirm('正式简历将进入回收站，历史版本会保留。确认继续？')){await del(`/api/resumes/${id}`);back()}}}><Trash2 size={15}/>删除简历</button>}
      {!readOnly&&<button className="button" disabled={!localDirty||!resume.data.current_version} onClick={discard}>放弃修改</button>}
      <button className="button" onClick={()=>setTemplateOpen(true)}><LayoutTemplate size={15}/>模板</button>
      <button className="button" disabled={!resume.data.current_version} onClick={()=>exportVersion(resume.data.current_version)}><Download size={15}/>导出正式简历</button>
      <button className="button primary" disabled={saving||readOnly} onClick={save}>{saving?'保存中…':readOnly?'已回收':'保存正式版本'}</button>
    </footer>
    {!readOnly&&pick&&<Picker title={`为${labels[pick]}添加来源`} facts={facts.data.filter(f=>factCategories(pick).includes(f.category))} chosen={[]} toggle={fid=>{const f=facts.data.find(x=>x.id===fid);if(f)addFact(f)}} close={()=>setPick(null)}/>}
    {!readOnly&&restore!==null&&<Modal title="以历史版本创建工作副本" close={()=>setRestore(null)}><p className="modal-note">将以 v{restore} 替换当前工作副本，历史版本不受影响。</p><div className="modal-actions"><button className="button" onClick={()=>setRestore(null)}>保留当前草稿</button><button className="button primary" onClick={async()=>{try{await post(`/api/resumes/${id}/versions/${restore}/restore`);setRestore(null);resume.reload();versions.reload()}catch(e){error((e as Error).message)}}}>创建工作副本</button></div></Modal>}
    {!readOnly&&confirmLeave&&<Modal title="有未保存的修改" close={()=>setConfirmLeave(false)}><p className="modal-note">当前工作副本存在未保存修改。可以选择正式保存、保留草稿离开，或放弃这些修改。</p><div className="modal-actions"><button className="button primary" onClick={async()=>{setConfirmLeave(false);await save();back()}}>保存正式版本</button><button className="button" onClick={()=>{setConfirmLeave(false);back()}}>保留工作副本并离开</button><button className="button danger" onClick={async()=>{setConfirmLeave(false);await discard();back()}}>放弃未保存修改</button></div></Modal>}
    {diffWith!==null&&<DiffModal id={id} from={diffWith} to={resume.data.current_version} close={()=>setDiffWith(null)}/>}
    {templateOpen&&<TemplateModal current={resume.data.template?.template_version_id} templates={templates.data} loading={templates.loading} onChoose={async(tvId)=>{try{await patch(`/api/resumes/${id}/template`,{template_version_id:tvId});setTemplateOpen(false);resume.reload()}catch(e){error((e as Error).message)}}} close={()=>setTemplateOpen(false)}/>}
    {!readOnly&&editing&&<BlockEditor content={content} target={editing} changed={changed.includes(`${editing.sectionId}:${editing.blockId}`)} update={update} removeBlock={removeBlock} close={()=>setEditing(null)}/>}
    {!readOnly&&menu&&<BlockContextMenu menu={menu} block={menuBlock} canMoveUp={menuBlock!==null&&menuIndex>0} canMoveDown={menuBlock!==null&&menuSection!==null&&menuIndex>-1&&menuIndex<menuSection.blocks.length-1} onEdit={target=>openEdit(target)} onAddSource={addSource} onRemove={sid=>{if(!menu)return;removeBlock(sid,menu.blockId);setMenu(null)}} onMove={(sid,dir)=>{if(!menu)return;moveBlock(sid,menu.blockId,dir);setMenu(null)}} onClose={()=>setMenu(null)}/>}
  </main>
}

function StageToolbar({zoom,setZoom,pageCount}:{zoom:number;setZoom:(v:number)=>void;pageCount:number}){
  const gotoPage=(page:number)=>{
    const target=Math.min(Math.max(1,page),pageCount)
    document.getElementById(`resume-page-${target}`)?.scrollIntoView({behavior:'smooth',block:'start'})
  }
  const fit=()=>setZoom(Math.min(1.4,Math.max(0.5,Math.round(((window.innerWidth-200)/840)*20)/20)))
  return <div className="stage-toolbar">
    <button className="toolbar-btn" onClick={()=>setZoom(Math.max(0.5,Math.round((zoom-0.1)*10)/10))} title="缩小">−</button>
    <span className="toolbar-zoom">{Math.round(zoom*100)}%</span>
    <button className="toolbar-btn" onClick={()=>setZoom(Math.min(1.4,Math.round((zoom+0.1)*10)/10))} title="放大">＋</button>
    <button className="toolbar-btn" onClick={fit}>适应窗口</button>
    <span className="toolbar-sep"/>
    <button className="toolbar-btn" onClick={()=>gotoPage(1)} title="第一页">«</button>
    <span className="toolbar-pages">共 {pageCount} 页</span>
    <button className="toolbar-btn" onClick={()=>gotoPage(pageCount)} title="最后一页">»</button>
  </div>
}

function TemplateModal({current,templates,loading,onChoose,close}:{current:number|undefined;templates:{slug:string;name:string;description:string;layout:string;template_version_id:number}[];loading:boolean;onChoose:(templateVersionId:number)=>void;close:()=>void}){
  return <Modal title="选择模板" close={close}>
    <p className="modal-note">模板决定 A4 版式与配色。切换先保存在工作副本中，正式保存后形成新版本（原因标记为“模板调整”），历史版本继续使用原模板。</p>
    {loading?<Loading/>:<div className="template-grid">{templates.map(t=><button key={t.slug} className={`template-card${t.template_version_id===current?' current':''}`} onClick={()=>onChoose(t.template_version_id)}>
      <span className={`template-thumb thumb-${t.slug}`}/>
      <b>{t.name}</b>
      <small>{t.description}</small>
      <em>{layoutLabel(t.layout)} · v{t.template_version_id}</em>
      {t.template_version_id===current&&<span className="template-current">当前模板</span>}
    </button>)}</div>}
  </Modal>
}

// Controlled Markdown subset shared with the export renderer: bold, italic,
// unordered lists and links. Content is escaped before the transforms.
const MD_LINK_RE=/\[([^\]]+)\]\(([^)\s]+)\)/g
export function mdLite(text:string):string{
  let escaped=(text||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
  escaped=escaped.replace(MD_LINK_RE,(_m,lead,url)=>`<a href="${url.replace(/"/g,'&quot;')}" target="_blank" rel="noreferrer">${lead}</a>`)
  escaped=escaped.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
  escaped=escaped.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g,'$1<em>$2</em>')
  const lines=escaped.split('\n');const out:string[]=[];let list:string[]=[]
  for(const line of lines){
    const trimmed=line.trim()
    if(trimmed.startsWith('- ')){list.push(`<li>${trimmed.slice(2)}</li>`);continue}
    if(list.length){out.push(`<ul>${list.join('')}</ul>`);list=[]}
    out.push(line)
  }
  if(list.length)out.push(`<ul>${list.join('')}</ul>`)
  return out.join('<br/>')
}

function DiffModal({id,from,to,close}:{id:number;from:number;to:number;close:()=>void}){
  const diff=useLoad<any>(`/api/resumes/${id}/versions/${from}/diff/${to}`,{changes:[]})
  const kindLabels:Record<string,string>={added:'新增',removed:'移除',modified:'修改'}
  return <Modal title={`对比 v${from} 与 v${to}`} close={close}>
    {diff.loading?<Loading/>:diff.data.changes.length?diff.data.changes.map((c:any)=><div className="diff-row" key={c.key}>
      <div className="diff-head"><b>{c.after?.section_title||c.before?.section_title}</b><span className={`diff-kind ${c.kind}`}>{kindLabels[c.kind]||c.kind}</span></div>
      {c.before&&<p className="diff-line before"><b>v{from}</b> {c.before.title}{c.before.content?`：${c.before.content}`:''}</p>}
      {c.after&&<p className="diff-line after"><b>v{to}</b> {c.after.title}{c.after.content?`：${c.after.content}`:''}</p>}
    </div>):<p className="modal-note">两个版本的正文内容一致。</p>}
  </Modal>
}

function factBlock(f:Fact,sid:string):Block{const d=f.details||f.content||{};const fields=Object.fromEntries(Object.entries(d).filter(([,v])=>v));if(sid==='profile')delete fields.bio;const extra=(f.custom_fields||[]).filter(x=>x.value);const field_labels=Object.fromEntries(extra.map(x=>[x.key,x.label||x.key]));extra.forEach(x=>{fields[x.key]=x.value});const standard=sid==='profile'?(d.bio?['bio']:['summary']):sid==='basics'?['phone','email','city','desired_city','hometown','status','graduation','availability']:sid==='education'?['period','major','degree','gpa','ranking']:sid==='experience'?['period','organization','role','team_size','tools']:sid==='skills'?['skill_category','proficiency']:sid==='awards'?['period','issuer','result']:['link_type','label','url'];const display_fields=standard.filter(k=>fields[k]).concat(extra.filter(x=>x.displayable).map(x=>x.key));const content=sid==='profile'?(d.bio||d.summary||''):sid==='education'?[d.achievement,d.courses].filter(Boolean).join('\n'):sid==='experience'?['context','work','outcome','challenge','solution','public_note'].map(k=>d[k]).filter(Boolean).join('\n'):sid==='skills'?(d.context||''):sid==='awards'?(d.note||''):sid==='links'?(d.note||''):'';return {id:`fact-${f.id}-${Date.now()}`,type:'fact',title:f.title,content:content||brief(f),fields,field_labels,display_fields,source_refs:[f.id],origin:'fact'} as Block}
export function splitText(value:string,max=900){if(!value)return [''];const chunks:string[]=[];for(let start=0;start<value.length;start+=max)chunks.push(value.slice(start,start+max));return chunks}
const fragmentLimit=(sid:string)=>['basics','skills','awards'].includes(sid)?520:900

export const MAIN_IDS=['target','profile','experience','education','links']
export const SIDE_IDS=['basics','skills','awards']
export const ALL_IDS=['basics','target','profile','experience','education','skills','awards','links']
export const MAIN_BUDGET=2400
export const SIDE_BUDGET=1500
export const BANNER_BUDGET=2200
// Section order and packing budget per template layout; mirrors render_resume_html().
export const layoutMainIds=(layout:string)=>layout==='plain'?ALL_IDS:layout==='banner'?ALL_IDS.filter(id=>id!=='basics'):MAIN_IDS
export const layoutBudget=(layout:string)=>layout==='banner'?BANNER_BUDGET:MAIN_BUDGET
export const layoutLabel=(layout:string)=>layout==='plain'?'单栏通排':layout==='banner'?'横幅单栏':'侧栏双栏'
type Item={section:Section;block:Block;continued:boolean}
const emptyBlock=(sid:string):Block=>({id:`${sid}--empty`,title:'',content:'',source_refs:[],origin:'empty'})
const itemWeight=(it:Item,side:boolean)=>{const b=it.block;return (side?70:90)+(b.content||'').length+Object.keys(b.fields||{}).length*(side?10:20)}

// Fragments blocks, packs them into fixed-size pages, and marks headings that
// continue from an earlier page. Mirrors render_resume_html() in app/services.py
// so preview page breaks match the exported A4 HTML.
export function streamItems(content:Content,ids:string[],budget:number,side:boolean):Item[][]{
  const items:Item[]=[]
  for(const id of ids){
    const original=section(content,id)
    if(!original.blocks.length){items.push({section:original,block:emptyBlock(id),continued:false});continue}
    const limit=fragmentLimit(id)
    for(const block of original.blocks){
      const chunks=splitText(block.content||'',limit)
      chunks.forEach((chunk,index)=>items.push({section:original,block:{...block,id:index?`${block.id}--fragment-${index}`:block.id,content:chunk,fields:index===0?block.fields:{},display_fields:index===0?block.display_fields:[],fragment_index:index,continuation:index>0},continued:false}))
    }
  }
  const pages:Item[][]=[];let current:Item[]=[];let size=0
  for(const it of items){const w=itemWeight(it,side);if(current.length&&size+w>budget){pages.push(current);current=[];size=0}current.push(it);size+=w}
  if(current.length||!pages.length)pages.push(current)
  const seen=new Set<string>()
  for(const page of pages){const local=new Set<string>();for(const it of page){it.continued=seen.has(it.section.id);local.add(it.section.id)}for(const key of local)seen.add(key)}
  return pages
}

type TemplateInfo={slug:string;name:string;layout:string;template_version_id:number}|null
function Canvas({content,mode,template,select,changed=[],addFact,onEdit,onContext}:{content:Content;mode:'select'|'edit';template?:TemplateInfo;select?:(s:string)=>void;changed?:string[];addFact?:(s:string)=>void;onEdit?:(target:BlockRef)=>void;onContext?:(target:BlockRef,x:number,y:number)=>void}){
  const layout=template?.layout||'sidebar'
  const plain=layout==='plain'
  const banner=layout==='banner'
  const single=plain||banner
  const mainPages=streamItems(content,layoutMainIds(layout),layoutBudget(layout),false)
  const sidePages=single?[]:streamItems(content,SIDE_IDS,SIDE_BUDGET,true)
  const count=Math.max(mainPages.length,sidePages.length,1)
  const shared={mode,select,changed,addFact,onEdit,onContext}
  const basicBlock=section(content,'basics').blocks[0]
  const bannerName=basicBlock?.title||'简历'
  return <section className={`resume-stage theme-${template?.slug||'classic'} ${mode==='edit'?'edit-mode':'select-mode'}`}>
    {Array.from({length:count},(_,i)=><Paper key={i} number={i+1} layout={layout} theme={template?.slug||'classic'} sidebar={!single&&(sidePages[i]?.length?<Sidebar items={sidePages[i]} {...shared}/>:<div className="continuation-mark">RESUME / {String(i+1).padStart(2,'0')}</div>)}>
      {banner&&(i===0
        ?<header className="resume-banner"><h1>{bannerName}</h1><div className="banner-meta">{bannerFields(basicBlock)}</div></header>
        :<header className="resume-banner banner-slim"><h1>{bannerName}</h1></header>)}
      <main className="resume-main"><div className="main-sections">{renderGroups(mainPages[i]||[],shared)}</div></main>
    </Paper>)}
  </section>
}
function bannerFields(b:Block|undefined){if(!b)return null;const fields=b.fields||{};const keys=(b.display_fields||Object.keys(fields)).filter(k=>fields[k]);const labelsFor={...fieldLabels,...(b.field_labels||{})};return <>{keys.map(k=><span key={k}><b>{labelsFor[k]||k}</b> {fields[k]}</span>)}</>}
function Paper({number,layout,theme,sidebar,children}:{number:number;layout:string;theme:string;sidebar:ReactNode;children:ReactNode}){const plain=layout!=='sidebar';return <article className={`resume-paper theme-${theme}${plain?' plain':''}${layout==='banner'?' banner':''}`} id={`resume-page-${number}`} data-page={number}>{plain?children:<><aside className="resume-sidebar">{sidebar}</aside>{children}</>}</article>}
function Sidebar({items,...shared}:{items:Item[];mode:'select'|'edit';select?:(s:string)=>void;changed:string[];addFact?:(s:string)=>void;onEdit?:(target:BlockRef)=>void;onContext?:(target:BlockRef,x:number,y:number)=>void}){return <div className="sidebar-content">{renderGroups(items,shared)}</div>}
function renderGroups(items:Item[],shared:any){return <>{items.length?renderGroupList(items,shared):<SectionGroup section={emptySection('target')} blocks={[]} continued={false} {...shared}/>}</>}
function emptySection(id:string):Section{return {id,title:labels[id],visibility:true,blocks:[]}}
function renderGroupList(items:Item[],shared:any){
  const groups:{section:Section;blocks:Block[];continued:boolean}[]=[]
  for(const it of items){
    const last=groups[groups.length-1]
    if(last&&last.section.id===it.section.id){if(!it.block.id.endsWith('--empty'))last.blocks.push(it.block)}
    else groups.push({section:it.section,blocks:it.block.id.endsWith('--empty')?[]:[it.block],continued:it.continued})
  }
  if(!groups.length)groups.push({section:emptySection('target'),blocks:[],continued:false})
  return groups.map((g,index)=><SectionGroup key={`${g.section.id}-${index}`} section={g.section} blocks={g.blocks} continued={g.continued} {...shared}/>)
}
function SectionGroup({section:s,blocks,continued=false,mode,select,changed,addFact,sidebar=false,onEdit,onContext}:{section:Section;blocks:Block[];continued?:boolean;mode:'select'|'edit';select?:(s:string)=>void;changed:string[];addFact?:(s:string)=>void;sidebar?:boolean;onEdit?:(target:BlockRef)=>void;onContext?:(target:BlockRef,x:number,y:number)=>void}){
  if(!s.visibility)return null
  const canPick=factCategories(s.id).length>0
  return <section className={`resume-section ${sidebar?'sidebar-section':''} ${mode==='select'&&canPick?'selection-ready':''}`} onClick={()=>mode==='select'&&canPick&&select?.(s.id)}>
    <div className="template-section-title"><b>{s.title}{continued&&<span className="continued-mark">（续）</span>}</b>{mode==='edit'&&canPick&&<button className="mini-button" onClick={e=>{e.stopPropagation();addFact?.(s.id)}}>添加来源</button>}</div>
    {blocks.map(b=><BlockView key={b.id} section={s} block={b} mode={mode} changed={changed.includes(`${s.id}:${sourceIdOf(b)}`)} sidebar={sidebar} onEdit={onEdit} onContext={onContext}/>)}
  </section>
}
function BlockView({section:s,block:b,mode,changed,sidebar,onEdit,onContext}:{section:Section;block:Block;mode:'select'|'edit';changed:boolean;sidebar:boolean;onEdit?:(target:BlockRef)=>void;onContext?:(target:BlockRef,x:number,y:number)=>void}){const fields=b.fields||{};const fieldKeys=(b.display_fields||Object.keys(fields)).filter(k=>fields[k]);const sourceId=sourceIdOf(b);const labelsFor={...fieldLabels,...(b.field_labels||{})};const editClick=(e:ReactMouseEvent)=>{if(mode!=='edit')return;e.stopPropagation();onEdit?.({sectionId:s.id,blockId:sourceId,fragmentIndex:b.fragment_index??0})};const editContext=(e:ReactMouseEvent)=>{if(mode!=='edit')return;e.preventDefault();e.stopPropagation();onContext?.({sectionId:s.id,blockId:sourceId,fragmentIndex:b.fragment_index??0},e.clientX,e.clientY)};const showTitle=!!b.title&&b.title!==s.title;return <article className={`resume-block ${changed?'changed-block':''} ${b.continuation?'continuation-block':''} ${mode==='edit'?'editable-block':''}`} data-block-key={`${s.id}:${sourceId}`} onClick={editClick} onContextMenu={editContext} title={mode==='edit'?'点击编辑，右键更多操作':undefined}><div className="block-head">{showTitle&&<b>{b.title}</b>}{b.continuation&&<small className="continuation-label">续</small>}{mode==='edit'&&b.source_refs.length>0&&<small className={`source-tag${changed?' alert':''}`}>{changed?'来源已变化':'事实来源'}</small>}</div>{fieldKeys.length>0&&<div className="block-meta">{fieldKeys.map(k=><span key={k}><b>{labelsFor[k]||k}</b> {fields[k]}</span>)}</div>}<p className="block-copy" dangerouslySetInnerHTML={{__html:mdLite(b.content)}}/></article>}
function BlockEditor({content,target,changed,update,removeBlock,close}:{content:Content;target:BlockRef;changed:boolean;update:UpdateBlock;removeBlock:(sid:string,bid:string)=>void;close:()=>void}){
  const s=content.sections.find(x=>x.id===target.sectionId)
  const block=s?.blocks.find(x=>x.id===target.blockId)
  const factId=block&&block.source_refs.length?block.source_refs[0]:0
  const fact=useLoad<Fact|null>(factId?`/api/facts/${factId}`:'',null)
  const copyRef=useRef<HTMLTextAreaElement|null>(null)
  if(!s||!block)return null
  const fields=block.fields||{}
  const fieldKeys=(block.display_fields||Object.keys(fields)).filter(k=>fields[k])
  const labelsFor={...fieldLabels,...(block.field_labels||{})}
  const chunks=splitText(block.content||'',fragmentLimit(target.sectionId))
  const copy=chunks[target.fragmentIndex]||''
  const fragmentLabel=target.fragmentIndex>0?`正文 · 续段 ${target.fragmentIndex+1}`:'正文'
  const canRemove=block.source_refs.length>0
  const writeCopy=(next:string,start:number,len:number)=>{update(target.sectionId,target.blockId,next,'content',undefined,target.fragmentIndex);requestAnimationFrame(()=>{const el=copyRef.current;if(!el)return;el.focus();el.setSelectionRange(start,start+len)})}
  const wrapSelection=(before:string,after:string,placeholder:string)=>{const el=copyRef.current;if(!el)return;const start=el.selectionStart??0,end=el.selectionEnd??0;const sel=copy.slice(start,end)||placeholder;writeCopy(copy.slice(0,start)+before+sel+after+copy.slice(end),start+before.length,sel.length)}
  const makeList=()=>{const el=copyRef.current;if(!el)return;const start=el.selectionStart??0,end=el.selectionEnd??0;const sel=copy.slice(start,end)||'列表内容';const lines=sel.split('\n').map(l=>l.trim()?`- ${l}`:l).join('\n');writeCopy(copy.slice(0,start)+lines+copy.slice(end),start,lines.length)}
  const addLink=()=>{const el=copyRef.current;if(!el)return;const start=el.selectionStart??0,end=el.selectionEnd??0;const sel=copy.slice(start,end);if(!sel)return;const url=window.prompt('链接地址（https://…）');if(!url)return;const snippet=`[${sel}](${url})`;writeCopy(copy.slice(0,start)+snippet+copy.slice(end),start,snippet.length)}
  return <Modal title={`编辑 · ${labels[target.sectionId]} · ${block.title}`} close={close}>
    <Field label="条目标题"><input value={block.title} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'title')}/></Field>
    {fieldKeys.length>0&&<div className="block-editor-fields">{fieldKeys.map(k=><Field key={k} label={labelsFor[k]||k}><input value={fields[k]} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'field',k)}/></Field>)}</div>}
    <Field label={fragmentLabel} hint="支持 Markdown 子集：**粗体**、*斜体*、- 列表、[文字](链接)。修改会同步到工作副本并自动保存草稿。">
      <div className="format-bar">
        <button type="button" onClick={()=>wrapSelection('**','**','加粗文字')}>粗体</button>
        <button type="button" onClick={()=>wrapSelection('*','*','斜体文字')}>斜体</button>
        <button type="button" onClick={makeList}>列表</button>
        <button type="button" onClick={addLink}>链接</button>
      </div>
      <textarea ref={copyRef} className="block-editor-copy" value={copy} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'content',undefined,target.fragmentIndex)}/>
    </Field>
    {block.source_refs.length>0?(
      <div className={`source-note${changed?' changed':''}`}>
        <header><b>来源提醒</b><span>{changed?'来源已变化':'事实来源 · 一致'}</span></header>
        <p><b>原始事实</b>：{fact.data?brief(fact.data):'加载中…'}</p>
        <p>编辑区中的措辞是简历正文；事实库后续修改不会自动改写这里。</p>
        {fact.data&&fact.data.evidence_count>0&&<small>该事实关联 {fact.data.evidence_count} 份证据；证据默认不出现在正文。</small>}
      </div>
    ):(
      <div className="source-note user-note">
        <header><b>来源提醒</b><span>{block.origin==='ai'?'AI 内容':'用户内容'}</span></header>
        <p>此段没有事实来源，将以用户内容呈现，不伪装为事实来源。</p>
      </div>
    )}
    <div className="modal-actions">
      {canRemove&&<button className="button danger" onClick={()=>{if(confirm('移除该条目？此操作只影响当前工作副本。')){removeBlock(target.sectionId,target.blockId);close()}}}><Trash2 size={14}/>移除条目</button>}
      <button className="button primary" onClick={close}>完成</button>
    </div>
  </Modal>
}

function BlockContextMenu({menu,block,canMoveUp,canMoveDown,onEdit,onAddSource,onRemove,onMove,onClose}:{menu:BlockMenu;block:Block|null;canMoveUp:boolean;canMoveDown:boolean;onEdit:(target:BlockRef)=>void;onAddSource:(sectionId:string)=>void;onRemove:(sectionId:string)=>void;onMove:(sectionId:string,dir:1|-1)=>void;onClose:()=>void}){
  const canAdd=factCategories(menu.sectionId).length>0
  const canRemove=!!block&&block.source_refs.length>0
  const left=Math.max(8,Math.min(menu.x,window.innerWidth-190))
  const top=Math.max(8,Math.min(menu.y,window.innerHeight-220))
  return <>
    <div className="context-menu-layer" onClick={onClose} onContextMenu={e=>{e.preventDefault();onClose()}}/>
    <div className="context-menu" style={{left,top}} onClick={e=>e.stopPropagation()}>
      <button onClick={()=>onEdit({sectionId:menu.sectionId,blockId:menu.blockId,fragmentIndex:menu.fragmentIndex})}><FilePenLine size={15}/>编辑文本</button>
      {canAdd&&<button onClick={()=>onAddSource(menu.sectionId)}><Plus size={15}/>添加来源</button>}
      {canRemove&&<button disabled={!canMoveUp} onClick={()=>onMove(menu.sectionId,-1)}>↑ 上移条目</button>}
      {canRemove&&<button disabled={!canMoveDown} onClick={()=>onMove(menu.sectionId,1)}>↓ 下移条目</button>}
      {canRemove&&<button className="danger" onClick={()=>{if(confirm('移除该条目？此操作只影响当前工作副本。'))onRemove(menu.sectionId)}}><Trash2 size={15}/>移除条目</button>}
      <button className="muted" onClick={onClose}>取消</button>
    </div>
  </>
}
function BenchHead({title,subtitle,back,compact=false}:{title:string;subtitle:string;back:()=>void;compact?:boolean}){return <header className={`workbench-head${compact?' compact':''}`}><button className="back-btn" onClick={back}><ArrowLeft size={15}/>返回</button><div><p className="eyebrow">{title}</p><h1>{subtitle}</h1></div><span className="a4-state">固定 A4</span></header>}
function Title({crumb,title,desc,back,action}:{crumb:string;title:string;desc:string;back:()=>void;action?:ReactNode}){return <><div className="breadcrumb"><button className="back-btn" onClick={back}><ArrowLeft size={15}/>返回概览</button><span>/ {crumb}</span></div><header className="page-title"><div><p className="eyebrow">{crumb}</p><h1>{title}</h1><p>{desc}</p></div>{action}</header></>}
function Field({label,hint,children}:{label:string;hint?:string;children:ReactNode}){return <label className="field"><b>{label}</b>{hint&&<small>{hint}</small>}{children}</label>}
function Modal({title,close,children}:{title:string;close:()=>void;children:ReactNode}){
  useEffect(()=>{const h=(e:KeyboardEvent)=>{if(e.key==='Escape')close()};window.addEventListener('keydown',h);return()=>window.removeEventListener('keydown',h)},[close])
  return <div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)close()}}><section className="modal"><header><h2>{title}</h2><button className="icon-btn" onClick={close}><X size={18}/></button></header><div className="modal-body">{children}</div></section></div>
}
function Loading(){return <div className="loading"><LoaderCircle size={18}/>正在加载</div>}; function Empty({icon:Icon,title,body}:{icon:any;title:string;body:string}){return <div className="empty"><Icon size={25}/><h3>{title}</h3><p>{body}</p></div>}

async function downloadExport(id:number,version:number){const base=import.meta.env.VITE_API_URL||'http://127.0.0.1:8000';const r=await fetch(`${base}/api/resumes/${id}/versions/${version}/export`,{method:'POST'});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'导出失败');const blob=await r.blob();const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`resume-v${version}.html`;a.click();URL.revokeObjectURL(url)}
