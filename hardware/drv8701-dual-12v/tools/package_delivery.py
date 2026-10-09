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
assert not drc['violations'] and not drc['unconnected_items']
erc = read('validation/schematic_erc.json')
assert all(not sheet.get('violations', []) for sheet in erc['sheets'])
schematic = read('validation/schematic_net_equivalence.json')
native_sch = read('EasyEDA_Pro/native-net-equivalence.json')
native_pcb = read('EasyEDA_Pro/native-pcb-equivalence.json')
native_format = read('EasyEDA_Pro/native-format-validation.json')
for report in [schematic, native_sch, native_pcb]:
    assert report['passed'] and not report['errors']
assert not native_format['failures'] and native_format['unmapped'] == 0
assert native_pcb['components'] == 38 and native_pcb['namedNets'] == 34
assert native_pcb['tracks'] == 258 and native_pcb['vias'] == 76
assert native_pcb['padInstances'] == 181
assert abs(native_pcb['totalPhysicalThicknessMm'] - 1.6) < 1e-6
assert len(native_pcb['copperLayerReport']) == 4

manual = read('manual_routes.json')
assert manual['autorouter_used'] is False and manual['pathfinder_used'] is False
audit = read('source/engineering_audit_snapshot.json')
pcb_sha = sha(ROOT / 'DRV8701_DUAL_12V.kicad_pcb')
assert audit['sha256'] == pcb_sha, 'Independent engineering audit is from an older PCB.'
web_import = read('validation/kicad5-import-validation.json')
assert web_import['actual5Drc']['errors'] == 0 and web_import['actual5Drc']['unconnected_pads'] == 0
assert web_import['actual5Erc']['errors'] == 0 and web_import['actual5Erc']['warnings'] == 0
assert web_import['addedCopperAreaByBridgesMm2'] == 0.0
assert sha(ROOT / 'imports/DRV8701_12V_KiCad5_Import.zip') == web_import['archiveSha256']
assert sha(ROOT / 'source/Toshiba_TPH1R403NL_Rev3_0_A.pdf') == '12a06e5d86ab4f4fd7d9dc543e2c7d85796f29c18ecd32b010ac4c99267ede17'

report = {
    'generatedAt': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
    'status': 'Web import uses the separate KiCad5 archive; full source package retained for review; hardware not validated',
    'webImportArchive': 'DRV8701_12V_KiCad5_Import.zip',
    'webImportGuide': 'IMPORT_IN_WEB_PRO.md',
    'webImportFormat': 'KiCad 5.1 legacy .pro/.sch/.lib/.kicad_pcb with local libraries',
    'easyedaActualWebImportVerified': False,
    'webImportValidation': 'validation/kicad5-import-validation.json',
    'webImportArchiveSha256': web_import['archiveSha256'],
    'actualKiCad5Drc': web_import['actual5Drc'],
    'actualKiCad5Erc': web_import['actual5Erc'],
    'legacyImportTracks': 290,
    'legacyImportDrainBridgeSegments': 32,
    'legacyDrainBridgeAddedPhysicalCopperMm2': 0.0,
    'nativeEntry': 'EasyEDA_Pro/DRV8701_DUAL_12V.eprj3',
    'nativeClientTarget': 'EasyEDA Pro V4.1+ offline/semi-offline desktop',
    'sourcePcbSha256': pcb_sha,
    'boardMm': [48, 36],
    'layers': 4,
    'nominalTotalThicknessMm': native_pcb['totalPhysicalThicknessMm'],
    'copperThicknessMmEach': 0.035,
    'assumedFinishedHoleCopperMinMm': 0.020,
    'motorSupplyV': 12,
    'currentBasisA': {'motorEach': 1.8, 'common': 3.6},
    'mainTraceWidthMm': {'motorEachOuter': 0.7, 'commonVMOuter': 1.8},
    'components': 38,
    'nets': 34,
    'uniquePhysicalPins': 173,
    'padInstances': 181,
    'segments': 258,
    'vias': 76,
    'pours': 3,
    'sourceValuesAndConnectionsPreserved': True,
    'autorouterUsed': False,
    'pathfinderUsed': False,
    'kicadErc': {'errors': 0, 'warnings': 0},
    'kicadDrc': {'violations': 0, 'unconnectedItems': 0, 'exclusionsUsed': False},
    'schematicSourceNetEquivalent': schematic['passed'],
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
        'Gate/SH geometry is not strict Kelvin and local VM bypass includes two vias; switching waveforms need hardware measurement.',
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
