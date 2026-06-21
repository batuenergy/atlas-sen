var D=window.__ATLAS_DATA__;var REG=D.REG;
var PLAY='<svg width="11" height="11" viewBox="0 0 11 11"><path d="M2 1l8 4.5-8 4.5z" fill="#1A1A18"/></svg>';
var PAUSE='<svg width="11" height="11" viewBox="0 0 11 11"><rect x="2" y="1" width="2.5" height="9" fill="#1A1A18"/><rect x="6.5" y="1" width="2.5" height="9" fill="#1A1A18"/></svg>';
var map=L.map('map',{zoomControl:false,attributionControl:false}).setView([23.6,-102],5);
L.control.attribution({prefix:false,position:'bottomright'}).addAttribution('© OpenStreetMap · CARTO').addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',{subdomains:'abcd',maxZoom:19}).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png',{subdomains:'abcd',maxZoom:19,opacity:.6}).addTo(map);
var CAP=8;
function rad(mw){return Math.min(CAP,Math.max(2,0.12*Math.pow(Math.max(mw,0),0.62)));}
function capForZoom(z){return Math.max(8,Math.min(16,8+(z-5)*2.2));}
map.on('zoomend',function(){var nc=capForZoom(map.getZoom());if(nc!==CAP){CAP=nc;redraw();}});
function satCol(s){if(s==null)return '#D8D5CE';if(s>=1.5)return '#A32D2D';if(s>=1.1)return '#E24B4A';if(s>=0.8)return '#E08585';return '#EBC4C4';}
function satWord(s){if(s==null)return'sin datos';if(s>=1.5)return'crítica';if(s>=1.1)return'saturada';if(s>=0.8)return'en balance';return'holgada';}
function satTone(s){if(s==null)return'#6B6B66';if(s>=1.5)return'#A32D2D';if(s>=1.1)return'#C2410C';if(s>=0.8)return'#6B6B66';return'#1D7A4F';}
function satHTML(s){if(s==null)return '<span class="tag">Saturación: sin datos</span>';return 'Saturación <b style="color:'+satTone(s)+'">'+s.toFixed(2)+'×</b> · <span style="color:'+satTone(s)+'">'+satWord(s)+'</span><br><span class="tag">generación conectada ÷ (capacidad de transformación, MVA × 0.9). &gt;1 = más generación que la red local puede transformar</span>';}
var genGroup=L.layerGroup().addTo(map),hubGroup=L.layerGroup().addTo(map),conGroup=L.layerGroup(),satGroup=L.layerGroup(),zoneGroup=L.layerGroup(),tzGroup=L.layerGroup();
map.createPane('linesPane');map.getPane('linesPane').style.zIndex=350;
var lineRenderer=L.svg({pane:'linesPane'}),lineGroup=L.layerGroup();
function lineStyle(kv){if(kv>=400)return['#A32D2D',1.6,.6];if(kv>=230)return['#C2410C',1.2,.52];if(kv>=115)return['#7C8AA0',.8,.46];return['#B8B3A8',.6,.4];}
(D.OL||[]).forEach(function(o){var s=lineStyle(o[0]);lineGroup.addLayer(L.polyline(o[1],{renderer:lineRenderer,color:s[0],weight:s[1],opacity:s[2],interactive:false}));});
// CENACE control-region territories (choropleth, below lines/markers)
map.createPane('regionsPane');map.getPane('regionsPane').style.zIndex=300;
var rgnRenderer=L.svg({pane:'regionsPane'}),rgnGroup=L.layerGroup();
var REGPAL=['#3C7DC4','#1D9E75','#D8803A','#9B6BD8','#C94F7C','#5BA3A0','#C9A227','#7C8AA0','#8A6240','#639922'];
var RMETA={};(D.R||[]).forEach(function(r){RMETA[r[0]]=r;});
Object.keys(D.RP||{}).forEach(function(rn){var ci=REG.indexOf(rn);var col=REGPAL[(ci<0?0:ci)%REGPAL.length];
  var m=RMETA[rn];var cap=m?('<br>'+Math.round(m[1]).toLocaleString()+' MW generación · '+Math.round(m[2]).toLocaleString()+' MVA AT'):'';
  (D.RP[rn]||[]).forEach(function(poly){var pg=L.polygon(poly,{renderer:rgnRenderer,color:col,weight:1.2,opacity:.55,fillColor:col,fillOpacity:.13});
    pg.bindTooltip('Región '+rn,{sticky:true});pg.bindPopup('<b>Región '+rn+'</b> · control CENACE'+cap+'<br><a class="poplink" onclick="openDemandForRegion(\''+rn+'\')">Ver demanda en vivo →</a>');rgnGroup.addLayer(pg);});});
var on={gen:true,hub:true,con:false,sat:false,zone:false,tz:false,line:false,rgn:false};
var f={src:{},grp:'',mkt:'',mw:0,cod:0,reg:'',kv:'',mva:0,sat:0,zona:'',tdiv:'',year:0};
Object.keys(D.T).forEach(function(t){f.src[t]=true;});
var T={on:false,year:2026,agg:'cum',big:false};
function filtBase(p){return f.src[p[4]] && (!f.grp||p[7]===f.grp) && (!f.mkt||p[8]===f.mkt) && p[3]>=f.mw && (!f.reg||REG[p[6]]===f.reg) && (!f.zona||p[14]===f.zona) && (!f.tdiv||p[15]===f.tdiv);}
function plantPass(p){
  if(!filtBase(p))return false;
  if(f.cod!==0 && !(p[9]&&p[9]>=f.cod))return false;
  if(f.year)return p[9]===f.year;
  if(T.on)return p[9]>0 && p[9]<=T.year;
  return true;}
function hubPass(h){return (!f.kv||h[3]===+f.kv) && h[4]>=f.mva && (f.sat===0||(h[6]!=null&&h[6]>=f.sat)) && (!f.reg||REG[h[7]]===f.reg) && (!f.zona||h[8]===f.zona) && (!f.tdiv||h[9]===f.tdiv);}
// markers (persistent; styled on redraw for dissolve)
var plantM=D.P.map(function(p){
  var col=(D.T[p[4]]||['?','#999'])[1];
  var m=L.circleMarker([p[1],p[2]],{radius:rad(p[3]),stroke:true,color:'#fff',weight:0.75,opacity:0.6,fillColor:col,fillOpacity:.8});
  var own=p[7]?('<br>'+p[7]):'';var mkt=p[8]?(' · '+p[8]):'';var cod=p[9]?(' · '+p[9]):'';
  var con=p[10]?('<br><span class="tag">conecta a '+p[10]+(p[11]!=null?' · ~'+p[11]+' km':'')+'</span>'):'';
  var zn=p[14]?('<br><span class="tag">zona '+p[14]+'</span>'):'';var td=p[15]?(' <span class="tag">tarifa '+p[15]+'</span>'):'';
  m.bindPopup('<b>'+p[0]+'</b><br>'+p[3].toLocaleString()+' MW · '+(D.T[p[4]]||['?'])[0]+mkt+cod+zn+td+own+con);
  return {m:m,r:p,base:(p[5]==='l'?.5:.8)};
});
plantM.slice().sort(function(a,b){return a.r[3]-b.r[3];}).forEach(function(o){genGroup.addLayer(o.m);});
function hubR(h){return Math.max(2.5,Math.min(4.5,(h[4]||40)/260+2.5));}
var hubM=D.H.map(function(h){
  var m=L.circleMarker([h[1],h[2]],{radius:hubR(h),color:'#64748B',weight:h[3]>=400?1.5:0.9,fill:false,opacity:.85});
  var st=h[6]!=null?('<br>'+satHTML(h[6])):'';var hzn=h[8]?('<br><span class="tag">zona '+h[8]+'</span>'):'';var htd=h[9]?(' <span class="tag">tarifa '+h[9]+'</span>'):'';
  m.bindPopup('<b>'+h[0]+'</b><br>'+h[3]+' kV'+(h[4]?' · '+h[4].toLocaleString()+' MVA':'')+(h[5]?'<br>'+h[5].toLocaleString()+' MW conectados':'')+st+hzn+htd);
  hubGroup.addLayer(m);return {m:m,r:h};
});
D.P.forEach(function(p){if(p[12]!=null&&p[11]>0.15){var pl=L.polyline([[p[1],p[2]],[p[12],p[13]]],{color:'#C9C6BC',weight:1,opacity:.7});conGroup.addLayer(pl);
  conGroup.addLayer(L.circleMarker([p[12],p[13]],{radius:2,stroke:false,fillColor:'#C9C6BC',fillOpacity:.8}));}});
D.R.forEach(function(r){var c=L.circleMarker([r[3],r[4]],{radius:Math.max(13,Math.sqrt(r[1])*0.32),color:satCol(r[5]),weight:2,fillColor:satCol(r[5]),fillOpacity:.14});
  c.bindPopup('<b>'+r[0]+'</b><br>'+r[1].toLocaleString()+' MW generación · '+r[2].toLocaleString()+' MVA transformación AT<br>'+satHTML(r[5]));satGroup.addLayer(c);});
// CFE tariff-division polygons
var TZPAL=['#7F77DD','#1D9E75','#D85A30','#378ADD','#C9A227','#534AB7','#97C459','#A98B63','#185FA5','#D4537E','#0F6E56','#993C1D','#3C3489','#639922','#854F0B','#5DCAA5','#B4537E'];
var tzNames=Object.keys(D.TZ||{}).sort();
tzNames.forEach(function(dv,i){var col=TZPAL[i%TZPAL.length];
  (D.TZ[dv]||[]).forEach(function(poly){
    var pg=L.polygon(poly,{color:col,weight:1,opacity:.6,fillColor:col,fillOpacity:.14});
    pg.bindTooltip('División tarifaria: '+dv,{sticky:true});tzGroup.addLayer(pg);});});
var ZHULL={};(D.Z||[]).forEach(function(z){ZHULL[z[0]]=z;});
function drawZone(name){zoneGroup.clearLayers();if(!name||!ZHULL[name]){map.removeLayer(zoneGroup);return;}
  var z=ZHULL[name];var poly=L.polygon(z[2],{color:'#185FA5',weight:1.5,opacity:.8,fillColor:'#185FA5',fillOpacity:.07});
  poly.bindTooltip(z[0]+' · '+z[1]+' · '+z[5]+' subest.');zoneGroup.addLayer(poly);zoneGroup.addTo(map);
  try{map.fitBounds(poly.getBounds().pad(0.25),{maxZoom:8});}catch(e){}}
function show(o,vis,op,rr){o.m.setStyle({fillOpacity:vis?op:0});o.m.setRadius(vis?rr:0);}
function redraw(){
  var pv=0,hv=0,desat=on.sat;
  plantM.forEach(function(o){var ok=on.gen&&plantPass(o.r);if(ok)pv++;show(o,ok,desat?.16:o.base,rad(o.r[3]));});
  hubM.forEach(function(o){var ok=on.hub&&hubPass(o.r);if(ok)hv++;o.m.setStyle({opacity:ok?.85:0});o.m.setRadius(ok?hubR(o.r):0);});
  // tally
  var gw=0;plantM.forEach(function(o){if(on.gen&&plantPass(o.r))gw+=o.r[3];});
  document.getElementById('tally').innerHTML='<b>'+pv.toLocaleString()+'</b> plantas · <b>'+hv.toLocaleString()+'</b> nodos · <b>'+(gw/1000).toFixed(1)+'</b> GW';
  document.getElementById('empty').style.display=(pv===0&&hv===0)?'block':'none';
  // source row counts
  var bt={};plantM.forEach(function(o){if(on.gen&&plantPass(o.r))bt[o.r[4]]=(bt[o.r[4]]||0)+o.r[3];});
  document.querySelectorAll('#srcrows .row').forEach(function(row){var t=row.getAttribute('data-t');var c=row.querySelector('.ct');if(c)c.textContent=Math.round(bt[t]||0).toLocaleString();});
  // active-filter badge
  var act=0;if(f.grp)act++;if(f.mkt)act++;if(f.mw>0)act++;if(f.cod>0)act++;if(f.reg)act++;if(f.kv)act++;if(f.mva>0)act++;if(f.sat>0)act++;if(f.year)act++;
  if(Object.keys(D.T).some(function(t){return !f.src[t];}))act++;
  var b=document.getElementById('fbadge');b.textContent=act;b.classList.toggle('on',act>0);
  if(T.on)buildTimeChart();
}
function layer(k,vis){on[k]=vis;document.getElementById('lr_'+k).classList.toggle('on',vis);document.getElementById('lr_'+k).classList.toggle('off',!vis);
  if(k==='gen')vis?genGroup.addTo(map):map.removeLayer(genGroup);
  if(k==='hub')vis?hubGroup.addTo(map):map.removeLayer(hubGroup);
  if(k==='con')vis?conGroup.addTo(map):map.removeLayer(conGroup);
  if(k==='sat')vis?satGroup.addTo(map):map.removeLayer(satGroup);
  if(k==='zone')vis?zoneGroup.addTo(map):map.removeLayer(zoneGroup);
  if(k==='tz')vis?tzGroup.addTo(map):map.removeLayer(tzGroup);
  if(k==='line')vis?lineGroup.addTo(map):map.removeLayer(lineGroup);
  if(k==='rgn')vis?rgnGroup.addTo(map):map.removeLayer(rgnGroup);
  redraw();}
// activation toggle (the checkbox), independent of expand
document.querySelectorAll('.sw[data-tog]').forEach(function(sw){var k=sw.getAttribute('data-tog');sw.onclick=function(e){e.stopPropagation();layer(k,!on[k]);};});
// expand/collapse filters (the chevron + label), independent of on/off
var exp={gen:true,hub:true};
function toggleExp(k){exp[k]=!exp[k];document.getElementById(k==='gen'?'genfilters':'netfilters').classList.toggle('show',exp[k]);
  document.querySelectorAll('.chev[data-exp="'+k+'"]').forEach(function(c){c.classList.toggle('open',exp[k]);});}
document.querySelectorAll('[data-exp]').forEach(function(el){el.onclick=function(e){e.stopPropagation();toggleExp(el.getAttribute('data-exp'));};});
document.getElementById('genfilters').onclick=function(e){e.stopPropagation();};
document.getElementById('netfilters').onclick=function(e){e.stopPropagation();};
// source rows (legend = filter)
var order=['pv','wind','hydro','geo','nuc','cc','th','coal','tg','cog','ci','cegen','bat'];
var sr=document.getElementById('srcrows');
order.forEach(function(t){if(!D.T[t])return;var row=document.createElement('div');row.className='row on';row.setAttribute('data-t',t);
  row.innerHTML='<span class="dot" style="background:'+D.T[t][1]+'"></span><span class="nm">'+D.T[t][0]+'</span><span class="ct"></span>';
  row.onclick=function(ev){ev.stopPropagation();f.src[t]=!f.src[t];row.classList.toggle('on',f.src[t]);row.classList.toggle('off',!f.src[t]);redraw();};sr.appendChild(row);});
// selects
var gc={};D.P.forEach(function(p){if(p[7])gc[p[7]]=(gc[p[7]]||0)+1;});
var gs=Object.keys(gc).sort(function(a,b){return gc[b]-gc[a];});
document.getElementById('f_grp').innerHTML='<option value="">Todos</option>'+gs.map(function(g){return '<option value="'+g+'">'+g+' ('+gc[g]+')</option>';}).join('');
document.getElementById('f_grp').onchange=function(){f.grp=this.value;redraw();};
document.getElementById('f_reg').innerHTML='<option value="">Todas</option>'+REG.map(function(r){return '<option>'+r+'</option>';}).join('');
document.getElementById('f_reg').onchange=function(){f.reg=this.value;redraw();};
var zset={};D.P.forEach(function(p){if(p[14])zset[p[14]]=1;});D.H.forEach(function(h){if(h[8])zset[h[8]]=1;});
document.getElementById('f_zona').innerHTML='<option value="">Todas ('+Object.keys(zset).length+')</option>'+Object.keys(zset).sort().map(function(z){return '<option>'+z+'</option>';}).join('');
document.getElementById('f_zona').onchange=function(){f.zona=this.value;drawZone(this.value);redraw();};
document.getElementById('f_tdiv').innerHTML='<option value="">Todas ('+tzNames.length+')</option>'+tzNames.map(function(z){return '<option>'+z+'</option>';}).join('');
document.getElementById('f_tdiv').onchange=function(){f.tdiv=this.value;if(this.value&&!on.tz){document.querySelector('[data-tog="tz"]').click();}redraw();};
function seg(id,key,after){var el=document.getElementById(id);Array.prototype.forEach.call(el.children,function(b){b.onclick=function(){Array.prototype.forEach.call(el.children,function(x){x.classList.remove('on');});b.classList.add('on');f[key]=b.getAttribute('data-v');redraw();if(after)after();};});}
seg('f_mkt','mkt');seg('f_kv','kv');
function sld(id,out,key,fmt){document.getElementById(id).oninput=function(){f[key]=+this.value;document.getElementById(out).textContent=fmt(+this.value);redraw();};}
sld('f_mw','o_mw','mw',function(v){return v.toLocaleString()+' MW';});
sld('f_mva','o_mva','mva',function(v){return v.toLocaleString()+' MVA';});
sld('f_sat','o_sat','sat',function(v){return v.toFixed(1);});
document.getElementById('f_cod').oninput=function(){f.cod=(+this.value<=1960?0:+this.value);document.getElementById('o_cod').textContent=(+this.value<=1960?'cualquiera':this.value);redraw();};
function doReset(){f={src:{},grp:'',mkt:'',mw:0,cod:0,reg:'',kv:'',mva:0,sat:0,zona:'',tdiv:'',year:0};Object.keys(D.T).forEach(function(t){f.src[t]=true;});updateYrChip();
  document.querySelectorAll('#srcrows .row').forEach(function(r){r.classList.add('on');r.classList.remove('off');});
  document.getElementById('f_grp').value='';document.getElementById('f_reg').value='';document.getElementById('f_zona').value='';document.getElementById('f_tdiv').value='';drawZone('');
  ['f_mkt','f_kv'].forEach(function(id){Array.prototype.forEach.call(document.getElementById(id).children,function(x,i){x.classList.toggle('on',i===0);});});
  [['f_mw','o_mw','0 MW'],['f_cod','o_cod','cualquiera'],['f_mva','o_mva','0 MVA'],['f_sat','o_sat','0']].forEach(function(a){document.getElementById(a[0]).value=document.getElementById(a[0]).min;document.getElementById(a[1]).textContent=a[2];});
  redraw();}
document.getElementById('reset').onclick=doReset;document.getElementById('empty-reset').onclick=doReset;
// sheet + about
var sheet=document.getElementById('sheet'),scrim=document.getElementById('scrim');
function openSheet(v){sheet.classList.toggle('open',v);scrim.classList.toggle('on',v);if(v){openLane(false);closeDLane();}}
document.getElementById('pill-ctrl').onclick=function(){openSheet(!sheet.classList.contains('open'));};
document.getElementById('sheet-x').onclick=function(){openSheet(false);};
scrim.onclick=function(){openSheet(false);};
document.addEventListener('keydown',function(e){if(e.key==='Escape'){openSheet(false);closeDLane();openLane(false);openIntro(false);}});
// intro / framing overlay — shown on first visit, re-openable via the (i)
var introBg=document.getElementById('intro-bg');
function openIntro(v){introBg.classList.toggle('on',v);}
function dismissIntro(){openIntro(false);try{localStorage.setItem('atlasIntroSeen','1');}catch(e){}}
document.getElementById('intro-go').onclick=dismissIntro;
document.getElementById('intro-x').onclick=dismissIntro;
introBg.onclick=function(e){if(e.target===introBg)dismissIntro();};
document.getElementById('info').onclick=function(e){e.stopPropagation();openIntro(true);};
try{if(!localStorage.getItem('atlasIntroSeen'))openIntro(true);}catch(e){openIntro(true);}
// time lane
var lane=document.getElementById('lane');
function openLane(v){T.on=v;lane.classList.toggle('open',v);document.getElementById('pill-time').style.opacity=v?'0':'1';
  if(v){closeDLane();openSheet(false);}
  document.getElementById('pill-demand').style.opacity=(v||document.getElementById('dlane').classList.contains('open'))?'0':(DEM?'1':'0');
  if(!v){f.year=0;updateYrChip();}redraw();}
document.getElementById('pill-time').onclick=function(){openLane(true);};
document.getElementById('lane-x').onclick=function(){if(ttimer){clearInterval(ttimer);ttimer=null;tb.innerHTML=PLAY;}openLane(false);};
document.getElementById('t_slider').oninput=function(){T.year=+this.value;if(f.year){f.year=0;updateYrChip();}redraw();};
seg('t_agg','agg');document.getElementById('t_agg').children[0].onclick=function(){tagg('cum',this);};document.getElementById('t_agg').children[1].onclick=function(){tagg('ann',this);};
function tagg(v,b){Array.prototype.forEach.call(b.parentNode.children,function(x){x.classList.remove('on');});b.classList.add('on');T.agg=v;if(v!=='ann'){f.year=0;}updateYrChip();redraw();}
var ttimer=null,tb=document.getElementById('t_play');tb.innerHTML=PLAY;
tb.onclick=function(){if(ttimer){clearInterval(ttimer);ttimer=null;tb.innerHTML=PLAY;return;}f.year=0;updateYrChip();T.year=1960;document.getElementById('t_slider').value=1960;redraw();tb.innerHTML=PAUSE;
  ttimer=setInterval(function(){T.year++;if(T.year>2026){clearInterval(ttimer);ttimer=null;tb.innerHTML=PLAY;return;}document.getElementById('t_slider').value=T.year;redraw();},120);};
var GRP={cc:'Ciclo combinado',th:'Termo/Carbón',coal:'Termo/Carbón',tg:'Turbogás/CI',ci:'Turbogás/CI',cog:'Cogeneración',pv:'Solar',wind:'Eólica',hydro:'Hidro',geo:'Geotérmica',nuc:'Nuclear'};
var GCOL={'Solar':D.T.pv[1],'Eólica':D.T.wind[1],'Hidro':D.T.hydro[1],'Geotérmica':D.T.geo[1],'Nuclear':D.T.nuc[1],'Ciclo combinado':D.T.cc[1],'Cogeneración':D.T.cog[1],'Turbogás/CI':D.T.tg[1],'Termo/Carbón':D.T.th[1]};
var TORDER=['Termo/Carbón','Turbogás/CI','Ciclo combinado','Cogeneración','Nuclear','Geotérmica','Hidro','Eólica','Solar'];
var Y0=1960,Y1=2026,NY=Y1-Y0+1;
var _addn={},_cum={},_geom={W:860,mL:28,pw:826};
function buildTimeChart(){
  var addn={};TORDER.forEach(function(s){addn[s]=new Array(NY).fill(0);});
  plantM.forEach(function(o){var p=o.r,g=GRP[p[4]];if(!g||!filtBase(p))return;var y=p[9];if(!y||y<Y0||y>Y1)return;addn[g][y-Y0]+=p[3];});
  var cum={};TORDER.forEach(function(s){cum[s]=[];var r=0;for(var i=0;i<NY;i++){r+=addn[s][i];cum[s].push(r);}});
  _addn=addn;_cum=cum;
  var big=T.big;
  var W=860,Hh=big?188:58,mL=big?34:28,mR=8,mT=big?12:3,mB=big?18:12,pw=W-mL-mR,ph=Hh-mT-mB,maxY=0,i;
  for(i=0;i<NY;i++){var t=0;TORDER.forEach(function(s){t+=(T.agg==='cum'?cum[s][i]:addn[s][i]);});if(t>maxY)maxY=t;}maxY=Math.max(maxY,1);
  var gi=T.year-Y0;
  function X(k){return mL+k/(NY-1)*pw;}function Yp(v){return mT+ph-v/maxY*ph;}
  _geom={W:W,mL:mL,pw:pw};
  var svg='<svg viewBox="0 0 '+W+' '+Hh+'" preserveAspectRatio="none" style="width:100%;height:'+Hh+'px;display:block">';
  if(big){for(i=1;i<=4;i++){var gv=maxY*i/4,gy=Yp(gv);svg+='<line x1="'+mL+'" y1="'+gy+'" x2="'+(W-mR)+'" y2="'+gy+'" stroke="#000" stroke-opacity="0.05"/><text x="'+(mL-4)+'" y="'+(gy+3)+'" text-anchor="end" font-size="8" fill="#A3A39E">'+Math.round(gv/1000)+'</text>';}}
  if(T.agg==='cum'){var lo=new Array(NY).fill(0);TORDER.forEach(function(s){var u=[],l=[];for(i=0;i<=gi;i++){var v=lo[i]+cum[s][i];u.push(X(i)+','+Yp(v));l.push(X(i)+','+Yp(lo[i]));lo[i]=v;}svg+='<polygon points="'+u.concat(l.reverse()).join(' ')+'" fill="'+GCOL[s]+'" fill-opacity="0.92"/>';});}
  else{var bw=Math.max(1.4,pw/NY*0.82);for(i=0;i<=gi;i++){var base=0,dim=(f.year&&(Y0+i)!==f.year)?0.26:1;TORDER.forEach(function(s){var v=addn[s][i];if(v<=0)return;svg+='<rect x="'+(X(i)-bw/2)+'" y="'+Yp(base+v)+'" width="'+bw+'" height="'+(Yp(base)-Yp(base+v))+'" fill="'+GCOL[s]+'" fill-opacity="'+dim+'"/>';base+=v;});if(f.year&&(Y0+i)===f.year&&base>0){svg+='<rect x="'+(X(i)-bw/2-1.5)+'" y="'+Yp(base)+'" width="'+(bw+3)+'" height="'+(Yp(0)-Yp(base))+'" fill="none" stroke="#1A1A18" stroke-width="1.2"/>';}}}
  var gx=X(gi);svg+='<line x1="'+gx+'" y1="'+mT+'" x2="'+gx+'" y2="'+(mT+ph)+'" stroke="#A3A39E" stroke-width="1" opacity="'+(T.year<Y1?1:0)+'"/>';
  (big?[1960,1970,1980,1990,2000,2010,2014,2020,2026]:[1960,1990,2014,2026]).forEach(function(y){svg+='<text x="'+X(y-Y0)+'" y="'+(Hh-4)+'" text-anchor="middle" font-size="8" fill="#A3A39E">'+y+'</text>';});
  if(!big)svg+='<text x="2" y="'+(mT+7)+'" font-size="8" fill="#A3A39E">'+Math.round(maxY/1000)+'GW</text>';
  svg+='</svg>';
  document.getElementById('tchart').innerHTML='<div id="thover"></div><div id="ttip"></div>'+svg;
  var tot=0;TORDER.forEach(function(s){tot+=cum[s][gi];});
  document.getElementById('t_yr').textContent=T.year;document.getElementById('t_tot').textContent=(tot/1000).toFixed(1);
}
function updateYrChip(){var c=document.getElementById('t_yrchip');if(!c)return;if(f.year){var tot=0;TORDER.forEach(function(s){tot+=_addn[s]?(_addn[s][f.year-Y0]||0):0;});c.innerHTML='Altas '+f.year+' · +'+Math.round(tot).toLocaleString()+' MW';c.classList.add('on');}else{c.classList.remove('on');}}
// hover scrub + click interactions on the chart
function yearAt(e){var el=document.getElementById('tchart'),r=el.getBoundingClientRect(),px=e.clientX-r.left,vx=px/r.width*_geom.W,fr=Math.max(0,Math.min(1,(vx-_geom.mL)/_geom.pw)),k=Math.round(fr*(NY-1));return {k:k,year:Y0+k,px:px,py:e.clientY-r.top,cw:r.width};}
function onChartMove(e){var info=yearAt(e),k=info.k,year=info.year,hov=document.getElementById('thover'),tip=document.getElementById('ttip');if(!hov||!tip)return;
  var lpx=(_geom.mL+k/(NY-1)*_geom.pw)/_geom.W*info.cw;hov.style.left=lpx+'px';hov.classList.add('on');
  var rows='',tadd=0;TORDER.slice().reverse().forEach(function(s){var v=_addn[s]?(_addn[s][k]||0):0;if(v>0.5){tadd+=v;rows+='<div class="tr"><span class="sw" style="background:'+GCOL[s]+'"></span>'+s+'<span class="tv">+'+Math.round(v).toLocaleString()+'</span></div>';}});
  var ctot=0;TORDER.forEach(function(s){ctot+=_cum[s]?(_cum[s][k]||0):0;});
  var b='<div class="ty">'+year+'</div>';
  b+=rows?(rows+'<div class="tt-tot"><span>Altas '+year+'</span><span class="tv">+'+Math.round(tadd).toLocaleString()+' MW</span></div>'):'<div class="tr" style="color:rgba(255,255,255,.55)">Sin altas este año</div>';
  b+='<div class="tt-sub">Acumulado '+(ctot/1000).toFixed(1)+' GW</div>';
  tip.innerHTML=b;tip.style.left=Math.max(80,Math.min(info.cw-80,lpx))+'px';tip.style.top=info.py+'px';tip.classList.add('on');}
function onChartLeave(){var hov=document.getElementById('thover'),tip=document.getElementById('ttip');if(hov)hov.classList.remove('on');if(tip)tip.classList.remove('on');}
function onChartClick(e){var info=yearAt(e),k=info.k,year=info.year;
  if(T.agg==='ann'){var has=TORDER.some(function(s){return _addn[s]&&_addn[s][k]>0.5;});f.year=(f.year===year||!has)?0:year;updateYrChip();redraw();}
  else{T.year=year;document.getElementById('t_slider').value=year;redraw();}}
var _tch=document.getElementById('tchart');
_tch.addEventListener('mousemove',onChartMove);_tch.addEventListener('mouseleave',onChartLeave);_tch.addEventListener('click',onChartClick);
document.getElementById('t_yrchip').onclick=function(){f.year=0;updateYrChip();redraw();};
var _bigBtn=document.getElementById('t_big');
_bigBtn.onclick=function(){T.big=!T.big;lane.classList.toggle('big',T.big);_bigBtn.classList.toggle('on',T.big);_bigBtn.title=T.big?'Reducir':'Expandir';buildTimeChart();};
// ===== Live demand (CENACE) — fetched at runtime from same-origin JSON =====
var DEM=null,Dbig=false,_dH=[],_dgeom={W:860,mL:44,pw:804,n:0},_curB=null,
    dlaneEl=document.getElementById('dlane'),pillDem=document.getElementById('pill-demand');
var ACCENT='#1D4ED8';
var DSER=[['demandaMW','Demanda',ACCENT,false,2.2],['generacionMW','Generación','#9A9A95',false,1],['pronosticoMW','Pronóstico','#93B4E0',true,1.3]];
// region highlight — links chart selection <-> map (highlight only; pan if offscreen, never auto-zoom)
map.createPane('hiPane');map.getPane('hiPane').style.zIndex=360;
var hiRenderer=L.svg({pane:'hiPane'}),hiGroup=L.layerGroup().addTo(map);
function highlightRegion(name){hiGroup.clearLayers();_curB=null;var polys=(D.RP||{})[name];if(!polys)return;
  var b=null;polys.forEach(function(poly){var pg=L.polygon(poly,{renderer:hiRenderer,color:ACCENT,weight:2,opacity:.9,fill:false,interactive:false});hiGroup.addLayer(pg);b=b?b.extend(pg.getBounds()):pg.getBounds();});
  _curB=b;if(b&&!map.getBounds().intersects(b)){map.panTo(b.getCenter(),{animate:true,duration:.5});}}
function centerOnRegion(){if(_curB){try{map.flyToBounds(_curB.pad(0.12),{maxZoom:6,duration:.6});}catch(e){}}else{map.flyTo([23.6,-102],5,{duration:.6});}}
function buildDemandChart(name){
  if(!DEM||!DEM.regions||!DEM.regions[name])return;
  var H=DEM.regions[name].hourly||[];var n=H.length;_dH=H;
  var W=860,Hh=Dbig?320:150,mL=44,mR=12,mT=12,mB=18,pw=W-mL-mR,ph=Hh-mT-mB,maxY=0,minY=Infinity;
  H.forEach(function(p){DSER.forEach(function(s){var v=p[s[0]];if(v!=null){if(v>maxY)maxY=v;if(v<minY)minY=v;}});});
  if(!isFinite(minY))minY=0;var pad=(maxY-minY)*0.12||maxY*0.1||1;var lo=Math.max(0,minY-pad),hi=maxY+pad;
  _dgeom={W:W,mL:mL,pw:pw,n:n};
  function X(i){return mL+(n<=1?0:i/(n-1)*pw);}function Yp(v){return mT+ph-(v-lo)/(hi-lo)*ph;}
  var steps=Dbig?6:4;
  var svg='<svg viewBox="0 0 '+W+' '+Hh+'" preserveAspectRatio="none" style="width:100%;height:'+Hh+'px;display:block">';
  for(var g=0;g<=steps;g++){var gv=lo+(hi-lo)*g/steps,gy=Yp(gv);svg+='<line x1="'+mL+'" y1="'+gy+'" x2="'+(W-mR)+'" y2="'+gy+'" stroke="#000" stroke-opacity="0.05"/><text x="'+(mL-5)+'" y="'+(gy+3)+'" text-anchor="end" font-size="8" fill="#A3A39E">'+(gv/1000).toFixed(hi<10000?1:0)+'</text>';}
  [1,2,0].forEach(function(si){var s=DSER[si];var p=[];for(var i=0;i<n;i++){if(H[i][s[0]]==null)continue;p.push(X(i)+','+Yp(H[i][s[0]]));}if(p.length>=2)svg+='<polyline points="'+p.join(' ')+'" fill="none" stroke="'+s[2]+'" stroke-width="'+s[4]+'"'+(s[3]?' stroke-dasharray="4 3"':'')+'/>';});
  var lastA=-1;for(i=0;i<n;i++){if(H[i].demandaMW!=null)lastA=i;}
  if(lastA>=0&&lastA<n-1){var ax=X(lastA);svg+='<line x1="'+ax+'" y1="'+mT+'" x2="'+ax+'" y2="'+(mT+ph)+'" stroke="#A3A39E" stroke-width="1" stroke-dasharray="2 2"/><text x="'+(ax+4)+'" y="'+(mT+9)+'" font-size="8" fill="#6B6B66">ahora</text>';}
  var every=Dbig?1:3;for(var i=0;i<n;i++){if(H[i].hora%every===0)svg+='<text x="'+X(i)+'" y="'+(Hh-4)+'" text-anchor="middle" font-size="8" fill="#A3A39E">'+H[i].hora+'</text>';}
  svg+='<text x="3" y="'+(mT+6)+'" font-size="8" fill="#A3A39E">GW</text></svg>';
  document.getElementById('dchart').innerHTML='<div id="dhover"></div><div id="dtip"></div>'+svg;
  var lat=DEM.regions[name].latest;var dem=lat?lat.demandaMW:null,gen=lat?lat.generacionMW:null;
  var sur=(dem!=null&&gen!=null)?gen-dem:null,sc=sur==null?'var(--muted)':(sur>=0?'#1D7A4F':'#A32D2D');
  function st(v,lab){return '<div class="dstat"><b>'+(v==null?'n/d':v.toLocaleString())+'</b><span>'+lab+'</span></div>';}
  document.getElementById('d_stats').innerHTML=st(dem,'Demanda (MW)')+st(gen,'Generación (MW)')+
    '<div class="dstat"><b style="color:'+sc+'">'+(sur==null?'n/d':(sur>=0?'+':'−')+Math.abs(sur).toLocaleString())+'</b><span>Superávit'+(lat?' · h'+lat.hora:'')+'</span></div>';
  document.getElementById('d_upd').textContent='Fuente: CENACE'+(DEM.updatedAt?' · '+DEM.updatedAt.replace('T',' ').replace('Z',' UTC'):'');
}
// hover scrub on demand chart
function dAt(e){var el=document.getElementById('dchart'),r=el.getBoundingClientRect(),px=e.clientX-r.left,vx=px/r.width*_dgeom.W,fr=Math.max(0,Math.min(1,(vx-_dgeom.mL)/_dgeom.pw)),k=_dgeom.n<=1?0:Math.round(fr*(_dgeom.n-1));return {k:k,px:px,py:e.clientY-r.top,cw:r.width};}
function onDMove(e){var info=dAt(e),row=_dH[info.k];if(!row)return;var hov=document.getElementById('dhover'),tip=document.getElementById('dtip');if(!hov||!tip)return;
  var lpx=(_dgeom.mL+(_dgeom.n<=1?0:info.k/(_dgeom.n-1)*_dgeom.pw))/_dgeom.W*info.cw;hov.style.left=lpx+'px';hov.classList.add('on');
  var b='<div class="ty">Hora '+row.hora+':00</div>';
  DSER.forEach(function(s){var v=row[s[0]];if(v==null)return;b+='<div class="tr"><span class="sw" style="background:'+s[2]+'"></span>'+s[1]+'<span class="tv">'+v.toLocaleString()+' MW</span></div>';});
  tip.innerHTML=b;tip.style.left=Math.max(82,Math.min(info.cw-82,lpx))+'px';tip.style.top=info.py+'px';tip.classList.add('on');}
function onDLeave(){var hov=document.getElementById('dhover'),tip=document.getElementById('dtip');if(hov)hov.classList.remove('on');if(tip)tip.classList.remove('on');}
var _dch=document.getElementById('dchart');_dch.addEventListener('mousemove',onDMove);_dch.addEventListener('mouseleave',onDLeave);
document.getElementById('d_center').onclick=centerOnRegion;
var _dBig=document.getElementById('d_big');
_dBig.onclick=function(){Dbig=!Dbig;dlaneEl.classList.toggle('big',Dbig);_dBig.classList.toggle('on',Dbig);_dBig.title=Dbig?'Reducir':'Expandir';buildDemandChart(document.getElementById('d_reg').value);};
function selectDemand(){var nm=document.getElementById('d_reg').value;buildDemandChart(nm);highlightRegion(nm);}
function openDLane(){openSheet(false);dlaneEl.classList.add('open');pillDem.style.opacity='0';openLane(false);selectDemand();}
function closeDLane(){dlaneEl.classList.remove('open');hiGroup.clearLayers();if(DEM)pillDem.style.opacity='1';}
function openDemandForRegion(name){if(!DEM||!DEM.regions[name])return;document.getElementById('d_reg').value=name;openDLane();}
pillDem.onclick=function(){if(DEM)openDLane();};
document.getElementById('dlane-x').onclick=closeDLane;
document.getElementById('d_reg').onchange=selectDemand;
fetch(window.ATLAS_DEMAND_URL||'data/demand/today.json',{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(j){
  if(!j||!j.regions)return;DEM=j;
  var names=Object.keys(j.regions);
  names.sort(function(a,b){var sa=a.indexOf('Interconectado')>=0,sb=b.indexOf('Interconectado')>=0;return sa===sb?a.localeCompare(b):(sa?-1:1);});
  document.getElementById('d_reg').innerHTML=names.map(function(nm){return '<option value="'+nm+'">'+nm+'</option>';}).join('');
  pillDem.style.display='inline-flex';
}).catch(function(){});
redraw();
