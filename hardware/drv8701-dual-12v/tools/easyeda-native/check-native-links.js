#!/usr/bin/env node
'use strict';
const fs=require('fs'),path=require('path');
const E=require(path.join(process.env.EASYEDA_TOOL_ROOT||__dirname,'kicad-to-easyeda-eprj3/scripts/lib/eprj3'));
const root=process.argv[2];if(!root)throw new Error('Usage: check-native-links.js <native-project>');
const files=[];function walk(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){const f=path.join(d,e.name);if(e.isDirectory())walk(f);else if(/\.(esch2|epcb2)$/.test(e.name))files.push(f);}}walk(root);
const views={SCH_PAGE:new Map(),PCB:new Map()},errors=[],rows=[];
for(const file of files){const docs=[];for(const r of E.readRecords(file)){if(r.type==='DOCHEAD')docs.push({head:r,records:[]});else docs.at(-1).records.push(r);}
 for(const d of docs.filter(d=>d.head.body.docType in views)){
  const attrs=new Map();for(const r of d.records)if(r.type==='ATTR'){if(!attrs.has(r.body.parentId))attrs.set(r.body.parentId,{});attrs.get(r.body.parentId)[r.body.key]=r.body.value;}
  for(const c of d.records.filter(r=>r.type==='COMPONENT')){const a=attrs.get(c.id)||{},ref=a.Designator;if(!ref)continue;const dev=docs.find(x=>x.head.body.uuid===a.Device&&x.head.body.docType==='DEVICE'),fp=docs.find(x=>x.head.body.uuid===a.Footprint&&x.head.body.docType==='FOOTPRINT');
   if(!dev||!fp){errors.push('Missing offline device/footprint '+ref+' in '+file);continue;}const da=dev.records.find(r=>r.type==='META')?.body.attributes||{},sym=docs.find(x=>x.head.body.uuid===da.Symbol&&x.head.body.docType==='SYMBOL');
   if(!sym)errors.push('Missing device symbol '+ref+' in '+file);if(da.Footprint!==a.Footprint)errors.push('Device/placed-footprint differs '+ref);if(d.head.body.docType==='SCH_PAGE'&&a.Symbol!==da.Symbol)errors.push('Device/placed-symbol differs '+ref);
   views[d.head.body.docType].set(ref,{device:a.Device,symbol:da.Symbol,footprint:a.Footprint,uniqueId:a['Unique ID']||c.body.attrs?.['Unique ID'],allLibrariesEmbedded:!!sym&&!!fp&&!!dev});
  }
 }
}
for(const [ref,s]of views.SCH_PAGE){const p=views.PCB.get(ref);if(!p){errors.push('Missing PCB counterpart '+ref);continue;}for(const k of['device','symbol','footprint','uniqueId'])if(s[k]!==p[k])errors.push('SCH/PCB '+k+' differs '+ref);rows.push({reference:ref,...s});}
for(const ref of views.PCB.keys())if(!views.SCH_PAGE.has(ref))errors.push('Missing schematic counterpart '+ref);
const report={passed:errors.length===0,components:rows.length,pairedDevices:new Set(rows.map(r=>r.device)).size,pairedFootprints:new Set(rows.map(r=>r.footprint)).size,externalLibraryDependencies:0,errors,rows};
fs.writeFileSync(path.join(root,'native-library-link-equivalence.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,rows:undefined},null,2));process.exitCode=errors.length?1:0;
