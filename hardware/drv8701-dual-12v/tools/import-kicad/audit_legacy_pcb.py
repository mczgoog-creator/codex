#!/usr/bin/env python3
"""Independently compare loaded source and legacy PCB using KiCad 9's real reader.

No board edits, zone fills, placements or routing. Saved-fill caches deliberately
excluded: the actual KiCad 5.1 environment must regenerate its native caches.
"""
import os
os.environ.setdefault('KICAD_CONFIG_HOME','/workspace/scratch/kicad-config')
from pathlib import Path
import json,sys,collections,hashlib
import pcbnew as p

def xy(v): return [int(v.x),int(v.y)]
def angle(obj): return round(obj.GetOrientationDegrees()%360,9)
def layers(b,obj): return sorted(b.GetLayerName(l) for l in obj.GetLayerSet().Seq())
def serialsort(values): return sorted(values,key=lambda x:json.dumps(x,sort_keys=True))
def poly_points(poly):
    return [dict(outline=[xy(poly.COutline(i).CPoint(j)) for j in range(poly.COutline(i).PointCount())],holes=[[xy(poly.CHole(i,k).CPoint(j)) for j in range(poly.CHole(i,k).PointCount())] for k in range(poly.HoleCount(i))]) for i in range(poly.OutlineCount())]

def board_snapshot(path):
    b=p.LoadBoard(str(path)); footprints=[]; pads=[]; tracks=[]; vias=[]; zones=[]; outline=[]
    for f in b.GetFootprints():
        footprints.append(dict(reference=f.GetReference(),value=f.GetValue(),position=xy(f.GetPosition()),orientation=angle(f),layer=b.GetLayerName(f.GetLayer()),lib_name=str(f.GetFPID().GetLibItemName())))
        for pad in f.Pads():
            row=dict(reference=f.GetReference(),number=pad.GetNumber(),position=xy(pad.GetPosition()),size=xy(pad.GetSize()),orientation=angle(pad),shape=pad.GetShape(),attribute=pad.GetAttribute(),drill_shape=pad.GetDrillShape(),drill=xy(pad.GetDrillSize()),offset=xy(pad.GetOffset()),layers=layers(b,pad),net=pad.GetNetname(),roundrect_radius=pad.GetRoundRectRadiusRatio(),solder_mask_margin=pad.GetLocalSolderMaskMargin(),solder_paste_margin=pad.GetLocalSolderPasteMargin(),solder_paste_ratio=pad.GetLocalSolderPasteMarginRatio())
            pads.append(row)
    for t in b.GetTracks():
        if isinstance(t,p.PCB_VIA):
            vias.append(dict(position=xy(t.GetPosition()),size=t.GetWidth(p.F_Cu),drill=t.GetDrillValue(),layers=layers(b,t),net=t.GetNetname(),via_type=t.GetViaType()))
        else:
            tracks.append(dict(start=xy(t.GetStart()),end=xy(t.GetEnd()),width=t.GetWidth(),layer=b.GetLayerName(t.GetLayer()),net=t.GetNetname()))
    for z in b.Zones():
        zones.append(dict(layer=b.GetLayerName(z.GetLayer()),net=z.GetNetname(),outline=poly_points(z.Outline()),minimum_thickness=z.GetMinThickness(),clearance=z.GetLocalClearance(),connection=z.GetPadConnection(),thermal_gap=z.GetThermalReliefGap(),thermal_spoke_width=z.GetThermalReliefSpokeWidth(),priority=z.GetAssignedPriority(),fill_mode=z.GetFillMode(),hatch_style=z.GetHatchStyle(),hatch_pitch=z.GetBorderHatchPitch()))
    for item in b.GetDrawings():
        if item.GetLayer()!=p.Edge_Cuts:continue
        typ=item.GetShape()
        if typ==p.SHAPE_T_RECT:
            sx,sy=xy(item.GetStart());ex,ey=xy(item.GetEnd())
            points=[[sx,sy],[ex,sy],[ex,ey],[sx,ey]]
            for i in range(4):
                outline.append(dict(points=sorted([points[i],points[(i+1)%4]]),width=item.GetWidth(),layer='Edge.Cuts'))
        elif typ==p.SHAPE_T_SEGMENT:
            outline.append(dict(points=sorted([xy(item.GetStart()),xy(item.GetEnd())]),width=item.GetWidth(),layer='Edge.Cuts'))
        else:raise ValueError('Unexpected outline shape')
    result=dict(footprints=serialsort(footprints),pads=serialsort(pads),tracks=serialsort(tracks),vias=serialsort(vias),zone_boundaries_and_settings=serialsort(zones),outline=serialsort(outline),board_thickness=b.GetDesignSettings().GetBoardThickness(),copper_layers=b.GetCopperLayerCount())
    fill_status=[dict(layer=b.GetLayerName(z.GetLayer()),filled=z.IsFilled(),vertices=z.GetFilledPolysList(z.GetLayer()).FullPointCount()) for z in b.Zones()]
    return result,fill_status

def library_snapshot(directory):
    b=p.BOARD(); result={}
    for path in sorted(directory.glob('*.kicad_mod')):
        fp=p.FootprintLoad(str(directory),path.stem)
        if fp is None: raise ValueError('Library footprint could not be loaded: '+str(path))
        result[path.stem]=serialsort([dict(number=x.GetNumber(),position=xy(x.GetPosition()),size=xy(x.GetSize()),angle=angle(x),shape=x.GetShape(),drill=xy(x.GetDrillSize()),drill_shape=x.GetDrillShape(),roundrect=x.GetRoundRectRadiusRatio(),layers=layers(b,x)) for x in fp.Pads()])
    return result

def main():
    base=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[2]
    legacy=Path(sys.argv[2]) if len(sys.argv)>2 else base/'KiCad_Import_5'
    src=base/'DRV8701_DUAL_12V.kicad_pcb';target=legacy/'DRV8701_DUAL_12V.kicad_pcb'
    source,source_fill=board_snapshot(src);dest,dest_fill=board_snapshot(target)
    mismatches={}
    for key in source.keys():
        if source[key]!=dest[key]:
            if isinstance(source[key],list):
                sc=collections.Counter(json.dumps(x,sort_keys=True) for x in source[key]);dc=collections.Counter(json.dumps(x,sort_keys=True) for x in dest[key])
                mismatches[key]={'source_only':[json.loads(k) for k in (sc-dc).elements()],'target_only':[json.loads(k) for k in (dc-sc).elements()]}
            else:mismatches[key]={'source':source[key],'target':dest[key]}
    target_board=p.LoadBoard(str(target))
    timestamp_map=json.loads((legacy/'pcb-format-conversion.json').read_text())['component_timestamp_map']
    link_errors=[]
    for f in target_board.GetFootprints():
        expected=timestamp_map[f.GetReference()].lower()
        loaded=f.GetPath().AsString().replace('-','').split('/')[-1]
        if loaded[-8:].lower()!=expected:link_errors.append(f.GetReference())
    src_library=library_snapshot(base/'DRV8701_Custom.pretty')
    dst_library=library_snapshot(legacy/'DRV8701_Custom.pretty')
    library_rows=[dict(footprint=k,physical_pads=len(v),source_and_legacy_pad_geometry_identical=v==dst_library.get(k)) for k,v in src_library.items()]
    library_errors=[k for k in src_library.keys()|dst_library.keys() if src_library.get(k)!=dst_library.get(k)]
    (legacy/'footprint-library-equivalence.json').write_text(json.dumps({'reader':p.Version(),'all_equal':not library_errors,'footprints':library_rows,'mismatched_footprints':library_errors},indent=2)+'\n')
    report={'reader':p.Version(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'legacy_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'exactly_equal_excluding_native_fill_cache':not mismatches,'component_link_errors':link_errors,'library_geometry_errors':library_errors,'counts':{k:len(v) for k,v in source.items() if isinstance(v,list)},'source_fill_cache':source_fill,'legacy_fill_cache':dest_fill,'fill_cache_status':('Filled caches present; their generation/DRC evidence is reported separately.' if all(x['filled'] and x['vertices']>0 for x in dest_fill) else 'Legacy fill caches intentionally cleared; actual KiCad 5.1 native refill and DRC are separate required checks.'),'mismatches':mismatches}
    (legacy/'pcb-geometry-equivalence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'mismatches','source_fill_cache','legacy_fill_cache'}},indent=2))
    if mismatches or link_errors or library_errors:
        print(json.dumps(mismatches,indent=2)[:10000]); return 1
    return 0
if __name__=='__main__':sys.exit(main())
