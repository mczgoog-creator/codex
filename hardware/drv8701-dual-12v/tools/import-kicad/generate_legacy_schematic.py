#!/usr/bin/env python3
"""Generate actual KiCad 5.1 legacy SCH/LIB/INI files from the validated design.

This is a loss-checked syntax conversion, not a design edit. The original modern
files are read-only inputs. Coordinates in the old schematic/library are mils;
all primitives in this source have a direct legacy representation. Unsupported
primitives fail explicitly. PCB/footprint conversion is handled separately.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "KiCad_Import_5"
NAME = "DRV8701_DUAL_12V"
LIB_NAME = "DRV8701_Custom"


def parse(text):
    tokens = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', text)
    stack = []
    result = []
    for token in tokens:
        if token == "(":
            item = []
            (stack[-1] if stack else result).append(item)
            stack.append(item)
        elif token == ")":
            if not stack:
                raise ValueError("Unbalanced close parenthesis")
            stack.pop()
        elif token.startswith('"'):
            # KiCad's escaping agrees with JSON for the strings in this source.
            stack[-1].append(json.loads(token))
        else:
            stack[-1].append(token)
    assert not stack and len(result) == 1
    return result[0]


def children(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def child(node, key, default=None):
    found = children(node, key)
    return found[0] if found else default


def value(node, key, default=None):
    found = child(node, key)
    return found[1] if found and len(found) > 1 else default


def quote(text):
    return json.dumps(str(text), ensure_ascii=False)


def mil(mm):
    value = float(mm) / 0.0254
    return int(round(value))


def dimensions(node, key="at"):
    return tuple(mil(x) for x in child(node, key)[1:3])


def fontsize(node):
    effects = child(node, "effects")
    font = child(effects, "font") if effects else None
    size = child(font, "size") if font else None
    return mil(size[1]) if size else 50


def hidden(node):
    effects = child(node, "effects")
    return value(effects, "hide", "no") == "yes" if effects else False


def alignment(node):
    effects = child(node, "effects")
    justify = child(effects, "justify") if effects else None
    return "L" if justify and "left" in justify else "R" if justify and "right" in justify else "C"


def fieldline(index, item, schematic=False):
    name, text = item[1:3]
    x, y = dimensions(item)
    angle = float(child(item, "at")[3])
    assert angle in (0, 90, 180, 270), angle
    orient = "H" if angle in (0, 180) else "V"
    visibility = "0001" if hidden(item) else "0000"
    font = fontsize(item)
    align = alignment(item)
    if schematic:
        out = f"F {index} {quote(text)} {orient} {x} {y} {font} {visibility} {align} CNN"
        if index >= 4:
            out += " " + quote(name)
        return out
    return f"F{index} {quote(text)} {x} {y} {font} {orient} {'I' if hidden(item) else 'V'} {align} CNN"


ELECTRICAL = {
    "input": "I", "output": "O", "bidirectional": "B", "tri_state": "T",
    "passive": "P", "power_in": "W", "power_out": "w", "open_collector": "C",
    "open_emitter": "E", "no_connect": "N", "free": "U", "unspecified": "U",
}
PIN_ORIENT = {0: "R", 90: "U", 180: "L", 270: "D"}
PIN_SHAPE = {"line": "", "inverted": "I", "clock": "C", "inverted_clock": "IC",
             "input_low": "L", "clock_low": "CL", "output_low": "V", "edge_clock_high": "F",
             "non_logic": "X"}
FILL = {"none": "N", "outline": "F", "background": "f"}


def symbol_library(symbols):
    output = ["EESchema-LIBRARY Version 2.4", "#encoding utf-8"]
    docs = ["EESchema-DOCLIB  Version 2.0"]
    counts = {}
    for symbol in symbols:
        name = symbol[1].split(":", 1)[1]
        properties = {p[1]: p for p in children(symbol, "property")}
        pin_names = child(symbol, "pin_names")
        offset = mil(value(pin_names, "offset", 0))
        show_names = "N" if value(pin_names, "hide", "no") == "yes" else "Y"
        show_numbers = "N" if value(child(symbol, "pin_numbers", []), "hide", "no") == "yes" else "Y"
        prefix = properties["Reference"][2]
        symbol_kind = "P" if child(symbol, "power") else "N"
        output += ["#", "# " + name, "#", f"DEF {name} {prefix} 0 {offset} {show_numbers} {show_names} 1 F {symbol_kind}"]
        for i, key in enumerate(("Reference", "Value", "Footprint", "Datasheet")):
            output.append(fieldline(i, properties[key]))
        output.append("DRAW")
        pincount = 0
        for part in children(symbol, "symbol"):
            match = re.search(r"_(\d+)_(\d+)$", part[1])
            assert match, part[1]
            unit, convert = map(int, match.groups())
            for primitive in part[2:]:
                assert isinstance(primitive, list)
                kind = primitive[0]
                if kind in ("rectangle", "polyline"):
                    width = mil(value(child(primitive, "stroke"), "width", 0))
                    fill = FILL[value(child(primitive, "fill"), "type", "none")]
                    if kind == "rectangle":
                        x1, y1 = dimensions(primitive, "start")
                        x2, y2 = dimensions(primitive, "end")
                        output.append(f"S {x1} {y1} {x2} {y2} {unit} {convert} {width} {fill}")
                    else:
                        points = children(child(primitive, "pts"), "xy")
                        coords = " ".join(str(mil(coord)) for point in points for coord in point[1:3])
                        output.append(f"P {len(points)} {unit} {convert} {width} {coords} {fill}")
                elif kind == "pin":
                    _, electrical, shape = primitive[:3]
                    pinname = child(primitive, "name")
                    pinnum = child(primitive, "number")
                    at = child(primitive, "at")
                    orient = PIN_ORIENT[int(float(at[3]))]
                    x, y = mil(at[1]), mil(at[2])
                    length = mil(value(primitive, "length"))
                    assert not any(c.isspace() for c in pinname[1]), pinname[1]
                    assert not any(c.isspace() for c in pinnum[1]), pinnum[1]
                    extra = PIN_SHAPE[shape]
                    if value(primitive, "hide", "no") == "yes":
                        extra = "N" + extra
                    output.append(f"X {pinname[1]} {pinnum[1]} {x} {y} {length} {orient} "
                                  f"{fontsize(pinnum)} {fontsize(pinname)} {unit} {convert} {ELECTRICAL[electrical]}"
                                  + (" " + extra if extra else ""))
                    pincount += 1
                else:
                    raise ValueError(f"No legacy conversion implemented for {name}: {kind}")
        output += ["ENDDRAW", "ENDDEF"]
        description = properties.get("Description")
        docs += ["#", "$CMP " + name]
        if description:
            docs.append("D " + description[2])
        if properties.get("Datasheet") and properties["Datasheet"][2]:
            docs.append("F " + properties["Datasheet"][2])
        docs += ["$ENDCMP"]
        counts[name] = pincount
    output += ["#", "#End Library"]
    docs += ["#", "#End Doc Library"]
    return "\n".join(output)+"\n", "\n".join(docs)+"\n", counts


def schematic(tree):
    symbols = children(tree, "symbol")
    timestamp_map = {}
    output = ["EESchema Schematic File Version 4", "LIBS:DRV8701_Custom", "EELAYER 30 0", "EELAYER END",
              "$Descr A3 16535 11693", "encoding utf-8", "Sheet 1 1"]
    title = child(tree, "title_block")
    for old, new in [("Title", "title"), ("Date", "date"), ("Rev", "rev"), ("Comp", "company")]:
        output.append(old+" "+quote(value(title, new, "")))
    comments = {int(c[1]): c[2] for c in children(title, "comment")}
    for i in range(1, 5):
        output.append(f"Comment{i} {quote(comments.get(i, ''))}")
    output.append("$EndDescr")
    for symbol in symbols:
        properties = {p[1]: p for p in children(symbol, "property")}
        ref = properties["Reference"][2]
        uuid = value(symbol, "uuid")
        timestamp = uuid.replace("-", "")[:8].upper()
        assert re.fullmatch(r"[0-9A-F]{8}", timestamp)
        timestamp_map[ref] = {"uuid": uuid, "timestamp": timestamp, "pcb_path": "/"+timestamp}
        unit = value(symbol, "unit")
        x, y = dimensions(symbol)
        assert float(child(symbol, "at")[3]) == 0, "This source only uses unrotated symbols"
        assert not child(symbol, "mirror"), "No mirror expected in this source"
        library_symbol = LIB_NAME + ":" + value(symbol, "lib_id").split(":", 1)[-1]
        output += ["$Comp", f"L {library_symbol} {ref}", f"U {unit} 1 {timestamp}", f"P {x} {y}"]
        keys = ["Reference", "Value", "Footprint", "Datasheet"]
        keys += [key for key in properties if key not in keys]
        for i, key in enumerate(keys):
            output.append(fieldline(i, properties[key], schematic=True))
        output += [f"\t{unit}    {x} {y}", "\t1    0    0    -1", "$EndComp"]
    assert len(set(m["timestamp"] for m in timestamp_map.values())) == len(timestamp_map), "Timestamp prefix collision"
    count = {"components": sum(value(s, "on_board", "yes") == "yes" for s in symbols),
             "schematic_symbols": len(symbols),
             "nonphysical_symbols": sum(value(s, "on_board", "yes") != "yes" for s in symbols),
             "wires": 0, "labels": 0, "no_connects": 0, "texts": 0}
    for item in tree[1:]:
        if not isinstance(item, list):
            continue
        if item[0] == "wire":
            points = children(child(item, "pts"), "xy")
            assert len(points) == 2
            coords = " ".join(str(mil(v)) for point in points for v in point[1:3])
            output += ["Wire Wire Line", "\t"+coords]
            count["wires"] += 1
        elif item[0] == "label":
            x, y = dimensions(item)
            assert float(child(item, "at")[3]) == 0
            # Old spin=2 gives horizontal text anchored to its right end,
            # matching modern (justify right) left-facing pin stubs.
            spin = 2 if alignment(item) == "R" else 0
            output += [f"Text Label {x} {y} {spin} {fontsize(item)} ~ 0", item[1]]
            count["labels"] += 1
        elif item[0] == "no_connect":
            x, y = dimensions(item)
            output.append(f"NoConn ~ {x} {y}")
            count["no_connects"] += 1
        elif item[0] == "text":
            x, y = dimensions(item)
            assert float(child(item, "at")[3]) == 0
            output += [f"Text Notes {x} {y} 0 {fontsize(item)} ~ 0", item[1].replace("\n", r"\n")]
            count["texts"] += 1
        elif item[0] not in {"version", "generator", "generator_version", "uuid", "paper", "title_block",
                             "lib_symbols", "symbol", "embedded_fonts"}:
            raise ValueError(f"Unsupported sheet primitive: {item[0]}")
    output.append("$EndSCHEMATC")
    return "\n".join(output)+"\n", timestamp_map, count


def pro_file():
    # KiCad 5 project files are INI, unlike KiCad 6+ .kicad_pro JSON.
    return """update=2026-10-09
version=1
last_client=kicad
[general]
version=1
RootSch=DRV8701_DUAL_12V.sch
BoardNm=DRV8701_DUAL_12V.kicad_pcb
[cvpcb]
version=1
NetIExt=net
[eeschema]
version=1
LibDir=
[schematic_editor]
version=1
PageLayoutDescrFile=
PlotDirectoryName=
SubpartIdSeparator=0
SubpartFirstId=65
NetFmtName=Pcbnew
SpiceAjustPassiveValues=0
LabSize=40
ERC_TestSimilarLabels=1
[pcbnew]
version=1
PageLayoutDescrFile=
LastNetListRead=DRV8701_DUAL_12V.net
CopperLayerCount=4
BoardThickness=1.6
AllowMicroVias=0
AllowBlindVias=0
RequireCourtyardDefinitions=0
ProhibitOverlappingCourtyards=1
MinTrackWidth=0.15
MinViaDiameter=0.40
MinViaDrill=0.20
MinMicroViaDiameter=0.20
MinMicroViaDrill=0.10
MinHoleToHole=0.25
TrackWidth1=0.20
TrackWidth2=0.25
TrackWidth3=0.30
TrackWidth4=0.70
TrackWidth5=1.80
ViaDiameter1=0.45
ViaDrill1=0.20
ViaDiameter2=0.65
ViaDrill2=0.30
ViaDiameter3=0.80
ViaDrill3=0.40
SilkLineWidth=0.12
SilkTextSizeV=0.60
SilkTextSizeH=0.60
SilkTextSizeThickness=0.11
SilkTextItalic=0
SilkTextUpright=1
CopperLineWidth=0.20
CopperTextSizeV=1.50
CopperTextSizeH=1.50
CopperTextThickness=0.30
CopperTextItalic=0
CopperTextUpright=1
EdgeCutLineWidth=0.05
CourtyardLineWidth=0.05
SolderMaskClearance=0
SolderMaskMinWidth=0
SolderPasteClearance=0
SolderPasteRatio=0
[pcbnew/Netclasses]
[pcbnew/Netclasses/Default]
Name=Default
Desc=Default net class.
Clearance=0.15
TrackWidth=0.20
ViaDiameter=0.45
ViaDrill=0.20
uViaDiameter=0.30
uViaDrill=0.10
dPairWidth=0.20
dPairGap=0.25
dPairViaGap=0.25
"""


def expected_physical(source):
    expected = {}
    for component in source["components"]:
        ref, kind, pins = component["ref"], component["kind"], component["pins"]
        if kind in {"n_channel_mosfet", "p_channel_mosfet"}:
            pins = {str(i): pins["S" if i <= 3 else "G" if i == 4 else "D"] for i in range(1, 9)}
        elif kind == "electrolytic_capacitor":
            pins = {"1": pins["+"], "2": pins["-"]}
        elif kind in {"zener_diode", "led"}:
            pins = {"1": pins["K"], "2": pins["A"]}
        for number, net in pins.items():
            expected[ref+"."+number] = net
    return expected


def read_netlist(netfile):
    """Read either the XML or S-expression netlist exported by real Eeschema."""
    text = Path(netfile).read_text()
    if text.lstrip().startswith("<"):
        return ET.fromstring(text)
    tree = parse(text)
    assert tree[0] == "export", "Not an Eeschema netlist"
    root = ET.Element("export")
    design = ET.SubElement(root, "design")
    for key in ("source", "tool", "date"):
        ET.SubElement(design, key).text = value(child(tree, "design", []), key)
    components = ET.SubElement(root, "components")
    for comp in children(child(tree, "components"), "comp"):
        item = ET.SubElement(components, "comp", ref=value(comp, "ref"))
        ET.SubElement(item, "value").text = value(comp, "value")
        ET.SubElement(item, "tstamps").text = value(comp, "tstamps", value(comp, "tstamp"))
    nets = ET.SubElement(root, "nets")
    for net in children(child(tree, "nets"), "net"):
        item = ET.SubElement(nets, "net", name=value(net, "name"), code=value(net, "code"))
        for node in children(net, "node"):
            ET.SubElement(item, "node", ref=value(node, "ref"), pin=value(node, "pin"))
    return root


def validate_library(env):
    readback = TARGET/"validation/legacy_library_readback.kicad_sym"
    # This command uses KiCad's actual legacy-library parser, independent of our writer.
    # The official tool requires a new output path; keep repeated validation usable.
    with tempfile.TemporaryDirectory(prefix=".legacy-lib-readback-", dir=TARGET/"validation") as directory:
        temporary = Path(directory)/(LIB_NAME+".kicad_sym")
        subprocess.run(["kicad-cli", "sym", "upgrade", "--output", str(temporary), str(TARGET/(LIB_NAME+".lib"))],
                       check=True, env=env)
        readback.write_bytes(temporary.read_bytes())
    source = parse((ROOT/(NAME+".kicad_sch")).read_text())
    original = {s[1].split(":", 1)[1]: s for s in children(child(source, "lib_symbols"), "symbol")}
    roundtrip = {s[1]: s for s in children(parse(readback.read_text()), "symbol")}
    def pin_details(symbol):
        return {child(p, "number")[1]: {"name": child(p, "name")[1], "electrical": p[1], "style": p[2],
                                       "at": [mil(child(p, "at")[1]), mil(child(p, "at")[2]), child(p, "at")[3]],
                                       "length": mil(value(p, "length"))}
                for part in children(symbol, "symbol") for p in children(part, "pin")}
    errors = []
    if set(original) != set(roundtrip):
        errors.append("Symbol name sets differ")
    for name in original:
        if name not in roundtrip or pin_details(original[name]) != pin_details(roundtrip[name]):
            errors.append(name+": pin details changed")
    report = {"passed": not errors, "reader": "Official KiCad legacy LIB parser via kicad-cli sym upgrade",
              "symbols": len(roundtrip), "pin_definitions": sum(len(pin_details(x)) for x in roundtrip.values()),
              "pin_positions_numbers_names_types_styles_and_lengths_preserved": not errors, "errors": errors}
    (TARGET/"validation/legacy_library_roundtrip.json").write_text(json.dumps(report, indent=2)+"\n")
    if errors:
        raise SystemExit("Legacy library conversion mismatch: "+"; ".join(errors))


def validate(source, timestamps, provided_netlist=None):
    path = TARGET/"validation"
    env = os.environ.copy()
    for var, dirname in [("XDG_CACHE_HOME", "cache"), ("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config")]:
        p = Path("/tmp/drv8701-legacy-kicad")/dirname
        p.mkdir(parents=True, exist_ok=True)
        env[var] = str(p)
    sch = TARGET/(NAME+".sch")
    validate_library(env)
    netfile = Path(provided_netlist).resolve() if provided_netlist else path/"legacy_schematic_netlist.xml"
    if not provided_netlist:
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "--output", str(netfile), str(sch)], check=True, env=env)
    netlist = read_netlist(netfile)
    actual = {}
    memberships = {}
    for net in netlist.findall("./nets/net"):
        name = net.attrib["name"].removeprefix("/")
        memberships[name] = set()
        for node in net.findall("node"):
            pinname = node.attrib["ref"]+"."+node.attrib["pin"]
            actual[pinname] = name
            memberships[name].add(pinname)
    expected = expected_physical(source)
    errors = []
    isolated_nc_nets = set()
    for pin, name in expected.items():
        found = actual.get(pin)
        if name is None:
            # Eeschema 5 includes an NC pin as a singleton Net-(Ref-PadN),
            # whereas current Eeschema names it unconnected-*. Require actual
            # electrical isolation, plus the respective generated naming.
            ref, number = pin.rsplit(".", 1)
            auto_nc_name = found is not None and (found == f"Net-({ref}-Pad{number})" or found.startswith("unconnected-"))
            if found is not None and (not auto_nc_name or memberships[found] != {pin}):
                errors.append(f"{pin}: NC unexpectedly connected to {found} members={sorted(memberships[found])}")
            elif found is not None:
                isolated_nc_nets.add(found)
        elif name != found:
            errors.append(f"{pin}: expected {name}, got {found}")
    for pin in actual:
        if pin not in expected:
            errors.append("Unexpected pin "+pin)
    found_components = {c.attrib["ref"]: c for c in netlist.findall("./components/comp")}
    for component in source["components"]:
        ref = component["ref"]
        found = found_components.get(ref)
        if found is None:
            errors.append("Missing component "+ref)
        elif found.findtext("value") != component["value"]:
            errors.append(f"{ref}: value changed to {found.findtext('value')}")
        elif (found.findtext("tstamps") or found.findtext("tstamp") or "").replace("-", "").lower()[-8:] != timestamps[ref]["timestamp"].lower():
            errors.append(f"{ref}: component timestamp mismatch {found.findtext('tstamps') or found.findtext('tstamp')}")
    if set(found_components) != {c["ref"] for c in source["components"]}:
        errors.append("Component reference sets differ")
    namednets = set(actual.values()) - isolated_nc_nets
    if namednets != set(source["nets"]):
        errors.append(f"Named net sets differ: {sorted(namednets ^ set(source['nets']))}")
    result = {"passed": not errors, "reader": "Externally exported Eeschema netlist" if provided_netlist else "KiCad 9 CLI direct legacy read (known external-symbol loading limitation)",
              "exporter_version": netlist.findtext("./design/tool"),
              "netlist_path": str(netfile), "netlist_sha256": hashlib.sha256(netfile.read_bytes()).hexdigest(),
              "components": len(found_components), "values_matched": len(source["components"]),
              "named_nets": len(namednets), "physical_pins": len(expected),
              "connected_pins": sum(v is not None for v in expected.values()),
              "nc_pins": sum(v is None for v in expected.values()),
              "nc_singleton_net_memberships_checked": True,
              "nc_automatic_net_names": sorted(isolated_nc_nets), "errors": errors}
    (path/"legacy_net_equivalence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    if errors:
        raise SystemExit("Legacy netlist mismatch: "+"; ".join(errors))
    if provided_netlist:
        extension = ".xml" if netfile.read_text().lstrip().startswith("<") else ".net"
        (path/("eeschema_exported"+extension)).write_bytes(netfile.read_bytes())
        if extension == ".net" and netfile != TARGET/(NAME+".net"):
            (TARGET/(NAME+".net")).write_bytes(netfile.read_bytes())
        # ERC must be run in the same real reader that loaded the external legacy
        # symbols. Do not produce a misleading empty KiCad 9 CLI legacy ERC report.
        print(json.dumps(result, indent=2))
        return
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "--output", str(TARGET/(NAME+".net")), str(sch)], check=True, env=env)
    subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "--output", str(path/"legacy_erc.json"), str(sch)], check=True, env=env)
    subprocess.run(["kicad-cli", "sch", "export", "pdf", "--output", str(path/"legacy_schematic_preview.pdf"), str(sch)], check=True, env=env)
    report = json.loads((path/"legacy_erc.json").read_text())
    violations = [v for s in report["sheets"] for v in s["violations"]]
    print(json.dumps({**result, "erc_violations": len(violations)}, indent=2))


def main():
    global ROOT, TARGET
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-validate", action="store_true", help="Generate only; leave verification for a separately installed KiCad reader")
    parser.add_argument("--legacy-netlist", type=Path,
                        help="Validate an XML or S-expression netlist exported after actually loading SCH/LIB in Eeschema 5.1")
    parser.add_argument("--base", type=Path, default=ROOT, help="Read modern source files from this project directory")
    parser.add_argument("--out", type=Path, help="Write a self-contained legacy project to this directory")
    args = parser.parse_args()
    ROOT = args.base.resolve()
    TARGET = args.out.resolve() if args.out else ROOT/"KiCad_Import_5"
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET/"validation").mkdir(exist_ok=True)
    original = ROOT/(NAME+".kicad_sch")
    text = original.read_text()
    tree = parse(text)
    assert tree[0] == "kicad_sch"
    design_path = ROOT/"design_netlist.json"
    source = json.loads((design_path if design_path.is_file() else ROOT/"source_netlist.json").read_text())
    lib, dcm, libcounts = symbol_library(children(child(tree, "lib_symbols"), "symbol"))
    sch, timestamps, counts = schematic(tree)
    (TARGET/(NAME+".sch")).write_text(sch)
    (TARGET/(LIB_NAME+".lib")).write_text(lib)
    (TARGET/(LIB_NAME+".dcm")).write_text(dcm)
    # KiCad 5 cache spelling replaces ':' by '_' for namespaced symbols.
    cache = lib
    for name in libcounts:
        cache = cache.replace("DEF "+name+" ", "DEF "+LIB_NAME+"_"+name+" ")
        cache = cache.replace('F1 '+quote(name)+' ', 'F1 '+quote(LIB_NAME+"_"+name)+' ')
    (TARGET/(NAME+"-cache.lib")).write_text(cache)
    (TARGET/(NAME+".pro")).write_text(pro_file())
    (TARGET/"sym-lib-table").write_text('(sym_lib_table\n (lib (name "DRV8701_Custom")(type "Legacy")(uri "${KIPRJMOD}/DRV8701_Custom.lib")(options "")(descr "Self-contained genuine KiCad 5 legacy symbols"))\n)\n')
    (TARGET/"fp-lib-table").write_text('(fp_lib_table\n (lib (name "DRV8701_Custom")(type "KiCad")(uri "${KIPRJMOD}/DRV8701_Custom.pretty")(options "")(descr "Self-contained KiCad 5-compatible footprints"))\n)\n')
    (TARGET/"validation/component_timestamp_map.json").write_text(json.dumps(timestamps, indent=2)+"\n")
    (TARGET/"validation/schematic_format_conversion.json").write_text(json.dumps({
        "source": original.name, "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "schematic_format": "EESchema Schematic File Version 4 (KiCad 5.1 legacy)",
        "symbol_library_format": "EESchema-LIBRARY Version 2.4",
        "project_format": "KiCad 5 INI .pro", "source_component_uuid_prefixes_unique": True,
        "component_timestamp_rule": "8 uppercase hex characters from source instance UUID prefix",
        "counts": counts, "symbol_definition_pins": libcounts,
        "pin_electrical_types_preserved": True, "source_files_modified": False,
        "changed_connectivity": False, "changed_values": False,
    }, indent=2)+"\n")
    if not args.no_validate:
        validate(source, timestamps, args.legacy_netlist)


if __name__ == "__main__":
    main()
