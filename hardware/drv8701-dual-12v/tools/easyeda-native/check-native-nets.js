#!/usr/bin/env node
'use strict';
const fs=require('fs'),path=require('path');
const E=require(path.join(process.env.EASYEDA_TOOL_ROOT||__dirname,'kicad-to-easyeda-eprj3/scripts/lib/eprj3'));
const [root,expectedFile]=process.argv.slice(2);
if(!root||!expectedFile)throw new Error('Usage: check-native-nets.js <native-project> <expected-pin-nets.json>');
const expected=JSON.parse(fs.readFileSync(expectedFile));
const files=[];function walk(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){const f=path.join(d,e.name);if(e.isDirectory())walk(f);else if(e.name.endsWith('.esch2'))files.push(f);}}walk(root);
const actual={},errors=[];let componentCount=0;
function pointOn(p,b){const dx=b.endX-b.startX,dy=b.endY-b.startY;return Math.abs((p.x-b.startX)*dy-(p.y-b.startY)*dx)<1e-5&&p.x>=Math.min(b.startX,b.endX)-1e-5&&p.x<=Math.max(b.startX,b.endX)+1e-5&&p.y>=Math.min(b.startY,b.endY)-1e-5&&p.y<=Math.max(b.startY,b.endY)+1e-5;}
for(const f of files){
 const docs=[];for(const r of E.readRecords(f)){if(r.type==='DOCHEAD')docs.push({head:r,records:[]});else docs.at(-1).records.push(r);}
 const page=docs.find(d=>d.head.body.docType==='SCH_PAGE');
 const attrs=new Map();for(const r of page.records)if(r.type==='ATTR'){if(!attrs.has(r.body.parentId))attrs.set(r.body.parentId,{});attrs.get(r.body.parentId)[r.body.key]=r.body.value;}
 const lines=page.records.filter(r=>r.type==='LINE'&&r.body.lineGroup);
 for(const c of page.records.filter(r=>r.type==='COMPONENT')){
  const ca=attrs.get(c.id)||{},ref=ca.Designator;if(!ref)continue;componentCount++;
  const sym=docs.find(d=>d.head.body.uuid===ca.Symbol);if(!sym)throw new Error('Missing symbol for '+ref);
  const pinAttrs=new Map();for(const r of sym.records)if(r.type==='ATTR'){if(!pinAttrs.has(r.body.parentId))pinAttrs.set(r.body.parentId,{});pinAttrs.get(r.body.parentId)[r.body.key]=r.body.value;}
  // Schematic local space is Y-down; rotation is clockwise in that space.
  const a=c.body.rotation*Math.PI/180,co=Math.cos(a),si=Math.sin(a);
  for(const pin of sym.records.filter(r=>r.type==='PIN')){
   const n=pinAttrs.get(pin.id)?.['Pin Number'];if(!n)continue;
   const px=c.body.isMirror?-pin.body.x:pin.body.x,py=pin.body.y;
   const p={x:c.body.x+co*px-si*py,y:c.body.y+si*px+co*py};
   const nets=new Set(lines.filter(l=>pointOn(p,l.body)).map(l=>attrs.get(l.body.lineGroup)?.NET).filter(Boolean));
   if(nets.size>1)errors.push(`${ref}.${n} touches conflicting named wires: ${[...nets]}`);
   actual[ref+'.'+n]=nets.size?[...nets][0]:null;
  }
 }
}
for(const [p,n] of Object.entries(expected))if(actual[p]!==n)errors.push(`${p}: expected ${n}, native ${actual[p]}`);
for(const p of Object.keys(actual))if(!(p in expected))errors.push('Unexpected native pin '+p);
const report={passed:errors.length===0,components:componentCount,physicalPinAssignments:Object.keys(actual).length,namedNets:new Set(Object.values(actual).filter(Boolean)).size,noConnectPins:Object.values(actual).filter(n=>n===null).length,errors};
fs.writeFileSync(path.join(root,'native-net-equivalence.json'),JSON.stringify(report,null,2));
fs.writeFileSync(path.join(root,'native-physical-pin-nets.json'),JSON.stringify(actual,null,2));
console.log(JSON.stringify(report,null,2));process.exitCode=errors.length?1:0;
