// Template descriptor plumbing: the backend registry (app/templates.py) is the
// single source of truth; these helpers turn its payload into CSS variables so
// the canvas needs no per-template stylesheets.
import type { CSSProperties } from 'react'

export type TemplateLayout = 'sidebar' | 'plain' | 'banner' | 'grid' | 'line' | 'timeline'
// Row of GET /api/templates.
export type TemplateDescriptor = { id:number; slug:string; name:string; description:string; layout:string; serif?:boolean; tokens:Record<string,string>; version:number|null; template_version_id:number }
// Template info embedded in resume payloads (GET /api/resumes/{id}.template).
export type TemplateInfo = { slug:string; name:string; layout:string; serif?:boolean; tokens?:Record<string,string>; template_version_id?:number; template_id?:number } | null

// Classic palette doubles as the CSS fallback in styles.css.
export const CLASSIC_TOKENS:Record<string,string> = { sidebar_bg:'#163b43', sidebar_fg:'#f4f7f4', sidebar_muted:'#cad9d5', sidebar_heading:'#a7c9c2', heading:'#17343a', title:'#263f40', meta:'#66807b', meta_label:'#527875', copy:'#4c605d', accent:'#236b74', rule:'#d5e0dc' }
export const DEFAULT_TEMPLATE:TemplateInfo = { slug:'classic', name:'经典侧栏模板', layout:'sidebar', tokens:CLASSIC_TOKENS }

const VAR_NAMES:Record<string,string> = { sidebar_bg:'--t-sidebar-bg', sidebar_fg:'--t-sidebar-fg', sidebar_muted:'--t-sidebar-muted', sidebar_heading:'--t-sidebar-heading', heading:'--t-heading', title:'--t-title', meta:'--t-meta', meta_label:'--t-meta-label', copy:'--t-copy', accent:'--t-accent', rule:'--t-rule' }

// Inline style mapping a template's palette onto the CSS custom properties
// consumed by .resume-paper / .resume-banner rules.
export function templateVars(template?:TemplateInfo):CSSProperties{
  const tokens={...CLASSIC_TOKENS,...(template?.tokens||{})}
  const style:Record<string,string>={}
  for(const [key,value] of Object.entries(tokens)) if(VAR_NAMES[key]) style[VAR_NAMES[key]]=value
  return style as CSSProperties
}

export const layoutLabel=(layout?:string)=>layout==='plain'?'单栏通排':layout==='banner'?'横幅单栏':layout==='grid'?'表格表单':layout==='line'?'经典线式':layout==='timeline'?'时间轴通排':'侧栏双栏'

// Miniature thumbnail for template pickers, generated from the palette: dark
// band = 侧栏/横幅底色/表头行, tinted band = 分隔线/纸面, accent bar = 时间轴线。
export function templateThumbStyle(template:TemplateDescriptor):CSSProperties{
  const t={...CLASSIC_TOKENS,...template.tokens}
  if(template.layout==='banner') return {background:`linear-gradient(${t.sidebar_bg} 0 26%, #fff 26%)`}
  if(template.layout==='plain') return {background:`linear-gradient(#fff 0 18%, ${t.rule} 18% 100%)`}
  if(template.layout==='grid') return {background:`linear-gradient(#fff 0 24%, ${t.sidebar_bg} 24% 34%, #fff 34% 58%, ${t.rule} 58% 62%, #fff 62%)`,boxShadow:`inset 0 0 0 1px ${t.rule}`}
  if(template.layout==='line') return {background:`linear-gradient(#fff 0 26%, ${t.sidebar_bg} 26% 29%, #fff 29% 55%, ${t.rule} 55% 58%, #fff 58%)`}
  if(template.layout==='timeline') return {background:`linear-gradient(90deg, #fff 0 30%, ${t.accent} 30% 32%, #fff 32%)`}
  return {background:`linear-gradient(105deg, ${t.sidebar_bg} 0 30%, #fff 30%)`}
}
