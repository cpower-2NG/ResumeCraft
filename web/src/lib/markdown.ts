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
