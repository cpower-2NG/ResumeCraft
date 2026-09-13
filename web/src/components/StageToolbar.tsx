export function StageToolbar({zoom,setZoom,pageCount}:{zoom:number;setZoom:(v:number)=>void;pageCount:number}){
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
