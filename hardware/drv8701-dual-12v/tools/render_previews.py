#!/usr/bin/env python3
"""Export review graphics from CAD, without editing any PCB object.

Fit-page SVG exports retain a board whose outline extends to negative X.
Inkscape converts those vectors to PNG/PDF; default KiCad PDF page exports
clip negative coordinates. These files are inspection views, not Gerbers.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / 'DRV8701_DUAL_12V.kicad_pcb'
ENV = dict(os.environ)
for name, subdir in [('KICAD_CONFIG_HOME', 'kicad-config'),
                     ('XDG_CONFIG_HOME', 'config'),
                     ('XDG_CACHE_HOME', 'cache'),
                     ('XDG_DATA_HOME', 'share')]:
    ENV.setdefault(name, '/workspace/scratch/' + subdir)
    Path(ENV[name]).mkdir(parents=True, exist_ok=True)

def run(*args):
    subprocess.run(args, cwd=ROOT, env=ENV, check=True)

def export_svg(target, layers, mirror=False):
    args = ['kicad-cli', 'pcb', 'export', 'svg', '--mode-single',
            '--layers', layers, '--fit-page-to-board',
            '--exclude-drawing-sheet', '--output', str(target)]
    if mirror:
        args.append('--mirror')
    run(*args, str(PCB))
    target.write_text(''.join(line.rstrip() + '\n'
                              for line in target.read_text().splitlines()))

source_sha = hashlib.sha256(PCB.read_bytes()).hexdigest()
files = []
for side, layers in [('top', 'F.Cu,F.SilkS,Edge.Cuts'),
                     ('bottom', 'B.Cu,B.SilkS,Edge.Cuts')]:
    svg = ROOT / ('pcb_' + side + '.svg')
    png = svg.with_suffix('.png')
    export_svg(svg, layers, mirror=(side == 'bottom'))
    run('inkscape', str(svg), '--export-type=png',
        '--export-filename=' + str(png), '--export-width=975',
        '--export-background=white', '--export-background-opacity=1')
    files.extend([svg, png])

layer_dir = ROOT / 'pcb_layer_pdfs'
layer_dir.mkdir(exist_ok=True)
writer = PdfWriter()
layers = [('F.Cu', 'F_Cu'), ('In1.Cu', 'In1_Cu'),
          ('In2.Cu', 'In2_Cu'), ('B.Cu', 'B_Cu'),
          ('F.SilkS', 'F_Silkscreen')]
with tempfile.TemporaryDirectory(prefix='drv8701-previews-', dir='/workspace/scratch') as temporary:
    for layer, suffix in layers:
        svg = Path(temporary) / (suffix + '.svg')
        pdf = layer_dir / ('DRV8701_DUAL_12V-' + suffix + '.pdf')
        export_svg(svg, layer + ',Edge.Cuts')
        run('inkscape', str(svg), '--export-type=pdf',
            '--export-filename=' + str(pdf))
        reader = PdfReader(pdf)
        assert len(reader.pages) == 1
        writer.add_page(reader.pages[0])
        files.append(pdf)
combined = ROOT / 'PCB_layers_review.pdf'
writer.add_metadata({'/Title': 'DRV8701 Rev B: F.Cu, In1.Cu, In2.Cu, B.Cu, F.SilkS',
                     '/Subject': 'CAD inspection views; PCB SHA256 ' + source_sha})
with combined.open('wb') as stream:
    writer.write(stream)
assert len(PdfReader(combined).pages) == len(layers)
assert hashlib.sha256(PCB.read_bytes()).hexdigest() == source_sha
files.append(combined)
report = {'generated_utc': datetime.now(timezone.utc).isoformat(),
          'pcb_sha256': source_sha, 'source_unchanged': True,
          'vector_pdf_pages': len(layers),
          'pdf_layer_order': [layer for layer, _ in layers],
          'bottom_png_svg_view': 'mirrored, viewed from bottom',
          'pdf_layer_view': 'unmirrored, viewed through top',
          'pcb_geometry_modified': False,
          'files_sha256': {f.relative_to(ROOT).as_posix():
                           hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(ROOT / 'validation/preview_exports.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'pages': len(layers), 'pcb_sha256': source_sha, 'files': len(files)}))
