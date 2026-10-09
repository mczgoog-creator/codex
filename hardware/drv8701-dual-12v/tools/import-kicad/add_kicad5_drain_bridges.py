#!/usr/bin/env python3
"""Add the approved, fixed 32 MOS drain connections using actual KiCad 5.1.

Run with KiCad 5.1's pcbnew Python binding. The input must be the original
258-segment legacy conversion. --output is required to protect the source.
No routing search is performed: each known drain lead connects vertically
to the exposed drain pad's center Y at that lead's existing X coordinate.
The separate geometry audit proves these segments add no physical copper.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pcbnew


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
    assert len(list(board.GetTracks())) == 258 + 76, "Expected unbridged board"
    mosfets = {m.GetReference(): m for m in board.GetModules()
               if m.GetReference() in {"Q" + str(i) for i in range(1, 9)}}
    assert len(mosfets) == 8
    bridges = []
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
            end = pcbnew.wxPoint(start.x, exposed.GetPosition().y)
            track = pcbnew.TRACK(board)
            track.SetStart(start)
            track.SetEnd(end)
            track.SetWidth(250000)
            track.SetLayer(pcbnew.F_Cu)
            track.SetNetCode(pad.GetNetCode())
            board.Add(track)
            bridges.append({
                "reference": reference, "lead_pad": pad.GetPadName(),
                "net": pad.GetNetname(), "layer": "F.Cu", "width_mm": 0.25,
                "start_mm": [start.x / 1e6, start.y / 1e6],
                "end_mm": [end.x / 1e6, end.y / 1e6],
            })
    assert len(bridges) == 32
    assert len(list(board.GetTracks())) == 290 + 76
    assert pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert pcbnew.SaveBoard(str(args.output), board)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "runtime": version,
        "method": "Fixed explicit drain lead to exposed-pad vertical connections",
        "autorouting_used": False, "additional_segments": 32,
        "total_segments": 290, "vias": 76, "bridges": bridges,
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "verification": "Actual KiCad 5.1 GUI DRC and independent copper containment required",
    }, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
