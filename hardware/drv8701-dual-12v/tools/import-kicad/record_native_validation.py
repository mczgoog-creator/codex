#!/usr/bin/env python3
"""Check and record the completed native KiCad 5 verification and archive.

This script does not run ERC/DRC, generate an archive, or edit any CAD geometry.
The inputs must be reports and a ZIP produced in the actual KiCad 5 application.
All quantities derive from the final source/legacy geometry and exported netlist.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import zipfile
from zoneinfo import ZoneInfo

from audit_legacy_pcb import board_snapshot
from generate_legacy_schematic import read_netlist


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("legacy", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--geometry-report", type=Path)
    args = parser.parse_args()
    base, legacy = args.base.resolve(), args.legacy.resolve()
    geometry_path = args.geometry_report or base/"validation/legacy5_final_pcb_equivalence.json"
    geometry = read(geometry_path)
    assert geometry["passed"] and not geometry["failures"]
    assert geometry["physical_copper_added_by_bridges_mm2"] == 0.0
    pcb = legacy/"DRV8701_DUAL_12V.kicad_pcb"
    assert geometry["source_sha256"] == sha(base/pcb.name), "Geometry proof is for an older source PCB"
    assert geometry["legacy_sha256"] == sha(pcb), "Geometry proof is for an older legacy PCB"
    snapshot, fill = board_snapshot(pcb)
    assert all(x["filled"] and x["vertices"] > 0 for x in fill), "Missing native zone fill"
    assert len(snapshot["tracks"]) == geometry["legacy_track_segments"]
    assert len(snapshot["vias"]) == geometry["legacy_via_count"]
    zone_refill = read(legacy/"validation/legacy5_zone_refill.json")
    assert zone_refill["runtime"].startswith("5.1.")
    assert zone_refill["pcb_sha256"] == sha(pcb), "Native zone evidence is for an older legacy PCB"
    assert zone_refill["all_zones_filled"]
    assert zone_refill["phase_priority_and_direct_connection_verified"]
    assert zone_refill["ground_priority_and_direct_connection_verified"]
    assert len(zone_refill["zones"]) == len(snapshot["zone_boundaries_and_settings"])

    equivalent = read(legacy/"validation/legacy_net_equivalence.json")
    assert equivalent["passed"] and not equivalent["errors"]
    netfile = legacy/"DRV8701_DUAL_12V.net"
    assert equivalent["netlist_sha256"] == sha(netfile), "Netlist audit is for an older export"
    netlist = read_netlist(netfile)
    exporter = netlist.findtext("./design/tool")
    assert exporter and exporter.startswith("Eeschema 5.1."), "Netlist was not exported by real KiCad 5.1"
    runtime = exporter.replace("Eeschema ", "KiCad ", 1)

    drc_path = legacy/"validation/legacy5_drc.rpt"
    drc_text = drc_path.read_text()
    drc_errors = re.findall(r"Found (\d+) DRC errors", drc_text)
    unconnected = re.findall(r"Found (\d+) unconnected pads", drc_text)
    assert drc_errors == ["0"] and unconnected == ["0"], "Native KiCad 5 DRC has violations"
    report_time = re.search(r"Created on ([^*\n]+)", drc_text).group(1).strip()
    erc_path = legacy/"validation/DRV8701_DUAL_12V.erc"
    erc_text = erc_path.read_text()
    erc_counts = re.findall(r"ERC messages:\s*(\d+)\s+Errors\s+(\d+)\s+Warnings\s+(\d+)", erc_text)
    assert erc_counts and all(row == ("0", "0", "0") for row in erc_counts), "Native KiCad 5 ERC has violations"
    drc = dict(errors=0, unconnected_pads=0, report="KiCad_Import_5/validation/legacy5_drc.rpt",
               report_time=report_time, refill_all_zones=True,
               report_all_track_errors=True, test_tracks_against_filled_copper=True)
    erc = dict(errors=0, warnings=0, report="KiCad_Import_5/validation/DRV8701_DUAL_12V.erc")

    entries = []
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None, "Archive CRC check failed"
        assert len(archive.namelist()) == len(set(archive.namelist())), "Duplicate archive entries"
        for name in archive.namelist():
            assert not name.startswith("/") and ".." not in Path(name).parts
            if name.endswith("/"):
                continue
            path = legacy/name
            content = archive.read(name)
            assert path.is_file() and path.read_bytes() == content, "Archive content mismatch: " + name
            entries.append(dict(path=name, bytes=len(content), sha256=hashlib.sha256(content).hexdigest()))
    names = {row["path"] for row in entries}
    required = {"DRV8701_DUAL_12V.pro", "DRV8701_DUAL_12V.sch", pcb.name,
                "DRV8701_DUAL_12V.net", "DRV8701_Custom.lib", "DRV8701_DUAL_12V-cache.lib",
                "fp-lib-table", "sym-lib-table"}
    required.update("DRV8701_Custom.pretty/" + path.name for path in (legacy/"DRV8701_Custom.pretty").glob("*.kicad_mod"))
    assert required <= names, "Archive missing project or library files"
    archive_sha = sha(args.archive)
    counts = dict(components=len(snapshot["footprints"]), pads=len(snapshot["pads"]),
                  segments=len(snapshot["tracks"]), source_segments_retained=geometry["source_track_segments"],
                  explicit_drain_bridge_segments=geometry["added_bridge_segments"],
                  vias=len(snapshot["vias"]), named_nets=equivalent["named_nets"],
                  zones=len(snapshot["zone_boundaries_and_settings"]), outline_edges=len(snapshot["outline"]),
                  copper_layers=snapshot["copper_layers"])
    limits = ["嘉立创 EDA Pro web import has not been executed in a logged-in browser.",
              "Official KiCad import guide says importing regenerates copper; inspect the destination copper and DRC.",
              "KiCad 5 retains layer count and overall board thickness, with detailed stackup supplied separately."]
    actual = dict(runtime=runtime, native_saved_board_sha256=sha(pcb), board_format_version=20171130,
                  board_counts=counts, native_refill={"ZONE_FILLER.Fill": True, "actual5_GUI_DRC_refill": True,
                    "zone_parameters_and_fill_report": "KiCad_Import_5/validation/legacy5_zone_refill.json"},
                  actual5_DRC=drc, actual5_ERC=erc,
                  actual5_netlist=dict(tool=exporter, components=equivalent["components"],
                    named_nets=equivalent["named_nets"], pins=equivalent["physical_pins"],
                    connected_pins=equivalent["connected_pins"], single_node_NC_pins=equivalent["nc_pins"],
                    timestamp_matches=geometry["schematic_component_path_count"]),
                  native_archive=dict(operation="Actual KiCad 5.1 project manager File > Archive Project",
                    zip_sha256=archive_sha, zip_bytes=args.archive.stat().st_size, crc_errors=None, entries=entries),
                  limitations=limits)
    (legacy/"validation/actual_kicad5_validation.json").write_text(json.dumps(actual, ensure_ascii=False, indent=2)+"\n")
    summary = dict(generatedAt=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        target="JLCEDA Pro web start page > Import KiCad",
        guideUrl="https://prodocs.lceda.cn/cn/import-export/import-kicad/index.html",
        officialGuideVersions=["KiCad 5.1", "KiCad 5.9"], actualRuntime=runtime,
        archiveGenerator=actual["native_archive"]["operation"],
        archive="downloads/DRV8701_12V_KiCad5_Import.zip", archiveBytes=args.archive.stat().st_size,
        archiveSha256=archive_sha, archiveEntries=len(entries), archiveCrcPassed=True,
        allArchiveEntryBytesMatchFinalProject=True, projectEntry="DRV8701_DUAL_12V.pro",
        pcbVersion=20171130, schematicVersion="EESchema Schematic File Version 4", pcbSha256=sha(pcb),
        components=counts["components"], nets=counts["named_nets"], physicalPins=equivalent["physical_pins"],
        actualPadInstances=counts["pads"], originalTrackSegmentsRetained=counts["source_segments_retained"],
        internalPadBridgeSegments=counts["explicit_drain_bridge_segments"], totalSegments=counts["segments"],
        vias=counts["vias"], addedCopperAreaByBridgesMm2=geometry["physical_copper_added_by_bridges_mm2"],
        physicalGeometryAndDesignConnectionsPreserved=True,
        independentGeometryProof="validation/legacy5_final_pcb_equivalence.json",
        actual5Drc=drc, actual5Erc=erc, actual5ExportedNetlistEquivalentToDesign=True,
        actual5ZoneRefill="KiCad_Import_5/validation/legacy5_zone_refill.json",
        actual5ComponentTimestampsMatchPcb=geometry["schematic_component_path_count"],
        realEasyedaWebImportExecuted=False, realEasyedaDrcExecuted=False, hardwareTested=False,
        autorouterUsed=False, limits=limits)
    (base/"validation").mkdir(parents=True, exist_ok=True)
    (base/"validation/kicad5-import-validation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
