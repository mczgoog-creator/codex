#!/usr/bin/env python3
"""Prove 32 legacy-connectivity bridge tracks add no physical copper.

Read-only. Original source never changes. This audit checks real KiCad-loaded
shapes: outer approximation of each track's full capsule is wholly contained
in inner approximations of the original drain pad + exposed drain pad union.
Both approximations use 1 nm maximum error and conservative directions.
This explicitly includes the track endpoint caps, not just its centreline.
"""
import os
os.environ.setdefault('KICAD_CONFIG_HOME','/workspace/scratch/kicad-config')
from pathlib import Path
import sys,json,collections,hashlib
import pcbnew as p
from audit_legacy_pcb import board_snapshot,library_snapshot,xy

WIDTH_NM=250000
MAX_ERROR_NM=1

def track_key(row):
    return json.dumps(row,sort_keys=True,separators=(',',':'))

def undirected_key(row):
    v=dict(row)
    v['start'],v['end']=sorted([v['start'],v['end']])
    return track_key(v)

def real_track_row(board,t):
    return dict(start=xy(t.GetStart()),end=xy(t.GetEnd()),width=t.GetWidth(),layer=board.GetLayerName(t.GetLayer()),net=t.GetNetname())

def contained_track(track, small_pad, exposed_pad):
    # The union below is a subset of the true original pad copper shapes.
    inside=p.SHAPE_POLY_SET(); inside_small=p.SHAPE_POLY_SET()
    exposed_pad.TransformShapeToPolygon(inside,p.F_Cu,0,MAX_ERROR_NM,p.ERROR_INSIDE)
    small_pad.TransformShapeToPolygon(inside_small,p.F_Cu,0,MAX_ERROR_NM,p.ERROR_INSIDE)
    inside.BooleanAdd(inside_small)
    # The true track capsule is a subset of this outer approximation.
    outside=p.SHAPE_POLY_SET()
    track.TransformShapeToPolygon(outside,p.F_Cu,0,MAX_ERROR_NM,p.ERROR_OUTSIDE)
    capsule_area=outside.Area()/1e12
    pad_union_area=inside.Area()/1e12
    outside.BooleanSubtract(inside)
    return dict(full_track_capsule_contained_in_original_pad_union=outside.IsEmpty(),
      outside_original_pad_union_area_mm2=outside.Area()/1e12,
      outside_original_pad_union_outline_count=outside.OutlineCount(),
      conservative_track_capsule_area_mm2=capsule_area,
      conservative_pad_union_area_mm2=pad_union_area)

def main():
    base=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[2]
    legacy=Path(sys.argv[2]) if len(sys.argv)>2 else base/'KiCad_Import_5'
    source_path=base/'DRV8701_DUAL_12V.kicad_pcb'
    target_path=legacy/'DRV8701_DUAL_12V.kicad_pcb'
    report_path=Path(sys.argv[3]) if len(sys.argv)>3 else legacy/'finalpcb-source-equivalence.json'
    source,source_fill=board_snapshot(source_path)
    target,target_fill=board_snapshot(target_path)
    source_board=p.LoadBoard(str(source_path));target_board=p.LoadBoard(str(target_path))
    source_tracks=collections.Counter(track_key(t) for t in source['tracks'])
    target_tracks=collections.Counter(track_key(t) for t in target['tracks'])
    lost=source_tracks-target_tracks
    added=target_tracks-source_tracks
    missing_source=[json.loads(x) for x in lost.elements()]
    added_rows=[json.loads(x) for x in added.elements()]
    added_undirected=collections.Counter(undirected_key(x) for x in added_rows)
    retained_fields={k:source[k]==target[k] for k in source if k!='tracks'}
    expected={}
    source_components={f.GetReference():f for f in source_board.GetFootprints()}
    for ref in ['Q'+str(i) for i in range(1,9)]:
        fp=source_components[ref]
        drain=[pad for pad in fp.Pads() if pad.GetNumber() in {'5','6','7','8'}]
        exposed=max(drain,key=lambda pad:pad.GetSize().x*pad.GetSize().y)
        small=[pad for pad in drain if pad is not exposed]
        if exposed.GetNumber()!='5' or sorted(pad.GetNumber() for pad in small)!=['5','6','7','8']:
            raise ValueError('Unexpected original drain geometry: '+ref)
        for pad in small:
            pos=pad.GetPosition();ep=exposed.GetPosition()
            if p.F_Cu not in pad.GetLayerSet().Seq() or pad.GetNetname()!=exposed.GetNetname():
                raise ValueError('Unexpected original pad net/layer: '+ref)
            row=dict(start=xy(pos),end=[int(pos.x),int(ep.y)],width=WIDTH_NM,layer='F.Cu',net=pad.GetNetname())
            key=undirected_key(row)
            if key in expected:raise ValueError('Duplicate expected bridge')
            expected[key]=(ref,pad,exposed,row)
    expected_counter=collections.Counter(expected.keys())
    unexpected=[json.loads(x) for x in (added_undirected-expected_counter).elements()]
    absent=[json.loads(x) for x in (expected_counter-added_undirected).elements()]
    actual_added=[];remaining=collections.Counter(added)
    for item in target_board.GetTracks():
        if isinstance(item,p.PCB_VIA):continue
        row=real_track_row(target_board,item);key=track_key(row)
        if remaining[key]:
            remaining[key]-=1;actual_added.append((item,row))
    bridges=[]
    for track,row in actual_added:
        match=expected.get(undirected_key(row))
        if match is None:continue
        ref,pad,exposed,expected_row=match
        result=contained_track(track,pad,exposed)
        result.update(reference=ref,drain_pad_number=pad.GetNumber(),exposed_pad_number=exposed.GetNumber(),track=row)
        bridges.append(result)
    source_lib=library_snapshot(base/'DRV8701_Custom.pretty')
    target_lib=library_snapshot(legacy/'DRV8701_Custom.pretty')
    lib_equal=source_lib==target_lib
    # Legacy SCH timestamp is exactly the source instance UUID prefix. Compare
    # loaded old-format paths with the component identity map supplied by converter.
    timestamp_path=base/'KiCad_Import_5/pcb-format-conversion.json'
    timestamps=json.loads(timestamp_path.read_text())['component_timestamp_map']
    link_errors=[]
    for fp in target_board.GetFootprints():
        got=fp.GetPath().AsString().replace('-','').split('/')[-1][-8:].upper()
        if got!=timestamps[fp.GetReference()]:link_errors.append(fp.GetReference())
    failures=[]
    if missing_source:failures.append('Original track multiset was modified or lost')
    if len(source['tracks'])!=258 or len(target['tracks'])!=290 or len(added_rows)!=32:failures.append('Unexpected track counts')
    if unexpected or absent:failures.append('Additional segments differ from the 32 authorised drain bridges')
    if any(not v for v in retained_fields.values()):failures.append('Physical geometry or zone parameters changed')
    if not lib_equal:failures.append('Footprint library pad geometry changed')
    if link_errors:failures.append('Schematic component path mismatch')
    if len(bridges)!=32 or any(not x['full_track_capsule_contained_in_original_pad_union'] for x in bridges):failures.append('Bridge copper containment proof failed')
    if len(target['vias'])!=76:failures.append('Via count changed')
    report=dict(reader=p.Version(),source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),legacy_sha256=hashlib.sha256(target_path.read_bytes()).hexdigest(),passed=not failures,
      source_track_segments=258,legacy_track_segments=len(target['tracks']),added_bridge_segments=len(added_rows),
      original_258_track_segment_multiset_retained=not missing_source,added_segments_exactly_authorised_drain_bridges=not unexpected and not absent,
      equivalence_excluding_added_bridges_and_version_specific_zone_fill_cache=retained_fields,
      original_76_vias_retained=retained_fields['vias'],physical_pad_count=len(target['pads']),
      all_38_schematic_component_paths_retained=not link_errors,
      library_pad_geometry_unchanged=lib_equal,
      physical_copper_added_by_bridges_mm2=sum(x['outside_original_pad_union_area_mm2'] for x in bridges),
      geometric_proof=dict(method='Conservative polygon BooleanSubtract: outward track capsule minus union of inward original small-drain and exposed-drain pad shapes',max_arc_error_nm=MAX_ERROR_NM,track_error_direction='ERROR_OUTSIDE',pad_error_direction='ERROR_INSIDE',includes_track_endpoint_caps=True,numeric_coordinate_units='nanometres; integer clipping',source_shapes_from='actual pcbnew PAD.TransformShapeToPolygon for original roundrect/rect pads'),
      source_fill_cache=source_fill,legacy_fill_cache=target_fill,
      fill_cache_comparison='KiCad 5 uses its native regenerated fill cache. Copper-zone boundaries and parameters are compared; cache geometry is version dependent and is not asserted identical.',
      bridges=bridges,unexpected_additional_segments=unexpected,missing_expected_bridges=absent,missing_source_track_segments=missing_source,component_link_errors=link_errors,failures=failures)
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'bridges','source_fill_cache','legacy_fill_cache'}},indent=2))
    return 0 if not failures else 1

if __name__=='__main__':sys.exit(main())
