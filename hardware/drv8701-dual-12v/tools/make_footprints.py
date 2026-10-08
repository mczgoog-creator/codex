#!/usr/bin/env python3
"""Generate the project's hand-solderable, body-centred footprint library.

No PCB, routes or design nets are generated. Dimensions are explicit engineering
choices or reference-derived values. SS12D10G4 matches the exact native JLC library
device HX SS12D10G4 (C5149841), not a guessed generic slide-switch.
"""
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'DRV8701_Custom.pretty'
LIB.mkdir(exist_ok=True)
MANIFEST = {}

def n(v):
    return ('%.6f' % v).rstrip('0').rstrip('.') or '0'

class Footprint:
    def __init__(self, name, description, attr='smd', source=None):
        self.name, self.description, self.source = name, description, source
        self.parts = [f'(footprint "{name}" (version 20240108) (generator "manual_dr8701_project") (layer "F.Cu")',
                      f'  (descr {json.dumps(description)})',
                      f'  (attr {attr})',
                      '  (fp_text reference "REF**" (at 0 -4.2) (layer "F.SilkS") (effects (font (size 0.7 0.7) (thickness 0.12))))',
                      f'  (fp_text value "{name}" (at 0 4.2) (layer "F.Fab") (hide yes) (effects (font (size 0.7 0.7) (thickness 0.12))))']
        self.pads = []
        self.courtyard = None
        self.origin = 'body_center_mm'
        self.body_offset = [0, 0]
    def line(self, x1,y1,x2,y2, layer='F.SilkS', width=.12):
        self.parts.append(f'  (fp_line (start {n(x1)} {n(y1)}) (end {n(x2)} {n(y2)}) (stroke (width {n(width)}) (type solid)) (layer "{layer}"))')
    def rect(self,x1,y1,x2,y2,layer='F.Fab',width=.1):
        self.parts.append(f'  (fp_rect (start {n(x1)} {n(y1)}) (end {n(x2)} {n(y2)}) (stroke (width {n(width)}) (type solid)) (fill none) (layer "{layer}"))')
    def circle(self,x,y,r,layer='F.Fab',width=.1):
        self.parts.append(f'  (fp_circle (center {n(x)} {n(y)}) (end {n(x+r)} {n(y)}) (stroke (width {n(width)}) (type solid)) (fill none) (layer "{layer}"))')
    def text(self,txt,x,y,size=.7,layer='F.SilkS'):
        self.parts.append(f'  (fp_text user {json.dumps(txt)} (at {n(x)} {n(y)}) (layer "{layer}") (effects (font (size {n(size)} {n(size)}) (thickness .12))))')
    def pad(self,num,x,y,sx,sy,kind='smd',shape='roundrect',drill=None,roundratio=.2,role=None):
        layers='"F.Cu" "F.Paste" "F.Mask"' if kind=='smd' else '"*.Cu" "*.Mask"'
        dr=(' (drill oval '+n(drill[0])+' '+n(drill[1])+')') if isinstance(drill,(list,tuple)) else (f' (drill {n(drill)})' if drill else '')
        rr=f' (roundrect_rratio {n(roundratio)})' if shape=='roundrect' else ''
        self.parts.append(f'  (pad "{num}" {kind} {shape} (at {n(x)} {n(y)}) (size {n(sx)} {n(sy)}){dr} (layers {layers}){rr})')
        self.pads.append({'number':str(num),'x_mm':x,'y_mm':y,'size_x_mm':sx,'size_y_mm':sy,'type':kind,'shape':shape,'drill_mm':drill,'role':role})
    def court(self,x1,y1,x2,y2):
        self.courtyard=[x1,y1,x2,y2]
        self.rect(x1,y1,x2,y2,'F.CrtYd',.05)
    def save(self):
        p=LIB/(self.name+'.kicad_mod')
        p.write_text('\n'.join(self.parts+[')'])+'\n')
        MANIFEST[self.name]={'description':self.description,'origin':self.origin,'body_center_offset_mm':self.body_offset,'source':self.source,'pads':self.pads,'courtyard_mm':self.courtyard,'file':str(p)}

def passive(name,bodyx,bodyy,padcenter,padx,pady,led=False):
    p=Footprint(name,'Hand-solderable metric passive; body-centred; '+ ('pin1 cathode, pin2 anode' if led else 'symmetric two-terminal passive'))
    p.pad(1,-padcenter,0,padx,pady,role='K' if led else None)
    p.pad(2,padcenter,0,padx,pady,role='A' if led else None)
    p.rect(-bodyx/2,-bodyy/2,bodyx/2,bodyy/2)
    ey=max(bodyy/2,pady/2)+.30
    p.line(-.25,-ey,.25,-ey)
    p.line(-.25,ey,.25,ey)
    if led:
        ex=padcenter+padx/2+.32
        p.line(-ex,-ey,-ex,ey)
    p.court(-max(bodyx/2,padcenter+padx/2)-.25,-max(bodyy/2,pady/2)-.25,max(bodyx/2,padcenter+padx/2)+.25,max(bodyy/2,pady/2)+.25)
    p.save()

def main():
    p=Footprint('DRV8701_RGE24','TI RGE0024F VQFN24 4x4mm P0.5; pads0.24x0.6, opposite pad-centre3.8mm, EP2.8x2.8. EP pin25 GND. Hot-air/paste required for reliable centre-pad soldering.',source='Texas Instruments DRV8701 datasheet RGE0024F recommended land pattern; verified /workspace/scratch/datasheets/drv8701-ti-github-mirror.pdf')
    for i in range(6):
        p.pad(i+1,-1.9,-1.25+i*.5,.6,.24)
        p.pad(i+7,-1.25+i*.5,1.9,.24,.6)
        p.pad(i+13,1.9,1.25-i*.5,.6,.24)
        p.pad(i+19,1.25-i*.5,-1.9,.24,.6)
    p.pad(25,0,0,2.8,2.8,shape='rect',role='GND_EP')
    p.rect(-2,-2,2,2)
    for sx in [-1,1]:
        for sy in [-1,1]:
            p.line(sx*1.68,sy*2.40,sx*2.40,sy*2.40)
            p.line(sx*2.40,sy*1.68,sx*2.40,sy*2.40)
    p.circle(-2.70,-1.25,.13,'F.SilkS',.12)
    p.court(-2.5,-2.5,2.5,2.5)
    p.save()

    p=Footprint('TPH1R403NL_SOPAdvance','TPH1R403NL SOP Advance 5x5 body / nominal6mm lead span; source1-3, gate4, drain5-8 and exposed-drain pad5. JLC native footprint crosscheck. Exact Toshiba part land-pattern PDF still unavailable: hardware review required before fabrication.',source='Native JLC footprint 572e0c5f381c446594eedc8b8157fefb.efoo from public project mirror-zdxddmx/eda/ProPrj_DRV8701电机双驱.epro; only library geometry reused, board layout not reused.')
    for i,x in enumerate([-1.905,-.635,.635,1.905],1):
        p.pad(i,x,2.77,.5,1.2,role='G' if i==4 else 'S')
    for i,x in enumerate([1.905,.635,-.635,-1.905],5):
        p.pad(i,x,-2.77,.5,1.2,role='D')
    p.pad(5,0,-.45,4.25,3.5,shape='rect',role='D_EP')
    p.rect(-2.5,-2.5,2.5,2.5)
    p.line(-2.60,-2.5,-2.60,2.5)
    p.line(2.60,-2.5,2.60,2.5)
    p.circle(-1.905,3.64,.10,'F.SilkS',.10)
    p.court(-2.75,-3.70,2.75,3.70)
    p.save()

    passive('C_0603_1608Metric',1.6,.8,.8,.95,.95)
    passive('R_0603_1608Metric',1.6,.8,.8,.95,.95)
    passive('LED_0603_1608Metric',1.6,.8,.8,.95,.95,True)
    passive('R_1210_3225Metric',3.2,2.5,1.55,1.15,2.7)

    p=Footprint('D_SOD123','SOD-123 BZT52 family 2-pin; pin1 cathode, pin2 anode; verify selected manufacturer; hand-solderable pads.',source='Industry SOD-123 body nominal2.8x1.8mm, lead-span nominal3.7mm')
    p.pad(1,-1.65,0,1.1,1.25,role='K')
    p.pad(2,1.65,0,1.1,1.25,role='A')
    p.rect(-1.4,-.9,1.4,.9)
    p.line(-1.1,-.9,-1.1,.9,'F.Fab',.12)
    p.line(-1.1,-1.03,1.1,-1.03)
    p.line(-1.1,1.03,1.1,1.03)
    # Short second dash above the cathode-side end of the body; no pad enclosure.
    p.line(-1.1,-1.30,-.65,-1.30)
    p.court(-2.45,-1.25,2.45,1.25)
    p.save()

    p=Footprint('CP_Radial_D10.0mm_P5.00mm','470uF radial electrolytic procurement envelope: body diameter10mm, pitch5mm, positive1 atx-2.5. Select a real25V low-ESR part within this envelope; voltage/capacitance/height not guaranteed by footprint.',attr='through_hole',source='Explicit PCB procurement envelope; real capacitor manufacturer still to be selected and checked')
    p.pad(1,-2.5,0,2.0,2.0,kind='thru_hole',shape='rect',drill=.9,role='+')
    p.pad(2,2.5,0,2.0,2.0,kind='thru_hole',shape='circle',drill=.9,role='-')
    p.circle(0,0,5)
    p.circle(0,0,5.13,'F.SilkS',.12)
    p.text('+',-3.3,-2.0,.9)
    p.line(.7,-4.8,.7,4.8,'F.Fab',.1)
    p.circle(0,0,5.25,'F.CrtYd',.05)
    p.courtyard=[-5.25,-5.25,5.25,5.25]
    p.save()

    src='https://raw.githubusercontent.com/KiCad/kicad-footprints/master/Connector_AMASS.pretty/AMASS_XT30UPB-M_1x02_P5.0mm_Vertical.kicad_mod'
    p=Footprint('AMASS_XT30UPB_M_SourceNumbering','AMASS XT30UPB-M vertical male. Source numbering1=positive/right,2=negative/left. Official KiCad library physical polarity retained but pad numbers reversed and origin translated to body centre. Body10.2x5.2mm,pitch5mm,drill1.8mm.',attr='through_hole',source=src+' ; upstream manufacturer link https://www.tme.eu/en/Document/4acc913878197f8c2e30d4b8cdc47230/XT30UPB%20SPEC.pdf')
    # Original origin is physical negative terminal; translate x by -2.5.
    for layer,w,offset in [('F.Fab',.1,0),('F.SilkS',.12,.11)]:
        pts=[(-5.1-offset,-1.3-offset),(-3.4-offset,-2.6-offset),(5.1+offset,-2.6-offset),(5.1+offset,2.6+offset),(-3.4-offset,2.6+offset),(-5.1-offset,1.3+offset)]
        for a,b in zip(pts,pts[1:]+pts[:1]):p.line(*a,*b,layer,w)
    p.pad(2,-2.5,0,3,3,kind='thru_hole',shape='rect',drill=1.8,role='negative')
    p.pad(1,2.5,0,3,3,kind='thru_hole',shape='circle',drill=1.8,role='positive')
    p.text('-',-2.5,-2.15,.7)
    p.text('+',2.5,-2.15,.7)
    pts=[(-5.6,-1.8),(-3.9,-3.1),(5.6,-3.1),(5.6,3.1),(-3.9,3.1),(-5.6,1.8)]
    for a,b in zip(pts,pts[1:]+pts[:1]):p.line(*a,*b,'F.CrtYd',.05)
    p.courtyard=[-5.6,-3.1,5.6,3.1]
    p.save()

    p=Footprint('XH2.54_1x04_Vertical','Source XH2.54-4P retained. Four pins pitch2.54mm, pin-row-centred origin; body centre is(0,+0.525mm). Imported JST XH2.50 body envelope enlarged0.12mm for pitch; not an interchangeable JST-certified part. Verify domestic connector real housing/lock and pin dimensions before fabrication.',attr='through_hole',source='https://raw.githubusercontent.com/KiCad/kicad-footprints/master/Connector_JST.pretty/JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical.kicad_mod ; body envelope only, pitch intentionally changed to source2.54mm')
    p.origin='pin_row_center_mm'
    p.body_offset=[0,.525]
    for i,x in enumerate([-3.81,-1.27,1.27,3.81],1):
        p.pad(i,x,0,1.8,1.8,kind='thru_hole',shape='rect' if i==1 else 'circle',drill=1.0)
    # For body-centred origin, row is0.525mm above body centre in JST envelope;
    # requirement fixes rowy=0, so use the unchanged original asymmetry.
    p.rect(-6.26,-2.35,6.26,3.4)
    p.rect(-6.37,-2.46,6.37,3.51,'F.SilkS',.12)
    p.line(-4.42,-2.45,-3.81,-1.75,'F.Fab',.1)
    p.line(-3.81,-1.75,-3.20,-2.45,'F.Fab',.1)
    p.text('1',-3.81,-1.6,.7)
    p.court(-6.76,-2.85,6.76,3.9)
    p.save()

    p=Footprint('SS12D10G4','Exact native JLC footprint SW-TH_SHOU-HAN_SS12D10G4 for HX SS12D10G4 C5149841. Body12.7x6.7mm,pitch4.8mm; vertical plated slots1.1x2.3mm with oval pads1.7x2.9mm. Common pin2; no invented mounting holes. Match real selected switch before fabrication.',attr='through_hole',source='Native JLC footprint6fe0c40ca65a4350ad02ae7d2df1c4e9.efoo in ProDoc_DRV8701单驱2_2025-04-30.epro; same PAD records in footprint ef13eca from a second exact same-model JLC project. Manufacturer attached PDF https://atta.szlcsc.com/upload/public/pdf/source/20220907/2020D7183ED16DD6E2B9F5A13FB144CF.pdf remains network-blocked.')
    for i,x in enumerate([-4.8,0,4.8],1):
        p.pad(i,x,0,1.7,2.9,kind='thru_hole',shape='oval',drill=[1.1,2.3],role='common' if i==2 else 'throw')
    p.rect(-6.35,-3.35,6.35,3.35)
    p.rect(-6.48,-3.48,6.48,3.48,'F.SilkS',.12)
    p.rect(-3.55,-1.8,3.55,1.8,'F.Fab',.10)
    for x in [-4.8,0,4.8]:
        p.text(str(1+int(round((x+4.8)/4.8))),x,-2.15,.6)
    p.court(-6.6,-3.6,6.6,3.6)
    p.save()

    (ROOT/'footprint_geometry.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'fp-lib-table').write_text('(fp_lib_table\n  (lib (name "DRV8701_Custom")(type "KiCad")(uri "${KIPRJMOD}/DRV8701_Custom.pretty")(options "")(descr "Project footprints; hardware review limitations recorded in footprint_geometry.json"))\n)\n')
    print(f'Wrote {len(MANIFEST)} footprints to {LIB}')

if __name__=='__main__':
    main()
