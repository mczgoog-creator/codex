#!/usr/bin/env python3
"""Add explicit SOP Advance drain-pad connections using actual KiCad 5.1.

Run with KiCad 5.1's pcbnew Python binding. --output protects the input.
No routing search is performed: each known drain lead connects along the
footprint's local Y axis to the exposed drain pad, preserving its local X.
Cardinal footprint rotations are supported; already-present bridges remain.
The separate geometry audit proves these segments add no physical copper.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pcbnew


def track_key(track):
    points = sorted([(track.GetStart().x, track.GetStart().y),
                     (track.GetEnd().x, track.GetEnd().y)])
    return tuple(points[0] + points[1]) + (track.GetWidth(), track.GetLayer(), track.GetNetCode())


def bridge_end(module, pad, exposed):
    angle = module.GetOrientationDegrees() % 360
    if angle not in (0, 90, 180, 270):
        raise ValueError("Only cardinal SOP Advance rotations are supported")
    position, center = pad.GetPosition(), exposed.GetPosition()
    return pcbnew.wxPoint(position.x, center.y) if angle in (0, 180) else pcbnew.wxPoint(center.x, position.y)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("--output must differ from the input")
    version = pcbnew.GetBuildVersion()
    if not version.startswith("5.1."):
        parser.error("This script requires an actual KiCad 5.1 pcbnew binding")
    board = pcbnew.LoadBoard(str(args.input))
    original_tracks = [t for t in board.GetTracks() if not isinstance(t, pcbnew.VIA)]
    original_vias = [t for t in board.GetTracks() if isinstance(t, pcbnew.VIA)]
    existing = {track_key(t) for t in original_tracks}
    mosfets = {m.GetReference(): m for m in board.GetModules()
               if str(m.GetFPID().GetLibItemName()) == "TPH1R403NL_SOPAdvance"}
    assert set(mosfets) == {"Q" + str(i) for i in range(1, 9)}, "Expected the eight original motor MOSFETs"
    bridges = []
    already_present = []
    for reference in sorted(mosfets):
        drain_pads = [p for p in mosfets[reference].Pads()
                      if p.GetPadName() in ("5", "6", "7", "8")]
        exposed = max(drain_pads,
                      key=lambda p: p.GetSize().x * p.GetSize().y)
        leads = [p for p in drain_pads if p is not exposed]
        assert len(leads) == 4
        for pad in leads:
            assert pad.GetNetCode() == exposed.GetNetCode()
            start = pad.GetPosition()
            end = bridge_end(mosfets[reference], pad, exposed)
            track = pcbnew.TRACK(board)
            track.SetStart(start)
            track.SetEnd(end)
            track.SetWidth(250000)
            track.SetLayer(pcbnew.F_Cu)
            track.SetNetCode(pad.GetNetCode())
            row = {
                "reference": reference, "lead_pad": pad.GetPadName(),
                "net": pad.GetNetname(), "layer": "F.Cu", "width_mm": 0.25,
                "start_mm": [start.x / 1e6, start.y / 1e6],
                "end_mm": [end.x / 1e6, end.y / 1e6],
            }
            if track_key(track) in existing:
                already_present.append(row)
            else:
                board.Add(track)
                existing.add(track_key(track))
                bridges.append(row)
    assert len(bridges) + len(already_present) == sum(
        len([pad for pad in module.Pads() if pad.GetPadName() in ("5", "6", "7", "8")]) - 1
        for module in mosfets.values())
    assert len(list(board.GetTracks())) == len(original_tracks) + len(original_vias) + len(bridges)
    assert pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert pcbnew.SaveBoard(str(args.output), board)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "runtime": version,
        "method": "Explicit drain lead to exposed-pad connections along the local footprint Y axis",
        "autorouting_used": False, "pathfinding_used": False,
        "original_segments": len(original_tracks), "additional_segments": len(bridges),
        "total_segments": len(original_tracks) + len(bridges), "vias": len(original_vias),
        "bridges": bridges, "already_present_bridges": already_present,
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "verification": "Actual KiCad 5.1 GUI DRC and independent copper containment required",
    }, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
