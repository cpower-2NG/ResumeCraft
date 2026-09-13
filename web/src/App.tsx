import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CircleAlert, Search, X } from 'lucide-react'
import { api, post } from './api'
import { Modal, useLoad } from './components/ui'
import { TemplateGalleryModal } from './components/TemplateGalleryModal'
import { pendingKindLabels, searchTypeLabels, date, type Fact, type Pending, type Profile, type SearchResult } from './lib/resume'
import { Home } from './pages/Home'
import { Facts } from './pages/Facts'
import { Profiles } from './pages/Profiles'
import { Resumes } from './pages/Resumes'
import { Composer } from './pages/Composer'
import { Editor } from './pages/Editor'
import { TemplateLibrary } from './pages/TemplateLibrary'

type Page='home'|'facts'|'profiles'|'resumes'|'compose'|'editor'|'templates'

export default function App(){
  const [page,setPage]=useState<Page>('home')
  const [error,setError]=useState(''); const [profile,setProfile]=useState<Profile|null>(null); const [linked,setLinked]=useState<number|null>(null); const [resume,setResume]=useState<number|null>(null)
  // 模板库选中的模板：下一次“创建临时简历”会携带这个模板。
  const [pendingTemplate,setPendingTemplate]=useState<number|null>(null)
  const [focusFact,setFocusFact]=useState<Fact|null>(null)
  const [focusBlock,setFocusBlock]=useState<{sectionId:string;blockId:string}|null>(null)
  const [pendingOpen,setPendingOpen]=useState(false)
  const [insufficient,setInsufficient]=useState<Profile|null>(null)
  // 待创建临时简历的岗位画像：模板库大卡片弹窗挂起期间暂存。
  const [templatePick,setTemplatePick]=useState<Profile|null>(null)
  const pending = useLoad<Pending[]>('/api/pending-items',[])
  const startCompose = async (p:Profile,templateVersionId?:number|null) => { try {
    const tv=templateVersionId||pendingTemplate
    const query=tv?`&template_version_id=${tv}`:''
    const r=await post<{id:number}>(`/api/linked-resumes?profile_id=${p.id}${query}`)
    setPendingTemplate(null)
    setProfile(p); setLinked(r.id); setPage('compose')
  } catch(e) { setError((e as Error).message) } }
  const create = async (p:Profile) => {
    try {
      const facts = await api<Fact[]>('/api/facts')
      if (facts.length < 3) { setInsufficient(p); return }
      // 创建临时简历先弹出大卡片模板库，选定模板后再进入工作台。
      setTemplatePick(p)
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
      <button className="brand" onClick={()=>setPage('home')}><span>简</span>简历工坊</button>
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
    {page==='templates'&&<TemplateLibrary back={()=>setPage('home')} onCreate={(tvId)=>{setPendingTemplate(tvId||null);setPage('profiles')}}/>}
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
        <button className="button" onClick={()=>{setInsufficient(null);setPage('facts')}}>去资料库补充</button>
        <button className="button primary" onClick={()=>{const p=insufficient;setInsufficient(null);setTemplatePick(p)}}>继续制作</button>
      </div>
    </Modal>}
    {templatePick&&<TemplateGalleryModal current={pendingTemplate??undefined} onChoose={tvId=>{const p=templatePick;setTemplatePick(null);startCompose(p,tvId)}} close={()=>setTemplatePick(null)}/>}
  </div>
}

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
