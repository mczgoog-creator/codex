#!/usr/bin/env node
'use strict';
// Independent source/native comparison: this script never modifies or routes PCB.
const fs=require('fs'),path=require('path');
const B=path.join(process.env.EASYEDA_TOOL_ROOT||__dirname,'kicad-to-easyeda-eprj3/scripts/lib/');
const E=require(B+'eprj3'),K=require(B+'kicad');
const [projectDir,sourceFile,expectedFile]=process.argv.slice(2);
if(!expectedFile)throw new Error('Usage: check-native-pcb.js <project> <source.kicad_pcb> <expected-pin-nets.json>');
const expected=JSON.parse(fs.readFileSync(expectedFile));
const root=K.parse(fs.readFileSync(sourceFile,'utf8'));
const children=(n,t)=>(n||[]).filter(v=>Array.isArray(v)&&v[0]?.v===t),child=(n,t)=>children(n,t)[0];
const vals=n=>(n||[]).slice(1).map(v=>v.v),num=(n,t,i=0)=>Number(vals(child(n,t))[i]||0),str=(n,t,i=0)=>vals(child(n,t))[i]||'';
const MIL=1000/25.4,errors=[];
const nets=new Map(children(root,'net').map(n=>[n[1].v,n[2]?.v||'']));
const net=n=>str(n,'net_name')||nets.get(str(n,'net'))||'';
const lid=n=>n==='F.Cu'?1:n==='B.Cu'?2:/^In\d+\.Cu$/.test(n)?14+Number(n.match(/In(\d+)/)[1]):null;
const files=[];function walk(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){const f=path.join(d,e.name);if(e.isDirectory())walk(f);else if(e.name.endsWith('.epcb2'))files.push(f);}}walk(projectDir);
if(files.length!==1)throw new Error('Expected one PCB, found '+files.length);
const docs=[];for(const r of E.readRecords(files[0])){if(r.type==='DOCHEAD')docs.push({head:r,records:[]});else docs.at(-1).records.push(r);}
const pcb=docs.find(d=>d.head.body.docType==='PCB');
const sourceFp=new Map(children(root,'footprint').map(n=>[children(n,'property').find(p=>p[1]?.v==='Reference')?.[2]?.v||children(n,'fp_text').find(p=>p[1]?.v==='reference')?.[2]?.v,n]));
const shapeMap={circle:'ELLIPSE',rect:'RECT',roundrect:'RECT',oval:'OVAL'};
const close=(a,b,msg)=>{if(!Number.isFinite(a)||!Number.isFinite(b)||Math.abs(a-b)>1e-5)errors.push(`${msg}: source ${a}, native ${b}`);};
const angleDiff=(a,b)=>((a-b+540)%360)-180;
const attrs=new Map();for(const r of pcb.records)if(r.type==='ATTR'){if(!attrs.has(r.body.parentId))attrs.set(r.body.parentId,{});attrs.get(r.body.parentId)[r.body.key]=r.body.value;}
const padNets=new Map();for(const r of pcb.records)if(r.type==='PAD_NET'){const id=JSON.parse(r.id);padNets.set(id[1]+'.'+id[3],r.body.padNet||null);}
const nativePhysical={},padReport=[];
for(const c of pcb.records.filter(r=>r.type==='COMPONENT')){
 const ca=attrs.get(c.id)||{},ref=ca.Designator,fp=docs.find(d=>d.head.body.uuid===ca.Footprint);
 if(!fp){errors.push('Missing footprint for '+ref);continue;}
 const sf=sourceFp.get(ref),spads=children(sf,'pad'),npads=fp.records.filter(r=>r.type==='PAD');
 if(!sf){errors.push('Missing source footprint for '+ref);continue;}
 if(spads.length!==npads.length)errors.push('Source/native pad count differs for '+ref);
 for(const [i,p] of npads.entries()){
  const key=ref+'.'+p.body.num,n=padNets.get(c.id+'.'+p.id)||null;
  if(key in nativePhysical&&nativePhysical[key]!==n)errors.push('Conflicting duplicate physical pad '+key);
  nativePhysical[key]=n;padReport.push({reference:ref,pad:p.body.num,net:n,shape:p.body.defaultPad,hole:p.body.hole,slotRelativeAngle:p.body.relativeAngle});
  const sp=spads[i],b=p.body;if(!sp){errors.push('Unexpected pad instance '+key);continue;}
  if(sp[1].v!==b.num)errors.push('Pad order/number mismatch '+key);
  const shape=shapeMap[sp[3].v];if(shape!==b.defaultPad.padType)errors.push('Pad shape mismatch '+key);
  close(num(sp,'size'),b.defaultPad.width/MIL,key+' width');close(num(sp,'size',1),b.defaultPad.height/MIL,key+' height');
  const radius=sp[3].v==='roundrect'?num(sp,'roundrect_rratio')*Math.min(num(sp,'size'),num(sp,'size',1)):0;
  close(radius,(b.defaultPad.radius||0)/MIL,key+' corner radius');
  const margin=(n,k,fallback)=>child(n,k)?num(n,k):fallback;
  const mask=margin(sp,'solder_mask_margin',margin(sf,'solder_mask_margin',num(child(root,'setup'),'pad_to_mask_clearance')));
  const paste=margin(sp,'solder_paste_margin',margin(sf,'solder_paste_margin',num(child(root,'setup'),'pad_to_paste_clearance')));
  close(mask,b.topSolderExpansion/MIL,key+' top mask expansion');close(mask,b.bottomSolderExpansion/MIL,key+' bottom mask expansion');
  close(paste,b.topPasteExpansion/MIL,key+' top paste expansion');close(paste,b.bottomPasteExpansion/MIL,key+' bottom paste expansion');
  if(Math.abs(angleDiff(num(sp,'at',2),c.body.angle+b.padAngle))>1e-5)errors.push('Pad angle differs '+key);
  const a=c.body.angle*Math.PI/180,co=Math.cos(a),si=Math.sin(a),sa=num(sf,'at',2)*Math.PI/180,cs=Math.cos(sa),ss=Math.sin(sa);
  close(num(sf,'at')+cs*num(sp,'at')+ss*num(sp,'at',1),(c.body.x+co*b.centerX-si*b.centerY)/MIL,key+' world X');
  close(num(sf,'at',1)-ss*num(sp,'at')+cs*num(sp,'at',1),-(c.body.y+si*b.centerX+co*b.centerY)/MIL,key+' world Y');
  const drill=vals(child(sp,'drill')),oval=drill[0]==='oval',dx=Number(drill[oval?1:0]||0),dy=Number(drill[oval?2:0]||0),slot=Math.abs(dx-dy)>1e-8;
  if(dx>0){if(b.hole?.holeType!==(slot?'SLOT':'ROUND'))errors.push('Drill hole type differs '+key);close(Math.max(dx,dy),(b.hole?.width||0)/MIL,key+' drill long dimension');close(Math.min(dx,dy),(b.hole?.height||0)/MIL,key+' drill short dimension');if(slot&&Math.abs(angleDiff(dx<dy?90:0,b.relativeAngle))>1e-5)errors.push('Drill slot angle differs '+key);}
  else if(b.hole)errors.push('Unexpected hole on SMD '+key);
  if(b.plated!==(sp[2].v!=='np_thru_hole'))errors.push('Plating differs '+key);
  const srcLayer=sp[2].v.includes('thru_hole')?12:lid(str(sf,'layer'));if(b.layerId!==srcLayer)errors.push('Pad copper layer differs '+key);
 }
}
for(const [p,n]of Object.entries(expected))if(nativePhysical[p]!==n)errors.push(`${p}: expected ${n}, native PCB ${nativePhysical[p]}`);
for(const [p,n]of Object.entries(nativePhysical))if(!(p in expected)&&n)errors.push('Unexpected connected physical pad '+p);
const q=x=>Math.round(x*1e6)/1e6;
function multi(items){const m=new Map();for(const i of items){const k=JSON.stringify(i);m.set(k,(m.get(k)||0)+1);}return m;}
function compare(label,a,b){const ma=multi(a),mb=multi(b);for(const [k,n]of ma)if(mb.get(k)!==n)errors.push(`${label}: source count ${n}, native count ${mb.get(k)||0}: ${k}`);for(const[k,n]of mb)if(!ma.has(k))errors.push(`${label}: native-only ${n}: ${k}`);}
const srcTracks=children(root,'segment').map(n=>[net(n),lid(str(n,'layer')),q(num(n,'start')),q(num(n,'start',1)),q(num(n,'end')),q(num(n,'end',1)),q(num(n,'width'))]);
const nativeTracks=pcb.records.filter(r=>r.type==='LINE'&&[1,2,...Array.from({length:32},(_,i)=>i+15)].includes(r.body.layerId)).map(r=>{const b=r.body;return[b.netName,b.layerId,q(b.startX/MIL),q(-b.startY/MIL),q(b.endX/MIL),q(-b.endY/MIL),q(b.width/MIL)];});
compare('Track geometry/net/width/layer',srcTracks,nativeTracks);
const srcVias=children(root,'via').map(n=>[net(n),q(num(n,'at')),q(num(n,'at',1)),q(num(n,'size')),q(num(n,'drill'))]);
const nativeVias=pcb.records.filter(r=>r.type==='VIA').map(r=>{const b=r.body;return[b.netName,q(b.centerX/MIL),q(-b.centerY/MIL),q(b.viaDiameter/MIL),q(b.holeDiameter/MIL)];});
compare('Via geometry/net',srcVias,nativeVias);
const copperLayerReport=(child(root,'layers')||[]).slice(1).filter(Array.isArray).filter(n=>lid(n[1]?.v)!==null).map(n=>{const name=n[1].v,id=lid(name),l=pcb.records.find(r=>r.type==='LAYER'&&r.body.layerId===id);if(!l?.body.use)errors.push('Copper layer is disabled or missing '+name);return{name,nativeLayerId:id,enabled:!!l?.body.use,shown:!!l?.body.show};});
if(children(root,'arc').length)errors.push('Track arcs need an additional source-midpoint sweep check.');
const edgeKey=(a,b)=>[a.map(q),b.map(q)].map(p=>JSON.stringify(p)).sort();
const srcEdges=[];
for(const n of children(root,'gr_line').filter(n=>str(n,'layer')==='Edge.Cuts'))srcEdges.push(edgeKey([num(n,'start'),num(n,'start',1)],[num(n,'end'),num(n,'end',1)]));
for(const n of children(root,'gr_rect').filter(n=>str(n,'layer')==='Edge.Cuts')){const x=num(n,'start'),y=num(n,'start',1),xx=num(n,'end'),yy=num(n,'end',1),p=[[x,y],[xx,y],[xx,yy],[x,yy],[x,y]];for(let i=1;i<p.length;i++)srcEdges.push(edgeKey(p[i-1],p[i]));}
const nativeEdges=[];
for(const r of pcb.records.filter(r=>r.type==='POLY'&&r.body.polyType==='BOARD_OUTLINE')){
 let flat=r.body.path;if(flat[0]==='R'){const[_,x,y,w,h]=flat;flat=[x,y,x+w,y,x+w,y-h,x,y-h,x,y];}else flat=flat.filter(v=>v!=='L');
 if(flat.some(v=>typeof v!=='number')){errors.push('Unsupported curved native board outline');continue;}
 const pts=[];for(let i=0;i<flat.length;i+=2)pts.push([flat[i]/MIL,-flat[i+1]/MIL]);
 for(let i=1;i<pts.length;i++)nativeEdges.push(edgeKey(pts[i-1],pts[i]));
}
compare('Board outline edges',srcEdges,nativeEdges);
const stack=child(child(root,'setup'),'stackup'),sourceStack=children(stack,'layer');
const phys=pcb.records.filter(r=>r.type==='LAYER_PHYS'),layerMap={'F.SilkS':3,'F.Paste':7,'F.Mask':5,'B.Mask':6,'B.Paste':8,'B.SilkS':4};
let dielectricIndex=0;const physicalLayerReport=[];
for(const s of sourceStack){const name=s[1].v,id=layerMap[name]||lid(name)||(/dielectric/.test(name)?361+dielectricIndex++:null);if(id===null){errors.push('Unhandled source physical layer '+name);continue;}const p=phys.find(r=>JSON.parse(r.id)[1]===id);if(!p){errors.push('Missing physical layer '+name);continue;}const t=num(s,'thickness');close(t,p.body.thickness/MIL,'Physical stack '+name);physicalLayerReport.push({name,sourceThicknessMm:t,nativeThicknessMm:p.body.thickness/MIL});}
const actualTotal=phys.reduce((s,r)=>s+r.body.thickness/MIL,0);if(sourceStack.length)close(num(child(root,'general'),'thickness'),actualTotal,'Total physical stack');
// Convert polygon points to the converter's own documented rounding precision,
// then compare their ordered cyclic boundary, not just their bounding boxes.
const r2=x=>Math.round(x*100)/100;
function canonical(pts){if(pts.length>1&&JSON.stringify(pts[0])===JSON.stringify(pts.at(-1)))pts=pts.slice(0,-1);const keys=pts.map(p=>JSON.stringify(p)),min=[...keys].sort()[0],options=[];for(const p of[pts,[...pts].reverse()])for(let i=0;i<p.length;i++)if(JSON.stringify(p[i])===min)options.push(JSON.stringify([...p.slice(i),...p.slice(0,i)]));return options.sort()[0];}
function pathPoints(p){if(p[0]==='R'){const[_,x,y,w,h]=p;return[[x,y],[r2(x+w),y],[r2(x+w),r2(y-h)],[x,r2(y-h)]];}if(p[2]!=='L')throw new Error('Unsupported polygon descriptor '+JSON.stringify(p));const a=[p[0],p[1],...p.slice(3)];if(a.some(v=>typeof v!=='number'))throw new Error('Unsupported mixed polygon path');const pts=[];for(let i=0;i<a.length;i+=2)pts.push([r2(a[i]),r2(a[i+1])]);return pts;}
const srcBorders=[],srcFill=[],sourceZoneSettings=[];
let srcZoneCount=0;
for(const z of children(root,'zone')){
 if(child(z,'keepout'))continue;
 const layers=child(z,'layer')?[str(z,'layer')]:vals(child(z,'layers'));
 for(const l of layers){srcZoneCount++;const boundaries=[];for(const poly of children(z,'polygon')){const pts=children(child(poly,'pts'),'xy').map(p=>[r2(Number(p[1].v)*MIL),r2(-Number(p[2].v)*MIL)]);const boundary=canonical(pts);srcBorders.push([net(z),lid(l),boundary]);boundaries.push(boundary);}
  const cp=child(z,'connect_pads'),fill=child(z,'fill'),mode=vals(cp)[0];
  const padConnection=mode==='yes'?'DIRECT':mode==='no'?'NON_CONNECT':mode===undefined?'DIVERGENCE':null;
  if(!padConnection)errors.push('Unsupported source zone pad connection '+mode);
  const islandMode=num(fill,'island_removal_mode');if(![0,1].includes(islandMode))errors.push('Source area-threshold island removal cannot be compared with native keepIsland boolean');
  sourceZoneSettings.push({net:net(z),layer:l,layerId:lid(l),boundaries:boundaries.sort(),priority:num(z,'priority'),clearanceMm:num(cp,'clearance'),
   minimumThicknessMm:num(z,'min_thickness'),padConnection,thermalGapMm:num(fill,'thermal_gap'),thermalSpokeWidthMm:num(fill,'thermal_bridge_width'),
   fillMode:str(fill,'mode')||'polygon',islandRemovalMode:islandMode,keepIsland:islandMode===1,minimumIslandAreaMm2:child(fill,'island_area_min')?num(fill,'island_area_min'):10});
  for(const poly of children(z,'filled_polygon')){if(str(poly,'layer')&&str(poly,'layer')!==l)continue;const pts=children(child(poly,'pts'),'xy').map(p=>[r2(Number(p[1].v)/.254),r2(-Number(p[2].v)/.254)]);srcFill.push([net(z),lid(l),canonical(pts)]);}
 }
}
const pours=pcb.records.filter(r=>r.type==='POUR'),pourById=new Map(pours.map(r=>[r.id,r]));
const nativeBorders=pours.flatMap(r=>r.body.path.map(p=>[r.body.netName,r.body.layerId,canonical(pathPoints(p))]));
const nativeFill=[];for(const r of pcb.records.filter(r=>r.type==='POURED')){const p=pourById.get(JSON.parse(r.id)[1]);if(!p){errors.push('POURED references missing POUR '+r.id);continue;}for(const f of r.body.pourFill)for(const pp of f.path)nativeFill.push([p.body.netName,p.body.layerId,canonical(pathPoints(pp))]);}
compare('Zone border/net/layer',srcBorders,nativeBorders);compare('Filled copper polygon/net/layer',srcFill,nativeFill);
if(srcZoneCount!==pours.length)errors.push('Source/native zone count differs');
const copperRule=pcb.records.find(r=>r.id===JSON.stringify(['RULE','COPPER','copperRegion']))?.body.ruleContext;
const safeRule=pcb.records.find(r=>r.id===JSON.stringify(['RULE','SAFE','copperThickness1oz']))?.body.ruleContext;
const zoneSettingsReport=[];
for(const source of sourceZoneSettings){
 const matching=pours.filter(r=>r.body.netName===source.net&&r.body.layerId===source.layerId&&JSON.stringify(r.body.path.map(p=>canonical(pathPoints(p))).sort())===JSON.stringify(source.boundaries));
 if(matching.length!==1){errors.push('Expected exactly one native region for source zone settings '+source.net+' / '+source.layer);continue;}
 const native=matching[0],b=native.body,label='Zone '+source.net+' / '+source.layer+' / '+native.id;
 close(source.priority,b.order,label+' priority');
 close(source.minimumThicknessMm,b.width,label+' minimum width (official converter real-export mm exception)');
 if(b.pourType?.pourType!=='SOLID'||source.fillMode!=='polygon')errors.push(label+' fill mode differs');
 close(source.minimumThicknessMm,(b.pourType?.fineness||0)/MIL,label+' solid minimum fineness');
 if(b.keepIsland!==source.keepIsland)errors.push(label+' island removal mode differs');
 for(const key of ['sglPad','mulPad']){
  const rule=copperRule?.[key]?.content?.find(r=>r.layerId===source.layerId);
  if(!rule){errors.push(label+' missing native '+key+' copper connection rule');continue;}
  if(rule.connType!==source.padConnection)errors.push(label+' '+key+' pad connection differs');
  close(source.thermalGapMm,rule.spoSpac/MIL,label+' '+key+' thermal gap');
  close(source.thermalSpokeWidthMm,rule.spoWidth/MIL,label+' '+key+' thermal spoke width');
 }
 const spacing=safeRule?.safeSpacing?.[0]?.content;
 if(!spacing)errors.push(label+' missing native clearance table');
 else for(const row of spacing.slice(0,7))for(const value of row)close(source.clearanceMm,value/MIL,label+' copper-object clearance');
 zoneSettingsReport.push({...source,boundaries:undefined,nativePourId:native.id,nativePriority:b.order,nativePadConnection:copperRule?.sglPad?.content?.find(r=>r.layerId===source.layerId)?.connType,
  areaThresholdStatus:source.islandRemovalMode===0?'Unused: all unconnected islands removed':source.islandRemovalMode===1?'Unused: all islands retained':'unsupported'});
}
const widthByNet={};for(const t of nativeTracks){const s=widthByNet[t[0]]??={segments:0,widthsMm:[],nativeLayerIds:[]};s.segments++;if(!s.widthsMm.includes(t[6]))s.widthsMm.push(t[6]);if(!s.nativeLayerIds.includes(t[1]))s.nativeLayerIds.push(t[1]);}for(const s of Object.values(widthByNet))s.widthsMm.sort((a,b)=>a-b);
const report={passed:errors.length===0,source:sourceFile,nativePcb:files[0],components:pcb.records.filter(r=>r.type==='COMPONENT').length,uniquePhysicalPins:Object.keys(nativePhysical).length,padInstances:padReport.length,namedNets:new Set(Object.values(nativePhysical).filter(Boolean)).size,tracks:srcTracks.length,vias:srcVias.length,outlineEdges:srcEdges.length,zones:srcZoneCount,zoneBorders:srcBorders.length,filledCopperPolygons:srcFill.length,zoneSettingsReport,copperLayerReport,physicalLayerReport,totalPhysicalThicknessMm:actualTotal,widthByNet,errors};
fs.writeFileSync(path.join(projectDir,'native-pcb-equivalence.json'),JSON.stringify(report,null,2));
fs.writeFileSync(path.join(projectDir,'native-pcb-physical-pin-nets.json'),JSON.stringify(nativePhysical,null,2));
fs.writeFileSync(path.join(projectDir,'native-pcb-pad-geometry.json'),JSON.stringify(padReport,null,2));
console.log(JSON.stringify(report,null,2));process.exitCode=errors.length?1:0;
