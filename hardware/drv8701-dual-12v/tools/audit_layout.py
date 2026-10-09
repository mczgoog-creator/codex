#!/usr/bin/python3
"""Read-only, independent PCB layout measurements from actual KiCad objects.

This is an engineering geometry review, not a replacement for the CAD DRC or
electromagnetic/thermal verification.  Copper-path length estimates use actual
tracks, through vias and pad copper, but deliberately exclude zone copper.
Thus a zone-based connection is reported as unmeasured rather than disconnected.
No manual_routes.json or build_board.py coordinates are read.
"""
import argparse
import collections
import hashlib
import heapq
import itertools
import json
import math
import os
from pathlib import Path

os.environ.setdefault('KICAD_CONFIG_HOME', '/workspace/scratch/kicad-config')
import pcbnew as p


def xy(q):
    return (int(q.x), int(q.y))


def mm(q):
    return [round(x / 1e6, 6) for x in q]


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polygon(item, layer, clearance=0):
    poly = p.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(poly, layer, clearance, 1000, p.ERROR_OUTSIDE)
    return poly


def overlaps(a, b):
    copy = p.SHAPE_POLY_SET(a)
    copy.BooleanIntersection(b)
    return not copy.IsEmpty()


def point_on_segment(q, a, b, tolerance=2):
    vx, vy = b[0] - a[0], b[1] - a[1]
    length2 = vx * vx + vy * vy
    if not length2:
        return distance(q, a) <= tolerance
    t = ((q[0] - a[0]) * vx + (q[1] - a[1]) * vy) / length2
    if not -1e-10 <= t <= 1 + 1e-10:
        return False
    return distance(q, (a[0] + t * vx, a[1] + t * vy)) <= tolerance


class TrackGraph:
    """Track centreline network, with actual pad copper joining contained nodes."""
    def __init__(self, board, pads):
        self.graph = collections.defaultdict(list)
        self.pad_nodes = {}
        self.arcs = []
        tracks = [t for t in board.GetTracks() if not isinstance(t, p.PCB_VIA)]
        self.layers = list(board.GetEnabledLayers().Seq())
        copper_layers = [l for l in self.layers if p.IsCopperLayer(l)]
        endpoints = collections.defaultdict(set)
        for t in tracks:
            key = (t.GetNetname(), t.GetLayer())
            endpoints[key].update([xy(t.GetStart()), xy(t.GetEnd())])
            if isinstance(t, p.PCB_ARC):
                self.arcs.append(t)
        for v in board.GetTracks():
            if isinstance(v, p.PCB_VIA):
                for l in copper_layers:
                    if v.IsOnLayer(l):
                        endpoints[(v.GetNetname(), l)].add(xy(v.GetPosition()))
        # A track may pass through (or overlap) a pad without ending at its
        # centre.  Add the closest centreline contact as a split point, rather
        # than incorrectly requiring an endpoint at every terminal.
        for pad in pads:
            center = xy(pad.GetPosition())
            for t in tracks:
                layer = t.GetLayer()
                if t.GetNetname() != pad.GetNetname() or not pad.IsOnLayer(layer) or isinstance(t, p.PCB_ARC):
                    continue
                a, b = xy(t.GetStart()), xy(t.GetEnd())
                vx, vy = b[0] - a[0], b[1] - a[1]
                length2 = vx * vx + vy * vy
                if not length2:
                    continue
                along = max(0, min(1, ((center[0] - a[0]) * vx + (center[1] - a[1]) * vy) / length2))
                contact = (round(a[0] + along * vx), round(a[1] + along * vy))
                if polygon(pad, layer, t.GetWidth() // 2).Contains(p.VECTOR2I(*contact)):
                    endpoints[(t.GetNetname(), layer)].add(contact)
        for t in tracks:
            a, b = xy(t.GetStart()), xy(t.GetEnd())
            net, layer = t.GetNetname(), t.GetLayer()
            if isinstance(t, p.PCB_ARC):
                self.edge((net, layer, *a), (net, layer, *b), t.GetLength() / 1e6,
                          t.GetWidth() / 1e6)
                continue
            cuts = [q for q in endpoints[(net, layer)] if point_on_segment(q, a, b)]
            cuts.sort(key=lambda q: distance(a, q))
            for q1, q2 in zip(cuts, cuts[1:]):
                self.edge((net, layer, *q1), (net, layer, *q2), distance(q1, q2) / 1e6,
                          t.GetWidth() / 1e6)
        for v in board.GetTracks():
            if not isinstance(v, p.PCB_VIA):
                continue
            q = xy(v.GetPosition())
            nodes = [(v.GetNetname(), l, *q) for l in copper_layers if v.IsOnLayer(l)]
            for a, b in itertools.combinations(nodes, 2):
                self.edge(a, b, 0, None, transition=True)
        for pad in pads:
            ident = (pad.GetParentFootprint().GetReference(), pad.GetNumber(), xy(pad.GetPosition()))
            net = pad.GetNetname()
            nodes = []
            for layer in copper_layers:
                if not pad.IsOnLayer(layer):
                    continue
                center = (net, layer, *xy(pad.GetPosition()))
                nodes.append(center)
                for q in endpoints[(net, layer)]:
                    direct = polygon(pad, layer).Contains(p.VECTOR2I(*q))
                    touching = any(t.GetNetname() == net and t.GetLayer() == layer
                                   and not isinstance(t, p.PCB_ARC)
                                   and point_on_segment(q, xy(t.GetStart()), xy(t.GetEnd()))
                                   and polygon(pad, layer, t.GetWidth() // 2).Contains(p.VECTOR2I(*q))
                                   for t in tracks)
                    if direct or touching:
                        other = (net, layer, *q)
                        self.edge(center, other, distance(q, xy(pad.GetPosition())) / 1e6,
                                  None, in_pad=True)
            for a, b in itertools.combinations(nodes, 2):
                self.edge(a, b, 0, None, transition=True, in_pad=True)
            self.pad_nodes[ident] = nodes
        # Duplicate exposed-drain pads and their leads form one physical copper
        # conductor even when no track endpoint lies in the tiny pad overlap.
        for a_pad, b_pad in itertools.combinations(pads, 2):
            if a_pad.GetNetname() != b_pad.GetNetname() or not a_pad.GetBoundingBox().Intersects(b_pad.GetBoundingBox()):
                continue
            for layer in copper_layers:
                if a_pad.IsOnLayer(layer) and b_pad.IsOnLayer(layer) and overlaps(polygon(a_pad, layer), polygon(b_pad, layer)):
                    a = (a_pad.GetNetname(), layer, *xy(a_pad.GetPosition()))
                    b = (b_pad.GetNetname(), layer, *xy(b_pad.GetPosition()))
                    self.edge(a, b, distance(a[2:], b[2:]) / 1e6, None, in_pad=True)

    def edge(self, a, b, length, width, transition=False, in_pad=False):
        if a == b:
            self.graph[a]
            return
        info = dict(length=length, width=width, transition=transition, in_pad=in_pad)
        self.graph[a].append((b, info))
        self.graph[b].append((a, info))

    def node(self, pad):
        ident = (pad.GetParentFootprint().GetReference(), pad.GetNumber(), xy(pad.GetPosition()))
        return self.pad_nodes[ident][0]

    def shortest(self, a_pad, b_pad):
        a, b = self.node(a_pad), self.node(b_pad)
        if a[0] != b[0]:
            return dict(measured=False, reason='Different electrical nets')
        costs = {a: (0.0, 0)}
        queue = [(0.0, 0, a)]
        parent = {}
        while queue:
            length, transitions, node = heapq.heappop(queue)
            if costs[node] != (length, transitions):
                continue
            if node == b:
                steps = []
                while node != a:
                    previous, info = parent[node]
                    steps.append((previous, node, info))
                    node = previous
                widths = [info['width'] for _, _, info in steps
                          if info['width'] is not None and not info['in_pad']]
                return dict(measured=True, copper_centerline_length_mm=round(length, 4),
                            straight_pad_center_distance_mm=round(distance(a[2:], b[2:]) / 1e6, 4),
                            layer_transitions=transitions,
                            track_widths_mm=sorted(set(round(x, 4) for x in widths)),
                            path_layers=sorted({p.LayerName(n[1]) for n1, n2, _ in steps
                                                for n in (n1, n2)}))
            for other, info in self.graph[node]:
                candidate = (length + info['length'], transitions + int(info['transition']))
                if other not in costs or candidate < costs[other]:
                    costs[other] = candidate
                    parent[other] = (node, info)
                    heapq.heappush(queue, (*candidate, other))
        return dict(measured=False, reason='No track/pad/via-only path; zone copper is excluded')

    def reaches_without_pad(self, a_pad, b_pad, excluded_pad):
        a, b = self.node(a_pad), self.node(b_pad)
        blocked_shapes = {layer: polygon(excluded_pad, layer)
                          for layer in self.layers if p.IsCopperLayer(layer) and excluded_pad.IsOnLayer(layer)}
        blocked = {node for node in self.graph if node[0] == excluded_pad.GetNetname()
                   and node[1] in blocked_shapes
                   and blocked_shapes[node[1]].Contains(p.VECTOR2I(*node[2:]))}
        todo, seen = [a], {a}
        while todo:
            node = todo.pop()
            if node == b:
                return True
            for other, _ in self.graph[node]:
                if other not in blocked and other not in seen:
                    seen.add(other)
                    todo.append(other)
        return False


def run(board_path, cap_limit, ground_limit, silk_clearance, via_array_min):
    source_sha = hashlib.sha256(board_path.read_bytes()).hexdigest()
    board = p.LoadBoard(str(board_path))
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    pads = [pad for f in fps.values() for pad in f.Pads()]
    vias = [t for t in board.GetTracks() if isinstance(t, p.PCB_VIA)]
    tracks = [t for t in board.GetTracks() if not isinstance(t, p.PCB_VIA)]
    graph = TrackGraph(board, pads)

    def pad(ref, number):
        candidates = [z for z in fps[ref].Pads() if z.GetNumber() == str(number)]
        return min(candidates, key=lambda z: z.GetSize().x * z.GetSize().y)

    cap_map = [('U1', 'C1', 1, 4), ('U1', 'C1', 2, 3),
               ('U1', 'C2', 1, 2), ('U1', 'C2', 2, 1),
               ('U1', 'C3', 1, 1), ('U1', 'C5', 1, 7), ('U1', 'C6', 1, 8),
               ('U2', 'C8', 1, 4), ('U2', 'C8', 2, 3),
               ('U2', 'C9', 1, 2), ('U2', 'C9', 2, 1),
               ('U2', 'C10', 1, 1), ('U2', 'C12', 1, 7), ('U2', 'C13', 1, 8)]
    decoupling = []
    for u, cap, cap_pin, u_pin in cap_map:
        row = dict(driver=u, driver_pin=str(u_pin), capacitor=cap, capacitor_pin=str(cap_pin),
                   **graph.shortest(pad(u, u_pin), pad(cap, cap_pin)))
        row['target_max_track_path_mm'] = cap_limit
        if row['measured']:
            row['short_top_layer_connection'] = (row['copper_centerline_length_mm'] <= cap_limit
                                                and row['layer_transitions'] == 0)
        decoupling.append(row)
    returns = []
    for ref in ['C3', 'C5', 'C6', 'C10', 'C12', 'C13', 'C4', 'C11', 'C15']:
        cap_pad = pad(ref, 2)
        candidates = sorted((distance(xy(cap_pad.GetPosition()), xy(v.GetPosition())) / 1e6,
                             xy(v.GetPosition())) for v in vias if v.GetNetname() == 'GND')
        returns.append(dict(capacitor=ref, pad='2', target_max_via_center_distance_mm=ground_limit,
                            nearest_ground_via_distance_mm=round(candidates[0][0], 4) if candidates else None,
                            nearest_ground_via_mm=mm(candidates[0][1]) if candidates else None,
                            nearby_via_count_within_1_5mm=sum(d <= 1.5 for d, _ in candidates)))

    gate_pairs = [('U1', 24, 'Q1'), ('U1', 22, 'Q2'), ('U1', 17, 'Q3'), ('U1', 19, 'Q4'),
                  ('U2', 24, 'Q5'), ('U2', 22, 'Q6'), ('U2', 17, 'Q7'), ('U2', 19, 'Q8')]
    gates = [dict(driver=u, driver_pin=str(n), mosfet=q, **graph.shortest(pad(u, n), pad(q, 4)))
             for u, n, q in gate_pairs]
    phases = [dict(mosfet=q, connector=c, connector_pin=str(n),
                   **graph.shortest(pad(q, 1), pad(c, n)))
              for q, c, n in [('Q1', 'CN1', 1), ('Q3', 'CN1', 2), ('Q5', 'CN2', 1), ('Q7', 'CN2', 2)]]
    half_bridges = [dict(high_side_mosfet=hi, low_side_mosfet=lo, high_side_source_pin='1', low_side_drain_pin='8',
                         **graph.shortest(pad(hi, 1), pad(lo, 8)))
                    for hi, lo in [('Q1', 'Q2'), ('Q3', 'Q4'), ('Q5', 'Q6'), ('Q7', 'Q8')]]
    phase_copper = {}
    for net in ['L_A', 'L_B', 'R_A', 'R_B']:
        union = p.SHAPE_POLY_SET()
        for item in pads + tracks + vias:
            if item.GetNetname() == net and item.IsOnLayer(p.F_Cu):
                shape = p.SHAPE_POLY_SET()
                item.TransformShapeToPolygon(shape, p.F_Cu, 0, 1000, p.ERROR_INSIDE)
                union.BooleanAdd(shape)
        for z in board.Zones():
            if z.GetNetname() == net and z.IsOnLayer(p.F_Cu) and z.HasFilledPolysForLayer(p.F_Cu):
                union.BooleanAdd(z.GetFilledPolysList(p.F_Cu))
        phase_copper[net] = union
    direct_phase_bridges = []
    for hi, lo in [('Q1', 'Q2'), ('Q3', 'Q4'), ('Q5', 'Q6'), ('Q7', 'Q8')]:
        low_pads = [z for z in fps[lo].Pads() if z.GetNumber() in ['5', '6', '7', '8']
                    and z.GetSize().x * z.GetSize().y < p.FromMM(2) ** 2]
        for number in [1, 2, 3]:
            source = pad(hi, number)
            drain = min(low_pads, key=lambda z: distance(xy(source.GetPosition()), xy(z.GetPosition())))
            witness = p.PCB_TRACK(board)
            witness.SetStart(source.GetPosition())
            witness.SetEnd(drain.GetPosition())
            witness.SetWidth(p.FromMM(.4))
            witness.SetLayer(p.F_Cu)
            capsule = polygon(witness, p.F_Cu)
            capsule.BooleanSubtract(phase_copper[source.GetNetname()])
            direct_phase_bridges.append(dict(high_side_mosfet=hi, source_pin=str(number),
                                            low_side_mosfet=lo, drain_pin=drain.GetNumber(),
                                            length_mm=round(distance(xy(source.GetPosition()), xy(drain.GetPosition())) / 1e6, 4),
                                            straight_copper_width_mm=.4,
                                            straight_capsule_within_existing_filled_copper=capsule.IsEmpty(),
                                            area_outside_existing_copper_mm2=round(capsule.Area() / 1e12, 9),
                                            method='Outward straight-track capsule minus inward same-net pad/track shapes and actual filled phase-zone polygons'))
    bulk = [dict(capacitor='C15', mosfet=q, **graph.shortest(pad('C15', 1), pad(q, 5)))
            for q in ['Q1', 'Q3', 'Q5', 'Q7']]
    first_through = []
    for u, cap in [('U1', 'C3'), ('U2', 'C10')]:
        full = graph.shortest(pad('C15', 1), pad(u, 1))
        reachable = graph.reaches_without_pad(pad('C15', 1), pad(u, 1), pad(cap, 1)) if full['measured'] else None
        first_through.append(dict(driver=u, driver_pin='1', capacitor=cap, capacitor_pin='1',
                                  supply_anchor='C15.1', original_track_network_path_measured=full['measured'],
                                  supply_reaches_vm_pin_with_cap_pad_copper_nodes_removed=reachable,
                                  cap_pad_is_on_every_track_network_supply_path=not reachable if reachable is not None else None,
                                  scope='Topology of explicit tracks/vias/pads; copper zones excluded'))

    pad_shapes = [(z, layer, polygon(z, layer)) for z in pads
                  for layer in [p.F_Cu, p.B_Cu] if z.IsOnLayer(layer)]
    junctions = collections.defaultdict(list)
    for t in tracks:
        if isinstance(t, p.PCB_ARC):
            continue
        for a, b in [(xy(t.GetStart()), xy(t.GetEnd())), (xy(t.GetEnd()), xy(t.GetStart()))]:
            if a != b:
                junctions[(t.GetNetname(), t.GetLayer(), a)].append((b, t))
    corners = []
    excluded = collections.Counter()
    for (net, layer, a), items in junctions.items():
        # Unique outgoing directions, so duplicate overlay tracks do not alter degree.
        directions = {}
        for b, t in items:
            vx, vy = b[0] - a[0], b[1] - a[1]
            g = math.gcd(abs(vx), abs(vy))
            directions[(vx // g, vy // g)] = (b, t)
        if len(directions) != 2:
            excluded['ends_or_true_branch_junctions'] += 1
            continue
        if any(z.GetNetname() == net and l == layer and shape.Contains(p.VECTOR2I(*a))
               for z, l, shape in pad_shapes):
            excluded['within_same_net_pad_copper'] += 1
            continue
        if any(v.GetNetname() == net and v.IsOnLayer(layer)
               and distance(a, xy(v.GetPosition())) <= v.GetWidth(layer) / 2 for v in vias):
            excluded['within_same_net_via_copper'] += 1
            continue
        # An endpoint landing on the interior of a third track is a branch, not a bend.
        if any(t.GetNetname() == net and t.GetLayer() == layer
               and a not in [xy(t.GetStart()), xy(t.GetEnd())]
               and not isinstance(t, p.PCB_ARC)
               and point_on_segment(a, xy(t.GetStart()), xy(t.GetEnd())) for t in tracks):
            excluded['interior_track_branch_junctions'] += 1
            continue
        vectors = list(directions)
        cosine = sum(a * b for a, b in zip(*vectors)) / (math.hypot(*vectors[0]) * math.hypot(*vectors[1]))
        angle = math.degrees(math.acos(max(-1, min(1, cosine))))
        if angle < 179.99:
            corners.append(dict(net=net, layer=p.LayerName(layer), position_mm=mm(a),
                                included_angle_degrees=round(angle, 3),
                                classification='acute' if angle < 89.99 else 'right' if angle < 90.01 else 'obtuse'))

    power_vias = []
    power_nets = {'VM', 'VM_RAW', 'VM_IN', 'L_A', 'L_B', 'R_A', 'R_B', 'GND'}
    for v in vias:
        if v.GetNetname() not in power_nets:
            continue
        center = xy(v.GetPosition())
        # Only flag vias directly meeting a >=0.65mm power track. Signal/sense vias
        # on phase/VM nets are intentionally excluded from the current-transition test.
        meeting = [t for t in tracks if t.GetNetname() == v.GetNetname()
                   and t.GetWidth() >= p.FromMM(.65)
                   and not isinstance(t, p.PCB_ARC)
                   and point_on_segment(center, xy(t.GetStart()), xy(t.GetEnd()), v.GetWidth(p.F_Cu) // 2)]
        if not meeting:
            continue
        if len({t.GetLayer() for t in meeting}) < 2:
            # A narrow signal tee may intentionally use a single via while
            # sharing the node of an otherwise top-only power bus.
            continue
        nearby = [other for other in vias if other.GetNetname() == v.GetNetname()
                  and distance(center, xy(other.GetPosition())) <= 3e6]
        power_vias.append(dict(net=v.GetNetname(), position_mm=mm(center),
                               connected_power_track_layers=sorted({p.LayerName(t.GetLayer()) for t in meeting}),
                               nearby_same_net_via_count_within_3mm=len(nearby),
                               array_target_min=via_array_min, array_target_met=len(nearby) >= via_array_min,
                               via_diameter_mm=v.GetWidth(p.F_Cu) / 1e6, drill_mm=v.GetDrill() / 1e6))

    text_items = [t for t in board.GetDrawings() if isinstance(t, p.PCB_TEXT)]
    for fp in fps.values():
        text_items.extend([fp.Reference(), fp.Value()])
        text_items.extend(t for t in fp.GraphicalItems() if isinstance(t, p.PCB_TEXT))
    silk = []
    for text in text_items:
        layer = text.GetLayer()
        if layer not in [p.F_SilkS, p.B_SilkS] or not text.IsVisible():
            continue
        cu = p.F_Cu if layer == p.F_SilkS else p.B_Cu
        mask = p.F_Mask if layer == p.F_SilkS else p.B_Mask
        text_shape = polygon(text, layer, p.FromMM(silk_clearance))
        for z in pads:
            if z.IsOnLayer(mask) and overlaps(text_shape, polygon(z, cu, z.GetSolderMaskExpansion(cu))):
                silk.append(dict(text=text.GetText(), layer=p.LayerName(layer), text_position_mm=mm(xy(text.GetPosition())),
                                 obstruction='pad', reference=z.GetParentFootprint().GetReference(), pad=z.GetNumber(),
                                 obstruction_position_mm=mm(xy(z.GetPosition()))))
        for v in vias:
            # Deliberately stricter than solder-mask DRC: lettering must avoid even
            # tented through-via copper, matching the requested silk cleanup.
            if v.IsOnLayer(cu) and overlaps(text_shape, polygon(v, cu)):
                silk.append(dict(text=text.GetText(), layer=p.LayerName(layer), text_position_mm=mm(xy(text.GetPosition())),
                                 obstruction='via', net=v.GetNetname(), obstruction_position_mm=mm(xy(v.GetPosition()))))

    failures = []
    if any(r.get('short_top_layer_connection') is False for r in decoupling):
        failures.append('At least one measured driver capacitor path exceeds the distance target or changes layers')
    if any(r['cap_pad_is_on_every_track_network_supply_path'] is False for r in first_through):
        failures.append('A driver VM supply has an explicit copper route bypassing the nearest bypass capacitor pad')
    if any(r['nearest_ground_via_distance_mm'] is None or r['nearest_ground_via_distance_mm'] > ground_limit
           for r in returns if r['capacitor'] not in ['C4', 'C11', 'C15']):
        failures.append('At least one close driver bypass capacitor has a distant ground-return via')
    if any(r['classification'] in ['right', 'acute'] for r in corners):
        failures.append('Right or acute degree-two trace corners remain outside pad/via copper')
    if any(not r['array_target_met'] for r in power_vias):
        failures.append('At least one via meeting a power-width track lacks a local same-net via array')
    if any(not r['straight_capsule_within_existing_filled_copper'] for r in direct_phase_bridges):
        failures.append('A half bridge lacks one of the three direct parallel source-lead-to-drain copper bridges')
    if silk:
        failures.append('Silkscreen lettering overlaps pad/via clearance regions')
    unmeasured = [r for r in decoupling + gates + phases + half_bridges + bulk if not r['measured']]
    unchanged = source_sha == hashlib.sha256(board_path.read_bytes()).hexdigest()
    if not unchanged:
        failures.append('The source PCB changed during the read-only audit; rerun on the final board')
    return dict(reader=p.Version(), board=str(board_path), pcb_sha256=source_sha,
                source_file_unchanged_during_audit=unchanged,
                passed=not failures and not unmeasured, failures=failures,
                scope='Actual board geometry; independent of layout generator and manual route manifest',
                limitations=['Track-path lengths exclude copper zones, so unmeasured paths require separate CAD connectivity review.',
                             'Straight-line intra-pad lengths approximate conduction within a finite pad; no inductance or temperature is calculated.',
                             'Via-array counts measure local geometry; plating thickness/current sharing require fabrication and bench verification.',
                             'Corners inside same-net pads/vias and real branch junctions are excluded from bend classification.',
                             'Silkscreen test compares actual stroke polygons against pad mask openings and every through-via copper disk, including tented vias.'],
                thresholds=dict(max_driver_capacitor_track_path_mm=cap_limit, max_local_ground_via_center_distance_mm=ground_limit,
                                silk_to_pad_or_via_clearance_mm=silk_clearance,
                                minimum_vias_within_3mm_of_power_transition=via_array_min),
                counts=dict(components=len(fps), physical_pads=len(pads), tracks=len(tracks), vias=len(vias), arcs=len(graph.arcs)),
                driver_capacitor_paths=decoupling, vm_feed_through_capacitor_topology=first_through,
                ground_returns=returns, gate_paths=gates,
                high_side_source_to_motor_connector_paths=phases, bulk_to_high_side_drain_paths=bulk,
                half_bridge_high_side_source_to_low_side_drain_paths=half_bridges,
                direct_parallel_phase_bridges_with_actual_zone_copper=direct_phase_bridges,
                trace_bends=corners, bend_exclusions=dict(excluded), power_via_transitions=power_vias,
                silkscreen_lettering_collisions=silk, unmeasured_paths=unmeasured)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', nargs='?', type=Path, default=Path(__file__).resolve().parents[1] / 'DRV8701_DUAL_12V.kicad_pcb')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--cap-max-mm', type=float, default=3.0)
    parser.add_argument('--ground-via-max-mm', type=float, default=1.2)
    parser.add_argument('--silk-clearance-mm', type=float, default=.15)
    parser.add_argument('--via-array-min', type=int, default=3)
    args = parser.parse_args()
    report = run(args.board, args.cap_max_mm, args.ground_via_max_mm, args.silk_clearance_mm, args.via_array_min)
    target = args.output or args.board.parent / 'validation/layout_geometry_audit.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(output=str(target), passed=report['passed'], failures=report['failures'],
                          decoupling_max_measured_mm=max((x.get('copper_centerline_length_mm', 0) for x in report['driver_capacitor_paths']), default=0),
                          right_or_acute_corners=sum(x['classification'] in ['right', 'acute'] for x in report['trace_bends']),
                          silk_collisions=len(report['silkscreen_lettering_collisions']),
                          unmeasured_paths=len(report['unmeasured_paths'])), indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
