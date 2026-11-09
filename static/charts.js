const COLORS={Excellent:'#0e7c7b',Good:'#2f6fb0',Average:'#b87a0a',Poor:'#b83a2e'};
const BASE={margin:{t:20,r:15,b:45,l:45},font:{family:'IBM Plex Sans, sans-serif',size:12,color:'#1b2a41'},
  paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',xaxis:{gridcolor:'#e7ebf1'},yaxis:{gridcolor:'#e7ebf1'}};
function draw(id,data,layout){
  const el=document.getElementById(id);if(!el)return;
  Plotly.newPlot(el,data,Object.assign({},BASE,layout||{}),{displayModeBar:false,responsive:true});
}
function line(id,s,color,yTitle,range){
  if(!s||!s.x.length){document.getElementById(id).innerHTML='<p class="text-muted pt-4">No data yet.</p>';return;}
  draw(id,[{x:s.x,y:s.y,mode:'lines+markers',line:{color:color,width:2.5},marker:{size:7}}],
       {yaxis:{title:yTitle,range:range,gridcolor:'#e7ebf1'}});
}
function bars(id,s,yTitle){
  if(!s||!s.x.length){document.getElementById(id).innerHTML='<p class="text-muted pt-4">No data yet.</p>';return;}
  draw(id,[{x:s.x,y:s.y,type:'bar',marker:{color:s.y.map(v=>v<50?COLORS.Poor:v<70?COLORS.Average:v<85?COLORS.Good:COLORS.Excellent)},
       text:s.y.map(v=>v.toFixed(0)),textposition:'outside'}],{yaxis:{title:yTitle,range:[0,105],gridcolor:'#e7ebf1'}});
}
