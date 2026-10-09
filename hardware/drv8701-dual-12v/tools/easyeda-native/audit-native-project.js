#!/usr/bin/env node
'use strict';
// Dynamic final audit for the current source design. Does not route or edit CAD.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const BASE=process.env.EASYEDA_TOOL_ROOT||__dirname;
const E=require(path.join(BASE,'kicad-to-easyeda-eprj3/scripts/lib/eprj3'));
const K=require(path.join(BASE,'kicad-to-easyeda-eprj3/scripts/lib/kicad'));
const [projectDir,sourceDir,expectedFile,designFile]=process.argv.slice(2);
if(!designFile)throw new Error('Usage: audit-native-project.js <native> <source-dir> <expected-physical-pins.json> <design_netlist.json>');
const readJson=f=>JSON.parse(fs.readFileSync(f,'utf8'));
const design=readJson(designFile),expected=readJson(expectedFile),errors=[];
const expectedComponents=new Map(design.components.map(c=>[c.ref,c]));
if(expectedComponents.size!==design.components.length)errors.push('Duplicate source design reference');
const expectedRefs=[...expectedComponents.keys()].sort();
const expectedPinRefs=[...new Set(Object.keys(expected).map(k=>k.slice(0,k.lastIndexOf('.'))))].sort();
if(JSON.stringify(expectedRefs)!==JSON.stringify(expectedPinRefs))errors.push('Design references differ from physical-pin contract references');
const sourcePcb=path.join(sourceDir,'DRV8701_DUAL_12V.kicad_pcb');
const parsed=K.parse(fs.readFileSync(sourcePcb,'utf8'));
const children=(n,t)=>(n||[]).filter(v=>Array.isArray(v)&&v[0]?.v===t);
const sourceValues=new Map(children(parsed,'footprint').map(fp=>{
 const a=Object.fromEntries(children(fp,'property').map(p=>[p[1].v,p[2].v]));
 for(const t of children(fp,'fp_text'))if(['reference','value'].includes(t[1]?.v))a[t[1].v==='reference'?'Reference':'Value']??=t[2]?.v;
 return [a.Reference,a.Value];
}));
for(const [ref,c]of expectedComponents)if(sourceValues.get(ref)!==c.value)errors.push(`${ref}: design/source PCB value differs (${c.value}, ${sourceValues.get(ref)})`);
for(const ref of sourceValues.keys())if(!expectedComponents.has(ref))errors.push('Unexpected source PCB component '+ref);
const views={SCH_PAGE:new Map(),PCB:new Map()};
function walk(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){
 const f=path.join(d,e.name);if(e.isDirectory()){walk(f);continue;}
 if(!/\.(esch2|epcb2)$/.test(e.name))continue;
 const docs=[];for(const r of E.readRecords(f)){if(r.type==='DOCHEAD')docs.push({head:r,records:[]});else docs.at(-1).records.push(r);}
 for(const doc of docs.filter(d=>d.head.body.docType in views)){
  const attrs=new Map();for(const r of doc.records)if(r.type==='ATTR'){if(!attrs.has(r.body.parentId))attrs.set(r.body.parentId,{});attrs.get(r.body.parentId)[r.body.key]=r.body.value;}
  const view=views[doc.head.body.docType];
  for(const c of doc.records.filter(r=>r.type==='COMPONENT')){
   const a=attrs.get(c.id)||{},ref=a.Designator;if(!ref)continue;
   if(view.has(ref))errors.push('Duplicate native component '+ref+' in '+doc.head.body.docType);
   view.set(ref,{value:a.Name,device:a.Device,footprint:a.Footprint});
  }
 }
}}
walk(projectDir);
for(const [type,view]of Object.entries(views)){
 for(const [ref,c]of expectedComponents){const a=view.get(ref);if(!a)errors.push('Missing '+type+' component '+ref);else if(a.value!==c.value)errors.push(`${type} ${ref}: expected value ${c.value}, got ${a.value}`);}
 for(const ref of view.keys())if(!expectedComponents.has(ref))errors.push('Unexpected '+type+' component '+ref);
}
const format=readJson(path.join(projectDir,'native-format-validation.json'));
const sch=readJson(path.join(projectDir,'native-net-equivalence.json'));
const pcb=readJson(path.join(projectDir,'native-pcb-equivalence.json'));
const links=readJson(path.join(projectDir,'native-library-link-equivalence.json'));
const rule=readJson(path.join(projectDir,'native-design-rules.json'));
for(const [name,r]of Object.entries({schematic:sch,pcb,libraries:links}))if(!r.passed)errors.push(name+' audit failed');
if(format.failures.length||format.unmapped||format.outerValid!==format.records)errors.push('Unknown or failed native format record');
if(sch.components!==expectedComponents.size||pcb.components!==expectedComponents.size||links.components!==expectedComponents.size)errors.push('Native component count differs from design contract');
const expectedPins=Object.keys(expected).length,expectedNets=new Set(Object.values(expected).filter(Boolean)).size;
if(sch.physicalPinAssignments!==expectedPins||pcb.uniquePhysicalPins!==expectedPins)errors.push('Native physical pin count differs from contract');
if(sch.namedNets!==expectedNets||pcb.namedNets!==expectedNets)errors.push('Native named net count differs from contract');
const structureLog=fs.readFileSync(path.join(projectDir,'native-structure-validation.log'),'utf8');
if(!/OK \(0 errors, 0 warning\(s\)\)/.test(structureLog))errors.push('Official native structure validation did not pass without warnings');
const sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const sourceChecksums={};
for(const f of ['DRV8701_DUAL_12V.kicad_sch','DRV8701_DUAL_12V.kicad_pcb','DRV8701_DUAL_12V.kicad_pro'])if(fs.existsSync(path.join(sourceDir,f)))sourceChecksums[f]=sha(path.join(sourceDir,f));
sourceChecksums['design_netlist.json']=sha(designFile);sourceChecksums['expected_physical_pin_nets.json']=sha(expectedFile);
const entry=fs.readdirSync(projectDir).filter(f=>f.endsWith('.eprj3'));
if(entry.length!==1)errors.push('Expected exactly one native project entry');
const report={passed:errors.length===0,generatedAtUtc:new Date().toISOString(),projectEntry:entry[0],nativeFolderFormat:'official .eprj3 + .esch2 + .epcb2',sourceChecksumsSha256:sourceChecksums,noAutoroutingCalled:true,
 expectedDesign:{components:expectedComponents.size,physicalPins:expectedPins,namedNets:expectedNets,scope:design.scope},
 componentMetadataCheck:{schematicComponents:views.SCH_PAGE.size,pcbComponents:views.PCB.size,allValuesMatchDesign:errors.length===0},
 officialStructureCheck:{errors:0,warnings:0,log:'native-structure-validation.log'},
 formatCheck:{records:format.records,outerValid:format.outerValid,schemaValid:format.schemaValid,trustedExportRecords:format.trustedExportRecords,documentedDifferences:format.documentedDifferences,unmapped:format.unmapped,failures:format.failures},
 schematicCheck:sch,pcbCheck:pcb,libraryLinkCheck:{...links,rows:undefined},ruleCheck:rule,
 actualEasyedaClientOpenVerified:false,actualEasyedaClientDrcVerified:false,
 limitations:['This optional .eprj3 directory targets supported offline/semi-offline desktop clients, not the web .epro import picker.','Official current schema descriptions and real V4.1.36 export disagree on some length units; actual client stack/rule display remains unverified.','Copper and geometry are compared to source; actual EasyEDA client open and DRC have not been executed.'],errors};
fs.writeFileSync(path.join(projectDir,'native-final-audit.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,expected:report.expectedDesign,metadata:report.componentMetadataCheck,errors},null,2));
process.exitCode=errors.length?1:0;
