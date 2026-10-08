#!/usr/bin/env python3
"""Reproducibly transcribe the supplied DRV8701 schematic without design changes.

KiCad 9 is an editable intermediate for the official EasyEDA Pro importer.
No autorouter is used. Original logical D/G/S and A/K terminals are mapped to
the datasheet package pin numbers. Every connected terminal has a wire stub.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT / "source/source_netlist.json"
if not SOURCE.exists():
    SOURCE = Path("/workspace/scratch/drv8701/source_netlist.json")
DATA = json.loads(SOURCE.read_text())
COMPONENTS = {c["ref"]: c for c in DATA["components"]}
NS = uuid.UUID("a07a0ce6-3220-4c9e-a2ea-cf97c6c5c772")
ROOT = str(uuid.uuid5(NS, "schematic-root"))


def uid(key):
    return str(uuid.uuid5(NS, str(key)))


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def n(v):
    return f"{v:.4f}".rstrip("0").rstrip(".") if v else "0"


def effect(size=1.27, justify="", hide=False):
    return f'(effects (font (size {n(size)} {n(size)})){" (justify " + justify + ")" if justify else ""}{" (hide yes)" if hide else ""})'


def prop(name, value, x=0, y=0, hide=False, size=1.27, justify=""):
    return f'(property {q(name)} {q(value)} (at {n(x)} {n(y)} 0) {effect(size, justify, hide)})'


def pin(number, name, x, y, angle, electrical="passive", length=2.54):
    return (f'(pin {electrical} line (at {n(x)} {n(y)} {angle}) (length {n(length)}) '
            f'(name {q(name)} {effect(1.016)}) (number {q(number)} {effect(1.016)}))')


def poly(points, width=0.254):
    return f'(polyline (pts {" ".join(f"(xy {n(x)} {n(y)})" for x, y in points)}) (stroke (width {n(width)}) (type default)) (fill (type none)))'


def rect(x1, y1, x2, y2):
    return f'(rectangle (start {n(x1)} {n(y1)}) (end {n(x2)} {n(y2)}) (stroke (width 0.254) (type default)) (fill (type background)))'


LIB = {}
PINS = {}


def custom(name, prefix, pins, graphics, description):
    LIB[name] = (f'(symbol "DRV8701_Custom:{name}" (pin_names (offset 0.762)) '
                 f'(exclude_from_sim no) (in_bom yes) (on_board yes) '
                 + prop("Reference", prefix) + prop("Value", name) + prop("Footprint", "", hide=True)
                 + prop("Datasheet", "", hide=True) + prop("Description", description, hide=True)
                 + f'(symbol "{name}_0_1" {graphics}) '
                 + f'(symbol "{name}_1_1" ' + " ".join(pin(*p) for p in pins) + ') (embedded_fonts no))')
    PINS[name] = {str(p[0]): (p[2], p[3], p[4]) for p in pins}


def stock(name):
    source = Path("/usr/share/kicad/symbols/Device.kicad_sym").read_text()
    match = re.search(r'\(symbol "' + re.escape(name) + r'"\s', source)
    start = match.start()
    depth = 0
    quoted = False
    escaped = False
    for end in range(start, len(source)):
        char = source[end]
        if escaped:
            escaped = False
            continue
        if char == "\\" and quoted:
            escaped = True
            continue
        if char == '"':
            quoted = not quoted
        if not quoted:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if not depth:
                    break
    value = source[start:end+1]
    value = value.replace(f'(symbol "{name}"', f'(symbol "DRV8701_Custom:{name}"', 1)
    LIB[name] = value
    PINS[name] = {}
    for match in re.finditer(r'\(pin \w+ \w+\s*\(at ([\d.-]+) ([\d.-]+) ([\d.-]+)\).*?\(number "([^"]+)"', value, re.S):
        PINS[name][match[4]] = (float(match[1]), float(match[2]), int(float(match[3])))


for item in ("R", "C", "C_Polarized", "D_Zener", "LED"):
    stock(item)

driver_pins = []
driver_names = COMPONENTS["U1"]["pin_names"]
driver_types = {
    1: "power_in", 2: "power_out", 3: "output", 4: "output", 5: "power_in",
    6: "input", 7: "power_out", 8: "power_out", 9: "open_collector", 10: "output",
    11: "output", 12: "input", 13: "input", 14: "input", 15: "input",
    16: "power_in", 17: "output", 18: "input", 19: "output", 20: "input",
    21: "input", 22: "output", 23: "input", 24: "output", 25: "power_in",
}
for number in range(1, 26):
    left = number <= 13
    index = number - 1 if left else number - 14
    driver_pins.append((number, driver_names[str(number)], -13.97 if left else 13.97,
                        15.24 - index * 2.54, 0 if left else 180, driver_types[number]))
custom("DRV8701ERGET", "U", driver_pins, rect(-11.43, 17.78, 11.43, -17.78),
       "Texas Instruments DRV8701E PH/EN, RGE24 VQFN + exposed ground pad")

mos_pins = [(1, "S", -8.89, 0, 0), (2, "S", -8.89, -2.54, 0),
            (3, "S", -8.89, -5.08, 0), (4, "G", -8.89, 7.62, 0, "input"),
            (5, "D", 8.89, 7.62, 180), (6, "D", 8.89, 5.08, 180),
            (7, "D", 8.89, 2.54, 180), (8, "D", 8.89, 0, 180)]
mos_graphics = rect(-6.35, 10.16, 6.35, -7.62)
mos_graphics += poly([(-3.81, 7.62), (-3.81, -2.54)])
mos_graphics += poly([(-1.27, 7.62), (-1.27, -2.54)])
mos_graphics += poly([(-6.35, 7.62), (-3.81, 7.62)])
mos_graphics += poly([(-1.27, 5.08), (3.81, 5.08), (3.81, 7.62), (6.35, 7.62)])
mos_graphics += poly([(-1.27, 0), (-3.048, -1.016), (-3.048, 1.016), (-1.27, 0)])
mos_graphics += poly([(-1.27, -2.54), (-3.81, -2.54), (-3.81, -5.08), (-6.35, -5.08)])
custom("TPH1R403NL", "Q", mos_pins, mos_graphics,
       "Toshiba N-MOSFET SOP Advance: 1/2/3 source, 4 gate, 5/6/7/8 drain; thermal pad is drain")

custom("XT30_OUTPUT", "CN", [(1, "1", -5.08, 1.27, 0), (2, "2", -5.08, -1.27, 0)],
       rect(-2.54, 3.81, 2.54, -3.81), "Motor output connector; source schematic numbering retained")
custom("XT30_POWER", "P", [(1, "+12V", -5.08, 1.27, 0, "power_out"),
                         (2, "GND", -5.08, -1.27, 0, "power_out")],
       rect(-2.54, 3.81, 2.54, -3.81), "External 12 V supply entry; connected supply drives VM and GND")
custom("CONTROL_4PIN", "CN", [(i, name, -5.08, 6.35 - i * 2.54, 0, "output")
                              for i, name in [(1, "R_EN"), (2, "R_PH"), (3, "L_PH"), (4, "L_EN")]],
       rect(-2.54, 6.35, 10.16, -6.35), "External controller signal entry; original connector has no ground terminal")
custom("SS12D10G4", "U", [(1, "OFF", 7.62, 2.54, 180),
                          (2, "COM", -7.62, 0, 0), (3, "ON", 7.62, -2.54, 180)],
       poly([(-5.08, 0), (-2.54, 0), (3.81, 2.54), (5.08, 2.54)])
       + poly([(3.81, -2.54), (5.08, -2.54)]),
       "SPDT slide switch: pin 2 common to NSLEEP, pin 1 NC, pin 3 3V3")

SCHEMATIC = []
TERMINALS = {}
EXPECTED = {}
MANIFEST = []


def wire(x1, y1, x2, y2, key):
    SCHEMATIC.append(f'(wire (pts (xy {n(x1)} {n(y1)}) (xy {n(x2)} {n(y2)})) '
                     f'(stroke (width 0) (type default)) (uuid {q(uid("wire-" + key))}))')


def label(net, x, y, key, justify="left"):
    SCHEMATIC.append(f'(label {q(net)} (at {n(x)} {n(y)} 0) {effect(1.016, justify)} '
                     f'(uuid {q(uid("label-" + key))}))')


def text(value, x, y, size=1.27):
    SCHEMATIC.append(f'(text {q(value)} (at {n(x)} {n(y)} 0) {effect(size, "left")} '
                     f'(uuid {q(uid("text-" + value + str(x) + str(y)))}))')


def add(ref, lib, footprint, x, y, pin_nets, angle=0, label_pins=True):
    source = COMPONENTS[ref]
    if lib == "DRV8701ERGET":
        refpos = (x, y-22.86)
        valpos = (x, y-20.32)
    elif lib == "TPH1R403NL":
        refpos = (x, y-15.24)
        valpos = (x, y+11.43)
    elif lib in ("XT30_OUTPUT", "XT30_POWER", "CONTROL_4PIN", "SS12D10G4"):
        refpos = (x, y-12.7)
        valpos = (x, y-10.16)
    else:
        refpos = (x+3.81, y-1.27)
        valpos = (x+3.81, y+1.27)
    body = (f'(symbol (lib_id "DRV8701_Custom:{lib}") (at {n(x)} {n(y)} {angle}) (unit 1) '
            f'(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid {q(uid(ref))}) '
            + prop("Reference", ref, *refpos) + prop("Value", source["value"], *valpos, size=1.016)
            + prop("Footprint", "DRV8701_Custom:" + footprint, x, y, hide=True)
            + prop("Datasheet", "https://www.ti.com/lit/ds/symlink/drv8701.pdf" if ref in ("U1", "U2")
                   else "https://toshiba.semicon-storage.com/info/TPH1R403NL_datasheet_en_20191030.pdf?did=14296&prodName=TPH1R403NL" if ref.startswith("Q") else "", x, y, hide=True)
            + prop("Source", "Original PDF; connections and values retained", x, y, hide=True))
    TERMINALS[ref] = {}
    for pnum, (px, py, pa) in PINS[lib].items():
        body += f'(pin {q(pnum)} (uuid {q(uid(ref + "." + pnum))}))'
        # Schematic Y is downwards; all symbols in this project are unrotated.
        assert angle == 0
        px, py = x + px, y - py
        TERMINALS[ref][pnum] = (px, py, pa)
        net = pin_nets[pnum]
        EXPECTED[f"{ref}.{pnum}"] = net
        if net is None:
            SCHEMATIC.append(f'(no_connect (at {n(px)} {n(py)}) (uuid {q(uid("nc-" + ref + pnum))}))')
        elif label_pins:
            dx, dy = {0: (-5.08, 0), 180: (5.08, 0), 270: (0, -5.08), 90: (0, 5.08)}[pa]
            ex, ey = px + dx, py + dy
            wire(px, py, ex, ey, ref + pnum)
            label(net, ex, ey, ref + pnum, "right" if pa == 0 else "left")
    body += f'(instances (project "DRV8701_DUAL_12V" (path "/{ROOT}" (reference {q(ref)}) (unit 1)))))'
    SCHEMATIC.append(body)
    MANIFEST.append({"Reference": ref, "Value": source["value"], "Footprint": "DRV8701_Custom:"+footprint,
                     "Quantity": 1, "PCB side": "Front", "Source fidelity": "Original value and connectivity"})


for channel, delta, driver, qbase, caprefs, motor, snub, resistor in [
    ("L", 0, "U1", 0, ["C1", "C2", "C3", "C4", "C5", "C6"], "CN1", "C16", "R8"),
    ("R", 205.74, "U2", 4, ["C8", "C9", "C10", "C11", "C12", "C13"], "CN2", "C17", "R9"),
]:
    text(f"{channel} MOTOR CHANNEL — ORIGINAL PH/EN DRIVER", 17.78+delta, 25.4, 1.778)
    add(driver, "DRV8701ERGET", "DRV8701_RGE24", 60.96+delta, 76.2,
        COMPONENTS[driver]["pins"])
    for i, mx, my in [(1, 132.08, 55.88), (2, 132.08, 101.6),
                      (3, 175.26, 55.88), (4, 175.26, 101.6)]:
        ref = f"Q{qbase+i}"
        logical = COMPONENTS[ref]["pins"]
        pins = {str(p): logical["S" if p in (1, 2, 3) else "G" if p == 4 else "D"]
                for p in range(1, 9)}
        add(ref, "TPH1R403NL", "TPH1R403NL_SOPAdvance", mx+delta, my, pins)
    text("SOP Advance: S=1,2,3; G=4; D=5,6,7,8 + thermal pad", 105.41+delta, 124.46, 1.016)
    text("Original charge-pump and supply capacitors: all 100nF", 17.78+delta, 132.08, 1.27)
    for i, ref in enumerate(caprefs):
        add(ref, "C", "C_0603_1608Metric", 27.94+delta+i*27.94, 149.86, COMPONENTS[ref]["pins"])
    text("Series RC across motor outputs: 100nF + 100 ohm", 17.78+delta, 171.45, 1.27)
    add(snub, "C", "C_0603_1608Metric", 60.96+delta, 186.69, COMPONENTS[snub]["pins"])
    add(resistor, "R", "R_1210_3225Metric", 60.96+delta, 207.01, COMPONENTS[resistor]["pins"])
    add(motor, "XT30_OUTPUT", "AMASS_XT30UPB_M_SourceNumbering", 149.86+delta, 194.31,
        COMPONENTS[motor]["pins"])
    text("12V motor: 0.4A rated / 1.8A stall max", 116.84+delta, 209.55, 1.016)

text("COMMON POWER, ENABLE AND ORIGINAL FOUR-SIGNAL INTERFACE", 17.78, 225.425, 1.778)
add("P2", "XT30_POWER", "AMASS_XT30UPB_M_SourceNumbering", 27.94, 246.38, COMPONENTS["P2"]["pins"])
add("C15", "C_Polarized", "CP_Radial_D10.0mm_P5.00mm", 66.04, 246.38, {"1": "VM", "2": "GND"})
add("R1", "R", "R_0603_1608Metric", 104.14, 246.38, COMPONENTS["R1"]["pins"])
add("D1", "D_Zener", "D_SOD123", 139.7, 246.38, {"1": "3V3", "2": "GND"})
add("U5", "SS12D10G4", "SS12D10G4", 184.15, 246.38, COMPONENTS["U5"]["pins"])
add("R5", "R", "R_0603_1608Metric", 228.6, 241.3, COMPONENTS["R5"]["pins"])
add("LED1", "LED", "LED_0603_1608Metric", 254, 246.38, {"1": "GND", "2": "ENABLE_LED_A"})
add("R7", "R", "R_0603_1608Metric", 292.1, 241.3, COMPONENTS["R7"]["pins"])
add("LED2", "LED", "LED_0603_1608Metric", 317.5, 246.38, {"1": "GND", "2": "POWER_LED_A"})
add("CN3", "CONTROL_4PIN", "XH2.54_1x04_Vertical", 379.73, 246.38, COMPONENTS["CN3"]["pins"])

text("SOURCE-FAITHFUL DESIGN — values and connections intentionally retained; no hardware validation.", 17.78, 266.7, 1.016)
text("CN3 has no ground pin: controller must share ground via power return. 3V3 is a 10k-fed zener node.", 17.78, 269.24, 1.016)
text("VREF/IDRIVE tied to AVDD; SP/SN grounded; nFAULT/SNSOUT/SO NC. No external current sensing or limit.", 17.78, 271.78, 1.016)
text("Original 100nF bypass values retained: compare TI recommendations before manufacture.", 17.78, 274.32, 1.016)

header = (f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") '
          f'(uuid {q(ROOT)}) (paper "A3") '
          '(title_block (title "DRV8701 DUAL MOTOR / 12 V") '
          '(date "2026-10-08") (rev "1.0") (company "Source: 8701 driver board, no current sensing 2.0") '
          '(comment 1 "Manual PCB routing only; no hardware validation") '
          '(comment 2 "Original source values and net connections preserved")) '
          '(lib_symbols ' + "\n".join(LIB.values()) + ')\n')
OUT.mkdir(parents=True, exist_ok=True)
(OUT/"source").mkdir(exist_ok=True)
(OUT/"validation").mkdir(exist_ok=True)
(OUT/"source/source_netlist.json").write_text(json.dumps(DATA, ensure_ascii=False, indent=2)+"\n")
SCH = OUT/"DRV8701_DUAL_12V.kicad_sch"
SCH.write_text(header + "\n".join(SCHEMATIC) + '\n(embedded_fonts no))\n')
# External symbol library keeps the project editable without system-library dependencies.
external = []
for name, block in LIB.items():
    external.append(block.replace(f'(symbol "DRV8701_Custom:{name}"', f'(symbol "{name}"', 1))
(OUT/"DRV8701_Custom.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") (generator_version "9.0")\n'
                                         + "\n".join(external) + ')\n')
(OUT/"sym-lib-table").write_text('(sym_lib_table (version 7)\n (lib (name "DRV8701_Custom")(type "KiCad")(uri "${KIPRJMOD}/DRV8701_Custom.kicad_sym")(options "")(descr "Self-contained source-faithful custom symbols"))\n)\n')
project = OUT/"DRV8701_DUAL_12V.kicad_pro"
if not project.exists():
    # A named project makes KiCad load the portable project-local library tables.
    # Board generation may subsequently add ordinary design rules/settings.
    project.write_text(json.dumps({"meta": {"filename": project.name, "version": 1}}, indent=2)+"\n")
with (OUT/"components.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(MANIFEST[0]))
    writer.writeheader()
    writer.writerows(MANIFEST)
(OUT/"validation/expected_physical_pin_nets.json").write_text(json.dumps(EXPECTED, indent=2)+"\n")
print(f"Generated {SCH}: {len(MANIFEST)} components, {len(set(EXPECTED.values())-{None})} named nets")

if os.environ.get("DRV8701_VALIDATE", "1") == "1":
    env = os.environ.copy()
    for var, dirname in [("XDG_CACHE_HOME", "cache"), ("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config")]:
        path = Path("/tmp/drv8701-kicad")/dirname
        path.mkdir(parents=True, exist_ok=True)
        env[var] = str(path)
    netfile = OUT/"validation/schematic_netlist.xml"
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "--output", str(netfile), str(SCH)],
                   check=True, env=env)
    exported = ET.parse(netfile).getroot()
    actual = {}
    for net in exported.findall("./nets/net"):
        # KiCad prefixes root-sheet local net labels with '/'; remove only the
        # root sheet delimiter, preserving the actual source net name.
        name = net.attrib["name"].removeprefix("/")
        for node in net.findall("node"):
            actual[node.attrib["ref"]+"."+node.attrib["pin"]] = name
    errors = []
    for pinname, expected in EXPECTED.items():
        actual_net = actual.get(pinname)
        if expected is None:
            if actual_net and not actual_net.startswith("unconnected-"):
                errors.append(f"{pinname}: NC unexpectedly connected to {actual_net}")
        elif actual_net != expected:
            errors.append(f"{pinname}: expected {expected}, got {actual_net}")
    actual_refs = {c.attrib["ref"] for c in exported.findall("./components/comp")}
    if actual_refs != set(COMPONENTS):
        errors.append(f"Component mismatch: actual {sorted(actual_refs)}, expected {sorted(COMPONENTS)}")
    result = {"passed": not errors, "components": len(actual_refs), "named_nets": len(set(v for v in EXPECTED.values() if v is not None)),
              "physical_pin_assignments": len(EXPECTED), "source_faithful": True, "errors": errors}
    (OUT/"validation/schematic_net_equivalence.json").write_text(json.dumps(result, indent=2)+"\n")
    if errors:
        raise SystemExit("Net equivalence failed: " + "; ".join(errors))
    subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "--output",
                    str(OUT/"validation/schematic_erc.json"), str(SCH)], check=True, env=env)
    subprocess.run(["kicad-cli", "sch", "export", "pdf", "--output", str(OUT/"DRV8701_DUAL_12V_schematic.pdf"), str(SCH)],
                   check=True, env=env)
    print("Source/netlist equivalence passed; KiCad ERC report and schematic PDF exported.")
