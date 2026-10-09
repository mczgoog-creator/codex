#!/usr/bin/env python3
"""Generate the authorized Rev B power-control addition and retained driver circuit.

KiCad 9 is an editable intermediate for the official EasyEDA Pro importer.
No autorouter is used. Original logical D/G/S and A/K terminals are mapped to
the datasheet package pin numbers. Every connected terminal has a wire stub.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA256 = "5fe34e962b121847c78609d269503a5184870e272b5e86f9133f7b740469b86e"
for original_file in (OUT/"source_netlist.json", OUT/"source/source_netlist.json"):
    if hashlib.sha256(original_file.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        raise SystemExit(f"Original source netlist changed: {original_file}")
ORIGINAL = json.loads((OUT/"source_netlist.json").read_text())
DATA = json.loads((OUT/"design_netlist.json").read_text())
COMPONENTS = {c["ref"]: c for c in DATA["components"]}
NS = uuid.UUID("a07a0ce6-3220-4c9e-a2ea-cf97c6c5c772")
ROOT = str(uuid.uuid5(NS, "schematic-root"))


def physical_pins(component):
    pins = component["pins"]
    if component["kind"] == "n_channel_mosfet":
        return {str(p): pins["S" if p <= 3 else "G" if p == 4 else "D"] for p in range(1, 9)}
    if component["kind"] == "electrolytic_capacitor":
        return {"1": pins["+"], "2": pins["-"]}
    if component["kind"] in ("zener_diode", "led"):
        return {"1": pins["K"], "2": pins["A"]}
    return pins


APPROVED_ADDITIONS = {
    "U6": {"value": "TPS25910RSAR", "kind": "power_load_switch", "pins": {
        "1": "VM_RAW", "2": "VM_RAW", "3": "VM_RAW", "4": "PWR_GATE", "5": "GND", "6": "GND",
        "7": "PWR_ILIM", "8": "GND", "9": "GND", "10": "VM", "11": "VM", "12": "VM",
        "13": "GND", "14": "GND", "15": None, "16": "PWR_EN", "17": "GND"}},
    "SW1": {"value": "SS12D10G4", "kind": "spdt_slide_switch", "pins": {"1": None, "2": "PWR_EN", "3": "GND"}},
    "R10": {"value": "100kΩ", "kind": "resistor", "pins": {"1": "VM_RAW", "2": "PWR_EN"}},
    "R11": {"value": "33kΩ", "kind": "resistor", "pins": {"1": "PWR_EN", "2": "GND"}},
    "R12": {"value": "40.2kΩ", "kind": "resistor", "pins": {"1": "PWR_ILIM", "2": "GND"}},
    "C18": {"value": "4.7uF", "kind": "capacitor", "pins": {"1": "VM_RAW", "2": "GND"}},
    "C19": {"value": "10nF", "kind": "capacitor", "pins": {"1": "PWR_GATE", "2": "GND"}},
}


def original_contract():
    errors = []
    changes = []
    original_physical_count = 0
    for original in ORIGINAL["components"]:
        ref = original["ref"]
        candidate = COMPONENTS.get(ref)
        if candidate is None:
            errors.append(f"Original component removed: {ref}")
            continue
        for field in ("value", "kind", "pin_names", "nc_pins"):
            if candidate.get(field) != original.get(field):
                errors.append(f"Original {ref} {field} changed")
        before, after = physical_pins(original), physical_pins(candidate)
        original_physical_count += len(before)
        if set(before) != set(after):
            errors.append(f"Original {ref} physical pin set changed")
        for pin, net in before.items():
            if after.get(pin) != net:
                changes.append({"pin": ref+"."+pin, "from": net, "to": after.get(pin)})
    permitted = [{"pin": "P2.1", "from": "VM", "to": "VM_RAW"}]
    if changes != permitted:
        errors.append(f"Observed original pin deltas differ from authorization: {changes}")
    original_refs = {c["ref"] for c in ORIGINAL["components"]}
    if set(COMPONENTS) - original_refs != set(APPROVED_ADDITIONS):
        errors.append("New component set differs from approved seven-part power topology")
    for ref, approved in APPROVED_ADDITIONS.items():
        actual = COMPONENTS.get(ref, {})
        for field in ("value", "kind", "pins"):
            if actual.get(field) != approved[field]:
                errors.append(f"Approved addition {ref} {field} differs")
    reconstructed = {}
    for component in DATA["components"]:
        for pin, net in component["pins"].items():
            if net is not None:
                reconstructed.setdefault(net, set()).add(component["ref"]+"."+pin)
    if reconstructed != {net: set(pins) for net, pins in DATA["nets"].items()}:
        errors.append("Design net membership table disagrees with component pin assignments")
    result = {"passed": not errors, "revision": "B", "original_source_sha256": ORIGINAL_SHA256,
              "original_component_values_preserved": len(ORIGINAL["components"]),
              "original_physical_pins_compared": original_physical_count,
              "unchanged_original_physical_pins": original_physical_count-len(changes),
              "authorized_existing_pin_deltas": changes, "added_references": sorted(APPROVED_ADDITIONS),
              "source_faithful": False, "remaining_original_circuit_preserved": not errors, "errors": errors}
    (OUT/"validation").mkdir(exist_ok=True)
    (OUT/"validation/rev_b_original_source_contract.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    if errors:
        raise SystemExit("Original-source contract failed: "+"; ".join(errors))
    return result


SOURCE_CONTRACT = original_contract()


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

efuse_pins = []
efuse_names = COMPONENTS["U6"]["pin_names"]
for number in range(1, 18):
    left = number <= 9
    index = number - 1 if left else number - 10
    # OUT10/11/12 are one internally connected output, not three voltage sources.
    # Pin10 represents that power output for ERC; 11/12 remain real passive
    # terminals of the same common output node. All three connect to VM.
    electrical = "power_in" if number in (1, 2, 3, 5, 6, 8, 9, 13, 14, 17) else \
                 "power_out" if number == 10 else "passive" if number in (11, 12) else "output" if number == 4 else \
                 "passive" if number == 7 else "open_collector" if number == 15 else "input"
    efuse_pins.append((number, efuse_names[str(number)], -13.97 if left else 13.97,
                       10.16-index*2.54, 0 if left else 180, electrical))
custom("TPS25910RSAR", "U", efuse_pins, rect(-11.43, 12.7, 11.43, -12.7),
       "TI TPS25910 high-side eFuse: active-low EN16; IN1/2/3; internally common OUT10/11/12 (10 represents power output); GND EP17")

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
custom("XT30_POWER", "P", [(1, "+12V_RAW", -5.08, 1.27, 0, "power_out"),
                         (2, "GND", -5.08, -1.27, 0, "power_out")],
       rect(-2.54, 3.81, 2.54, -3.81), "External 12 V supply entry; Rev B connected supply drives VM_RAW and GND")
custom("CONTROL_4PIN", "CN", [(i, name, -5.08, 6.35 - i * 2.54, 0, "output")
                              for i, name in [(1, "R_EN"), (2, "R_PH"), (3, "L_PH"), (4, "L_EN")]],
       rect(-2.54, 6.35, 10.16, -6.35), "External controller signal entry; original connector has no ground terminal")
custom("SS12D10G4", "U", [(1, "OFF", 7.62, 2.54, 180),
                          (2, "COM", -7.62, 0, 0), (3, "ON", 7.62, -2.54, 180)],
       poly([(-5.08, 0), (-2.54, 0), (3.81, 2.54), (5.08, 2.54)])
       + poly([(3.81, -2.54), (5.08, -2.54)]),
       "SPDT slide switch: pin 2 common; pins 1 and 3 throws; see instance nets for function")

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
    if lib in ("DRV8701ERGET", "TPS25910RSAR"):
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
    datasheet = source.get("datasheet", "") or ("https://www.ti.com/lit/ds/symlink/drv8701.pdf" if ref in ("U1", "U2")
                 else "https://toshiba.semicon-storage.com/info/TPH1R403NL_datasheet_en_20191030.pdf?did=14296&prodName=TPH1R403NL" if ref.startswith("Q") else "")
    body = (f'(symbol (lib_id "DRV8701_Custom:{lib}") (at {n(x)} {n(y)} {angle}) (unit 1) '
            f'(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid {q(uid(ref))}) '
            + prop("Reference", ref, *refpos) + prop("Value", source["value"], *valpos, size=1.016)
            + prop("Footprint", "DRV8701_Custom:" + footprint, x, y, hide=True)
            + prop("Datasheet", datasheet, x, y, hide=True)
            + prop("Source", "Authorized Rev B main power addition" if ref in APPROVED_ADDITIONS else
                   "Original PDF; Rev B authorized P2.1 input rail split" if ref == "P2" else
                   "Original PDF; connections and values retained", x, y, hide=True))
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
                     "Quantity": 1, "PCB side": "Front", "Source fidelity":
                     "Authorized Rev B addition" if ref in APPROVED_ADDITIONS else
                     "Original value; authorized P2.1 net split" if ref == "P2" else "Original value and connectivity",
                     "Rating / tolerance": source.get("rating", source.get("tolerance", ""))})


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
    text("SOP Advance: S=1,2,3; G=4; D=5,6,7,8 + thermal pad", 105.41+delta, 120.65, 1.016)
    text("Original charge-pump and supply capacitors: all 100nF", 17.78+delta, 132.08, 1.27)
    for i, ref in enumerate(caprefs):
        add(ref, "C", "C_0603_1608Metric", 27.94+delta+i*27.94, 149.86, COMPONENTS[ref]["pins"])
    text("Series RC across motor outputs: 100nF + 100 ohm", 17.78+delta, 171.45, 1.27)
    add(snub, "C", "C_0603_1608Metric", 60.96+delta, 186.69, COMPONENTS[snub]["pins"])
    add(resistor, "R", "R_1210_3225Metric", 60.96+delta, 207.01, COMPONENTS[resistor]["pins"])
    add(motor, "XT30_OUTPUT", "AMASS_XT30UPB_M_SourceNumbering", 175.26+delta, 129.54,
        COMPONENTS[motor]["pins"])
    text("12V motor: 0.4A rated / 1.8A stall max", 17.78+delta, 165.1, 1.016)

text("REV B MAIN HIGH-SIDE POWER", 104.14, 168.91, 1.27)
text("SW1 ON = EN low; OFF = divider high", 302.26, 168.91, 1.016)
add("U6", "TPS25910RSAR", "TPS25910_RSA16", 144.78, 196.85, COMPONENTS["U6"]["pins"])
add("C18", "C", "C_0805_2012Metric", 203.2, 184.15, COMPONENTS["C18"]["pins"])
add("R10", "R", "R_0603_1608Metric", 203.2, 207.01, COMPONENTS["R10"]["pins"])
add("R11", "R", "R_0603_1608Metric", 312.42, 187.96, COMPONENTS["R11"]["pins"])
add("R12", "R", "R_0603_1608Metric", 340.36, 187.96, COMPONENTS["R12"]["pins"])
add("C19", "C", "C_0603_1608Metric", 340.36, 210.82, COMPONENTS["C19"]["pins"])
add("SW1", "SS12D10G4", "SS12D10G4", 382.27, 195.58, COMPONENTS["SW1"]["pins"])
text("5A nominal limit; about 11ms typical start", 104.14, 217.17, 1.016)
text("OFF chip input standby: 2.5mA typ / 4mA max", 287.02, 219.71, 1.016)

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

text("REV B: authorized main power addition; all original values retained; only P2.1 changed to VM_RAW.", 17.78, 266.7, 1.016)
text("CN3 has no ground pin: controller must share ground via power return. 3V3 is a 10k-fed zener node.", 17.78, 269.24, 1.016)
text("VREF/IDRIVE tied to AVDD; SP/SN grounded; nFAULT/SNSOUT/SO NC. U6 adds a shared supply current limit.", 17.78, 271.78, 1.016)
text("Original 100nF bypass values retained: compare TI recommendations before manufacture.", 17.78, 274.32, 1.016)

header = (f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") '
          f'(uuid {q(ROOT)}) (paper "A3") '
          '(title_block (title "DRV8701 DUAL MOTOR / 12 V") '
          '(date "2026-10-09") (rev "B") (company "Source: 8701 driver board, no current sensing 2.0") '
          '(comment 1 "Manual PCB routing only; no hardware validation") '
          '(comment 2 "Rev B: authorized main eFuse; original values retained; P2 input rail split")) '
          '(lib_symbols ' + "\n".join(LIB.values()) + ')\n')
OUT.mkdir(parents=True, exist_ok=True)
(OUT/"source").mkdir(exist_ok=True)
(OUT/"validation").mkdir(exist_ok=True)
SCH = OUT/"DRV8701_DUAL_12V.kicad_sch"
SCH.write_text(header + "\n".join(SCHEMATIC) + '\n(embedded_fonts no))\n')
# External symbol library keeps the project editable without system-library dependencies.
external = []
for name, block in LIB.items():
    external.append(block.replace(f'(symbol "DRV8701_Custom:{name}"', f'(symbol "{name}"', 1))
(OUT/"DRV8701_Custom.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") (generator_version "9.0")\n'
                                         + "\n".join(external) + ')\n')
(OUT/"sym-lib-table").write_text('(sym_lib_table (version 7)\n (lib (name "DRV8701_Custom")(type "KiCad")(uri "${KIPRJMOD}/DRV8701_Custom.kicad_sym")(options "")(descr "Self-contained Rev B symbols; retained motor circuit and authorized power addition"))\n)\n')
project = OUT/"DRV8701_DUAL_12V.kicad_pro"
if not project.exists():
    # A named project makes KiCad load the portable project-local library tables.
    # Board generation may subsequently add ordinary design rules/settings.
    project.write_text(json.dumps({"meta": {"filename": project.name, "version": 1}}, indent=2)+"\n")
with (OUT/"components.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(MANIFEST[0]))
    writer.writeheader()
    writer.writerows(MANIFEST)
DESIGN_EXPECTED = {component["ref"]+"."+pin: net for component in DATA["components"]
                   for pin, net in physical_pins(component).items()}
if DESIGN_EXPECTED != EXPECTED:
    raise SystemExit("Drawing pin assignments disagree with independent design netlist")
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
    memberships = {}
    duplicate_actual_pins = []
    for net in exported.findall("./nets/net"):
        # KiCad prefixes root-sheet local net labels with '/'; remove only the
        # root sheet delimiter, preserving the actual source net name.
        name = net.attrib["name"].removeprefix("/")
        memberships[name] = set()
        for node in net.findall("node"):
            pinname = node.attrib["ref"]+"."+node.attrib["pin"]
            if pinname in actual:
                duplicate_actual_pins.append(pinname)
            actual[pinname] = name
            memberships[name].add(pinname)
    errors = []
    isolated_nc_nets = set()
    if duplicate_actual_pins:
        errors.append(f"Physical pins exported more than once: {duplicate_actual_pins}")
    for pinname, expected in DESIGN_EXPECTED.items():
        actual_net = actual.get(pinname)
        if expected is None:
            if actual_net and (not actual_net.startswith("unconnected-") or memberships[actual_net] != {pinname}):
                errors.append(f"{pinname}: NC unexpectedly connected to {actual_net}")
            elif actual_net:
                isolated_nc_nets.add(actual_net)
        elif actual_net != expected:
            errors.append(f"{pinname}: expected {expected}, got {actual_net}")
    actual_components = {c.attrib["ref"]: c for c in exported.findall("./components/comp")}
    actual_refs = set(actual_components)
    if actual_refs != set(COMPONENTS):
        errors.append(f"Component mismatch: actual {sorted(actual_refs)}, expected {sorted(COMPONENTS)}")
    for ref, component in COMPONENTS.items():
        if ref in actual_components and actual_components[ref].findtext("value") != component["value"]:
            errors.append(f"{ref}: exported value differs from active design")
    if set(actual) - set(DESIGN_EXPECTED):
        errors.append(f"Unexpected exported physical pins: {sorted(set(actual)-set(DESIGN_EXPECTED))}")
    actual_named_nets = set(actual.values())-isolated_nc_nets
    if actual_named_nets != set(DATA["nets"]):
        errors.append("Exported named network set differs from active design")
    original_actual_deltas = []
    for original in ORIGINAL["components"]:
        for pin, before in physical_pins(original).items():
            pinname = original["ref"]+"."+pin
            after = None if actual.get(pinname) in isolated_nc_nets else actual.get(pinname)
            if before != after:
                original_actual_deltas.append({"pin": pinname, "from": before, "to": after})
    if original_actual_deltas != SOURCE_CONTRACT["authorized_existing_pin_deltas"]:
        errors.append("Actual schematic original-pin changes differ from independently approved source contract")
    result = {"passed": not errors, "revision": "B", "components": len(actual_refs), "named_nets": len(actual_named_nets),
              "physical_pin_assignments": len(DESIGN_EXPECTED), "connected_pins": sum(v is not None for v in DESIGN_EXPECTED.values()),
              "nc_pins": sum(v is None for v in DESIGN_EXPECTED.values()), "nc_isolation_checked": True,
              "source_faithful": False, "authorized_revision": True, "remaining_original_circuit_preserved": not errors,
              "actual_original_pin_deltas": original_actual_deltas, "all_component_values_checked": True, "errors": errors}
    (OUT/"validation/schematic_net_equivalence.json").write_text(json.dumps(result, indent=2)+"\n")
    if errors:
        raise SystemExit("Net equivalence failed: " + "; ".join(errors))
    subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "--output",
                    str(OUT/"validation/schematic_erc.json"), str(SCH)], check=True, env=env)
    erc = json.loads((OUT/"validation/schematic_erc.json").read_text())
    violations = [v for sheet in erc["sheets"] for v in sheet["violations"]]
    subprocess.run(["kicad-cli", "sch", "export", "pdf", "--output", str(OUT/"DRV8701_DUAL_12V_schematic.pdf"), str(SCH)],
                   check=True, env=env)
    print(f"Rev B design/source contract and exported netlist passed; {len(violations)} ERC violations; schematic PDF exported.")
    if violations:
        raise SystemExit("ERC needs review: " + "; ".join(v["type"]+": "+v["description"] for v in violations))
