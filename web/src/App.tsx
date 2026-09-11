import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react'
import { AlertTriangle, ArchiveRestore, ArrowLeft, BookOpen, BriefcaseBusiness, ChevronRight, CircleAlert, Download, FilePenLine, FileUp, History, Library, LoaderCircle, Plus, Search, Trash2, X } from 'lucide-react'
import { api, del, patch, post, upload } from './api'

type CustomField = { key:string; label:string; value:string; displayable:boolean; sort_order:number }
type Fact = { id:number; category:string; title:string; content:Record<string,string>; details:Record<string,string>; custom_fields:CustomField[]; display_fields:string[]; tags:string[]; status:string; updated_at:string; evidence_count:number }
type Profile = { id:number; name:string; role_direction:string; core_requirements:string[]; resume_strategy:string; raw_jd:string; status:string; updated_at:string; active_resume_id?:number }
type Block = { id:string; title:string; content:string; fields?:Record<string,string>; field_labels?:Record<string,string>; display_fields?:string[]; source_refs:number[]; origin:string; fragment_index?:number; continuation?:boolean }
type Section = { id:string; title:string; visibility:boolean; blocks:Block[] }
type Content = { sections:Section[] }
type Resume = { id:number; display_name:string; profile_name:string; current_version:number; updated_at:string; dirty:boolean; warnings:number; status:string }
type Pending = { resume_id:number; affected:{section_id:string;block_id:string}[] }
type BlockRef = { sectionId:string; blockId:string; fragmentIndex:number }
type BlockMenu = BlockRef & { x:number; y:number }
type UpdateBlock = (sectionId:string, blockId:string, value:string, key?:'content'|'title'|'field', fieldKey?:string, fragmentIndex?:number)=>void

const labels:Record<string,string> = { basics:'基本信息', target:'求职目标', profile:'个人简介', education:'教育经历', experience:'项目与实践', skills:'技能', awards:'成果', links:'链接与作品集' }
const categories = ['basics','education','experience','skills','awards','links']
const fieldLabels:Record<string,string> = { name:'姓名', phone:'电话', email:'邮箱', city:'所在地', desired_city:'目标城市', birth_date:'出生日期', age:'年龄', hometown:'籍贯', status:'身份状态', graduation:'毕业时间', availability:'到岗安排', bio:'个人简介', school:'学校', major:'专业', degree:'学历', start_date:'入学时间', end_date:'毕业时间', period:'时间', gpa:'GPA', ranking:'专业排名', achievement:'成绩与成果', courses:'相关课程', kind:'经历类型', organization:'组织/公司', role:'角色', team_size:'团队规模', context:'背景/使用场景', work:'具体工作', tools:'工具与技术', outcome:'结果', challenge:'挑战', solution:'解决方案', public_note:'公开说明', skill_category:'技能分类', proficiency:'熟练程度', issuer:'颁发方', result:'结果', note:'说明', link_type:'链接类型', url:'地址', label:'显示名称' }
const date = (v?:string) => v ? new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium'}).format(new Date(v)) : '—'
const brief = (f:Fact) => Object.values(f.details || f.content || {}).filter(Boolean).slice(0,3).join(' · ') || '尚未补充详细信息'
const section = (content:Content,id:string):Section => content.sections.find(s=>s.id===id) || {id,title:labels[id],visibility:true,blocks:[]}
const sourceIdOf = (b:Block) => b.id.split('--fragment-')[0]
const factCategories = (id:string) => id === 'basics' || id === 'profile' ? ['basics'] : id === 'target' ? [] : [id]

export default function App(){
  const [page,setPage] = useState<'home'|'facts'|'profiles'|'resumes'|'compose'|'editor'>('home')
  const [error,setError] = useState(''); const [profile,setProfile] = useState<Profile|null>(null); const [linked,setLinked] = useState<number|null>(null); const [resume,setResume] = useState<number|null>(null)
  const pending = useLoad<Pending[]>('/api/pending-items',[])
  const create = async (p:Profile) => { try { const r=await post<{id:number}>(`/api/linked-resumes?profile_id=${p.id}`); setProfile(p); setLinked(r.id); setPage('compose') } catch(e) { setError((e as Error).message) } }
  const openResume = (id:number) => { setResume(id); setPage('editor') }
  return <div className="app-shell"><header className="topbar"><button className="brand" onClick={()=>setPage('home')}><span>R</span>ResumeCraft</button><button className="icon-btn badge" onClick={()=>setPage('resumes')} title="来源变化"><CircleAlert size={19}/>{pending.data.length>0&&<i>{pending.data.length}</i>}</button></header>{error&&<div className="flash"><AlertTriangle size={16}/>{error}<button onClick={()=>setError('')}><X size={15}/></button></div>}{page==='home'&&<Home go={setPage}/>} {page==='facts'&&<Facts back={()=>setPage('home')} error={setError}/>} {page==='profiles'&&<Profiles back={()=>setPage('home')} create={create} open={openResume} error={setError}/>} {page==='resumes'&&<Resumes back={()=>setPage('home')} open={openResume} create={()=>setPage('profiles')} pending={pending.data}/>} {page==='compose'&&profile&&linked&&<Composer id={linked} profile={profile} back={()=>setPage('profiles')} open={openResume} error={setError}/>} {page==='editor'&&resume&&<Editor id={resume} back={()=>setPage('resumes')} error={setError} refresh={pending.reload}/>}</div>
}

function useLoad<T>(path:string, initial:T){ const [data,setData]=useState<T>(initial); const [loading,setLoading]=useState(true); const [tick,setTick]=useState(0); useEffect(()=>{let live=true;setLoading(true);api<T>(path).then(v=>live&&setData(v)).catch(()=>{}).finally(()=>live&&setLoading(false));return()=>{live=false}},[path,tick]); return {data,loading,reload:()=>setTick(v=>v+1)} }
function Home({go}:{go:(p:any)=>void}){ const data=useLoad<{stats:Record<string,number>}>('/api/overview',{stats:{facts:0,profiles:0,resumes:0,working_copies:0}}); const modules=[[Library,'资料库','按分类维护事实与证据','facts'],[BriefcaseBusiness,'岗位画像','组织招聘要求和简历策略','profiles'],[FilePenLine,'ResumeCraft','在 A4 简历上直接工作','resumes']] as const; return <main className="page home"><p className="eyebrow">PERSONAL RESUME SYSTEM</p><h1>让经历沉淀为<br/><em>可持续维护的简历</em></h1><p className="lead">资料保持真实中立，岗位决定表达重点，版本记录每次正式交付。</p><section className="module-grid">{modules.map(([I,t,d,k])=><button className="module-card" key={k} onClick={()=>go(k)}><I size={22}/><h2>{t}</h2><p>{d}</p><ChevronRight size={16}/></button>)}</section><section className="stat-row">{[['事实资料',data.data.stats.facts],['岗位画像',data.data.stats.profiles],['正式简历',data.data.stats.resumes],['工作副本',data.data.stats.working_copies]].map(x=><div key={String(x[0])}><b>{x[1]}</b><span>{x[0]}</span></div>)}</section></main> }

function Facts({back,error}:{back:()=>void;error:(s:string)=>void}){
  const facts=useLoad<Fact[]>('/api/facts',[]), recycled=useLoad<Fact[]>('/api/facts?include_recycled=true',[])
  const [cat,setCat]=useState<string|null>(null),[q,setQ]=useState(''),[edit,setEdit]=useState<Fact|null>(null),[recycle,setRecycle]=useState(false)
  const list=(recycle?recycled.data.filter(f=>f.status==='recycled'):facts.data).filter(f=>(!cat||f.category===cat)&&`${f.title} ${brief(f)}`.toLowerCase().includes(q.toLowerCase()))
  const count=(k:string)=>facts.data.filter(f=>f.category===k).length
  return <main className="page">
    <Title crumb="资料库" title={cat?labels[cat]:'资料库'} desc={cat?'点击条目审阅详情、编辑分类字段或补充证据。':'按类别沉淀事实，所有详细字段都会保留。'} back={back} action={<div className="header-actions"><button className="button" onClick={()=>{setRecycle(!recycle);setCat(null)}}>{recycle?<ArchiveRestore size={15}/>:<Trash2 size={15}/>} {recycle?'返回资料库':'回收站'}</button><button className="button primary" onClick={()=>setEdit({id:0,category:cat||'experience',title:'',content:{},details:{},custom_fields:[],display_fields:[],tags:[],status:'active',updated_at:'',evidence_count:0})}><Plus size={16}/>新增资料</button></div>}/>
    <div className="filterbar"><Search size={16}/><input placeholder="搜索资料名称、详情或关键词" value={q} onChange={e=>setQ(e.target.value)}/></div>
    {!cat&&!q&&!recycle?<section className="library-grid">{categories.map(k=><button className="library-card" key={k} onClick={()=>setCat(k)}><BookOpen size={18}/><span><b>{labels[k]}</b><small>{count(k)} 条资料</small></span><ChevronRight size={15}/></button>)}</section>:<><nav className="category-tabs"><button className={!cat?'active':''} onClick={()=>setCat(null)}>全部</button>{categories.map(k=><button key={k} className={cat===k?'active':''} onClick={()=>setCat(k)}>{labels[k]}</button>)}</nav><section className="data-table"><div className="table-head"><span>资料名称</span><span>摘要</span><span>证据</span><span>更新时间</span></div>{(recycle?recycled.loading:facts.loading)?<Loading/>:list.length?list.map(f=><button className="table-row" key={f.id} onClick={()=>setEdit(f)}><span><b>{f.title}</b><small>{labels[f.category]}{f.status==='recycled'?' · 已回收':''}</small></span><span>{brief(f)}</span><span>{f.evidence_count?`${f.evidence_count} 份`:'未添加'}</span><time>{date(f.updated_at)}</time></button>):<Empty icon={BookOpen} title="没有匹配资料" body="可以新增资料，或调整搜索条件。"/>}</section></>}
    {edit&&<FactModal fact={edit} close={()=>setEdit(null)} done={()=>{setEdit(null);facts.reload();recycled.reload()}} error={error}/>}
  </main>
}

function FactModal({fact,close,done,error}:{fact?:Fact;close:()=>void;done:()=>void;error:(s:string)=>void}){
  const [title,setTitle]=useState(fact?.title||''),[cat,setCat]=useState(fact?.category||'experience'),[details,setDetails]=useState<Record<string,string>>(fact?.details||fact?.content||{}),[custom,setCustom]=useState<CustomField[]>(fact?.custom_fields||[]),[evidence,setEvidence]=useState(false),[saving,setSaving]=useState(false)
  useEffect(()=>{setTitle(fact?.title||'');setCat(fact?.category||'experience');setDetails(fact?.details||fact?.content||{});setCustom(fact?.custom_fields||[])},[fact])
  const schema=useLoad<{key:string;label:string;type:string;required:boolean}[]>(`/api/fact-schemas/${cat}`,[])
  const set=(key:string,value:string)=>setDetails(v=>({...v,[key]:value}))
  const save=async()=>{setSaving(true);try{const body={title,category:cat,details,content:details,custom_fields:custom.filter(x=>x.key.trim()),tags:fact?.tags||[],status:fact?.status==='recycled'?'recycled':'active'};fact&&fact.id?await patch(`/api/facts/${fact.id}`,body):await post('/api/facts',body);done()}catch(e){error((e as Error).message)}finally{setSaving(false)}}
  const remove=async()=>{if(!fact||!confirm('确认删除？正式简历引用过的资料会进入回收站。'))return;try{await del(`/api/facts/${fact.id}`);done()}catch(e){error((e as Error).message)}}
  const addCustom=()=>setCustom(v=>[...v,{key:`custom_${v.length+1}`,label:'自定义字段',value:'',displayable:true,sort_order:v.length}])
  return <Modal title={fact?.id?`编辑资料 · ${fact.title}`:'新增资料'} close={close}><Field label="资料分类"><select value={cat} onChange={e=>{setCat(e.target.value);setDetails({});setCustom([])}}>{categories.map(k=><option key={k} value={k}>{labels[k]}</option>)}</select></Field><Field label="资料名称" hint="用于列表识别，不替代分类详情。"><input autoFocus value={title} onChange={e=>setTitle(e.target.value)} placeholder="例如：越疆 X-Trainer 数据采集项目"/></Field><div className="fact-fields">{schema.loading?<Loading/>:schema.data.map(f=><Field key={f.key} label={`${f.label}${f.required?' *':''}`}>{f.type==='textarea'?<textarea value={details[f.key]||''} onChange={e=>set(f.key,e.target.value)} placeholder={`填写${f.label}，没有内容可以留空`}/>:<input type={f.type==='email'?'email':f.type==='url'?'url':'text'} value={details[f.key]||''} onChange={e=>set(f.key,e.target.value)} placeholder={`填写${f.label}，没有内容可以留空`}/>}</Field>)}</div><div className="custom-fields"><div className="custom-fields-head"><b>扩展字段</b><button className="mini-button" type="button" onClick={addCustom}><Plus size={13}/>添加字段</button></div>{custom.map((item,index)=><div className="custom-field-row" key={`${item.key}-${index}`}><input value={item.label} onChange={e=>setCustom(v=>v.map((x,i)=>i===index?{...x,label:e.target.value}:x))} placeholder="字段名称"/><input value={item.value} onChange={e=>setCustom(v=>v.map((x,i)=>i===index?{...x,value:e.target.value}:x))} placeholder="字段内容"/><button className="icon-btn" type="button" onClick={()=>setCustom(v=>v.filter((_,i)=>i!==index))}><X size={14}/></button></div>)}</div>{fact?.id&&<button className="evidence-link" onClick={()=>setEvidence(true)}><FileUp size={16}/>证据材料 <span>{fact.evidence_count} 份</span><ChevronRight size={15}/></button>}<div className="modal-actions">{fact?.status==='recycled'?<button className="button" onClick={async()=>{await post(`/api/facts/${fact.id}/restore`);done()}}><ArchiveRestore size={15}/>恢复资料</button>:fact?.id&&<button className="button danger" onClick={remove}><Trash2 size={15}/>删除</button>}<button className="button primary" disabled={!title.trim()||saving} onClick={save}>{saving?'保存中…':'保存资料'}</button></div>{evidence&&fact?.id&&<EvidenceModal fact={fact} close={()=>setEvidence(false)} error={error}/>}</Modal>
}

function EvidenceModal({fact,close,error}:{fact:Fact;close:()=>void;error:(s:string)=>void}){const list=useLoad<any[]>(`/api/facts/${fact.id}/evidence`,[]),[title,setTitle]=useState(''),[url,setUrl]=useState(''),[note,setNote]=useState(''),[file,setFile]=useState<File|null>(null);const save=async()=>{try{if(file){const fd=new FormData();fd.set('fact_id',String(fact.id));fd.set('title',title);fd.set('note',note);fd.set('file',file);await upload('/api/evidence/upload',fd)}else await post('/api/evidence',{fact_id:fact.id,title,url,note});setTitle('');setUrl('');setNote('');setFile(null);list.reload()}catch(e){error((e as Error).message)}};return <Modal title={`证据 · ${fact.title}`} close={close}><p className="modal-note">上传 PDF、PNG、JPEG、WEBP，或添加可验证链接。证据不会自动出现在简历正文。</p>{list.data.map(e=><div className="evidence-row" key={e.id}><FileUp size={15}/><span><b>{e.title}</b><small>{e.kind==='link'?e.url:e.filename}</small></span></div>)}<Field label="证据名称"><input value={title} onChange={e=>setTitle(e.target.value)}/></Field><Field label="上传文件或填写链接"><input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" onChange={e=>setFile(e.target.files?.[0]||null)}/><input value={url} disabled={!!file} onChange={e=>setUrl(e.target.value)} placeholder="https://..."/></Field><Field label="说明"><input value={note} onChange={e=>setNote(e.target.value)}/></Field><button className="button primary" disabled={!file&&!url.trim()} onClick={save}>添加证据</button></Modal> }

function Profiles({back,create,open,error}:{back:()=>void;create:(p:Profile)=>void;open:(id:number)=>void;error:(s:string)=>void}){const data=useLoad<Profile[]>('/api/requirement-profiles',[]),[edit,setEdit]=useState<Profile|null>(null);return <main className="page"><Title crumb="岗位画像" title="岗位画像" desc="先整理岗位要求，再选择最适合呈现的事实资料。" back={back} action={<button className="button primary" onClick={()=>setEdit({id:0,name:'',role_direction:'',core_requirements:[],resume_strategy:'',raw_jd:'',status:'active',updated_at:''})}><Plus size={16}/>新建岗位画像</button>}/><section className="profile-list">{data.loading?<Loading/>:data.data.map(p=><article className="profile-card" key={p.id}><div><p className="eyebrow">{p.role_direction||'岗位方向待补充'}</p><h2>{p.name}</h2><div className="chips">{p.core_requirements.map(x=><span key={x}>{x}</span>)}</div><p>{p.resume_strategy||'尚未设置简历强调方向。'}</p></div><div className="card-actions"><button className="button" onClick={()=>setEdit(p)}>编辑</button>{p.active_resume_id?<button className="button primary" onClick={()=>open(p.active_resume_id!)}>打开正式简历 <ChevronRight size={15}/></button>:<button className="button primary" onClick={()=>create(p)}>创建临时简历 <ChevronRight size={15}/></button>}</div></article>)}</section>{edit&&<ProfileModal profile={edit.id?edit:undefined} close={()=>setEdit(null)} done={()=>{setEdit(null);data.reload()}} create={create} error={error}/>}</main> }
function ProfileModal({profile,close,done,create,error}:{profile?:Profile;close:()=>void;done:()=>void;create:(p:Profile)=>void;error:(s:string)=>void}){const[name,setName]=useState(profile?.name||''),[role,setRole]=useState(profile?.role_direction||''),[req,setReq]=useState(profile?.core_requirements.join('、')||''),[strategy,setStrategy]=useState(profile?.resume_strategy||''),[jd,setJd]=useState(profile?.raw_jd||'');const save=async(start=false)=>{try{const body={name,role_direction:role,core_requirements:req.split(/[、，,]/).map(x=>x.trim()).filter(Boolean),resume_strategy:strategy,raw_jd:jd};const item=profile?await patch<Profile>(`/api/requirement-profiles/${profile.id}`,body):await post<Profile>('/api/requirement-profiles',body);done();if(start)create(item)}catch(e){error((e as Error).message)}};return <Modal title={profile?'编辑岗位画像':'新建岗位画像'} close={close}><Field label="画像名称"><input autoFocus value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="岗位方向"><input value={role} onChange={e=>setRole(e.target.value)}/></Field><Field label="核心技术要求"><input value={req} onChange={e=>setReq(e.target.value)} placeholder="Python、ROS2、数据标注"/></Field><Field label="简历强调方向"><textarea value={strategy} onChange={e=>setStrategy(e.target.value)}/></Field><details><summary>原始 JD 与来源</summary><textarea value={jd} onChange={e=>setJd(e.target.value)}/></details><div className="modal-actions"><button className="button" disabled={!name.trim()} onClick={()=>save(false)}>保存画像</button><button className="button primary" disabled={!name.trim()} onClick={()=>save(true)}>保存并选择资料</button></div></Modal> }

function Resumes({back,open,create,pending}:{back:()=>void;open:(id:number)=>void;create:()=>void;pending:Pending[]}){const data=useLoad<Resume[]>('/api/resumes',[]),recycled=useLoad<Resume[]>('/api/resumes?include_recycled=true',[]),[recycle,setRecycle]=useState(false);const rows=(recycle?recycled.data:data.data).filter(r=>recycle?r.status==='recycled':r.status==='active');const restore=async(id:number)=>{try{await post(`/api/resumes/${id}/restore`);data.reload();recycled.reload()}catch(e){console.error(e)}};return <main className="page"><Title crumb="ResumeCraft" title={recycle?'简历回收站':'正式简历'} desc={recycle?'已删除的正式简历仍可查看和恢复。':'每次正式保存都会增加一个不可变版本。'} back={back} action={<div className="header-actions">{!recycle&&<button className="button primary" onClick={create}><Plus size={16}/>创建临时简历</button>}<button className="button" onClick={()=>setRecycle(!recycle)}>{recycle?<ArchiveRestore size={15}/>:<Trash2 size={15}/>} {recycle?'返回正式简历':'回收站'}</button></div>}/>{!recycle&&pending.length>0&&<div className="warning-banner"><CircleAlert size={18}/><div><b>{pending.length} 项来源变化待处理</b><span>进入简历后，变化会直接标记在受影响的条目上。</span></div></div>}<section className="list-panel">{(data.loading||recycled.loading)?<Loading/>:rows.length?rows.map(r=><article className="resume-row" key={r.id} onClick={()=>open(r.id)}><FilePenLine size={18}/><span><b>{r.display_name}</b><small>v{r.current_version} · {date(r.updated_at)}{r.status==='recycled'?' · 已回收':''}</small></span>{r.status==='recycled'?<button className="button" onClick={e=>{e.stopPropagation();restore(r.id)}}><ArchiveRestore size={14}/>恢复</button>:<em>{r.warnings?`${r.warnings} 项来源变化`:'打开工作台'} <ChevronRight size={15}/></em>}</article>):<Empty icon={recycle?Trash2:FilePenLine} title={recycle?'回收站为空':'还没有正式简历'} body={recycle?'已删除的正式简历会保留在这里。':'从岗位画像创建一份临时简历开始。'}/>}</section></main> }

function Composer({id,profile,back,open,error}:{id:number;profile:Profile;back:()=>void;open:(id:number)=>void;error:(s:string)=>void}){const linked=useLoad<{selection:Record<string,number[]>;preview:Content}>(`/api/linked-resumes/${id}`,{selection:{},preview:{sections:[]}}),facts=useLoad<Fact[]>('/api/facts',[]),[sectionId,setSectionId]=useState<string|null>(null),[convertLoading,setConvertLoading]=useState(false);const toggle=async(fid:number)=>{if(!sectionId)return;const old=linked.data.selection[sectionId]||[],next={...linked.data.selection,[sectionId]:old.includes(fid)?old.filter(x=>x!==fid):[...old,fid]};try{await patch(`/api/linked-resumes/${id}`,{selection:next});linked.reload()}catch(e){error((e as Error).message)}};const convert=async()=>{if(convertLoading)return;setConvertLoading(true);try{open((await post<{resume_id:number}>(`/api/linked-resumes/${id}/convert`)).resume_id)}catch(e){error((e as Error).message)}finally{setConvertLoading(false)}};return <main className="workbench"><BenchHead title="临时简历" subtitle={`${profile.name} · ${profile.core_requirements.join('、')||'未设置核心要求'}`} back={back}/><p className="canvas-hint">初始画布只显示栏目；点击栏目选择事实资料，内容增加后自动续为 A4 页面。</p>{linked.loading?<Loading/>:<Canvas content={linked.data.preview} mode="select" select={id=>factCategories(id).length&&setSectionId(id)}/>}<footer className="actionbar"><button className="button" onClick={back}>退出选择</button><button className="button primary" disabled={linked.loading||convertLoading} onClick={convert}>{convertLoading?'正在生成…':'生成格式化简历'} {!convertLoading&&<ChevronRight size={16}/>}</button></footer>{sectionId&&<Picker title={labels[sectionId]} facts={facts.data.filter(f=>factCategories(sectionId).includes(f.category))} chosen={linked.data.selection[sectionId]||[]} toggle={toggle} close={()=>setSectionId(null)}/>}</main> }
function Picker({title,facts,chosen,toggle,close}:{title:string;facts:Fact[];chosen:number[];toggle:(id:number)=>void;close:()=>void}){const[q,setQ]=useState('');const shown=facts.filter(f=>`${f.title} ${brief(f)}`.toLowerCase().includes(q.toLowerCase()));return <div className="selection-backdrop"><section className="selection-modal"><header><div><p className="eyebrow">选择事实资料</p><h2>{title}</h2></div><button className="icon-btn" onClick={close}><X size={18}/></button></header><div className="filterbar"><Search size={16}/><input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="搜索资料名称或详情"/></div><div className="selection-list">{shown.map(f=><label key={f.id}><input type="checkbox" checked={chosen.includes(f.id)} onChange={()=>toggle(f.id)}/><span><b>{f.title}</b><small>{brief(f)}</small></span></label>)}</div><footer><span>已选择 {chosen.length} 条</span><button className="button primary" onClick={close}>完成选择</button></footer></section></div> }

function Editor({id,back,error,refresh}:{id:number;back:()=>void;error:(s:string)=>void;refresh:()=>void}){
  const resume=useLoad<any>(`/api/resumes/${id}`,null)
  const versions=useLoad<any[]>(`/api/resumes/${id}/versions`,[])
  const facts=useLoad<Fact[]>('/api/facts',[])
  const pending=useLoad<Pending[]>('/api/pending-items',[])
  const [content,setContent]=useState<Content|null>(null)
  const [restore,setRestore]=useState<number|null>(null)
  const [pick,setPick]=useState<string|null>(null)
  const [saving,setSaving]=useState(false)
  const [editing,setEditing]=useState<BlockRef|null>(null)
  const [menu,setMenu]=useState<BlockMenu|null>(null)
  useEffect(()=>{if(resume.data)setContent(resume.data.working_copy.content)},[resume.data])
  useEffect(()=>{if(!content||!resume.data||resume.data.status==='recycled')return;const t=window.setTimeout(()=>patch(`/api/resumes/${id}/working-copy`,{content}).catch(e=>error(e.message)),500);return()=>clearTimeout(t)},[content,id])
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
        next.content=chunks.join('\n')
        return next
      })}
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
  const exportVersion=async(v:number)=>{try{await downloadExport(id,v)}catch(e){error((e as Error).message)}}
  const openEdit=(target:BlockRef)=>{setMenu(null);setEditing(target)}
  const openMenu=(target:BlockRef,x:number,y:number)=>{setEditing(null);setMenu({...target,x,y})}
  const addSource=(sid:string)=>{setMenu(null);setPick(sid)}
  return <main className="workbench">
    <BenchHead title={`正式简历 · v${resume.data.current_version}`} subtitle={`${resume.data.profile_name} · ${readOnly?'已移入回收站':resume.data.working_copy.dirty?'工作副本有未保存修改':'工作副本已同步'}`} back={back}/>
    {changed.length>0&&!readOnly&&<div className="warning-banner compact"><CircleAlert size={17}/><div><b>来源资料已变化</b><span>受影响条目已标记；正文没有被自动改写。</span></div></div>}
    <Canvas content={content} mode={readOnly?'select':'edit'} changed={changed} addFact={setPick} onEdit={openEdit} onContext={openMenu}/>
    <section className="version-panel">
      <header><History size={17}/><h2>版本历史</h2></header>
      {versions.data.map(v=><div className="version-row" key={v.id}><span><b>v{v.version_number}</b><small>{v.reason==='format_conversion'?'格式化简历、未润色':v.change_summary} · {date(v.created_at)}</small></span><div className="card-actions"><button className="button" onClick={()=>exportVersion(v.version_number)}><Download size={14}/>导出 HTML</button>{!readOnly&&v.version_number!==resume.data.current_version&&<button className="button" onClick={()=>setRestore(v.version_number)}>以 v{v.version_number} 创建工作副本</button>}</div></div>)}
    </section>
    <footer className="actionbar">
      {readOnly
        ? <button className="button primary" onClick={async()=>{try{await post(`/api/resumes/${id}/restore`);resume.reload();versions.reload()}catch(e){error((e as Error).message)}}}><ArchiveRestore size={15}/>恢复简历</button>
        : <button className="button danger" onClick={async()=>{if(confirm('正式简历将进入回收站，历史版本会保留。确认继续？')){await del(`/api/resumes/${id}`);back()}}}><Trash2 size={15}/>删除简历</button>}
      <button className="button" onClick={()=>exportVersion(resume.data.current_version)}><Download size={15}/>导出正式简历</button>
      <button className="button primary" disabled={saving||readOnly} onClick={save}>{saving?'保存中…':readOnly?'已回收':'保存正式版本'}</button>
    </footer>
    {!readOnly&&pick&&<Picker title={`为${labels[pick]}添加来源`} facts={facts.data.filter(f=>factCategories(pick).includes(f.category))} chosen={[]} toggle={fid=>{const f=facts.data.find(x=>x.id===fid);if(f)addFact(f)}} close={()=>setPick(null)}/>}
    {!readOnly&&restore!==null&&<Modal title="以历史版本创建工作副本" close={()=>setRestore(null)}><p className="modal-note">将以 v{restore} 替换当前工作副本，历史版本不受影响。</p><div className="modal-actions"><button className="button" onClick={()=>setRestore(null)}>保留当前草稿</button><button className="button primary" onClick={async()=>{try{await post(`/api/resumes/${id}/versions/${restore}/restore`);setRestore(null);resume.reload();versions.reload()}catch(e){error((e as Error).message)}}}>创建工作副本</button></div></Modal>}
    {!readOnly&&editing&&<BlockEditor content={content} target={editing} update={update} close={()=>setEditing(null)}/>}
    {!readOnly&&menu&&<BlockContextMenu menu={menu} onEdit={target=>openEdit(target)} onAddSource={addSource} onClose={()=>setMenu(null)}/>}
  </main>
}

function factBlock(f:Fact,sid:string):Block{const d=f.details||f.content||{};const fields=Object.fromEntries(Object.entries(d).filter(([,v])=>v));if(sid==='profile')delete fields.bio;const extra=(f.custom_fields||[]).filter(x=>x.value);const field_labels=Object.fromEntries(extra.map(x=>[x.key,x.label||x.key]));extra.forEach(x=>{fields[x.key]=x.value});const standard=sid==='profile'?(d.bio?['bio']:['summary']):sid==='basics'?['phone','email','city','desired_city','hometown','status','graduation','availability']:sid==='education'?['period','major','degree','gpa','ranking']:sid==='experience'?['period','organization','role','team_size','tools']:sid==='skills'?['skill_category','proficiency']:sid==='awards'?['period','issuer','result']:['link_type','label','url'];const display_fields=standard.filter(k=>fields[k]).concat(extra.filter(x=>x.displayable).map(x=>x.key));const content=sid==='profile'?(d.bio||d.summary||''):sid==='education'?[d.achievement,d.courses].filter(Boolean).join('\n'):sid==='experience'?['context','work','outcome','challenge','solution','public_note'].map(k=>d[k]).filter(Boolean).join('\n'):sid==='skills'?(d.context||''):sid==='awards'?(d.note||''):sid==='links'?(d.note||''):'';return {id:`fact-${f.id}-${Date.now()}`,type:'fact',title:f.title,content:content||brief(f),fields,field_labels,display_fields,source_refs:[f.id],origin:'fact'} as Block}
function splitText(value:string,max=900){if(!value)return [''];const chunks:string[]=[];for(let start=0;start<value.length;start+=max)chunks.push(value.slice(start,start+max));return chunks}
const fragmentLimit=(sid:string)=>['basics','skills','awards'].includes(sid)?520:900
function paginate(content:Content){
  const mainIds=['target','profile','experience','education','links'],sideIds=['basics','skills','awards'];
  const units:Section[]=[];
  for(const id of mainIds){const original=section(content,id);if(!original.blocks.length){units.push(original);continue}for(const block of original.blocks){const chunks=splitText(block.content||'');chunks.forEach((chunk,index)=>units.push({...original,blocks:[{...block,id:index?`${block.id}--fragment-${index}`:block.id,content:chunk,fields:index===0?block.fields:{},display_fields:index===0?block.display_fields:[],fragment_index:index,continuation:index>0}]}))}}
  const sideUnits:Section[]=[];
  for(const id of sideIds){const original=section(content,id);if(!original.blocks.length){sideUnits.push(original);continue}for(const block of original.blocks){const chunks=splitText(block.content||'',520);chunks.forEach((chunk,index)=>sideUnits.push({...original,blocks:[{...block,id:index?`${block.id}--fragment-${index}`:block.id,content:chunk,fields:index===0?block.fields:{},display_fields:index===0?block.display_fields:[],fragment_index:index,continuation:index>0}]}))}}
  const pages:{main:Section[];side:Section[];first:boolean}[]=[];let current:Section[]=[];let size=0;
  for(const unit of units){const block=unit.blocks[0];const weight=110+Math.max(40,(block?.content?.length||0)*1.2)+(Object.keys(block?.fields||{}).length*30);if(current.length&&size+weight>2500){pages.push({main:current,side:[],first:pages.length===0});current=[];size=0}current.push(unit);size+=weight}
  if(current.length||!pages.length)pages.push({main:current,side:[],first:pages.length===0});
  const sidePages:Section[][]=[];let sideCurrent:Section[]=[];let sideSize=0;
  for(const unit of sideUnits){const block=unit.blocks[0];const weight=80+Math.max(25,(block?.content?.length||0)*.8)+(Object.keys(block?.fields||{}).length*18);if(sideCurrent.length&&sideSize+weight>1550){sidePages.push(sideCurrent);sideCurrent=[];sideSize=0}sideCurrent.push(unit);sideSize+=weight}
  if(sideCurrent.length)sidePages.push(sideCurrent);
  const count=Math.max(pages.length,sidePages.length,1);
  while(pages.length<count)pages.push({main:[],side:[],first:false});
  pages.forEach((page,index)=>{page.side=sidePages[index]||[]});
  return {pages}
}
function Canvas({content,mode,select,changed=[],addFact,onEdit,onContext}:{content:Content;mode:'select'|'edit';select?:(s:string)=>void;changed?:string[];addFact?:(s:string)=>void;onEdit?:(target:BlockRef)=>void;onContext?:(target:BlockRef,x:number,y:number)=>void}){const p=paginate(content);return <section className={`resume-stage ${mode==='edit'?'edit-mode':'select-mode'}`}>{p.pages.map((page,i)=><Paper key={i} number={i+1} sidebar={page.side.length?<Sidebar sections={page.side} mode={mode} select={select} changed={changed} addFact={addFact} onEdit={onEdit} onContext={onContext}/>:<div className="continuation-mark">RESUME / {String(i+1).padStart(2,'0')}</div>}><div className="main-sections">{page.main.map((s,n)=><ResumeSection key={`${s.id}-${s.blocks[0]?.id||'empty'}-${n}`} section={s} mode={mode} select={select} changed={changed} addFact={addFact} onEdit={onEdit} onContext={onContext}/>)}</div></Paper>)}</section>}
function Paper({number,sidebar,children}:{number:number;sidebar:ReactNode;children:ReactNode}){return <article className="resume-paper"><aside className="resume-sidebar">{sidebar}</aside><main className="resume-main">{children}</main></article>}
function Sidebar({sections,mode,select,changed,addFact,onEdit,onContext}:{sections:Section[];mode:'select'|'edit';select?:(s:string)=>void;changed:string[];addFact?:(s:string)=>void;onEdit?:(target:BlockRef)=>void;onContext?:(target:BlockRef,x:number,y:number)=>void}){return <div className="sidebar-content">{sections.map((s,index)=><ResumeSection key={`${s.id}-${s.blocks[0]?.id||'empty'}-${index}`} section={s} mode={mode} select={select} changed={changed} addFact={addFact} onEdit={onEdit} onContext={onContext} sidebar/>)}</div>}
function ResumeSection({section:s,mode,select,changed,addFact,sidebar=false,onEdit,onContext}:{section:Section;mode:'select'|'edit';select?:(s:string)=>void;changed:string[];addFact?:(s:string)=>void;sidebar?:boolean;onEdit?:(target:BlockRef)=>void;onContext?:(target:BlockRef,x:number,y:number)=>void}){if(!s.visibility)return null;const canPick=factCategories(s.id).length>0;return <section className={`resume-section ${sidebar?'sidebar-section':''} ${mode==='select'&&canPick?'selection-ready':''}`} onClick={()=>mode==='select'&&canPick&&select?.(s.id)}><div className="template-section-title"><b>{s.title}</b>{mode==='edit'&&canPick&&<button className="mini-button" onClick={e=>{e.stopPropagation();addFact?.(s.id)}}>添加来源</button>}</div>{s.blocks.map(b=><BlockView key={b.id} section={s} block={b} mode={mode} changed={changed.includes(`${s.id}:${sourceIdOf(b)}`)} sidebar={sidebar} onEdit={onEdit} onContext={onContext}/> )}</section>}
function BlockView({section:s,block:b,mode,changed,sidebar,onEdit,onContext}:{section:Section;block:Block;mode:'select'|'edit';changed:boolean;sidebar:boolean;onEdit?:(target:BlockRef)=>void;onContext?:(target:BlockRef,x:number,y:number)=>void}){const fields=b.fields||{};const fieldKeys=(b.display_fields||Object.keys(fields)).filter(k=>fields[k]);const sourceId=sourceIdOf(b);const labelsFor={...fieldLabels,...(b.field_labels||{})};const editClick=(e:ReactMouseEvent)=>{if(mode!=='edit')return;e.stopPropagation();onEdit?.({sectionId:s.id,blockId:sourceId,fragmentIndex:b.fragment_index??0})};const editContext=(e:ReactMouseEvent)=>{if(mode!=='edit')return;e.preventDefault();e.stopPropagation();onContext?.({sectionId:s.id,blockId:sourceId,fragmentIndex:b.fragment_index??0},e.clientX,e.clientY)};return <article className={`resume-block ${changed?'changed-block':''} ${b.continuation?'continuation-block':''} ${mode==='edit'?'editable-block':''}`} onClick={editClick} onContextMenu={editContext} title={mode==='edit'?'点击编辑，右键更多操作':undefined}><div className="block-head"><b>{b.title}</b>{b.continuation&&<small className="continuation-label">续</small>}{b.source_refs.length>0&&<small className={changed?'source-alert':''}>{changed?'来源已变化':'事实来源'}</small>}</div>{fieldKeys.length>0&&<div className="block-meta">{fieldKeys.map(k=><span key={k}><b>{labelsFor[k]||k}</b> {fields[k]}</span>)}</div>}<p className="block-copy">{b.content}</p></article>}
function BlockEditor({content,target,update,close}:{content:Content;target:BlockRef;update:UpdateBlock;close:()=>void}){
  const s=content.sections.find(x=>x.id===target.sectionId)
  const block=s?.blocks.find(x=>x.id===target.blockId)
  if(!s||!block)return null
  const fields=block.fields||{}
  const fieldKeys=(block.display_fields||Object.keys(fields)).filter(k=>fields[k])
  const labelsFor={...fieldLabels,...(block.field_labels||{})}
  const chunks=splitText(block.content||'',fragmentLimit(target.sectionId))
  const copy=chunks[target.fragmentIndex]||''
  const fragmentLabel=target.fragmentIndex>0?`正文 · 续段 ${target.fragmentIndex+1}`:'正文'
  return <Modal title={`编辑 · ${labels[target.sectionId]} · ${block.title}`} close={close}>
    <Field label="条目标题"><input value={block.title} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'title')}/></Field>
    {fieldKeys.length>0&&<div className="block-editor-fields">{fieldKeys.map(k=><Field key={k} label={labelsFor[k]||k}><input value={fields[k]} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'field',k)}/></Field>)}</div>}
    <Field label={fragmentLabel} hint="修改会同步到工作副本，并自动保存草稿。"><textarea className="block-editor-copy" value={copy} onChange={e=>update(target.sectionId,target.blockId,e.target.value,'content',undefined,target.fragmentIndex)}/></Field>
    <div className="modal-actions"><button className="button primary" onClick={close}>完成</button></div>
  </Modal>
}
function BlockContextMenu({menu,onEdit,onAddSource,onClose}:{menu:BlockMenu;onEdit:(target:BlockRef)=>void;onAddSource:(sectionId:string)=>void;onClose:()=>void}){
  const canAdd=factCategories(menu.sectionId).length>0
  const left=Math.max(8,Math.min(menu.x,window.innerWidth-190))
  const top=Math.max(8,Math.min(menu.y,window.innerHeight-120))
  return <>
    <div className="context-menu-layer" onClick={onClose} onContextMenu={e=>{e.preventDefault();onClose()}}/>
    <div className="context-menu" style={{left,top}} onClick={e=>e.stopPropagation()}>
      <button onClick={()=>onEdit({sectionId:menu.sectionId,blockId:menu.blockId,fragmentIndex:menu.fragmentIndex})}><FilePenLine size={15}/>编辑文本</button>
      {canAdd&&<button onClick={()=>onAddSource(menu.sectionId)}><Plus size={15}/>添加来源</button>}
      <button className="muted" onClick={onClose}>取消</button>
    </div>
  </>
}
function BenchHead({title,subtitle,back}:{title:string;subtitle:string;back:()=>void}){return <header className="workbench-head"><button className="back-btn" onClick={back}><ArrowLeft size={15}/>返回</button><div><p className="eyebrow">{title}</p><h1>{subtitle}</h1></div><span className="a4-state">固定 A4</span></header>}
function Title({crumb,title,desc,back,action}:{crumb:string;title:string;desc:string;back:()=>void;action?:ReactNode}){return <><div className="breadcrumb"><button className="back-btn" onClick={back}><ArrowLeft size={15}/>返回概览</button><span>/ {crumb}</span></div><header className="page-title"><div><p className="eyebrow">{crumb}</p><h1>{title}</h1><p>{desc}</p></div>{action}</header></>}
function Field({label,hint,children}:{label:string;hint?:string;children:ReactNode}){return <label className="field"><b>{label}</b>{hint&&<small>{hint}</small>}{children}</label>}
function Modal({title,close,children}:{title:string;close:()=>void;children:ReactNode}){return <div className="modal-backdrop"><section className="modal"><header><h2>{title}</h2><button className="icon-btn" onClick={close}><X size={18}/></button></header><div className="modal-body">{children}</div></section></div>}
function Loading(){return <div className="loading"><LoaderCircle size={18}/>正在加载</div>}; function Empty({icon:Icon,title,body}:{icon:any;title:string;body:string}){return <div className="empty"><Icon size={25}/><h3>{title}</h3><p>{body}</p></div>}

async function downloadExport(id:number,version:number){const base=import.meta.env.VITE_API_URL||'http://127.0.0.1:8000';const r=await fetch(`${base}/api/resumes/${id}/versions/${version}/export`,{method:'POST'});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'导出失败');const blob=await r.blob();const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`resume-v${version}.html`;a.click();URL.revokeObjectURL(url)}
