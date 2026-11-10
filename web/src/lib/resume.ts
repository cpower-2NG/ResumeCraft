// Resume domain types and pure rendering logic shared by every page.
// The page-packing code mirrors render_resume_html() in app/services.py so the
// SPA preview paginates exactly like the exported A4 HTML.
import { mdLite } from './markdown'

export type Fact = { id:number; category_code:string; schema_version_id:number; business_key?:string|null; title:string; fields:Record<string,string|number|null>; tags:string[]; skill_ids:number[]; linked_skills:{id:number;title:string}[]; skill_group?:{id:number;code:string;display_name:string}|null; status:string; source_note:string; updated_at:string; evidence_count:number }
export type Profile = { id:number; name:string; role_direction:string; core_requirements:string[]; general_requirements:string; responsibilities:string; resume_strategy:string; raw_jd:string; source_note:string; status:string; updated_at:string; active_resume_id?:number; opportunity_count?:number }
export type ResumePhoto = { photo_id?:number; evidence_id:number; preview_url:string; filename?:string; mime_type?:string; data_url?:string }
export type Block = { id:string; title:string; content:string; fields?:Record<string,string>; field_labels?:Record<string,string>; display_fields?:string[]; source_refs:number[]; origin:string; fragment_index?:number; continuation?:boolean; table_rows?:[string,string,string][]; photo?:ResumePhoto }
export type Section = { id:string; title:string; visibility:boolean; blocks:Block[] }
export type Content = { sections:Section[] }
export type Resume = { id:number; display_name:string; profile_name:string; current_version:number; updated_at:string; content_state:'clean'|'dirty'; evidence_sync_state:'clean'|'pending'|'conflict'; baseline_state:'current'|'stale'; warnings:number; status:string; template_id:number }
export type Pending = { id:number; resume_id:number|null; fact_id:number|null; evidence_id:number|null; profile_id:number|null; section_code:string; block_key:string; message:string; kind:string; status:string; created_at:string; source:any }
export type SearchResult = { type:'fact'|'evidence'|'profile'|'opportunity'|'resume'; id:number; title:string; subtitle:string; status:string; updated_at:string; payload:any }
export type BlockRef = { sectionId:string; blockId:string; fragmentIndex:number }
export type UpdateBlock = (sectionId:string, blockId:string, value:string, key?:'content'|'title'|'field', fieldKey?:string, fragmentIndex?:number)=>void

export const labels:Record<string,string> = { basics:'基本信息', target:'求职目标', profile:'个人简介', education:'教育经历', experience:'项目与实践', skills:'技能', awards:'成果', links:'链接与作品集' }
export const categoryLabels:Record<string,string> = { basics:'个人档案', education:'教育经历', experience:'经历', skill:'技能', achievement:'成果' }
export const categories = ['basics','education','experience','skill','achievement']
export const fieldLabels:Record<string,string> = { name:'姓名', phone:'电话', email:'邮箱', city:'所在地', desired_city:'目标城市', birth_date:'出生日期', age_text:'年龄', hometown:'籍贯', identity_status:'身份状态', graduation_date:'毕业时间', availability:'到岗安排', bio:'个人简介', school:'学校', major:'专业', degree:'学历', start_date:'开始时间', end_date:'结束时间', period_text:'展示时间段', gpa:'GPA', ranking:'专业排名', achievement:'成绩与成果', courses:'相关课程', experience_kind:'经历类型', organization:'组织/公司', role:'角色', team_size:'团队规模', context_summary:'背景', work_summary:'具体工作', tools_summary:'工具与技术', result_summary:'结果摘要', challenge:'挑战（内部）', solution:'解决方案', public_note:'公开说明', skill_group:'技能分组', skill_group_id:'技能分组', proficiency:'熟练程度', usage_context:'使用场景', achievement_kind:'成果类型', occurred_on:'取得日期', experience_fact_id:'主经历', issuer:'颁发方', result_text:'成果内容', note:'说明', role_direction:'岗位方向', core_requirements:'核心要求', summary:'简介' }
export const searchTypeLabels:Record<string,string> = { fact:'事实资料', evidence:'证据', profile:'岗位画像', opportunity:'招聘机会', resume:'正式简历' }
export const pendingKindLabels:Record<string,string> = { source_changed:'来源资料变化', source_recycled:'来源移入回收站', evidence_sync:'证据更新待处理', evidence_conflict:'证据更新合并失败', profile_changed:'画像变化待确认', export_warning:'导出警告', other:'其他待处理事项' }

export const date = (v?:string) => v ? new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium'}).format(new Date(v)) : '—'
export const optionLabels:Record<string,Record<string,string>> = {
  experience_kind:{project:'项目',work_internship:'实习/工作',competition:'竞赛',research:'科研',campus_volunteer:'校园/志愿',other:'其他'},
  setting:{course:'课程',lab:'实验室',company:'公司',personal:'个人',team:'团队',community:'社群/公益',competition:'竞赛',other:'其他'},
  achievement_kind:{honor:'荣誉',certificate:'证书',publication_patent:'发表/专利',project_result:'项目结果',other:'其他'},
}
export const optionLabel = (key:string,value?:string) => optionLabels[key]?.[value||''] || value || ''
const preferredBriefKeys:Record<string,string[]> = { basics:['city','identity_status','graduation_date'], education:['school','major','degree','period_text'], experience:['experience_kind','organization','role','period_text','result_summary'], skill:['skill_group','proficiency','usage_context'], achievement:['achievement_kind','issuer','result_text','period_text'] }
export const brief = (f:Fact) => [...(preferredBriefKeys[f.category_code]||Object.keys(f.fields||{})).map(k=>k==='experience_kind'||k==='achievement_kind'?optionLabel(k,String(f.fields?.[k]??'')):k==='skill_group'?f.skill_group?.display_name??'其他':f.fields?.[k]).filter(Boolean),...(f.linked_skills||[]).map(x=>x.title)].slice(0,3).join(' · ') || '尚未补充详细信息'
export const section = (content:Content,id:string):Section => content.sections.find(s=>s.id===id) || {id,title:labels[id],visibility:true,blocks:[]}
export const sourceIdOf = (b:Block) => b.id.split('--fragment-')[0]
export const factCategories = (id:string) => id === 'basics' ? ['basics'] : id === 'profile' || id === 'target' || id === 'links' ? [] : id === 'skills' ? ['skill'] : id === 'awards' ? ['achievement'] : [id]

export { mdLite }

// —— 组稿正文策展（与 app/services.py 的 curated_* 同一套规则）——
// 经历条目按 work → solution → outcome 组织成列表；背景在有"具体工作"时省略，
// 挑战属于内部叙述不上纸面；结果行里的量化指标加粗。教育经历给课程行加"核心课程"
// 前缀，与参考简历一致。
const BOLD_METRIC_RE=/\d+(?:\.\d+)?\s*[%％]|第\s*\d+\s*名|省[一二三]等奖|国[一二三]等奖|\d+\s*(?:倍|名|人|项|份|台|万\+?)/g
const boldMetrics=(t:string)=>/\*\*/.test(t)?t:t.replace(BOLD_METRIC_RE,m=>`**${m.trim()}**`)
export const curatedExperience=(d:Record<string,unknown>)=>{const parts:string[]=[];const context=String(d.context_summary||d.context||'').trim();const work=String(d.work_summary||d.work||'').trim();if(context&&!work)parts.push(context);for(const [k,legacy] of [['work_summary','work'],['solution','solution'],['result_summary','outcome']] as const){const v=String(d[k]||d[legacy]||'').trim();if(v)parts.push(k==='result_summary'?boldMetrics(v):v)}return parts.map(p=>`- ${p}`).join('\n')}
export const curatedEducation=(d:Record<string,unknown>)=>{const lines:string[]=[];const a=String(d.achievement||'').trim();const c=String(d.courses||'').trim();if(a)lines.push(a);if(c)lines.push(`核心课程：${c}`);return lines.join('\n')}

export function factBlock(f:Fact,sid:string):Block{const d=f.fields||{};const fields:Record<string,string>=Object.fromEntries(Object.entries(d).filter(([,v])=>v).map(([k,v])=>[k,String(v)]));if(f.skill_group)fields.skill_group=f.skill_group.display_name;const standard=sid==='basics'?['phone','email','city','desired_city','hometown','identity_status','graduation_date','availability']:sid==='education'?['period_text','major','degree','gpa','ranking']:sid==='experience'?['period_text','organization','role','team_size','tools_summary']:sid==='skills'?['skill_group','proficiency']:['period_text','issuer','result_text'];const display_fields=standard.filter(k=>fields[k]);const content=sid==='education'?curatedEducation(d):sid==='experience'?curatedExperience(d):sid==='skills'?String(d.usage_context||''):sid==='awards'?String(d.note||''):'';return {id:`fact-${f.id}-${Date.now()}`,type:'fact',title:f.title,content:content||brief(f),fields,field_labels:{},display_fields,source_refs:[f.id],origin:'fact'} as Block}

export function splitText(value:string,max=900){if(!value)return [''];const chunks:string[]=[];for(let start=0;start<value.length;start+=max)chunks.push(value.slice(start,start+max));return chunks}
// 正文切片上限：侧栏版心只有约 44mm，切片要更短。与 services.py 的
// section_fragment_limit 保持一致。
export const fragmentLimit=(inSidebar:boolean)=>inSidebar?520:900
// 该栏目是否由侧栏承载，决定正文的切片口径。编辑续段时要按同一口径重新切片，
// 否则会切在与预览不同的位置上。
export const inSidebarStream=(layout:string|undefined,sectionId:string)=>layout==='sidebar'&&SIDE_IDS.includes(sectionId)

export const MAIN_IDS=['profile','experience','education','links']
// 侧栏布局里由侧栏承载的栏目。基本信息不在此列——它已经由侧栏页头（姓名 +
// 联系方式 + 简介）呈现，重复成栏目会让同一段内容在侧栏出现两次。
export const SIDE_IDS=['skills','awards']
export const ALL_IDS=['basics','target','profile','experience','education','skills','awards','links']

// —— 结构化字段的兜底回收（与 app/services.py 的 hydrate_block 同一套规则）——
// 渲染器完全依赖块上的 fields（时间右对齐、元信息行、时间轴左时间列）。历史数据
// 迁移或外部写入会把字段压平进正文，这里把" · "分隔的短段尾巴解析回字段：
// 时间形状的段回收为 period，成果栏目里"含奖级词"的段回收为 result，其余段成为
// 无标签的 meta 值。已带 fields 的块一律不动。
const PERIOD_VALUE_RE=/^\d{4}(?:\.\d{1,2})?(?:\s*[-–—~至]\s*(?:\d{4}(?:\.\d{1,2})?|至今|应届))?\s*$/
const AWARD_RESULT_RE=/(奖|第\s*\d+\s*名|名次|冠军|亚军|季军|金|银|铜|入围|优胜|一等|二等|三等|Top\s*\d+)/
const META_TAIL_SEP=' · '
const isMetaSegment=(s:string)=>{const t=s.trim();return !!t&&t.length<=16&&!/[。！？；;，]/.test(t)}
const classifyAwardSegments=(segments:string[])=>{const out:Record<string,string>={};const issuer=segments.find(s=>!AWARD_RESULT_RE.test(s));const result=segments.find(s=>AWARD_RESULT_RE.test(s));if(issuer)out.issuer=issuer;if(result)out.result=result;return out}

export function hydrateBlock(block:Block,sectionId=''):Block{
  if(block.fields)return block
  const content=String(block.content||'')
  if(!content.includes(META_TAIL_SEP))return block
  const lines=content.split('\n')
  const segments=lines[lines.length-1].split(META_TAIL_SEP)
  if(segments.length<2)return block
  const tail:string[]=[]
  while(segments.length>1&&isMetaSegment(segments[segments.length-1])){tail.unshift(segments.pop()!.trim())}
  let remaining=segments.join(META_TAIL_SEP).trim()
  if(remaining&&isMetaSegment(remaining)&&(sectionId==='awards'||tail.some(seg=>PERIOD_VALUE_RE.test(seg)))){tail.unshift(remaining);remaining=''}
  if(tail.length<2||(remaining&&!/[。！？；…]$/.test(remaining)))return block
  const recovered:Record<string,string>={}
  const period=tail.find(seg=>PERIOD_VALUE_RE.test(seg))
  if(period)recovered.period=period
  const rest=tail.filter(seg=>seg!==period)
  if(sectionId==='awards'){Object.assign(recovered,classifyAwardSegments(rest))}
  else{rest.forEach((value,index)=>{recovered[`extra_${index+1}`]=value})}
  if(!Object.keys(recovered).length)return block
  const body=[...lines.slice(0,-1).filter(line=>line.trim()),remaining].filter(Boolean)
  return {...block,fields:recovered,field_labels:{},display_fields:[...(block.display_fields||[]),...Object.keys(recovered).filter(k=>!(block.display_fields||[]).includes(k))],content:body.join('\n')}
}

export function hydrateContent(content:Content):Content{
  return {sections:content.sections.map(s=>({...s,blocks:s.blocks.map(b=>hydrateBlock(b,String(s.id||'')))}))}
}

// 元信息行实际渲染的值序列：去标签、去重，period 由调用方决定是否排除。
// 标签（"组织公司/熟练程度"这类数据库字段名直译）只在编辑器里出现。
export const metaValues=(b:Block,exclude:string[]=[]):string[]=>{
  const fields=b.fields||{}
  const displayed=b.display_fields||Object.keys(fields)
  const out:string[]=[]
  for(const k of displayed){
    if(exclude.includes(k))continue
    const v=String(fields[k]??'').trim()
    if(v&&!out.includes(v))out.push(v)
  }
  return out
}

// —— 技能分组与成果表格（与 services.py 的 skill_groups/awards_table_rows 同构）——
export function skillGroups(blocks:Block[]):[string,string][]{
  if(!blocks.length)return[]
  const grouped:Record<string,string[]>={};const order:string[]=[]
  for(const b of blocks){
    const fields=b.fields||{}
    const cat=String(fields.skill_group||fields.skill_category||'').trim()
    if(!cat)return[]
    if(!grouped[cat]){grouped[cat]=[];order.push(cat)}
    const prof=String(fields.proficiency||'').trim()
    const ctx=String(b.content||'').trim()
    const note=[prof,ctx].filter(Boolean).join('，')
    const label=String(b.title||'').trim()
    grouped[cat].push(note?`${label}（${note}）`:label)
  }
  return order.map(cat=>[cat,grouped[cat].join('、')])
}

export function awardsTableRows(blocks:Block[]):[string,string,string][]{
  const rows:[string,string,string][]=[]
  for(const b of blocks){
    const fields=b.fields||{}
    const period=String(fields.period_text||fields.period||'').trim()
    const result=String(fields.result_text||fields.result||'').trim()
    if(!period||!result)return[]
    const issuer=String(fields.issuer||'').trim()
    rows.push([period,String(b.title||''),issuer?`${result}（${issuer}）`:result])
  }
  return rows
}

// —— 分页权重模型（单位：px，96dpi 下的 A4 = 1123px 高）——
// 权重即估算的渲染高度，预算即版心可用高度。与 app/services.py 的
// LAYOUT_METRICS / PAGE_BUDGET_PX 是同一张表：数值由
// `python scripts/calibrate_layout.py && node web/scripts/measure_calib.mjs`
// 从真实导出 CSS 的浏览器布局中实测得出，并按“安全一侧”取整（行高与固定成本向上
// 取、每行字符数向下取），保证估算不低于实际渲染——低估会让导出正文越过 A4 底边
// 被 overflow:hidden 裁掉。
//
// 衬线模板不需要单独一列：实测 Georgia/Times 对中文会落到 SimSun，中文字宽不变，
// 每行字符数与同布局的非衬线模板一致。
const LAYOUT_METRICS:Record<string,{header:number;header_first:number;title:number;base:number;extra:number;content_line:number;units_per_line:number;meta:number;meta_units:number;pair_units_per_line:number;pair_meta_units:number}> = {
  sidebar:  {header:48, header_first:35, title:21, base:37, extra:0, content_line:17, units_per_line:75, meta:15, meta_units:53, pair_units_per_line:37, pair_meta_units:42},
  side:     {header:26, header_first:26, title:21, base:34, extra:0, content_line:15, units_per_line:28, meta:15, meta_units:15, pair_units_per_line:28, pair_meta_units:15},
  plain:    {header:48, header_first:35, title:21, base:34, extra:0, content_line:17, units_per_line:112, meta:15, meta_units:71, pair_units_per_line:54, pair_meta_units:42},
  banner:   {header:48, header_first:35, title:21, base:34, extra:0, content_line:17, units_per_line:112, meta:15, meta_units:71, pair_units_per_line:54, pair_meta_units:42},
  grid:     {header:46, header_first:36, title:21, base:34, extra:0, content_line:17, units_per_line:112, meta:15, meta_units:71, pair_units_per_line:56, pair_meta_units:42},
  line:     {header:42, header_first:29, title:21, base:40, extra:0, content_line:17, units_per_line:112, meta:15, meta_units:71, pair_units_per_line:54, pair_meta_units:42},
  timeline: {header:48, header_first:35, title:24, base:37, extra:0, content_line:17, units_per_line:98, meta:15, meta_units:71, pair_units_per_line:54, pair_meta_units:42},
  rail:     {header:13, header_first:0, title:21, base:34, extra:0, content_line:17, units_per_line:100, meta:15, meta_units:71, pair_units_per_line:54, pair_meta_units:42},
}
export const MAIN_BUDGET=1047
export const SIDE_BUDGET=1045
export const BANNER_BUDGET=948
export const GRID_BUDGET=1008
export const LINE_BUDGET=1016
export const TIMELINE_BUDGET=980
export const RAIL_BUDGET=1087
const BUDGETS:Record<string,number>={sidebar:MAIN_BUDGET,side:SIDE_BUDGET,plain:980,banner:BANNER_BUDGET,grid:GRID_BUDGET,line:LINE_BUDGET,timeline:TIMELINE_BUDGET,rail:RAIL_BUDGET}
// 紧凑档（auto-compact）：内容估算总高比一页多不出 8% 时，整页换紧凑刻度重排。
// 紧凑 CSS 的实测收缩比 ≈ 0.91 ≤ 1/TRIGGER（≈ 0.926），触发的内容装回一页不会
// 裁字。与 services.py 的 COMPACT_TRIGGER/COMPACT_BUDGET_FACTOR 与决策算法保持一致。
export const COMPACT_TRIGGER=1.08
export const COMPACT_BUDGET_FACTOR=1.15
// 求职意向横带的高度（底座 + 行高）与技能分组/成果表格的装饰成本，
// 与 services.py 的同名常量保持一致（measure_parts.mjs 实测回填）。
export const INTENT_BAND_BASE_PX=40
export const INTENT_BAND_LINE_PX=18
export const GROUP_GAP_PX=8
export const AWARDS_HEADER_PX=25
export const AWARDS_ROW_PX=27
// 侧栏首页除了栏目，还要放侧栏页头（姓名 + 联系方式 + 简介），这部分高度必须从第一
// 页的侧栏预算里扣掉，否则侧栏首页会溢出 A4 底边被裁掉。与 services.py 的
// SIDEBAR_* 常数同一口径。
const SIDEBAR_NAME_PX=51
const SIDEBAR_FIELD_PX=19
const SIDEBAR_BIO_LINE_PX=18
const SIDEBAR_HEAD_BASE_PX=20
const SIDEBAR_PHOTO_PX=144
export const HEADER_PHOTO_EXTRA_PX=64
// 双栏收尾：短栏目两两并排（一行两个模块）。时间轴保持单列，左时间栏是它的
// 识别特征。配对只发生在相邻栏目之间以保持栏目顺序，且必须真正省下纵向空间才
// 配对——半宽折行会让正文变高，落差悬殊的栏目并排反而更费版面。
// 并排（一行两栏）**只作为例外**，整宽通排才是默认版式；早先只按"并排省版面"决定
// 配对，密集内容下每一行都成了两栏，四种版式全变成同一张两列表格。现在按布局给
// "每页最多并排几行"的额度（侧栏布局一页已是两列、时间轴的左时间栏是识别特征，
// 都给 0；表格表单是表格语汇，给 2）。并排上限 = 页预算 × PAIR_MAX_SHARE，再按半栏
// 宽度等比收紧，0.26 让只有真正的短栏目能并排。常数与 app/services.py 的
// PAIR_BUDGET_BY_LAYOUT/PAIR_MAX_SHARE/PAIR_REF_CHARS/PAIR_MIN_SAVING 保持一致。
const PAIR_BUDGET_BY_LAYOUT:Record<string,number>={sidebar:0,side:0,plain:0,banner:0,grid:3,line:0,timeline:0,rail:0}
const PAIR_MAX_SHARE=0.4
const PAIR_REF_CHARS=33
const PAIR_MIN_SAVING=20
// 两栏高度要相当才并排：短栏至少达到高栏的一半，否则短栏底下空出一大块、主经历还会
// 被压成半宽。相对比例而非绝对像素——像素阈值会连带推掉高度相当的好配对。
const PAIR_MIN_BALANCE=0.35
type Metrics=typeof LAYOUT_METRICS[string]
const pairBudgetFor=(layout:string)=>PAIR_BUDGET_BY_LAYOUT[layout]??0
// 当前布局允许的并排单元高度上限（半栏越窄上限越低）。
const pairHeightCap=(layout:string,budget:number)=>{
  const style=LAYOUT_METRICS[layout]||LAYOUT_METRICS.sidebar
  return Math.min(style.pair_units_per_line/PAIR_REF_CHARS,1)*budget*PAIR_MAX_SHARE
}
// 侧栏页头（姓名 + 联系方式 + 简介）的估算高度，与 services.py 的
// sidebar_head_height 同一公式：姓名行 + 每个联系字段一行 + 简介行数。
export const sidebarHeadHeight=(basic:Block|undefined):number=>{
  const style=LAYOUT_METRICS.side
  let rows=0
  for(const value of metaValues(basic||{id:'',title:'',content:'',source_refs:[],origin:'fact'})){
    rows+=Math.max(1,Math.ceil(textUnits(value)/style.meta_units))
  }
  const bioLines=contentLineCount(basic?.content||'',style.units_per_line)
  return SIDEBAR_HEAD_BASE_PX+(basic?.photo?SIDEBAR_PHOTO_PX:0)+SIDEBAR_NAME_PX+rows*SIDEBAR_FIELD_PX+bioLines*SIDEBAR_BIO_LINE_PX
}
export const headerPhotoHeight=(basic:Block|undefined,layout:string)=>layout==='sidebar'||!basic?.photo?0:HEADER_PHOTO_EXTRA_PX
// Section order and packing budget per template layout; mirrors render_resume_html().
// 侧栏布局：基本信息由侧栏页头（姓名 + 联系方式 + 简介）呈现，不再重复成栏目；
// 技能与成果在侧栏，主栏承载其余栏目。其余布局的姓名与联系方式由页头呈现，
// 求职目标变成页头下的一条意向横带（见 targetBand），不再是独立栏目。
export const layoutMainIds=(layout:string)=>layout==='sidebar'?MAIN_IDS:ALL_IDS.filter(id=>id!=='basics'&&id!=='target')
// 按布局直接查表：曾用一串条件挑预算，plain 没有分支而落到 sidebar 的预算上，
// 凭空多出近百像素，导出正文因此越过 A4 底边被裁掉。
export const layoutBudget=(layout:string)=>BUDGETS[layout]??MAIN_BUDGET
// 被关掉的栏目（内容里的 visibility=false）不参与编排：与导出端
// app/services.py 的 section_visible 同一判断。若不在这里滤掉，它会照占版面预算，
// 预览的断页就与导出对不上。
export const sectionVisible=(content:Content,sid:string)=>section(content,sid).visibility!==false
export const renderableIds=(content:Content,ids:string[])=>ids.filter(sid=>sectionVisible(content,sid))

// 求职意向横带：主文案取条目标题（与栏目同名时退回正文），辅助文案是策略句；
// 占位文案不上纸面。高度与导出端 intent band 的估算同一公式。
const PLACEHOLDER_STRATEGY='请填写与目标岗位匹配的简历强调方向。'
export const targetBand=(content:Content,layout:string)=>{
  const s=section(content,'target')
  if(!s.visibility)return null
  const block=s.blocks.find(b=>String(b.content||'').trim()||String(b.title||'').trim())||null
  if(!block)return null
  const bandTitle=String(block.title||'').trim()
  let copy=String(block.content||'').trim()
  if(copy===PLACEHOLDER_STRATEGY)copy=''
  const primary=bandTitle&&bandTitle!==labels.target?bandTitle:copy
  // 辅助文案只在确实不同于主文案时才排：条目标题与正文都写成岗位方向的情况真实存在
  // （例如工作副本里正文被填成同一个词），否则横带会把同一个词打印两遍。导出端同一判断。
  const secondary=primary===bandTitle&&bandTitle&&copy&&copy!==primary?copy:''
  if(!primary)return null
  const unitsPerLine=(LAYOUT_METRICS[layout]||LAYOUT_METRICS.sidebar).units_per_line
  const height=INTENT_BAND_BASE_PX+Math.ceil(textUnits(`${primary}${secondary}`)/unitsPerLine)*INTENT_BAND_LINE_PX
  return {primary,secondary,height}
}

export type FlowUnit={kind:'flow';section:Section;block:Block;continued?:boolean;weight?:number}
export type PairUnit={kind:'pair';sectionA:Section;blocksA:Block[];sectionB:Section;blocksB:Block[];weight:number}
export type Unit=FlowUnit|PairUnit

const emptyBlock=(sid:string):Block=>({id:`${sid}--empty`,title:'',content:'',source_refs:[],origin:'empty'})
// 空栏目在画布上只显示一条"点击选择资料"的占位行，不占版面预算。这样预览的断点与
// 导出完全一致——导出端（app/services.py）直接把这些栏目剔掉不排。
const isPlaceholder=(block:Block)=>block.origin==='empty'
// 正文行数：末尾换行先去掉——render_markdown 会把它变成行尾 <br>，而行尾 <br> 不
// 产生新的行盒；按“多一行”计价会让每条内容凭空高一整行（真实正文大多以换行结尾），
// 页数因此被高估、页面被过早切断。与 services.py 的 content_line_count 同一口径。
// 字宽单位：全角记 2、其余记 1。折行按字宽而不是字数，中文正文与带拉丁词的正文
// 才能共用一套每行容量常数。与 services.py 的 text_units 同一口径。
const textUnits=(text:string)=>{
  let total=0
  for(const char of text){
    const code=char.codePointAt(0)||0
    const wide=(code>=0x1100&&code<=0x115f)||(code>=0x2e80&&code<=0x303e)||(code>=0x3041&&code<=0x33ff)
      ||(code>=0x3400&&code<=0x4dbf)||(code>=0x4e00&&code<=0x9fff)||(code>=0xa000&&code<=0xa4cf)
      ||(code>=0xac00&&code<=0xd7a3)||(code>=0xf900&&code<=0xfaff)||(code>=0xfe30&&code<=0xfe6f)
      ||(code>=0xff00&&code<=0xff60)||(code>=0xffe0&&code<=0xffe6)||(code>=0x20000&&code<=0x3fffd)
    total+=wide?2:1
  }
  return total
}
const contentLineCount=(content:string,unitsPerLine:number)=>{
  const text=String(content||'').replace(/\n+$/,'')
  if(!text)return 0
  return text.split('\n').reduce((s,seg)=>s+Math.max(1,Math.ceil(textUnits(seg)/unitsPerLine)),0)
}
const metaFieldLines=(b:Block,side:boolean,unitsPerLine:number)=>{
  const values=metaValues(b,['period','period_text'])
  if(!values.length)return 0
  if(side)return values.reduce((s,v)=>s+Math.max(1,Math.ceil(textUnits(v)/unitsPerLine)),0)
  return Math.max(1,Math.ceil(textUnits(values.join(' · '))/unitsPerLine))
}
// 与 services.py 的 section_item_weight 同一公式：固定成本 + 正文行数 × 行高
// + 元信息行数 × 行高，否则预览分页与导出断点会错位。
// 该条目是否渲染自己的标题行（与栏目标题同名时由栏目承载，不再重复渲染），
// 以及条目标题行的成本——与 services.py 的 block_has_title/section_item_weight 同口径。
const blockHasTitle=(block:Block,sid:string)=>{
  const title=String(block.title||'')
  return !!title&&title!==(labels[sid]||sid)
}
const itemWeight=(block:Block,style:Metrics,sid:string)=>{
  const weight=style.base+style.extra+contentLineCount(block.content,style.units_per_line)*style.content_line+metaFieldLines(block,false,style.meta_units)*style.meta
  return weight-(blockHasTitle(block,sid)?0:style.title)
}

// 把栏目切成页面单元并分页：flow = 某栏目的一个条目（栏目标题行按页计一次），
// pair = 相邻两个短栏目并排成一行两个模块。与 render_resume_html() 的
// stream_pages 逐项镜像，预览分页与导出断点保持一致。
//
// 配对以栏目顺序为准，只并排相邻栏目，因此不会打乱栏目次序；并且只在真正省下
// 纵向空间时成立。pair 是原子单元，放不下当前页剩余空间时退化回两个 flow 单元，
// 避免为等一整对而空出大半页、形成只有一两行的尾页。
//
// inSidebar 决定用哪一列的口径计价——侧栏版心只有约 44mm，每行字数与条目固定成本
// 都和主栏差一个量级，用错口径会让整页的估算失真。firstPageHead 是首页额外的固定
// 占用（侧栏页头 / 意向横带），只从第一页扣。stats.total 回传全部内容的估算总高，
// 供紧凑档决策使用（与 paginate 的 stats 同口径）。
export function streamItems(content:Content,ids:string[],budget:number,inSidebar:boolean,layout:string='',firstPageHead=0,stats?:{total:number}):Unit[][]{
  const styleFor=()=>LAYOUT_METRICS[inSidebar?'side':layout]||LAYOUT_METRICS.side
  const sectionOf=(id:string)=>section(content,id)
  const blocksOf=(sid:string)=>sectionOf(sid).blocks
  const fragmentFlow=(sid:string,blocks:Block[]):Unit[]=>{
    const style=styleFor()
    const limit=fragmentLimit(inSidebar)
    const out:Unit[]=[]
    if(!blocks.length){
      // 空栏目保留标题行（选择/添加来源的点击入口）。
      out.push({kind:'flow',section:sectionOf(sid),block:emptyBlock(sid)})
      return out
    }
    // 技能按分类合并成一行一类；成果（非侧栏）排成三列表格。与 fragment_flow 同构。
    if(sid==='skills'){
      const groups=skillGroups(blocks)
      if(groups.length){
        for(const [category,line] of groups){
          const text=`**${category}**：${line}`
          out.push({kind:'flow',section:sectionOf(sid),block:{id:`${sid}--group-${category}`,title:'',content:text,fields:{},display_fields:[],source_refs:[],origin:'skill-group'},weight:contentLineCount(text,style.units_per_line)*style.content_line+GROUP_GAP_PX})
        }
        return out
      }
    }
    if(sid==='awards'&&!inSidebar){
      const rows=awardsTableRows(blocks)
      if(rows.length){
        out.push({kind:'flow',section:sectionOf(sid),block:{id:`${sid}--table`,title:'',content:'',fields:{},display_fields:[],source_refs:[],origin:'awards-table',table_rows:rows},weight:AWARDS_HEADER_PX+rows.length*AWARDS_ROW_PX})
        return out
      }
    }
    for(const block of blocks){
      const chunks=splitText(block.content||'',limit)
      // 续段只带正文：重复标题与元信息会让同一个条目看起来出现两次。
      chunks.forEach((chunk,index)=>out.push({kind:'flow',section:sectionOf(sid),block:{...block,title:index?'':block.title,id:index?`${block.id}--fragment-${index}`:block.id,content:chunk,fields:index===0?block.fields:{},display_fields:index===0?block.display_fields:[],fragment_index:index,continuation:index>0}}))
    }
    return out
  }
  // 整栏估算高度：栏目标题行 + 各条目（固定成本 + 正文行 + 元信息行）。
  const columnHeight=(sid:string,charsPerLine:number,metaChars:number)=>{
    const style=styleFor()
    const blocks=blocksOf(sid)
    let total=style.header
    if(!blocks.length)return total+style.base
    if(sid==='skills'){
      const groups=skillGroups(blocks)
      if(groups.length){
        for(const [category,line] of groups){
          total+=contentLineCount(`**${category}**：${line}`,charsPerLine)*style.content_line+GROUP_GAP_PX
        }
        return total
      }
    }
    if(sid==='awards'&&!inSidebar){
      const rows=awardsTableRows(blocks)
      if(rows.length)return total+AWARDS_HEADER_PX+rows.length*AWARDS_ROW_PX
    }
    for(const block of blocks){
      total+=style.base+style.extra+contentLineCount(block.content,charsPerLine)*style.content_line+metaFieldLines(block,false,metaChars)*style.meta
      if(!blockHasTitle(block,sid))total-=style.title
    }
    return total
  }
  // 相邻两栏并排的估算高度；不值得配对时返回 null（保持整宽通排）。
  const pairHeight=(sid:string,sid2:string):number|null=>{
    const style=LAYOUT_METRICS[layout]||LAYOUT_METRICS.sidebar
    const stacked=columnHeight(sid,style.units_per_line,style.meta_units)+columnHeight(sid2,style.units_per_line,style.meta_units)
    const heightA=columnHeight(sid,style.pair_units_per_line,style.pair_meta_units)
    const heightB=columnHeight(sid2,style.pair_units_per_line,style.pair_meta_units)
    const paired=Math.max(heightA,heightB)
    if(paired>pairHeightCap(layout,budget)||stacked-paired<PAIR_MIN_SAVING)return null
    if(Math.min(heightA,heightB)<paired*PAIR_MIN_BALANCE)return null
    return paired
  }

  const units:Unit[]=[]
  const pairable=!inSidebar&&pairBudgetFor(layout)>0
  const pairBudget=inSidebar?0:pairBudgetFor(layout)
  let index=0
  while(index<ids.length){
    const sid=ids[index]
    if(pairable&&index+1<ids.length){
      const sid2=ids[index+1]
      const weight=pairHeight(sid,sid2)
      if(weight!==null){
        units.push({kind:'pair',sectionA:sectionOf(sid),blocksA:blocksOf(sid),sectionB:sectionOf(sid2),blocksB:blocksOf(sid2),weight})
        index+=2
        continue
      }
    }
    units.push(...fragmentFlow(sid,blocksOf(sid)))
    index+=1
  }

  const pages:Unit[][]=[];let current:Unit[]=[];let size=0;let totalSize=firstPageHead;let currentId:string|null=null
  let pairsOnPage=0
  const pageBudget=()=>budget-(pages.length?0:firstPageHead)
  // 页内是否已有真正的正文（空栏目占位行不算，否则它会替后面的第一个栏目把
  // header_first 的便宜占掉，预览就会比导出更早断页）。
  const hasContent=()=>current.some(u=>u.kind==='pair'||!isPlaceholder(u.block))
  let cursor=0
  while(cursor<units.length){
    const unit=units[cursor]
    if(unit.kind==='pair'){
      // 本页并排额度用完就整宽通排：并排是"让短栏目别独占一行"的例外手段，不是默认版式。
      if(pairsOnPage<pairBudget&&(!hasContent()||size+unit.weight<=pageBudget())){current.push(unit);size+=unit.weight;totalSize+=unit.weight;pairsOnPage+=1;cursor+=1;continue}
      // 放不下当前页剩余的这一点空间：退化成两个整宽栏目接着排，把本页填满。
      units.splice(cursor,1,...fragmentFlow(unit.sectionA.id,unit.blocksA),...fragmentFlow(unit.sectionB.id,unit.blocksB))
      continue
    }
    const style=styleFor()
    if(isPlaceholder(unit.block)){unit.continued=false;current.push(unit);cursor+=1;continue}
    const w=itemWeight(unit.block,style,unit.section.id)
    let header=unit.section.id!==currentId?style.header:0
    if(hasContent()&&size+w+header>pageBudget()){pages.push(current);current=[];size=0;currentId=null;pairsOnPage=0;header=style.header_first}
    if(header){size+=header;totalSize+=header;currentId=unit.section.id}
    unit.continued=false
    current.push(unit);size+=w;totalSize+=w
    cursor+=1
  }
  if(current.length||!pages.length)pages.push(current)
  const seen=new Set<string>()
  for(const page of pages){
    const local=new Set<string>()
    for(const unit of page){
      if(unit.kind==='flow'){unit.continued=seen.has(unit.section.id);local.add(unit.section.id)}
    }
    for(const key of local)seen.add(key)
  }
  if(stats)stats.total=totalSize
  return pages
}

// 带紧凑档决策的分页：与 render_resume_html 的两段式 packing 同一算法——
// 普通刻度装不下、但总高不超过一页的 10% 时，用放大的预算重排一次，让内容以
// .compact 的收紧刻度装进一页。
export function streamPages(content:Content,ids:string[],budget:number,inSidebar:boolean,layout:string='',firstPageHead=0):{pages:Unit[][];compact:boolean}{
  const stats:{total:number}={total:0}
  const pages=streamItems(content,ids,budget,inSidebar,layout,firstPageHead,stats)
  if(pages.length>1&&ids.length&&stats.total<=budget*COMPACT_TRIGGER){
    const tighter=streamItems(content,ids,Math.floor(budget*COMPACT_BUDGET_FACTOR),inSidebar,layout,firstPageHead)
    if(tighter.length===1)return {pages:tighter,compact:true}
  }
  return {pages,compact:false}
}

// 工具页（Editor/Composer）的页数口径：先做字段兜底回收，再按布局预算 + 意向横带
// 估算，与画布/导出同一套。侧栏布局里横带占主栏首页、页头占侧栏首页，两者分开扣。
export function pageCountOf(content:Content,layout:string):number{
  const hydrated=hydrateContent(content)
  const band=targetBand(hydrated,layout)
  const sideHead=sidebarHeadHeight(section(hydrated,'basics').blocks[0])
  const basic=section(hydrated,'basics').blocks[0]
  const {pages}=streamPages(hydrated,renderableIds(hydrated,layoutMainIds(layout)),layoutBudget(layout),false,layout,(band?.height||0)+headerPhotoHeight(basic,layout))
  const sidePages=layout==='sidebar'?streamItems(hydrated,renderableIds(hydrated,SIDE_IDS),SIDE_BUDGET,true,'sidebar',sideHead):[]
  return Math.max(pages.length,sidePages.length,1)
}
