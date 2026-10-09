#!/usr/bin/env python3
"""Package the reviewed CAD files; never routes or changes circuit geometry."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT.parents[1] / 'downloads'
ARCHIVE = (DOWNLOADS if DOWNLOADS.is_dir() else ROOT.parent) / 'DRV8701_12V_EasyEDA_Pro.zip'
PREFIX = 'DRV8701_12V_EasyEDA_Pro'

def read(relative):
    return json.loads((ROOT / relative).read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

drc = read('final_drc.json')
design = read('design_netlist.json')
expected = read('validation/expected_physical_pin_nets.json')
layout = read('validation/layout_geometry_audit.json')
assert layout['passed']
assert not drc['violations'] and not drc['unconnected_items']
erc = read('validation/schematic_erc.json')
assert all(not sheet.get('violations', []) for sheet in erc['sheets'])
schematic = read('validation/schematic_net_equivalence.json')
native_sch = read('EasyEDA_Pro/native-net-equivalence.json')
native_pcb = read('EasyEDA_Pro/native-pcb-equivalence.json')
native_format = read('EasyEDA_Pro/native-format-validation.json')
native_audit = read('EasyEDA_Pro/native-final-audit.json')
for report in [schematic, native_sch, native_pcb]:
    assert report['passed'] and not report['errors']
assert not native_format['failures'] and native_format['unmapped'] == 0
assert native_pcb['components'] == len(design['components']) and native_pcb['namedNets'] == len(design['nets'])
assert native_pcb['uniquePhysicalPins'] == len(expected)
assert native_pcb['tracks'] == layout['counts']['tracks'] and native_pcb['vias'] == layout['counts']['vias']
assert native_pcb['padInstances'] == layout['counts']['physical_pads']
assert abs(native_pcb['totalPhysicalThicknessMm'] - 1.6) < 1e-6
assert len(native_pcb['copperLayerReport']) == 4

manual = read('manual_routes.json')
assert manual['autorouter_used'] is False and manual['pathfinder_used'] is False
assert len(manual['segments']) == native_pcb['tracks']
audit = read('source/engineering_audit_snapshot.json')
pcb_sha = sha(ROOT / 'DRV8701_DUAL_12V.kicad_pcb')
assert native_audit['passed'] and not native_audit['errors']
for filename, checksum in native_audit['sourceChecksumsSha256'].items():
    source = ROOT / ('validation/' + filename if filename == 'expected_physical_pin_nets.json' else filename)
    assert sha(source) == checksum, 'Native conversion is from an older source: ' + filename
assert audit['sha256'] == pcb_sha, 'Independent engineering audit is from an older PCB.'
assert layout['pcb_sha256'] == pcb_sha, 'Independent layout audit is from an older PCB.'
engineering = read('validation/rev_b_engineering_audit.json')
assert engineering['passed'] and engineering['sha256'] == pcb_sha
assert engineering['static_pin_value_checks_passed'] and engineering['manual_routing_evidence']['segment_geometry_equals_explicit_record']
previews = read('validation/preview_exports.json')
assert previews['source_unchanged'] and previews['pcb_sha256'] == pcb_sha
for filename, checksum in previews['files_sha256'].items():
    assert sha(ROOT / filename) == checksum, 'Preview is from an older source: ' + filename
web_import = read('validation/kicad5-import-validation.json')
assert web_import['actual5Drc']['errors'] == 0 and web_import['actual5Drc']['unconnected_pads'] == 0
assert web_import['actual5Erc']['errors'] == 0 and web_import['actual5Erc']['warnings'] == 0
assert web_import['addedCopperAreaByBridgesMm2'] == 0.0
assert sha(ROOT / 'imports/DRV8701_12V_KiCad5_Import.zip') == web_import['archiveSha256']
assert sha(DOWNLOADS / 'DRV8701_12V_KiCad5_Import.zip') == web_import['archiveSha256']
geometry = read('validation/legacy5_final_pcb_equivalence.json')
assert geometry['passed'] and not geometry['failures']
assert geometry['source_sha256'] == pcb_sha and geometry['legacy_sha256'] == web_import['pcbSha256']
assert web_import['components'] == native_pcb['components'] and web_import['nets'] == native_pcb['namedNets']
assert web_import['physicalPins'] == len(expected) and web_import['actualPadInstances'] == native_pcb['padInstances']
assert web_import['originalTrackSegmentsRetained'] == native_pcb['tracks'] and web_import['vias'] == native_pcb['vias']
assert sha(ROOT / 'source/Toshiba_TPH1R403NL_Rev3_0_A.pdf') == '12a06e5d86ab4f4fd7d9dc543e2c7d85796f29c18ecd32b010ac4c99267ede17'
assert sha(ROOT / 'source/TI_TPS25910_SLUSAR6D.pdf') == 'b2b1c899abf10f42a9090d0a94f9fc63376bdbb19300fd42c2c5bfa1f8fd56de'
assert sha(ROOT / 'source/TI_TPS25910EVM_SLVU760A.pdf') == '5b2f6dd78907d0bf8cf0c8f1e942d8a5bddc5b56714582ede7d8b2ecbfbe43db'
power_footprint = read('validation/tps25910_footprint_review.json')
assert power_footprint['all_17_pad_centres_sizes_match']
assert sha(ROOT / 'DRV8701_Custom.pretty/TPS25910_RSA16.kicad_mod') == power_footprint['footprint_sha256']
original_contract = read('validation/rev_b_original_source_contract.json')
assert original_contract['passed'] and not original_contract['errors']
assert sha(ROOT / 'source_netlist.json') == original_contract['original_source_sha256']
assert sha(ROOT / 'source/source_netlist.json') == original_contract['original_source_sha256']

report = {
    'generatedAt': datetime.now(ZoneInfo('Asia/Ulaanbaatar')).isoformat(),
    'revision': 'B',
    'status': 'Web import uses the separate KiCad5 archive; full source package retained for review; hardware not validated',
    'webImportArchive': 'DRV8701_12V_KiCad5_Import.zip',
    'webImportGuide': 'IMPORT_IN_WEB_PRO.md',
    'webImportFormat': 'KiCad 5.1 legacy .pro/.sch/.lib/.kicad_pcb with local libraries',
    'easyedaActualWebImportVerified': False,
    'webImportValidation': 'validation/kicad5-import-validation.json',
    'webImportArchiveSha256': web_import['archiveSha256'],
    'actualKiCad5Drc': web_import['actual5Drc'],
    'actualKiCad5Erc': web_import['actual5Erc'],
    'legacyImportTracks': web_import['totalSegments'],
    'legacyImportDrainBridgeSegments': web_import['internalPadBridgeSegments'],
    'legacyDrainBridgeAddedPhysicalCopperMm2': 0.0,
    'nativeEntry': 'EasyEDA_Pro/DRV8701_DUAL_12V.eprj3',
    'nativeClientTarget': 'EasyEDA Pro V4.1+ offline/semi-offline desktop',
    'sourcePcbSha256': pcb_sha,
    'boardMm': [39, 60],
    'layers': 4,
    'nominalTotalThicknessMm': native_pcb['totalPhysicalThicknessMm'],
    'copperThicknessMmEach': 0.035,
    'assumedFinishedHoleCopperMinMm': 0.020,
    'motorSupplyV': 12,
    'currentBasisA': {'motorEach': 1.8, 'common': 3.6},
    'mainTraceWidthMm': {'motorEachOuter': 0.7, 'commonVMOuter': 1.8},
    'components': native_pcb['components'],
    'nets': native_pcb['namedNets'],
    'uniquePhysicalPins': len(expected),
    'padInstances': native_pcb['padInstances'],
    'segments': native_pcb['tracks'],
    'vias': native_pcb['vias'],
    'pours': native_pcb['zones'],
    'sourceValuesAndConnectionsPreserved': False,
    'originalComponentValuesPreserved': True,
    'remainingOriginalCircuitPreserved': schematic['remaining_original_circuit_preserved'],
    'authorizedCircuitChange': 'P2.1 VM to VM_RAW; seven added main-power components',
    'mainPowerControl': {
        'ic': 'TPS25910RSA', 'switch': 'SW1 controls active-low EN; contacts do not carry motor current',
        'continuousDeviceRatingA': 5, 'currentLimitA': [4.5, 5.0, 5.5],
        'offDeviceBiasCurrentMa': {'typical': 2.5, 'maximum': 4.0},
        'startup': 'Keep U5 disabled and motor EN=0 until VM is stable',
    },
    'layoutGeometryAuditPassed': True,
    'engineeringAudit': 'validation/rev_b_engineering_audit.json',
    'layoutGeometryAudit': 'validation/layout_geometry_audit.json',
    'firstPowerOnInstructions': 'FIRST_POWER_ON.md',
    'previewExportAudit': 'validation/preview_exports.json',
    'driverCapacitorMaxMeasuredPathMm': max(r['copper_centerline_length_mm'] for r in layout['driver_capacitor_paths']),
    'autorouterUsed': False,
    'pathfinderUsed': False,
    'kicadErc': {'errors': 0, 'warnings': 0},
    'kicadDrc': {'violations': 0, 'unconnectedItems': 0, 'exclusionsUsed': False},
    'schematicDesignNetEquivalent': schematic['passed'],
    'nativeSchematicNetEquivalent': native_sch['passed'],
    'nativePcbNetAndCopperEquivalent': native_pcb['passed'],
    'nativeFormat': {
        'outerRecords': native_format['records'],
        'outerValid': native_format['outerValid'],
        'schemaValidRecords': native_format['schemaValid'],
        'documentedFieldDifferences': native_format['documentedDifferences'],
        'unexplainedFailures': len(native_format['failures']),
        'unmappedTypes': native_format['unmapped'],
    },
    'easyedaActualClientOpenVerified': False,
    'easyedaActualClientDrcRun': False,
    'hardwarePowerAndThermalTestsRun': False,
    'toshibaExactManufacturerDatasheetRead': True,
    'toshibaManufacturerPdf': 'source/Toshiba_TPH1R403NL_Rev3_0_A.pdf',
    'toshibaManufacturerPdfSha256': '12a06e5d86ab4f4fd7d9dc543e2c7d85796f29c18ecd32b010ac4c99267ede17',
    'limits': [
        'Toshiba exact-model PDF electrical data and ordinary SOP Advance package outline read; PDF does not supply recommended PCB copper land pattern.',
        'Actual EasyEDA client was unavailable; confirm dimensions, stack, units, copper filling and DRC in client.',
        'Current official schema and real exported template differ; all known differences are listed in native-format-validation.json.',
        'Original 100nF charge-pump/LDO caps, Zener feed, IDRIVE choice and control interface without GND are preserved by user request.',
        'SW1 cuts forward input power to VM; the eFuse still consumes input bias. C15 charge and motor regeneration can retain output voltage.',
        'Start with both bridges disabled; soft-start timing depends on gate-current tolerances and internal SOA limiting.',
        'C18 effective capacitance, via plating, actual connector fit, switching waveforms and temperature require procurement or bench checks.',
    ],
}
(ROOT / 'validation/final_delivery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

excluded = {'initial_drc.json', 'current_drc.json', 'DRV8701_DUAL_12V.kicad_prl', 'FILES_SHA256.txt'}
files = [p for p in sorted(ROOT.rglob('*')) if p.is_file()
         and p.relative_to(ROOT).as_posix() not in excluded
         and '.git' not in p.parts and 'node_modules' not in p.parts
         and '__pycache__' not in p.parts
         and not p.name.endswith(('.bak', '.sch-bak', '.kicad_pcb-bak', '.lck'))]
manifest = ''.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in files)
(ROOT / 'FILES_SHA256.txt').write_text(manifest)
files.append(ROOT / 'FILES_SHA256.txt')

with zipfile.ZipFile(ARCHIVE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files:
        archive.write(path, PREFIX + '/' + path.relative_to(ROOT).as_posix())
with zipfile.ZipFile(ARCHIVE) as archive:
    assert archive.testzip() is None
    for path in files:
        name = PREFIX + '/' + path.relative_to(ROOT).as_posix()
        assert hashlib.sha256(archive.read(name)).hexdigest() == sha(path)
print(json.dumps({'archive': str(ARCHIVE), 'bytes': ARCHIVE.stat().st_size,
                  'files': len(files), 'sha256': sha(ARCHIVE), 'crcAndContentVerified': True}))
