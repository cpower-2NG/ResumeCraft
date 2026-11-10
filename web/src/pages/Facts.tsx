import { useEffect, useMemo, useRef, useState } from 'react'
import { ArchiveRestore, BookOpen, ChevronRight, ExternalLink, Eye, FileUp, ImagePlus, Plus, RotateCcw, Search, Tag as TagIcon, Trash2, X } from 'lucide-react'
import { apiUrl, del, patch, post, upload } from '../api'
import { Empty, Field, Loading, Modal, Title, useLoad } from '../components/ui'
import { brief, categories, categoryLabels, date, type Fact } from '../lib/resume'

type SchemaField = {
  key:string
  label:string
  value_type:string
  requirement_level:string
  options?:{value:string;label:string}[]
}

const emptyFact = (category='experience'):Fact => ({
  id:0,
  category_code:category,
  schema_version_id:0,
  business_key:null,
  title:'',
  fields:{},
  tags:[],
  skill_ids:[],
  linked_skills:[],
  skill_group:null,
  status:'active',
  source_note:'',
  updated_at:'',
  evidence_count:0,
})

export function Facts({back,error,focus,onFocusHandled}:{back:()=>void;error:(s:string)=>void;focus:Fact|null;onFocusHandled:()=>void}){
  const facts=useLoad<Fact[]>('/api/facts',[])
  const recycled=useLoad<Fact[]>('/api/facts?status=recycled',[])
  const [cat,setCat]=useState<string|null>(null)
  const [q,setQ]=useState('')
  const [tag,setTag]=useState('')
  const [edit,setEdit]=useState<Fact|null>(null)
  const [recycle,setRecycle]=useState(false)
  useEffect(()=>{if(focus){setEdit(focus);onFocusHandled()}},[focus])

  const source=recycle?recycled.data.filter(f=>f.status==='recycled'):facts.data
  const list=source.filter(f=>(!cat||f.category_code===cat)&&(!tag||f.tags.includes(tag))&&`${f.title} ${brief(f)} ${f.tags.join(' ')}`.toLowerCase().includes(q.toLowerCase()))
  const tags=useMemo(()=>Array.from(new Set(facts.data.flatMap(f=>f.tags))).sort((a,b)=>a.localeCompare(b,'zh-CN')),[facts.data])
  const count=(key:string)=>facts.data.filter(f=>f.category_code===key).length
  const noEvidence=facts.data.filter(f=>(f.category_code==='experience'||f.category_code==='achievement')&&!f.evidence_count).length
  const noTags=facts.data.filter(f=>!f.tags.length).length

  return <main className="page">
    <Title
      crumb="资料库"
      title={cat?categoryLabels[cat]:'资料库'}
      desc={cat?'按实际对象组织资料；技能与经历、成果与主经历的关系可直接维护。':'个人档案、经历、能力和成果分开维护；主题标签用于筛选，链接作为具体经历的证据。'}
      back={back}
      action={<div className="header-actions">
        <button className="button" onClick={()=>{setRecycle(!recycle);setCat(null);setTag('')}}>
          {recycle?<ArchiveRestore size={15}/>:<Trash2 size={15}/>} {recycle?'返回资料库':'回收站'}
        </button>
        <button className="button primary" onClick={()=>setEdit(emptyFact(cat||'experience'))}>
          <Plus size={16}/>新增资料
        </button>
      </div>}
    />
    <div className="filterbar"><Search size={16}/><input placeholder="搜索名称、详情或主题标签" value={q} onChange={e=>setQ(e.target.value)}/></div>
    {!!tags.length&&<div className="category-tabs tag-filter"><TagIcon size={14}/>{tags.map(name=><button key={name} className={tag===name?'active':''} onClick={()=>setTag(tag===name?'':name)}>{name}</button>)}</div>}
    {!cat&&!q&&!tag&&!recycle
      ? <>
        <section className="library-grid">{categories.map(key=><button className="library-card" key={key} onClick={()=>setCat(key)}>
          <BookOpen size={18}/><span><b>{categoryLabels[key]}</b><small>{count(key)} 条资料</small></span><ChevronRight size={15}/>
        </button>)}</section>
        <div className="home-extras">
          <section className="list-panel mini-panel"><div className="table-head"><span>最近修改</span></div>
            {facts.data.slice(0,5).map(f=><button className="table-row" key={f.id} onClick={()=>setEdit(f)}>
              <span><b>{f.title}</b><small>{categoryLabels[f.category_code]}</small></span><time>{date(f.updated_at)}</time>
            </button>)}
          </section>
          <aside className="quality-hints"><b>资料整理提示</b>
            {facts.data.length===0?<p>还没有资料，先建立个人档案。</p>:<>
              {noEvidence>0&&<p>{noEvidence} 条经历或成果还没有证据材料。</p>}
              {noTags>0&&<p>{noTags} 条资料缺少主题标签。</p>}
              {noEvidence===0&&noTags===0&&<p>资料关系与主题标签已补齐。</p>}
            </>}
          </aside>
        </div>
      </>
      : <>
        <nav className="category-tabs">
          <button className={!cat?'active':''} onClick={()=>setCat(null)}>全部</button>
          {categories.map(key=><button key={key} className={cat===key?'active':''} onClick={()=>setCat(key)}>{categoryLabels[key]}</button>)}
        </nav>
        <section className="data-table">
          <div className="table-head"><span>资料名称</span><span>摘要</span><span>主题标签</span><span>证据</span><span>更新时间</span></div>
          {(recycle?recycled.loading:facts.loading)?<Loading/>:list.length?list.map(f=><button className="table-row fact-table-row" key={f.id} onClick={()=>setEdit(f)}>
            <span><b>{f.title}</b><small>{categoryLabels[f.category_code]}{f.status==='recycled'?' · 已回收':''}</small></span>
            <span>{brief(f)}</span>
            <span className="fact-tags">{f.tags.length?f.tags.map(x=><i key={x}>{x}</i>):'—'}</span>
            <span>{f.evidence_count?`${f.evidence_count} 份`:'未添加'}</span>
            <time>{date(f.updated_at)}</time>
          </button>):<Empty icon={BookOpen} title="没有匹配资料" body="可以新增资料，或调整分类、标签和搜索条件。"/>}
        </section>
      </>}
    {edit&&<FactModal fact={edit} allFacts={facts.data} close={()=>setEdit(null)} done={()=>{setEdit(null);facts.reload();recycled.reload()}} error={error}/>}
  </main>
}

function FactModal({fact,allFacts,close,done,error}:{fact:Fact;allFacts:Fact[];close:()=>void;done:()=>void;error:(s:string)=>void}){
  const [title,setTitle]=useState(fact.title)
  const [category,setCategory]=useState(fact.category_code)
  const [fields,setFields]=useState<Record<string,string>>(Object.fromEntries(Object.entries(fact.fields||{}).map(([k,v])=>[k,v==null?'':String(v)])))
  const [skillIds,setSkillIds]=useState<number[]>(fact.skill_ids||[])
  const [tags,setTags]=useState(fact.tags.join('、'))
  const [evidence,setEvidence]=useState(false)
  const [saving,setSaving]=useState(false)
  const schema=useLoad<{schema_version_id:number;fields:SchemaField[]}>(`/api/fact-schemas/${category}`,{schema_version_id:0,fields:[]})
  const skillGroups=useLoad<{id:number;display_name:string}[]>('/api/skill-groups',[])
  const audits=useLoad<{id:number;action:string;summary:string;created_at:string}[]>(fact.id?`/api/facts/${fact.id}/audits`:'',[])

  useEffect(()=>{
    setTitle(fact.title)
    setCategory(fact.category_code)
    setFields(Object.fromEntries(Object.entries(fact.fields||{}).map(([k,v])=>[k,v==null?'':String(v)])))
    setSkillIds(fact.skill_ids||[])
    setTags(fact.tags.join('、'))
  },[fact])

  const set=(key:string,value:string)=>setFields(values=>({...values,[key]:value}))
  const save=async()=>{
    setSaving(true)
    try{
      const targetFields:Record<string,string|number>={...fields}
      if(category==='skill'&&targetFields.skill_group_id)targetFields.skill_group_id=Number(targetFields.skill_group_id)
      const body={
        title,
        category_code:category,
        schema_version_id:fact.schema_version_id||schema.data.schema_version_id,
        fields:targetFields,
        tags:tags.split(/[、，,]/).map(x=>x.trim()).filter(Boolean),
        skill_ids:skillIds,
        status:fact.status==='recycled'?'recycled':'active',
      }
      if(fact.id)await patch(`/api/facts/${fact.id}`,body)
      else await post('/api/facts',body)
      done()
    }catch(e){error((e as Error).message)}
    finally{setSaving(false)}
  }
  const remove=async()=>{
    if(!fact.id||!confirm('确认删除？已有正式简历引用时会保留在回收站。'))return
    try{await del(`/api/facts/${fact.id}`);done()}catch(e){error((e as Error).message)}
  }

  const skills=allFacts.filter(item=>item.category_code==='skill'&&item.status==='active')
  const experiences=allFacts.filter(item=>item.category_code==='experience'&&item.status==='active')

  return <Modal title={fact.id?`编辑资料 · ${fact.title}`:'新增资料'} close={close}>
    <div className="fact-form-grid">
      <Field label="资料分类"><select value={category} disabled={!!fact.id} onChange={e=>{setCategory(e.target.value);setFields({});setSkillIds([])}}>
        {categories.map(key=><option key={key} value={key}>{categoryLabels[key]}</option>)}
      </select></Field>
      <Field label="资料名称" hint="用于列表识别，不替代结构化字段。"><input value={title} onChange={e=>setTitle(e.target.value)} placeholder={category==='experience'?'例如：机器人数据采集与模仿学习项目':'填写可识别的名称'}/></Field>
    </div>
    {category==='basics'&&fact.id===0&&<p className="modal-note">每个工作区只保留一份个人档案。如果已有档案，请直接编辑原记录。</p>}
    {category==='basics'&&fact.id>0&&<ProfilePhotoPanel fact={fact} error={error}/>}
    <div className="fact-fields">
      {schema.loading?<Loading/>:schema.data.fields.map(field=>{
        const options=field.key==='experience_fact_id'
          ? experiences.map(item=>({value:String(item.id),label:item.title}))
          : field.key==='skill_group_id'
          ? skillGroups.data.map(item=>({value:String(item.id),label:item.display_name}))
          : field.options||[]
        const value=fields[field.key]||''
        return <Field key={field.key} label={`${field.label}${field.requirement_level==='required_for_output'?' *':''}`}>
          {field.value_type==='long_text'
            ? <textarea value={value} onChange={e=>set(field.key,e.target.value)} placeholder={`填写${field.label}`}/>
            : field.value_type==='enum'||field.key==='experience_fact_id'||field.key==='skill_group_id'
              ? <select value={value} onChange={e=>set(field.key,e.target.value)}>
                  <option value="">未选择</option>
                  {options.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              : <input type={field.value_type==='url'?'url':field.value_type==='date'?'date':'text'} value={value} onChange={e=>set(field.key,e.target.value)} placeholder={`填写${field.label}`}/>
          }
        </Field>
      })}
    </div>
    {category==='experience'&&<section className="relation-fields">
      <div className="custom-fields-head"><b>关联技能</b><small>只关联这个经历中实际使用的技能</small></div>
      <div className="relation-checks">{skills.map(skill=><label key={skill.id}><input type="checkbox" checked={skillIds.includes(skill.id)} onChange={()=>setSkillIds(ids=>ids.includes(skill.id)?ids.filter(id=>id!==skill.id):[...ids,skill.id])}/><span>{skill.title}</span></label>)}</div>
    </section>}
    <Field label="主题标签" hint="使用顿号或逗号分隔，例如：具身智能、数据采集、计算机视觉。">
      <input value={tags} onChange={e=>setTags(e.target.value)} placeholder="具身智能、机器人、数据采集"/>
    </Field>
    {fact.id&&<details className="audit-box"><summary>修改记录（{audits.data.length}）</summary>{audits.data.map(a=><p key={a.id} className="audit-row"><b>{a.summary}</b><small>{date(a.created_at)}</small></p>)}</details>}
    {fact.id&&<button className="evidence-link" onClick={()=>setEvidence(true)}><FileUp size={16}/>证据与作品链接 <span>{fact.evidence_count} 份</span><ChevronRight size={15}/></button>}
    <div className="modal-actions">
      {fact.status==='recycled'
        ? <button className="button" onClick={async()=>{await post(`/api/facts/${fact.id}/restore`);done()}}><ArchiveRestore size={15}/>恢复资料</button>
        : fact.id&&<button className="button danger" onClick={remove}><Trash2 size={15}/>删除</button>}
      <button className="button primary" disabled={!title.trim()||saving} onClick={save}>{saving?'保存中…':'保存资料'}</button>
    </div>
    {evidence&&fact.id&&<EvidenceModal fact={fact} close={()=>setEvidence(false)} error={error}/>}
  </Modal>
}

type EvidenceItem = {id:number;kind:string;title:string;url:string;filename:string;mime_type:string;size_bytes:number;preview_url:string;status:string;note:string}
type ProfilePhotoItem = {id:number;status:string;created_at:string;archived_at:string|null;evidence:EvidenceItem}

function ProfilePhotoPanel({fact,error}:{fact:Fact;error:(s:string)=>void}){
  const photos=useLoad<{current:ProfilePhotoItem|null;history:ProfilePhotoItem[]}>(`/api/facts/${fact.id}/profile-photo`,{current:null,history:[]})
  const input=useRef<HTMLInputElement>(null)
  const [busy,setBusy]=useState(false)
  const uploadPhoto=async(file:File)=>{
    setBusy(true)
    try{
      const data=new FormData()
      data.set('file',file)
      data.set('title','档案照片')
      await upload('/api/facts/'+fact.id+'/profile-photo',data)
      photos.reload()
    }catch(e){error((e as Error).message)}
    finally{setBusy(false);if(input.current)input.current.value=''}
  }
  const removePhoto=async()=>{
    if(!photos.data.current||!confirm('移除当前档案照片？历史照片仍会保留。'))return
    setBusy(true)
    try{await del(`/api/profile-photos/${photos.data.current.id}`);photos.reload()}
    catch(e){error((e as Error).message)}
    finally{setBusy(false)}
  }
  const restorePhoto=async(id:number)=>{
    setBusy(true)
    try{await post(`/api/profile-photos/${id}/restore`);photos.reload()}
    catch(e){error((e as Error).message)}
    finally{setBusy(false)}
  }
  const current=photos.data.current
  return <section className="profile-photo-panel">
    <div className="profile-photo-head"><div><b>档案照片</b><small>可选；上传后会显示在全部简历模板的页头，不会进入经历证据列表。</small></div>
      <input ref={input} hidden type="file" accept=".png,.jpg,.jpeg,.jfif,.webp" onChange={e=>{const file=e.target.files?.[0];if(file)uploadPhoto(file)}}/>
      <button className="button" disabled={busy} onClick={()=>input.current?.click()}><ImagePlus size={15}/>{current?'更换照片':'上传照片'}</button>
    </div>
    {photos.loading?<Loading/>:current
      ? <div className="profile-photo-current">
          <a href={apiUrl(current.evidence.preview_url)} target="_blank" rel="noreferrer" title="查看原图"><img src={apiUrl(current.evidence.preview_url)} alt="档案照片"/></a>
          <span><b>{current.evidence.filename}</b><small>{Math.max(1,Math.round(current.evidence.size_bytes/1024))} KB · 当前照片</small></span>
          <button className="mini-button danger" disabled={busy} onClick={removePhoto}><Trash2 size={13}/>移除</button>
        </div>
      : <div className="profile-photo-empty"><ImagePlus size={22}/><span>还没有档案照片</span><small>支持 PNG、JPEG、JFIF、WebP，最大 5 MB</small></div>}
    {photos.data.history.length>0&&<details className="profile-photo-history"><summary>历史照片（{photos.data.history.length}）</summary>
      {photos.data.history.map(photo=><div className="profile-photo-history-row" key={photo.id}><img src={apiUrl(photo.evidence.preview_url)} alt={photo.evidence.filename}/><span><b>{photo.evidence.filename}</b><small>{date(photo.archived_at||photo.created_at)}</small></span><button className="mini-button" disabled={busy} onClick={()=>restorePhoto(photo.id)}><RotateCcw size={13}/>恢复为当前</button></div>)}
    </details>}
  </section>
}

function EvidenceModal({fact,close,error}:{fact:Fact;close:()=>void;error:(s:string)=>void}){
  const list=useLoad<EvidenceItem[]>(`/api/facts/${fact.id}/evidence`,[])
  const [title,setTitle]=useState('')
  const [url,setUrl]=useState('')
  const [note,setNote]=useState('')
  const [file,setFile]=useState<File|null>(null)
  const [preview,setPreview]=useState<EvidenceItem|null>(null)
  const save=async()=>{
    try{
      if(file){
        const data=new FormData()
        data.set('fact_id',String(fact.id))
        data.set('title',title)
        data.set('note',note)
        data.set('file',file)
        await upload('/api/evidence/upload',data)
      }else{
        await post('/api/evidence',{kind:'link',fact_id:fact.id,title,url,note})
      }
      setTitle('');setUrl('');setNote('');setFile(null);list.reload()
    }catch(e){error((e as Error).message)}
  }
  const archive=async(id:number)=>{
    try{await del(`/api/evidence/${id}`);list.reload()}catch(e){error((e as Error).message)}
  }
  const open=async(item:EvidenceItem)=>{
    if(item.kind==='link'){
      window.open(item.preview_url||item.url,'_blank','noopener,noreferrer')
      return
    }
    setPreview(item)
  }
  if(preview){
    const src=apiUrl(preview.preview_url)
    const isImage=preview.mime_type.startsWith('image/')
    return <Modal title={`预览证据 · ${preview.title}`} close={()=>setPreview(null)} className="evidence-preview-modal">
      {isImage
        ? <img className="evidence-preview-image" src={src} alt={preview.title}/>
        : <iframe className="evidence-preview-frame" src={src} title={preview.title}/>}
      <div className="modal-actions">
        <a className="button" href={src} target="_blank" rel="noreferrer"><ExternalLink size={15}/>新窗口打开</a>
        <button className="button" onClick={()=>setPreview(null)}>返回证据列表</button>
      </div>
    </Modal>
  }
  return <Modal title={`证据 · ${fact.title}`} close={close}>
    <p className="modal-note">项目代码、作品主页、演示视频、证书或证明文件都挂在这里。证据不会自动进入简历正文。</p>
    {list.data.map(item=><div className="evidence-row" key={item.id}>
      <FileUp size={15}/>
      <button className="evidence-main" onClick={()=>open(item)}>
        <b>{item.title}</b>
        <small>{item.kind==='link'?item.url:item.filename}</small>
      </button>
      <div className="evidence-actions">
        <button className="mini-button" onClick={()=>open(item)}><Eye size={13}/>{item.kind==='link'?'打开链接':'预览'}</button>
        {item.status==='active'&&<button className="mini-button" onClick={()=>archive(item.id)}>标记失效</button>}
        {item.status!=='active'&&<small className="evidence-state">已失效</small>}
      </div>
    </div>)}
    <Field label="证据名称"><input value={title} onChange={e=>setTitle(e.target.value)}/></Field>
    <Field label="上传文件或填写链接"><input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" onChange={e=>setFile(e.target.files?.[0]||null)}/><input value={url} disabled={!!file} onChange={e=>setUrl(e.target.value)} placeholder="https://..."/></Field>
    <Field label="说明"><input value={note} onChange={e=>setNote(e.target.value)}/></Field>
    <button className="button primary" disabled={!file&&!url.trim()} onClick={save}>添加证据</button>
  </Modal>
}
