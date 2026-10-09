#!/usr/bin/env python3
"""Convert this source-faithful manually routed KiCad 9 PCB into genuine KiCad 5 syntax.

This is a document-format conversion, not placement/routing/fill generation.
Parser/serializer is dependency-free and preserves decimal input tokens exactly.
KiCad 5.1 syntax was checked against KiCad/kicad-source-mirror branch 5.1:
  pcbnew/pcb_parser.cpp, pcbnew/kicad_plugin.cpp, pcbnew/class_zone.cpp.
Use /usr/bin/python3 (KiCad's pcbnew module) to run the final semantic audit.
"""
from pathlib import Path
import re, json, sys, hashlib, collections, argparse

class Atom(str): pass

def parse(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text)
    stack=[]; root=None
    for tok in tokens:
        if tok=='(':
            node=[]
            if stack: stack[-1].append(node)
            else:
                if root is not None: raise ValueError('Multiple roots')
                root=node
            stack.append(node)
        elif tok==')':
            if not stack: raise ValueError('Unbalanced close')
            stack.pop()
        else:
            if not stack: raise ValueError('Atom outside root')
            stack[-1].append(json.loads(tok) if tok.startswith('"') else Atom(tok))
    if stack: raise ValueError('Unclosed list')
    return root

def a(v): return Atom(str(v))
def n(head, *items): return [a(head), *items]
def h(node): return str(node[0]) if isinstance(node,list) and node else None

def child(node,head,default=None):
    return next((v for v in node if h(v)==head),default)

def children(node,head): return [v for v in node if h(v)==head]

def value(node,head,default=None):
    got=child(node,head)
    return got[1] if got else default

def without(node,heads): return [v for v in node if h(v) not in heads]

def scalar(v):
    return str(v) if isinstance(v,Atom) else json.dumps(v,ensure_ascii=False)

def serialize(node, level=0):
    if not isinstance(node,list): return scalar(node)
    # Keep atoms and short leaf lists on one line, nested statements readable.
    if all(not isinstance(v,list) for v in node):
        return '('+' '.join(scalar(v) for v in node)+')'
    lead=[]; rest=[]; seen_list=False
    for v in node:
        if isinstance(v,list): seen_list=True
        if seen_list: rest.append(v)
        else: lead.append(v)
    return '('+' '.join(scalar(v) for v in lead)+'\n'+'\n'.join('  '*(level+1)+serialize(v,level+1) for v in rest)+'\n'+'  '*level+')'

OLD_LAYERS={'F.Cu':0,'In1.Cu':1,'In2.Cu':2,'B.Cu':31,
 'B.Adhes':32,'F.Adhes':33,'B.Paste':34,'F.Paste':35,'B.SilkS':36,'F.SilkS':37,
 'B.Mask':38,'F.Mask':39,'Dwgs.User':40,'Cmts.User':41,'Eco1.User':42,
 'Eco2.User':43,'Edge.Cuts':44,'Margin':45,'B.CrtYd':46,'F.CrtYd':47,
 'B.Fab':48,'F.Fab':49}
REPORT=collections.Counter()

# Fail closed: only tokens present in this design and verified in the 5.1 parser.
PAD_FIELDS={'at','size','drill','layers','net','die_length','solder_mask_margin',
 'solder_paste_margin','solder_paste_margin_ratio','clearance','zone_connect',
 'roundrect_rratio','thermal_width','thermal_gap','rect_delta','options','primitives'}
MOD_FIELDS={'layer','at','descr','tags','path','tstamp','tedit','autoplace_cost90',
 'autoplace_cost180','solder_mask_margin','solder_paste_margin','solder_paste_ratio',
 'clearance','zone_connect','thermal_width','thermal_gap','attr','fp_text',
 'fp_line','fp_circle','fp_arc','fp_poly','fp_curve','pad','model'}
TRACK_FIELDS={'start','end','width','layer','net','tstamp','status'}
VIA_FIELDS={'at','size','drill','layers','net','tstamp','status'}
ZONE_FIELDS={'net','net_name','layer','layers','tstamp','hatch','priority',
 'connect_pads','min_thickness','fill','polygon','filled_polygon','fill_segments'}

STAMP_MAP={}

def stamp(uuid):
    stamp=str(uuid).replace('-','')[:8].upper()
    old=STAMP_MAP.get(stamp)
    if old is not None and old!=str(uuid): raise ValueError(f'Timestamp collision {stamp}')
    STAMP_MAP[stamp]=str(uuid)
    return a(stamp)

def known(node, fields):
    unknown=[h(v) for v in node[1:] if isinstance(v,list) and h(v) not in fields]
    if unknown: raise ValueError(f'Unverified legacy fields in {h(node)}: {unknown}')
    return node

def rename_uuid(node):
    out=[]
    for v in node:
        if h(v)=='uuid': out.append(n('tstamp',stamp(v[1]))); REPORT['uuid_to_tstamp']+=1
        else: out.append(v)
    return out

def text_legacy(node,property_node=False):
    if property_node:
        key=str(node[1]); kind={'Reference':'reference','Value':'value'}.get(key,'user')
        if kind=='user' and not node[2]:
            REPORT['empty_nonrendered_properties_removed']+=1; return None
        out=n('fp_text',a(kind),node[2]) + node[3:]
        REPORT['property_to_fp_text']+=1
    else: out=list(node)
    out=without(out,{'uuid','tstamp','unlocked'})
    converted=[]
    for v in out:
        if h(v)=='hide':
            if str(v[1])=='yes': converted.append(a('hide'))
        elif h(v)=='effects':
            v=without(v,{'hide'})
            converted.append(v)
        else: converted.append(v)
    # Legacy fp_text does not accept tstamp, property uuid, or modern (hide yes).
    known(converted,{'at','layer','effects'})
    return converted

def graphic_legacy(node):
    typ=h(node)
    width=value(child(node,'stroke',[]),'width')
    if width is None: width=value(node,'width')
    if width is None: raise ValueError(f'Missing graphic width {typ}')
    fill=value(node,'fill','none')
    if str(fill) not in {'none','no'}: raise ValueError(f'Cannot silently alter a filled graphic {typ}')
    base=without(node,{'stroke','fill','uuid','tstamp'})
    sid=value(node,'uuid')
    if typ in {'fp_rect','gr_rect'}:
        s=child(node,'start')[1:]; e=child(node,'end')[1:]
        pts=[[s[0],s[1]],[e[0],s[1]],[e[0],e[1]],[s[0],e[1]]]
        extra=[v for v in base[1:] if h(v) not in {'start','end'}]
        out=[]
        for i in range(4):
            line=n(typ.replace('_rect','_line'),n('start',*pts[i]),n('end',*pts[(i+1)%4]),*extra,n('width',width))
            if sid:
                uid=hashlib.sha256((str(sid)+':edge:'+str(i)).encode()).hexdigest()
                line.append(n('tstamp',stamp(uid)))
            out.append(line)
        REPORT['rectangles_to_four_lines']+=1
        return out
    if typ.endswith('_arc'):
        # This design contains no arcs. Modern 3-point arcs need true geometric conversion.
        raise ValueError('3-point arc conversion not implemented for unexpected source geometry')
    base.append(n('width',width))
    if sid: base.append(n('tstamp',stamp(sid)))
    known(base,{'start','end','center','pts','layer','width','tstamp','status'})
    REPORT['stroke_to_width']+=1
    return [base]

def pad_legacy(node):
    if str(value(node,'remove_unused_layers','no'))!='no':
        raise ValueError('Cannot represent removal of unused pad layers in 5.1')
    out=without(node,{'uuid','remove_unused_layers','keep_end_layers'})
    # KiCad 5 pad grammar has no object timestamp.
    known(out,PAD_FIELDS)
    REPORT['pads']+=1
    return out

def module_legacy(node,symbols=None,standalone=False):
    ref=next((v[2] for v in children(node,'property') if str(v[1])=='Reference'),None)
    out=n('module',node[1])
    if symbols is not None:
        if ref not in symbols: raise ValueError(f'No schematic symbol for {ref}')
        out += [n('tedit',a('0')),n('tstamp',symbols[ref]),n('path','/'+str(symbols[ref]))]
        REPORT['schematic_pcb_path_links']+=1
    for v in node[2:]:
        typ=h(v)
        if typ in {'version','generator','generator_version','embedded_fonts','uuid','path','tstamp','tedit'}:
            REPORT['unsupported_module_metadata_removed']+=1; continue
        if typ=='property' or typ=='fp_text':
            converted=text_legacy(v,typ=='property')
            if converted is not None: out.append(converted)
        elif typ=='attr':
            attributes=[x for x in v[1:] if str(x) in {'smd','virtual'}]
            if attributes: out.append(n('attr',*attributes))
            if len(attributes)!=len(v)-1: REPORT['modern_tht_attr_removed']+=1
        elif typ=='pad': out.append(pad_legacy(v))
        elif typ and typ.startswith('fp_'):
            out += graphic_legacy(v)
        else: out.append(v)
    known(out,MOD_FIELDS)
    REPORT['modules']+=1
    return out

def zone_legacy(node):
    out=rename_uuid(without(node,{'filled_areas_thickness','filled_polygon','fill_segments'}))
    REPORT['modern_fill_cache_removed'] += len(children(node,'filled_polygon'))
    converted=[]
    for v in out:
        if h(v)=='filled_polygon':
            converted.append(without(v,{'layer','island'})); REPORT['zone_filled_polygon_layer_removed']+=1
        elif h(v)=='fill':
            known(v,{'mode','arc_segments','thermal_gap','thermal_bridge_width','smoothing','radius'})
            converted.append([x for x in v if str(x)!='yes'])
        else: converted.append(v)
    known(converted,ZONE_FIELDS)
    REPORT['zones']+=1
    return converted

def setup_legacy(project):
    rules=project['board']['design_settings']['rules']
    defaults=project['net_settings']['classes'][0]
    # 5.1 stores these settings in PCB rather than modern .kicad_pro.
    return n('setup',n('last_trace_width',a(defaults['track_width'])),
      n('trace_clearance',a(defaults['clearance'])),n('zone_clearance',a('0.15')),
      n('zone_45_only',a('no')),n('trace_min',a(rules['min_track_width'])),
      n('via_size',a(defaults['via_diameter'])),n('via_drill',a(defaults['via_drill'])),
      n('via_min_size',a(rules['min_via_diameter'])),n('via_min_drill',a(rules['min_through_hole_diameter'])),
      n('uvia_size',a('0.3')),n('uvia_drill',a('0.1')),n('uvias_allowed',a('no')),
      n('uvia_min_size',a('0.3')),n('uvia_min_drill',a('0.1')),
      n('edge_width',a('0.05')),n('segment_width',a('0.2')),
      n('pcb_text_width',a('0.12')),n('pcb_text_size',a('1'),a('1')),
      n('mod_edge_width',a('0.12')),n('mod_text_width',a('0.12')),
      n('mod_text_size',a('0.7'),a('0.7')),n('pad_size',a('1'),a('1')),
      n('pad_drill',a('0.6')),n('pad_to_mask_clearance',a('0')),
      n('aux_axis_origin',a('0'),a('0')))

def netclasses_legacy(project):
    classes=project['net_settings']['classes']
    patterns=project['net_settings'].get('netclass_patterns',[])
    out=[]
    for c in classes:
        cls=n('net_class',c['name'],c.get('description',''),
           n('clearance',a(c['clearance'])),n('trace_width',a(c['track_width'])),
           n('via_dia',a(c['via_diameter'])),n('via_drill',a(c['via_drill'])),
           n('uvia_dia',a(c.get('microvia_diameter',0.3))),n('uvia_drill',a(c.get('microvia_drill',0.1))))
        for p in patterns:
            if p['netclass']==c['name']:
                cls.append(n('add_net',p['pattern']))
        out.append(cls)
    return out

def convert(base,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    src=parse((base/'DRV8701_DUAL_12V.kicad_pcb').read_text())
    sch=parse((base/'DRV8701_DUAL_12V.kicad_sch').read_text())
    symbols={}
    for node in children(sch,'symbol'):
        ref=next(p[2] for p in children(node,'property') if str(p[1])=='Reference')
        symbols[ref]=stamp(value(node,'uuid'))
    if len(symbols)!=38 or len(set(symbols.values()))!=38: raise ValueError('Schematic timestamp identity mismatch')
    project=json.loads((base/'DRV8701_DUAL_12V.kicad_pro').read_text())
    out=n('kicad_pcb',n('version',a('20171130')),n('host',a('pcbnew'),a('5.1.12')))
    for node in src[1:]:
        typ=h(node)
        if typ in {'version','generator','generator_version','embedded_fonts'}: continue
        if typ=='general': out.append(without(node,{'legacy_teardrops'}))
        elif typ=='paper': out.append(n('page',*node[1:])); REPORT['paper_to_page']+=1
        elif typ=='layers':
            ls=n('layers')
            for entry in node[1:]:
                name=str(entry[1])
                if name not in OLD_LAYERS:
                    # User.1..4 are declared but unused in this source board.
                    if re.search(r'\(layer\s+"'+re.escape(name)+r'"',serialize(src)):
                        raise ValueError(f'Used layer unavailable in 5.1: {name}')
                    REPORT['unused_modern_user_layers_removed']+=1; continue
                ls.append([a(OLD_LAYERS[name]),entry[1],entry[2]])
                REPORT['layer_ids_converted']+=1
            out.append(ls)
        elif typ=='setup':
            out.append(setup_legacy(project)); REPORT['setup_replaced_with_legacy_settings']+=1
            # Stackup is exported as explicit sidecar documentation; 5.1 grammar has no stackup.
            stackup=child(node,'stackup')
            if stackup: (outdir/'stackup-source.kicad-sexpr.txt').write_text(serialize(stackup)+'\n')
        elif typ=='footprint': out.append(module_legacy(node,symbols))
        elif typ in {'gr_line','gr_rect','gr_circle','gr_poly','gr_curve','gr_arc'}: out+=graphic_legacy(node)
        elif typ=='gr_text':
            node=rename_uuid(node); known(node,{'at','layer','effects','tstamp'})
            out.append(node)
        elif typ=='segment': out.append(known(rename_uuid(node),TRACK_FIELDS))
        elif typ=='via': out.append(known(rename_uuid(node),VIA_FIELDS))
        elif typ=='zone': out.append(zone_legacy(node))
        elif typ=='net': out.append(node)
        else: raise ValueError(f'Unsupported source board statement: {typ}')
    # Save netclasses alongside net definitions, before components.
    first_module=next(i for i,x in enumerate(out) if h(x)=='module')
    out[first_module:first_module]=netclasses_legacy(project)
    outfile=outdir/'DRV8701_DUAL_12V.kicad_pcb'
    outfile.write_text(serialize(out)+'\n')
    libdir=outdir/'DRV8701_Custom.pretty'; libdir.mkdir(exist_ok=True)
    for srcfile in sorted((base/'DRV8701_Custom.pretty').glob('*.kicad_mod')):
        libdir.joinpath(srcfile.name).write_text(serialize(module_legacy(parse(srcfile.read_text()),standalone=True))+'\n')
    (outdir/'pcb-format-conversion.json').write_text(json.dumps({'source_version':'20241229','target_version':'20171130','target_reader':'KiCad 5.1','symbol_timestamp_prefixes_unique':True,'component_timestamp_map':{str(k):str(v) for k,v in symbols.items()},'zone_policy':'native-refill-retain-original-constraints','transform_counts':dict(REPORT),'official_syntax_reference':'https://github.com/KiCad/kicad-source-mirror/tree/2758acfd4265f295c14a5bf009fa742e4abad131/pcbnew','sha256_source':hashlib.sha256((base/'DRV8701_DUAL_12V.kicad_pcb').read_bytes()).hexdigest(),'sha256_initial_unfilled_target':hashlib.sha256(outfile.read_bytes()).hexdigest()},indent=2)+'\n')
    print(outfile)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('base',type=Path,nargs='?',default=Path(__file__).resolve().parents[2])
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    convert(args.base,args.out or args.base/'KiCad_Import_5')
