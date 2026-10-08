#!/usr/bin/env node
'use strict';
// Validate the actual output using the current official primitive schemas.
// Report, rather than hide, differences explicitly documented in real exports.
const fs=require('fs'),path=require('path');
const BASE=process.env.EASYEDA_TOOL_ROOT||__dirname;
const {validateFormat,validateOuter}=require(BASE+'/easyeda-format-skill/validate.js');
const E=require(BASE+'/kicad-to-easyeda-eprj3/scripts/lib/eprj3.js');
const root=process.argv[2];if(!root)throw new Error('Usage: node validate-native.js <project-directory>');
const files=[];
function walk(d){for(const a of fs.readdirSync(d,{withFileTypes:true})){const p=path.join(d,a.name);if(a.isDirectory())walk(p);else if(/\.(esch2|epcb2|ecfg)$/.test(p))files.push(p);}}
walk(root);
const frame=JSON.parse(fs.readFileSync(BASE+'/kicad-to-easyeda-eprj3/scripts/lib/frame-a4.json'));
const trustedDocs=new Set([...frame.symbol,...frame.device].filter(r=>r.type==='DOCHEAD').map(r=>r.body.uuid));
const template=JSON.parse(fs.readFileSync(BASE+'/kicad-to-easyeda-eprj3/scripts/lib/pcb-config.json'));
const trustedTemplateBodies=new Set(template.map(r=>r.type+'|'+JSON.stringify(r.body)));
const stats={records:0,outerValid:0,schemaValid:0,trustedExportRecords:0,documentedDifferences:0,unmapped:0,failures:[]};
const examples=[],unmapped=[];
function knownDifference(type,doc,b,e){
 const f=e.field||'',m=e.message||'';
 if(['PCB','FOOTPRINT'].includes(doc)){
  if(f==='groupId'&&b.groupId===0&&m==='must be string')return 'Numeric 0 is the documented real-export ungrouped form.';
  if(type==='ATTR'&&f==='groupId'&&b.groupID===0&&/required property/.test(m))return 'Real PCB ATTR uses groupID (uppercase ID).';
  if(['ATTR','STRING'].includes(type)&&['bold','italic'].includes(f)&&[0,1].includes(b[f])&&/must be boolean/.test(m))return 'Real exported text styles use 0/1.';
  if(['ATTR','STRING'].includes(type)&&f==='specialColor'&&b.specialColor===null&&m==='must be string')return 'Documented default specialColor is null.';
  if(type==='PAD'&&f==='hole'&&b.hole===null&&m==='must be object')return 'Documented SMD pad has hole:null.';
  if(type==='PAD_NET'&&['padLen','propagationDelay'].includes(f)&&b[f]===null&&m==='must be number')return 'Unspecified pad delay/length is null in real exports.';
  if(type==='LAYER_PHYS'&&['material','permittivity','lossTangent'].includes(f)&&b[f]===null&&/must be/.test(m))return 'Copper/auxiliary physical layers carry null values in real exports.';
  if(type==='CANVAS'&&Object.keys(b).every(k=>['originX','originY'].includes(k))&&/required property/.test(m))return 'Real PCB template uses the two-field CANVAS form.';
  if(type==='PRIMITIVE'&&/required property/.test(m))return 'Static PRIMITIVE editor settings copied from official export.';
  if(type==='RULE_SELECTOR'&&Object.keys(b).length===0)return 'Default selector has an empty payload in official export.';
 }
 if(['SYMBOL','SCH_PAGE'].includes(doc)){
  if(type==='ATTR'&&['groupId','locked'].includes(f)&&/required property/.test(m))return 'Legacy exported binding attributes omit optional group/lock fields.';
  if(type==='ATTR'&&['rotation','keyVisible','valueVisible','align','value'].includes(f)&&b[f]===null&&/must be/.test(m))return 'Legacy exported binding/worksheet attributes use null display fields.';
  if(type==='PIN'&&f==='color'&&b.color===null&&m==='must be string')return 'Exported symbol pin uses null theme color.';
  if(type==='ATTR'&&['strikeout','underline','italic','fontWeight'].includes(f)&&/required property/.test(m))return 'Legacy exported binding ATTR omits null text-style flags.';
 }
 return null;
}
for(const file of files){
 let doc=null,uuid=null;
 for(const r of E.readRecords(file)){
  stats.records++;
  const outer=validateOuter(r.head);
  if(outer.valid)stats.outerValid++;else stats.failures.push({file,type:r.type,outer:true,errors:outer.errors});
  if(r.type==='DOCHEAD'){doc=r.body.docType;uuid=r.body.uuid;continue;}
  if(trustedDocs.has(uuid)){stats.trustedExportRecords++;continue;}
  if(doc==='PCB'&&trustedTemplateBodies.has(r.type+'|'+JSON.stringify(r.body))){stats.trustedExportRecords++;continue;}
  if(r.type==='NET'&&Object.keys(r.body||{}).length===0){stats.trustedExportRecords++;continue;}
  const key=doc+'_'+r.type;
  const result=validateFormat(key,r.body);
  if(result.valid){stats.schemaValid++;continue;}
  if(result.errors.every(e=>/Unknown type/.test(e.message))){stats.unmapped++;if(!unmapped.includes(key))unmapped.push(key);continue;}
  const bad=[];
  for(const e of result.errors){
   const reason=knownDifference(r.type,doc,r.body,e);
   if(reason){stats.documentedDifferences++;if(examples.length<80)examples.push({type:key,field:e.field,message:e.message,reason});}
   else bad.push(e);
  }
  if(bad.length)stats.failures.push({file:path.relative(root,file),doc,type:r.type,id:r.id,errors:bad,body:r.body});
 }
}
const report={...stats,documentedDifferenceExamples:examples,unmappedTypes:unmapped,
 compatibility:'Static format/reference validation only. No EasyEDA desktop client was available; actual open/DRC remains unverified.'};
fs.writeFileSync(path.join(root,'native-format-validation.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({...stats,failures:stats.failures.slice(0,12),unmappedTypes:unmapped},null,2));
process.exitCode=stats.failures.length?1:0;
