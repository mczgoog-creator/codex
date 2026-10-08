#!/usr/bin/env node
'use strict';
// Post-process output of the official zero-dependency KiCad -> EasyEDA converter.
// No routing is performed here. All traces and filled polygons come from source.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const BASE = process.env.EASYEDA_TOOL_ROOT || __dirname;
const E = require(BASE + '/kicad-to-easyeda-eprj3/scripts/lib/eprj3.js');
const K = require(BASE + '/kicad-to-easyeda-eprj3/scripts/lib/kicad.js');
const [projectDir, kicadPcb] = process.argv.slice(2);
if (!projectDir || !kicadPcb) throw new Error('Usage: node finalize-native.js <native-project-directory> <source.kicad_pcb>');
const idxFile = fs.readdirSync(projectDir).find(s => s.endsWith('.eprj3'));
const index = JSON.parse(fs.readFileSync(path.join(projectDir, idxFile), 'utf8'));
if(!Object.keys(index.profile.boards).length){
  const bid=crypto.randomBytes(8).toString('hex');index.profile.boards[bid]={uuid:bid,title:'Board1',zIndex:1};
  for(const p of Object.values(index.profile.pcbs))p.board=bid;
}
index.pcb_count=Object.keys(index.profile.pcbs).length;
fs.writeFileSync(path.join(projectDir,idxFile),JSON.stringify(index,null,2));
const client = crypto.createHash('md5').update(index.owner_uuid).digest('hex').slice(0, 16);
const root = K.parse(fs.readFileSync(kicadPcb, 'utf8'));
const children = (n, t) => n.filter(x => Array.isArray(x) && x[0]?.v === t);
const child = (n, t) => children(n, t)[0];
const values = n => (n || []).slice(1).map(v => v.v);
const num = (n, t, i = 0, def = 0) => Number(values(child(n, t))[i] ?? def);
const str = (n, t, i = 0, def = '') => values(child(n, t))[i] ?? def;
const mod = a => ((a % 360) + 360) % 360;
const MIL = 1000 / 25.4;
const sourceSetup=child(root,'setup')||[];
const globalMaskMargin=num(sourceSetup,'pad_to_mask_clearance',0,0);
const globalPasteMargin=num(sourceSetup,'pad_to_paste_clearance',0,0);
const footprints = children(root, 'footprint').map(fp => {
  const props = Object.fromEntries(children(fp, 'property').map(p => [p[1].v, p[2].v]));
  for (const tx of children(fp, 'fp_text')) if (tx[1]?.v === 'reference') props.Reference = tx[2]?.v;
  const refNode=children(fp,'property').find(p=>p[1]?.v==='Reference') || children(fp,'fp_text').find(p=>p[1]?.v==='reference');
  const effects=child(refNode||[],'effects'),font=child(effects||[],'font');
  return {name: fp[1].v, ref: props.Reference, angle: num(fp, 'at', 2),
    x: num(fp, 'at'), y: num(fp, 'at', 1), layer: str(fp, 'layer'),
    referenceText:refNode?{x:num(refNode,'at'),y:num(refNode,'at',1),angle:num(refNode,'at',2),
      size:num(font||[],'size',0,.65),width:num(font||[],'thickness',0,.12),
      hidden:refNode.some(v=>v?.v==='hide') || effects?.some(v=>v?.v==='hide') || str(refNode,'hide')==='yes'}:null,
    pads: children(fp, 'pad').map(p => {
      const drill = child(p,'drill'), dv=values(drill).filter(v=>v!==undefined);
      const oval=dv[0]==='oval', dx=Number(dv[oval?1:0]||0),dy=Number(dv[oval?2:0]||0);
      const offset=child(drill||[],'offset');
      return {num:p[1].v,type:p[2].v,shape:p[3].v,x:num(p,'at'),y:num(p,'at',1),
        angle:num(p,'at',2),width:num(p,'size'),height:num(p,'size',1),
        roundrectRatio:num(p,'roundrect_rratio'),drillX:dx,drillY:dy,
        holeOffsetX:Number(values(offset)[0]||0),holeOffsetY:Number(values(offset)[1]||0),
        solderMaskMargin:num(p,'solder_mask_margin',0,num(fp,'solder_mask_margin',0,globalMaskMargin)),
        pasteMargin:num(p,'solder_paste_margin',0,num(fp,'solder_paste_margin',0,globalPasteMargin)),
        pasteMarginRatio:num(p,'solder_paste_margin_ratio',0,num(fp,'solder_paste_margin_ratio',0,0))};
    })};
});
const sourceByRef = new Map(footprints.map(fp => [fp.ref, fp]));
const firstByName = new Map();
for (const fp of footprints) if (!firstByName.has(fp.name)) firstByName.set(fp.name, fp);
const layerRows = (child(root, 'layers') || []).slice(1).filter(Array.isArray);
const copperLayers = layerRows.filter(n => /^(F|B|In\d+)\.Cu$/.test(n[1]?.v)).map(n => n[1].v);
const innerLayers = copperLayers.filter(n => /^In\d/.test(n));
const copperIds = [1, ...innerLayers.map(n => 14 + Number(n.match(/In(\d+)/)[1])), 2];
const report = {source: kicadPcb, project: path.join(projectDir,idxFile), copperLayers, corrections:[], padCoordinates:[], warnings:[]};
function splitDocs(records) {
  const docs=[];
  for (const rec of records) {
    if (rec.type === 'DOCHEAD') docs.push({head:rec, records:[]});
    else { if (!docs.length) throw new Error('Record before DOCHEAD'); docs.at(-1).records.push(rec); }
  }
  return docs;
}
function rec(type,body,id=crypto.randomBytes(8).toString('hex')) { return {type,id,head:{type,id,ticket:0},body}; }
function writeDocs(file,docs) {
  for(const d of [...docs]) {
    d.head.body.client=client;
    d.head.head={type:'DOCHEAD'};
    let ticket=1;
    for(const r of d.records) {r.head.ticket=ticket++;r.ticket=r.head.ticket;}
  }
  E.writeRecords(file,docs.flatMap(d=>[d.head,...d.records]));
}
function attrBody(parentId,key,value,x=null,y=null) {
  return {groupId:'',locked:false,zIndex:1,parentId,key,value,keyVisible:false,valueVisible:x!==null,
    x,y,rotation:0,color:null,fillColor:null,fontFamily:null,fontSize:5,
    strikeout:null,underline:null,italic:null,fontWeight:null,align:'LEFT_BOTTOM'};
}
const files=[];
function walk(dir) {for(const e of fs.readdirSync(dir,{withFileTypes:true})) {const f=path.join(dir,e.name);if(e.isDirectory())walk(f);else if(/\.(esch2|epcb2|ecfg)$/.test(e.name))files.push(f);}}
walk(projectDir);
// Process the PCB first, then embed its exact footprints into the schematics.
files.sort((a,b)=>Number(b.endsWith('.epcb2'))-Number(a.endsWith('.epcb2')));
const pcbFootprintsByRef=new Map();
const pairedDevicesByRef=new Map(),pairedDeviceDocs=new Map();
for(const file of files) {
  const docs=splitDocs(E.readRecords(file));
  for(const d of docs) {
    const dt=d.head.body.docType;
    for(const r of d.records) {
      if(['SYMBOL','SCH_PAGE'].includes(dt)&&['COMPONENT','WIRE','BUS'].includes(r.type)) {
        if(r.body.groupId===undefined)r.body.groupId='';
        if(r.body.locked===undefined)r.body.locked=false;
      }
      if(['PCB','FOOTPRINT'].includes(dt)&&r.type==='ATTR'&&r.body.parentId&& !r.id.startsWith(r.body.parentId)) {
        r.id=r.body.parentId+r.id;r.head.id=r.id;
      }
    }
    if(dt==='SCH') {
      if(d.records.length===1) {
        const rule=(name,state,min)=>rec('RULE',{ruleState:state,ruleContext:{unit:'mm',track:{isOpen:true,content:[{layerId:1,stroDef:0.254,stroMax:2.54,stroMin:min}]}}},JSON.stringify(['RULE','TRACK',name]));
        d.records.push(rule('copperThickness1oz','DEFAULT',0.127),rule('copperThickness2oz','NORMAL',0.203));
        report.corrections.push('Added the two documented schematic track-rule records.');
      }
    }
    if(dt==='SCH_PAGE') {
      const wireIds=new Set(d.records.filter(r=>['WIRE','BUS'].includes(r.type)).map(r=>r.id));
      let ncGraphicCount=0;
      for(const r of d.records)if(r.type==='LINE'&&r.body.lineGroup&&!wireIds.has(r.body.lineGroup)) {
        // The converter represents no-connect X marks with two LINEs but
        // omits their group. Make the X a nonconductive graphical polyline.
        const b=r.body;
        r.type='POLY';r.head.type='POLY';
        r.body={groupId:'',locked:false,zIndex:b.zIndex,
          points:[{x:b.startX,y:b.startY},{x:b.endX,y:b.endY}],closed:false,startShape:'NONE',endShape:'NONE',
          strokeColor:null,strokeStyle:'SOLID',fillColor:null,strokeWidth:b.strokeWidth,fillStyle:'NONE'};
        ncGraphicCount++;
      }
      if(ncGraphicCount)report.corrections.push(`Preserved ${ncGraphicCount/2} no-connect X marks as nonconductive schematic graphics.`);
      const lines=d.records.filter(r=>r.type==='LINE' && r.body.lineGroup);
      const labels=d.records.filter(r=>r.type==='NETLABEL');
      for(const label of labels) {
        const p=label.body;
        const hits=lines.filter(l=>{
          const b=l.body,dx=b.endX-b.startX,dy=b.endY-b.startY;
          const cross=(p.x-b.startX)*dy-(p.y-b.startY)*dx;
          return Math.abs(cross)<1e-5 && p.x>=Math.min(b.startX,b.endX)-1e-7 && p.x<=Math.max(b.startX,b.endX)+1e-7 && p.y>=Math.min(b.startY,b.endY)-1e-7 && p.y<=Math.max(b.startY,b.endY)+1e-7;
        });
        if(!hits.length)throw new Error(`Schematic label ${p.value} at ${p.x},${p.y} is not on a wire.`);
        const parentId=hits[0].body.lineGroup;
        label.type='ATTR';label.head.type='ATTR';label.body=attrBody(parentId,'NET',p.value,p.x,p.y);
      }
      if(labels.length)report.corrections.push(`Converted ${labels.length} standalone NETLABEL records to wire NET attributes.`);
      const ca=new Map();
      for(const r of d.records)if(r.type==='ATTR'){if(!ca.has(r.body.parentId))ca.set(r.body.parentId,{});ca.get(r.body.parentId)[r.body.key]=r.body.value;}
      for(const r of d.records.filter(r=>r.type==='COMPONENT')){
        const ref=ca.get(r.id)?.Designator,pf=pcbFootprintsByRef.get(ref);if(!pf)continue;
        let a=d.records.find(ar=>ar.type==='ATTR'&&ar.body.parentId===r.id&&ar.body.key==='Footprint');
        if(!a){a=rec('ATTR',attrBody(r.id,'Footprint',pf.uuid));d.records.push(a);}else a.body.value=pf.uuid;
        r.body.attrs.FootprintName=JSON.stringify({uuid:pf.uuid,name:pf.title,source:''});
        if(!docs.some(dd=>dd.head.body.uuid===pf.uuid))docs.splice(docs.indexOf(d),0,JSON.parse(JSON.stringify(pf.doc)));
        const oldDevice=docs.find(dd=>dd.head.body.uuid===ca.get(r.id)?.Device);
        const symbol=docs.find(dd=>dd.head.body.uuid===ca.get(r.id)?.Symbol);
        if(!oldDevice||!symbol)throw new Error(`No embedded symbol/device for ${ref}`);
        const pairKey=symbol.head.body.uuid+'|'+pf.uuid;
        let pair=pairedDeviceDocs.get(pairKey);
        if(!pair){
          const dev=JSON.parse(JSON.stringify(oldDevice)),reuse=oldDevice.records.find(rr=>rr.type==='META')?.body.attributes?.Footprint===pf.uuid;
          const uuid=reuse?oldDevice.head.body.uuid:crypto.randomBytes(8).toString('hex');
          dev.head.body.uuid=uuid;
          const meta=dev.records.find(rr=>rr.type==='META');
          if(!reuse)meta.body.title=meta.body.title+' / '+pf.title;
          Object.assign(meta.body.attributes,{Footprint:pf.uuid,FootprintName:JSON.stringify({uuid:pf.uuid,name:pf.title,source:''})});
          pair={uuid,title:meta.body.title,doc:dev,symbolDoc:symbol};pairedDeviceDocs.set(pairKey,pair);
        }
        if(!docs.some(dd=>dd.head.body.uuid===pair.uuid))docs.splice(docs.indexOf(d),0,JSON.parse(JSON.stringify(pair.doc)));
        d.records.find(ar=>ar.type==='ATTR'&&ar.body.parentId===r.id&&ar.body.key==='Device').body.value=pair.uuid;
        r.body.attrs.DeviceName=JSON.stringify({uuid:pair.uuid,name:pair.title,source:''});
        pairedDevicesByRef.set(ref,{...pair,uniqueId:ca.get(r.id)?.['Unique ID']});
      }
    }
    if(dt==='FOOTPRINT') {
      // PART is a schematic SYMBOL record. FOOTPRINT has no sub-parts.
      d.records=d.records.filter(r=>r.type!=='PART');
      const title=d.records.find(r=>r.type==='META')?.body.title;
      const src=firstByName.get(title);
      if(src) {
        const pads=d.records.filter(r=>r.type==='PAD');
        if(pads.length!==src.pads.length)throw new Error(`Pad-count mismatch for ${title}`);
        pads.forEach((p,i)=>{
          const sp=src.pads[i],b=p.body;
          b.padAngle=mod(sp.angle-src.angle);
          b.defaultPad.width=sp.width*MIL;b.defaultPad.height=sp.height*MIL;
          b.topSolderExpansion=sp.solderMaskMargin*MIL;b.bottomSolderExpansion=sp.solderMaskMargin*MIL;
          if(sp.pasteMarginRatio)throw new Error('Nonzero source paste-margin ratio needs a verified anisotropic-pad encoding.');
          b.topPasteExpansion=sp.pasteMargin*MIL;b.bottomPasteExpansion=sp.pasteMargin*MIL;
          if(sp.shape==='roundrect')b.defaultPad.radius=sp.roundrectRatio*Math.min(sp.width,sp.height)*MIL;
          if(sp.drillX>0&&sp.drillY>0){
            const slot=Math.abs(sp.drillX-sp.drillY)>1e-8;
            b.hole={holeType:slot?'SLOT':'ROUND',width:Math.max(sp.drillX,sp.drillY)*MIL,height:Math.min(sp.drillX,sp.drillY)*MIL,cornerRadius:0};
            b.relativeAngle=slot&&sp.drillY>sp.drillX?90:0;
            b.padOffsetX=sp.holeOffsetX*MIL;b.padOffsetY=-sp.holeOffsetY*MIL;
          }
        });
        report.corrections.push(`Preserved drill slot type/orientation and roundrect corner radii for footprint ${title}.`);
      }
    }
    if(dt==='PCB') {
      const pcbMeta=d.records.find(r=>r.type==='META');
      if(pcbMeta&&!pcbMeta.body.board)pcbMeta.body.board=Object.keys(index.profile.boards)[0];
      const byId=new Map(d.records.map(r=>[r.id,r]));
      const attrs=new Map();
      for(const r of d.records)if(r.type==='ATTR') {if(!attrs.has(r.body.parentId))attrs.set(r.body.parentId,{});attrs.get(r.body.parentId)[r.body.key]=r.body.value;}
      for(const r of d.records.filter(r=>r.type==='COMPONENT')) {
        const ref=attrs.get(r.id)?.Designator;
        const src=sourceByRef.get(ref);
        if(!src)throw new Error(`No source placement for ${ref}`);
        if(src.layer!=='F.Cu')throw new Error(`Bottom-side component ${ref} requires a separately verified mirror transform.`);
        r.body.angle=mod(src.angle);
        const refAttr=d.records.find(ar=>ar.type==='ATTR'&&ar.body.parentId===r.id&&ar.body.key==='Designator');
        if(refAttr&&src.referenceText){
          const s=src.referenceText,rad=src.angle*Math.PI/180,c=Math.cos(rad),sn=Math.sin(rad);
          Object.assign(refAttr.body,{x:(src.x+c*s.x+sn*s.y)*MIL,y:-(src.y-sn*s.x+c*s.y)*MIL,
            angle:mod(s.angle),fontSize:s.size*MIL,strokeWidth:s.width*MIL,
            valueVisible:!s.hidden,origin:'CENTER_MIDDLE'});
        }
        const fpUuid=attrs.get(r.id)?.Footprint;
        const fpDoc=docs.find(dd=>dd.head.body.uuid===fpUuid);
        if(!fpDoc)throw new Error(`No embedded footprint for ${ref}`);
        pcbFootprintsByRef.set(ref,{uuid:fpUuid,title:fpDoc.records.find(fr=>fr.type==='META').body.title,doc:fpDoc});
        const pads=fpDoc.records.filter(p=>p.type==='PAD');
        const a=r.body.angle*Math.PI/180,co=Math.cos(a),si=Math.sin(a);
        const as=src.angle*Math.PI/180,cs=Math.cos(as),ss=Math.sin(as);
        pads.forEach((pad,i)=>{
          const b=pad.body,sp=src.pads[i];
          const nativeX=(r.body.x+co*b.centerX-si*b.centerY)/MIL;
          const nativeY=-(r.body.y+si*b.centerX+co*b.centerY)/MIL;
          const sourceX=src.x+cs*sp.x+ss*sp.y,sourceY=src.y-ss*sp.x+cs*sp.y;
          const error=Math.hypot(nativeX-sourceX,nativeY-sourceY);
          if(error>0.00001)throw new Error(`${ref}.${sp.num}: native pad mismatch ${error} mm`);
          report.padCoordinates.push({reference:ref,pad:sp.num,xMm:sourceX,yMm:sourceY,errorMm:error});
        });
      }
      report.corrections.push('Corrected component and footprint-pad rotation; verified all placed pad centers against source.');
      for(const r of d.records.filter(r=>r.type==='LAYER')) {
        const lid=r.body.layerId;
        if(lid>=15&&lid<=46) {r.body.use=copperIds.includes(lid);r.body.show=r.body.use;}
      }
      const emptyNetId=JSON.stringify(['NET','']);
      if(!byId.has(emptyNetId)) {
        const at=d.records.findIndex(r=>r.type==='NET');
        d.records.splice(at<0?d.records.length:at,0,rec('NET',null,emptyNetId));
        report.corrections.push('Added the documented empty NET index record.');
      }
      if(innerLayers.length) {
        // Physical-layer encoding follows real exported V4.1.36 data (mil).
        // Official type docs currently disagree; see RESEARCH.md for evidence.
        const setup=child(root,'setup'),stack=child(setup||[],'stackup');
        const stackLayers=children(stack||[],'layer');
        const thicknessMm=num(child(root,'general')||[],'thickness',0,1.6);
        const copperT=.035;
        const maskT=name=>{const s=stackLayers.find(n=>n[1]?.v===name);return s?num(s,'thickness',0,.01):.01;};
        const dielectricDefault=(thicknessMm-copperIds.length*copperT-maskT('F.Mask')-maskT('B.Mask'))/(copperIds.length-1);
        report.physicalStack={nominalBoardThicknessMm:thicknessMm,copperThicknessMm:copperT,sourceStackupPresent:stackLayers.length>0,layers:[]};
        d.records=d.records.filter(r=>r.type!=='LAYER_PHYS');
        const physical=[];
        const aux=(name,id,z,mask=false)=>{
          const s=stackLayers.find(n=>n[1]?.v===name),t=mask?maskT(name):s?num(s,'thickness',0,0):0;
          physical.push(rec('LAYER_PHYS',{material:mask?'':null,thickness:t*MIL,permittivity:mask?3.3:null,lossTangent:mask?.02:null,isKeepIsland:true,zIndex:z},JSON.stringify(['LAYER_PHYS',id])));
          report.physicalStack.layers.push({name,thicknessMm:t});
        };
        aux('F.SilkS',3,1);aux('F.Paste',7,2);aux('F.Mask',5,3,true);
        for(let i=0;i<copperIds.length;i++) {
          const layerName=copperLayers[i];
          const layerStack=stackLayers.find(s=>s[1]?.v===layerName);
          const t=layerStack?num(layerStack,'thickness',0,copperT):copperT;
          physical.push(rec('LAYER_PHYS',{material:null,thickness:t*MIL,permittivity:null,lossTangent:null,isKeepIsland:true,zIndex:1000+i*1000},JSON.stringify(['LAYER_PHYS',copperIds[i]])));
          report.physicalStack.layers.push({name:layerName,thicknessMm:t});
          if(i<copperIds.length-1){
            const j=stackLayers.indexOf(layerStack),next=stackLayers.findIndex(s=>s[1]?.v===copperLayers[i+1]);
            const ds=j>=0&&next>j?stackLayers.slice(j+1,next):[];
            const dt=ds.length?ds.reduce((a,s)=>a+num(s,'thickness',0,0),0):dielectricDefault;
            physical.push(rec('LAYER_PHYS',{material:'FR4',thickness:dt*MIL,permittivity:4.5,lossTangent:.02,isKeepIsland:true,zIndex:1001+i*1000},JSON.stringify(['LAYER_PHYS',361+i])));
            report.physicalStack.layers.push({name:'dielectric'+(i+1),thicknessMm:dt,material:'FR4'});
          }
        }
        aux('B.Mask',6,10000,true);aux('B.Paste',8,10001);aux('B.SilkS',4,10002);
        report.physicalStack.encodedTotalThicknessMm=report.physicalStack.layers.reduce((a,s)=>a+s.thicknessMm,0);
        if(Math.abs(report.physicalStack.encodedTotalThicknessMm-thicknessMm)>.00001)throw new Error('Native physical stack thickness differs from source board thickness.');
        const ins=d.records.findIndex(r=>r.type==='NET');
        d.records.splice(ins<0?d.records.length:ins,0,...physical);
        report.corrections.push(`Enabled ${copperIds.length} copper layers and wrote physical stack in real-export mil units.`);
        report.warnings.push('The current upstream layer_phys field description says 0.1 mm; actual exported template encodes mil. A desktop-client open remains required to confirm stack interpretation.');
        if(!stackLayers.length)report.warnings.push('The source has no supplier dielectric stackup. The native file carries a nominal 1.6mm / 35um-per-copper-layer FR4 stack; dielectric distribution must be confirmed against the selected fabrication stackup.');
      }
    }
  }
  writeDocs(file,docs);
}
// Give both views the same fully embedded device and source unique ID.
for(const file of files.filter(f=>f.endsWith('.epcb2'))){
  const docs=splitDocs(E.readRecords(file)),d=docs.find(dd=>dd.head.body.docType==='PCB');
  for(const c of d.records.filter(r=>r.type==='COMPONENT')){
    const ref=d.records.find(r=>r.type==='ATTR'&&r.body.parentId===c.id&&r.body.key==='Designator')?.body.value;
    const pair=pairedDevicesByRef.get(ref);if(!pair)continue;
    d.records.find(r=>r.type==='ATTR'&&r.body.parentId===c.id&&r.body.key==='Device').body.value=pair.uuid;
    c.body.attrs.DeviceName=JSON.stringify({uuid:pair.uuid,name:pair.title,source:''});
    if(pair.uniqueId)c.body.attrs['Unique ID']=pair.uniqueId;
    for(const lib of[pair.symbolDoc,pair.doc])if(!docs.some(dd=>dd.head.body.uuid===lib.head.body.uuid))docs.splice(docs.indexOf(d),0,JSON.parse(JSON.stringify(lib)));
  }
  writeDocs(file,docs);
}
if(pairedDevicesByRef.size)report.corrections.push(`Embedded full symbol/footprint devices in both schematic and PCB views for ${pairedDevicesByRef.size} components.`);
fs.writeFileSync(path.join(projectDir,'native-conversion-evidence.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({ok:true,project:report.project,layers:copperLayers,verifiedPads:report.padCoordinates.length,corrections:report.corrections,warnings:report.warnings},null,2));
