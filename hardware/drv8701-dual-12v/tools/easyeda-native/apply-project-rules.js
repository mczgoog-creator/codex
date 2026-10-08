#!/usr/bin/env node
'use strict';
// Set the requested DRV8701 design rules; never creates or changes routing.
const fs=require('fs'),path=require('path');
const BASE=process.env.EASYEDA_TOOL_ROOT||__dirname,E=require(path.join(BASE,'kicad-to-easyeda-eprj3/scripts/lib/eprj3'));
const [projectDir,unitArg]=process.argv.slice(2);
const encoding=unitArg||'mil-real-export-V4.1.36';
const U=encoding==='mil-real-export-V4.1.36'?1000/25.4:encoding==='internal10mil-current-schema'?1/.254:null;
if(!projectDir||!U)throw new Error('Usage: apply-project-rules.js <project> [mil-real-export-V4.1.36|internal10mil-current-schema]');
const files=[];function walk(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){const f=path.join(d,e.name);if(e.isDirectory())walk(f);else if(e.name.endsWith('.epcb2'))files.push(f);}}walk(projectDir);
const evidence={unitEncoding:encoding,unitConflict:'Latest official TRuleContext description uses 0.254mm internal units; real official V4.1.36 PCB template uses apparent mil values. No desktop client was available to resolve that discrepancy.',clearanceMm:.15,minTraceMm:.15,minDrillMm:.2,minAnnularRingMm:.1,defaultViaDiameterMm:.45,defaultViaDrillMm:.2,defaultTrackWidthsMm:{VM:1.8,MOTOR:.7,GATE:.25,SIGNAL:.2},rules:[]};
for(const file of files){
 const records=E.readRecords(file),docs=[];for(const r of records){if(r.type==='DOCHEAD')docs.push({head:r,records:[]});else docs.at(-1).records.push(r);}
 const pcb=docs.find(d=>d.head.body.docType==='PCB');
 const record=(type,id,body)=>({type,id,head:{type,id},body});
 const addRule=(type,name,context,state='NORMAL')=>{const id=JSON.stringify(['RULE',type,name]);const r=record('RULE',id,{ruleState:state,ruleContext:context}),old=pcb.records.findIndex(x=>x.id===id);if(old<0)pcb.records.push(r);else pcb.records[old]=r;evidence.rules.push({type,name});};
 const track=width=>({unit:'mm',track:{isOpen:true,content:[{layerId:1,stroMin:.15*U,stroDef:width*U,stroMax:3*U}]}});
 addRule('TRACK','copperThickness1oz',track(.2),'DEFAULT');
 for(const name of['DRV8701_VM','DRV8701_MOTOR','DRV8701_GATE','DRV8701_SIGNAL'])addRule('TRACK',name,track(evidence.defaultTrackWidthsMm[name.replace('DRV8701_','')]));
 const safe=pcb.records.find(r=>r.id===JSON.stringify(['RULE','SAFE','copperThickness1oz']));
 if(!safe)throw new Error('Missing real-export SAFE rule template');
 // First seven rows cover copper object pairs; preserve stricter mechanical/
 // board-edge rows from the authentic export, rescaled if schema units selected.
 safe.body.ruleContext.safeSpacing.forEach(s=>s.content=s.content.map((row,i)=>row.map(v=>i<7?.15*U:encoding==='internal10mil-current-schema'?v/10:v)));
 addRule('RADIUS','viaSize',{unit:'mm',minRadius:.2*U,defRadius:.225*U,maxRadius:1*U,minInner:.1*U,defInner:.1*U,maxInner:.5*U},'DEFAULT');
 addRule('DFM_MIN_HOLE_SIZE','DRV8701_min_drill',{unit:'mm',minHoleSize:.2*U},'DEFAULT');
 addRule('DFM_PAD_RING_DEFECT','DRV8701_min_annular_ring',{unit:'mm',minRingWidth:.1*U},'DEFAULT');
 addRule('SOLDER','solderMaskExpansion',{unit:'mm',padTopExpan:0,padBotExpan:0,viaTopExpan:-1000,viaBotExpan:-1000,testPointTopExpan:0,testPointBotExpan:0},'DEFAULT');
 const netNames=pcb.records.filter(r=>r.type==='NET').map(r=>JSON.parse(r.id)[1]).filter(Boolean);
 for(const n of netNames){const type=n==='VM'?'VM':/^[LR]_[AB]$/.test(n)?'MOTOR':/^[LR]_G[HL][12]$/.test(n)?'GATE':'SIGNAL';
  const id=JSON.stringify(['RULE_SELECTOR',['NET',n]]),body={ruleOrder:1,ruleKeyValue:{TRACK:'DRV8701_'+type},copperValue:{},innerPlaneValue:{}};
  const r=record('RULE_SELECTOR',id,body),old=pcb.records.findIndex(x=>x.id===id);if(old<0)pcb.records.push(r);else pcb.records[old]=r;
 }
 const template=pcb.records.find(r=>r.type==='RULE_TEMPLATE');if(template)template.body.name='DRV8701 4-layer 1oz 0.15mm clearance';
 for(const d of docs){let ticket=1;for(const r of d.records){r.head.ticket=ticket++;r.ticket=r.head.ticket;}}
 E.writeRecords(file,docs.flatMap(d=>[d.head,...d.records]));
}
fs.writeFileSync(path.join(projectDir,'native-design-rules.json'),JSON.stringify(evidence,null,2));
console.log(JSON.stringify({ok:true,...evidence},null,2));
