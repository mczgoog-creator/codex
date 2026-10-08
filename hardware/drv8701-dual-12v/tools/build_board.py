#!/usr/bin/python3
"""Explicit, manually planned placement and copper paths. No autorouter or pathfinder."""
import json, math, os
from pathlib import Path
os.environ.setdefault('KICAD_CONFIG_HOME','/workspace/scratch/kicad-config')
Path(os.environ['KICAD_CONFIG_HOME']).mkdir(parents=True,exist_ok=True)
import pcbnew as p

ROOT=Path(__file__).resolve().parents[1]
SOURCE=json.loads((ROOT/'source_netlist.json').read_text())
BOARD=p.BOARD(); BOARD.SetCopperLayerCount(4)
MM=p.FromMM
def xy(q): return p.VECTOR2I(MM(q[0]),MM(q[1]))
def pt(q): return (p.ToMM(q.x),p.ToMM(q.y))
NETS={}
for name in SOURCE['nets']:
    n=p.NETINFO_ITEM(BOARD,name); BOARD.Add(n); NETS[name]=n
PARTS={}; ROUTES=[]

def numeric(c):
    q=c['pins']
    if c['kind']=='n_channel_mosfet': return {str(i):q['S' if i<=3 else 'G' if i==4 else 'D'] for i in range(1,9)}
    if c['kind']=='electrolytic_capacitor': return {'1':q['+'],'2':q['-']}
    if c['kind']=='zener_diode': return {'1':q['K'],'2':q['A']}
    if c['kind']=='led': return {'1':q['K'],'2':q['A']}
    return q

def place(ref, footprint, at, angle=0):
    c=next(c for c in SOURCE['components'] if c['ref']==ref)
    f=p.FootprintLoad(str(ROOT/'DRV8701_Custom.pretty'),footprint)
    assert f is not None, footprint
    f.SetFPID(p.LIB_ID('DRV8701_Custom',footprint))
    f.SetReference(ref); f.SetValue(c['value']); f.SetPosition(xy(at)); f.SetOrientationDegrees(angle)
    for pad in f.Pads():
        name=numeric(c).get(pad.GetNumber())
        if name: pad.SetNet(NETS[name])
    f.Reference().SetVisible(False); f.Value().SetVisible(False)
    BOARD.Add(f); PARTS[ref]=f
    return f

def pad(ref, num):
    choices=[z for z in PARTS[ref].Pads() if z.GetNumber()==str(num)]
    assert choices,(ref,num)
    # Number 5 is shared by the exposed drain and a lead. Prefer the lead.
    return min(choices,key=lambda z:z.GetSize().x*z.GetSize().y)
def loc(ref,num): return pt(pad(ref,num).GetPosition())
def net(ref,num): return pad(ref,num).GetNetname()

def route(name,layer,width,*points):
    for a,b in zip(points,points[1:]):
        if math.dist(a,b)<1e-6: continue
        t=p.PCB_TRACK(BOARD); t.SetStart(xy(a)); t.SetEnd(xy(b)); t.SetWidth(MM(width)); t.SetLayer(layer); t.SetNet(NETS[name]); BOARD.Add(t)
        ROUTES.append({'net':name,'layer':p.LayerName(layer),'width_mm':width,'start_mm':a,'end_mm':b})

def via(name,at,diam=.45,drill=.20):
    v=p.PCB_VIA(BOARD); v.SetPosition(xy(at)); v.SetWidth(p.F_Cu,MM(diam)); v.SetDrill(MM(drill)); v.SetViaType(p.VIATYPE_THROUGH); v.SetLayerPair(p.F_Cu,p.B_Cu); v.SetNet(NETS[name]); BOARD.Add(v)
    return at

def escape(ref,num,at,width=.2):
    name=net(ref,num); route(name,p.F_Cu,width,loc(ref,num),at); return via(name,at)

def label(txt,at,size=.65,layer=p.F_SilkS,angle=0):
    size=max(.6,size)
    t=p.PCB_TEXT(BOARD);t.SetText(txt);t.SetPosition(xy(at));t.SetTextSize(xy((size,size)));t.SetTextThickness(MM(.11));t.SetLayer(layer);t.SetTextAngle(p.EDA_ANGLE(angle,p.DEGREES_T));t.SetMirrored(layer==p.B_SilkS); BOARD.Add(t)

# Exact placement: all components on the top. Coordinates are in millimetres.
for ref,x in [('CN1',8),('P2',24),('CN2',40)]: place(ref,'AMASS_XT30UPB_M_SourceNumbering',(x,3.6))
place('C15','CP_Radial_D10.0mm_P5.00mm',(24,12.6))
for offset,driver,qrefs,crefs in [
    (0,'U1',['Q1','Q2','Q3','Q4'],['C1','C2','C3','C4','C5','C6']),
    (27.5,'U2',['Q5','Q6','Q7','Q8'],['C8','C9','C10','C11','C12','C13'])]:
    place(driver,'DRV8701_RGE24',(10.25+offset,19),270)
    for ref,x,y in zip(qrefs,[4.5,4.5,16,16],[11,23,11,23]): place(ref,'TPH1R403NL_SOPAdvance',(x+offset,y))
    coords=[(9.85,14.3,0),(12.3,14.95,90),(16.1,16.2,0),(10.25,9.7,0),(6.4,15.7,180),(6.1,18.2,180)]
    for ref,(x,y,a) in zip(crefs,coords): place(ref,'C_0603_1608Metric',(x+offset,y),a)
place('CN3','XH2.54_1x04_Vertical',(16,31.175))
place('U5','SS12D10G4',(40.5,31.5))
for ref,at in [('C16',(2.7,31.5)),('C17',(27.1,31.5))]: place(ref,'C_0603_1608Metric',at)
for ref,at in [('R8',(6.7,31.5)),('R9',(31,31.5))]: place(ref,'R_1210_3225Metric',at)
for ref,at in [('R1',(24,19.7)),('R7',(23,24)),('R5',(27.6,24))]: place(ref,'R_0603_1608Metric',at)
place('D1','D_SOD123',(26.7,21.8))
place('LED2','LED_0603_1608Metric',(23,26.4));place('LED1','LED_0603_1608Metric',(27.6,26.4))

# 12 V rail: 1.8 mm external copper for the combined 3.6 A stall current.
route('VM',p.F_Cu,1.8,(2.595,8),(45.405,8))
route('VM',p.F_Cu,1.8,loc('P2',1),(26.5,8))
route('VM',p.F_Cu,1.8,(21.5,8),loc('C15',1))

for off,u,qs,cs,prefix in [
    (0,'U1',['Q1','Q2','Q3','Q4'],['C1','C2','C3','C4','C5','C6'],'L'),
    (27.5,'U2',['Q5','Q6','Q7','Q8'],['C8','C9','C10','C11','C12','C13'],'R')]:
    def q(x,y): return (x+off,y)
    higha,lowa,highb,lowb=qs; cp,vc,vmcap,vmfar,av,dv=cs
    # Three parallel source leads collected before the 0.70 mm motor path.
    for ref in qs:
        source=net(ref,1); a=loc(ref,1); c=loc(ref,3); y=a[1]+.55
        for i in (1,2,3): route(source,p.F_Cu,.5,loc(ref,i),(loc(ref,i)[0],y))
        route(source,p.F_Cu,.7,(a[0],y),(c[0],y))
    for hi,lo in [(higha,lowa),(highb,lowb)]:
        name=net(hi,1); x=loc(hi,1)[0]
        route(name,p.F_Cu,.7,(x,loc(hi,1)[1]+.55),(x,loc(lo,8)[1]),loc(lo,8))
    # Source-return current enters the uninterrupted ground plane through two
    # 0.3 mm drilled vias per low-side FET; individual source pads also flood.
    for lo in [lowa,lowb]:
        for i in (1,3):
            a=loc(lo,i); at=(a[0],26.4)
            route('GND',p.F_Cu,.7,(a[0],a[1]+.55),at);via('GND',at,.65,.3)
    # QFN ground/EP/SN/SP bonds, per TI layout recommendation.
    for i,end in [(5,q(9.5,17.7)),(16,q(10.5,20.3)),(20,q(11.5,19.75)),(21,q(11.5,19.25))]: route('GND',p.F_Cu,.2,loc(u,i),end)
    for x in [9.45,11.05]:
        for y in [18.2,19.8]:via('GND',q(x,y),.40,.20)
    # Pump capacitors: no values or electrical connections have been changed.
    route(prefix+'_CPL',p.F_Cu,.2,loc(u,4),q(10,16.1),q(9.05,15.15),loc(cp,1))
    route(prefix+'_CPH',p.F_Cu,.2,loc(u,3),q(10.5,16.1),q(10.65,15.95),loc(cp,2))
    route(prefix+'_VCP',p.F_Cu,.2,loc(u,2),q(11,16.6),loc(vc,1))
    route('VM',p.F_Cu,.3,loc(vc,2),q(12.3,8))
    route('VM',p.F_Cu,.3,loc(u,1),q(13.35,16.6),q(13.2,14.7),loc(vc,2))
    route('VM',p.F_Cu,.3,loc(vmfar,1),(loc(vmfar,1)[0],8))
    for cap,at in [(vmfar,(loc(vmfar,2)[0],10.6)),(av,(loc(av,2)[0],16.9)),(dv,(loc(dv,2)[0],19.1)),(vmcap,(loc(vmcap,2)[0]+.8,16.2))]:escape(cap,2,at)
    route(prefix+'_AVDD',p.F_Cu,.2,loc(u,7),q(8.35,16.9),loc(av,1))
    route(prefix+'_AVDD',p.F_Cu,.2,loc(u,6),q(9,16),loc(av,1))
    va=escape(u,12,q(7.7,20.25));vb=escape(av,1,q(7.4,15.5))
    route(prefix+'_AVDD',p.B_Cu,.2,va,q(8.2,20.75),q(8.2,15.5),vb)
    route(prefix+'_DVDD',p.F_Cu,.2,loc(u,8),loc(dv,1))
    vm1=via('VM',q(13.35,16.6));vm2=escape(vmcap,1,(loc(vmcap,1)[0],17),.3)
    route('VM',p.In2_Cu,.3,vm1,vm2)
    # Individually chosen gate and Kelvin sense routes. No automatic routing.
    gh2=escape(u,24,q(12.8,17.75),.25);g2=escape(higha,4,q(7.15,13.77),.25)
    route(prefix+'_GH2',p.In2_Cu,.25,gh2,q(12.8,12.6),q(7.15,12.6),g2)
    gl2=escape(u,22,q(12.8,18.75),.25);l2=escape(lowa,4,q(7.15,25.77),.25)
    route(prefix+'_GL2',p.In2_Cu,.25,gl2,q(6.8,18.75),q(6.8,25.77),l2)
    gh1=escape(u,17,q(11,21.65),.25);g1=escape(highb,4,q(18.655,13.77),.25)
    route(prefix+'_GH1',p.B_Cu,.25,gh1,q(10.65,22),q(10.65,23.4),q(13.6,23.4),q(18.655,18.345),g1)
    gl1=escape(u,19,q(12.8,20.25),.25);l1=escape(lowb,4,q(18.655,25.77),.25)
    route(prefix+'_GL1',p.In2_Cu,.25,gl1,q(18.655,20.25),l1)
    outa=via(prefix+'_A',q(2.595,15),.8,.4);route(prefix+'_A',p.F_Cu,.7,q(2.595,14.32),outa)
    outb=via(prefix+'_B',q(16.3,15),.8,.4);route(prefix+'_B',p.F_Cu,.7,q(16.3,14.32),outb)
    s2=escape(u,23,q(13.35,18.25));route(prefix+'_A',p.B_Cu,.2,s2,q(13.35,19.5),q(11.8,19.5),q(11.8,14.7),q(2.595,14.7),outa)
    s1=escape(u,18,q(11.5,22.25));route(prefix+'_B',p.In2_Cu,.2,s1,q(12,22.75),q(12,19.35),q(16.3,19.35),outb)
    if prefix=='R':via(prefix+'_B',q(14.095,21),.6,.3)
    escape(u,13,q(9,21.6));escape(u,15,q(10,22.8))

# Motor-output copper on the bottom is also 0.70 mm. The power connector is
# correctly renumbered to match the PDF (1 positive, 2 negative).
route('L_A',p.B_Cu,.7,(2.595,15),(1.3,13.705),(1.3,6.8),(7.4,6.8),loc('CN1',1))
route('L_B',p.B_Cu,.7,(16.3,15),(19.2,12.1),(19.2,1),(5.5,1),loc('CN1',2))
route('R_A',p.B_Cu,.7,(30.095,15),(29.3,14.205),(29.3,6.8),(39.3,6.8),loc('CN2',1))
route('R_B',p.B_Cu,.7,(43.8,15),(46.7,12.1),(46.7,1),(37.5,1),loc('CN2',2))

# Faithful RC snubbers, with 1210 / >=0.5 W resistors for <=20 kHz EN PWM.
route('L_SNUBBER',p.F_Cu,.25,loc('C16',2),loc('R8',1))
route('R_SNUBBER',p.F_Cu,.25,loc('C17',2),loc('R9',1))
route('L_A',p.F_Cu,.25,loc('C16',1),(1.4,31.5),(1.4,20.23),(2.595,20.23))
v=escape('R8',2,(8.25,28.8),.25);w=via('L_B',(8.25,26.8));route('L_B',p.B_Cu,.25,v,w);route('L_B',p.F_Cu,.25,w,(12.7,26.8),(12.7,21),(14.095,21))
v=escape('R9',2,(32.55,28.8),.25);route('R_B',p.In2_Cu,.25,v,(38.3,28.8),(38.3,25.6),(41.595,25.6),(41.595,21))
a=escape('C17',1,(26.3,28.6),.25);b=via('R_A',(26.3,27.45),.4,.2)
route('R_A',p.In2_Cu,.2,a,b);route('R_A',p.F_Cu,.25,b,(25.7,26.85),(25.7,23.1),(30.095,23.1),(30.095,21))

# Original shunt-Zener supply, enable switch and the two original LED circuits.
v=escape('R1',1,(23.2,19.2),.25);route('VM',p.B_Cu,.25,v,(23.2,14.3),loc('C15',1))
route('3V3',p.F_Cu,.25,loc('R1',2),(24.8,21.35),loc('D1',1))
route('3V3',p.F_Cu,.25,loc('R1',2),(24.8,21.4),loc('R7',1))
for ref in ['LED1','LED2']:escape(ref,1,(loc(ref,1)[0],26.4))
escape('D1',2,(28.35,21.0))
for r,l in [('R5','LED1'),('R7','LED2')]:route(net(r,2),p.F_Cu,.2,loc(r,2),loc(l,2))
v=escape('R7',1,(21.5,24));w=via('3V3',(21.5,27.5));route('3V3',p.B_Cu,.2,v,w);route('3V3',p.In2_Cu,.2,w,(21.5,29.3),(45.3,29.3),loc('U5',3))
v=escape('R5',1,(27.5,24));route('NSLEEP',p.B_Cu,.2,v,(27.5,28))
route('NSLEEP',p.B_Cu,.2,(9,21.6),(9,28),(40.5,28),loc('U5',2))
route('NSLEEP',p.B_Cu,.2,(36.5,21.6),(36.5,28))

# Four control signals. CN3 deliberately has no added ground pin.
v=escape('U1',14,(9.5,22.2));w=via('L_EN_IN',(7.7,24));route('L_EN_IN',p.In2_Cu,.2,v,w);route('L_EN_IN',p.B_Cu,.2,w,(7.7,29.7),(19.81,29.7),loc('CN3',4))
route('L_PH_IN',p.In2_Cu,.2,(10,22.8),(10,29.3),(17.27,29.3),loc('CN3',3))
route('R_EN_IN',p.F_Cu,.2,loc('U2',14),(37,28.1),(12.19,28.1),loc('CN3',1))
route('R_PH_IN',p.In2_Cu,.2,(37.5,22.8),(37.5,27),(14.73,27),(14.73,28.65))
via('R_PH_IN',(14.73,28.65));route('R_PH_IN',p.F_Cu,.2,(14.73,28.65),loc('CN3',2))

# Board outline and deliberately placed readable reference legends.
for a,b in [((0,0),(48,0)),((48,0),(48,36)),((48,36),(0,36)),((0,36),(0,0))]:
    d=p.PCB_SHAPE(BOARD);d.SetShape(p.SHAPE_T_SEGMENT);d.SetStart(xy(a));d.SetEnd(xy(b));d.SetWidth(MM(.05));d.SetLayer(p.Edge_Cuts);BOARD.Add(d)
for ref,at in [('CN1',(8,7)),('P2',(17.5,5.8)),('CN2',(40,7)),('C15',(27.8,18.3)),('U1',(10.25,24.9)),('U2',(37.75,24.9)),('CN3',(16,35.35)),('U5',(42.85,29.1))]:label(ref,at,.6)
for ref,x,y in [('Q1',.9,11),('Q2',.9,23),('Q3',12,11),('Q4',12,24.2),('Q5',30,17),('Q6',31,27.35),('Q7',47,11),('Q8',47,23)]:label(ref,(x,y),.6)
for off,refs in [(0,['C1','C2','C3','C4','C5','C6']),(27.5,['C8','C9','C10','C11','C12','C13'])]:
    for ref,(x,y) in zip(refs,[(9.85,12.9),(14.3,17.5),(16.1,17.7),(10.25,11.25),(3.8,16),(3.8,18.2)]):label(ref,(x+off,y),.6)
for ref,at in [('R1',(23,18.3)),('D1',(26.7,19.8)),('R7',(23,22.5)),('R5',(25.2,24)),('LED2',(23,28)),('LED1',(28,28)),('C16',(2.7,30)),('C17',(27.1,30)),('R8',(6.7,29.15)),('R9',(31,29.15))]:label(ref,at,.6)
label('DRV8701 DUAL / 12V',(13,34.2),.65,p.B_SilkS)
label('SOURCE VALUES / REV A',(33,34.2),.65,p.B_SilkS)

def pour(layer):
    z=p.ZONE(BOARD);z.SetLayer(layer);z.SetNet(NETS['GND']);z.SetLocalClearance(MM(.15));z.SetThermalReliefGap(MM(.25));z.SetThermalReliefSpokeWidth(MM(.5));z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.SetMinThickness(MM(.15));z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
    poly=z.Outline();poly.NewOutline()
    for q in [(0.4,.4),(47.6,.4),(47.6,35.6),(.4,35.6)]:poly.Append(xy(q))
    BOARD.Add(z)
for layer in [p.F_Cu,p.In1_Cu,p.B_Cu]:pour(layer)
BOARD.BuildListOfNets();BOARD.SynchronizeNetsAndNetClasses(False)
filename=ROOT/'DRV8701_DUAL_12V.kicad_pcb';p.SaveBoard(str(filename),BOARD)
BOARD=p.LoadBoard(str(filename))
p.ZONE_FILLER(BOARD).Fill(BOARD.Zones());p.SaveBoard(str(filename),BOARD)
# Nominal 1.6 mm four-layer, 1 oz copper on every layer. Board-house process
# tolerances and the final prepreg/core selection remain procurement details.
stack='''\n\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.04) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t\t(edge_connector no)
\t\t\t(castellated_pads no)
\t\t\t(edge_plating no)
\t\t)'''
text=filename.read_text();assert text.count('\t(setup\n')==1
filename.write_text(text.replace('\t(setup\n','\t(setup'+stack+'\n',1))
# SaveBoard's default project initialization can replace the design defaults.
# Write the intended manufacturing constraints explicitly after board save.
pro=ROOT/'DRV8701_DUAL_12V.kicad_pro'; settings=json.loads(pro.read_text())
rules=settings['board']['design_settings']['rules']
rules.update({'min_clearance':.15,'min_track_width':.15,'min_via_diameter':.4,'min_through_hole_diameter':.2,'min_via_annular_width':.1,'min_hole_clearance':.2,'min_hole_to_hole':.25,'min_silk_clearance':.15,'min_text_height':.6,'min_text_thickness':.08})
settings['board']['design_settings']['drc_exclusions']=[]
for c in settings['net_settings']['classes']:
    if c['name']=='Default':c.update({'clearance':.15,'track_width':.2,'via_diameter':.45,'via_drill':.2})
pro.write_text(json.dumps(settings,indent=2)+'\n')
(ROOT/'manual_routes.json').write_text(json.dumps({'autorouter_used':False,'pathfinder_used':False,'method':'Every component and segment explicitly hand-planned in tools/build_board.py; geometric DRC guides manual revisions. Copper-pour filling is CAD polygon filling, not routing.','segments':ROUTES},indent=2))
print(json.dumps({'board':str(filename),'components':len(PARTS),'nets':len(NETS),'segments':len(ROUTES),'vias':sum(isinstance(x,p.PCB_VIA) for x in BOARD.GetTracks()),'dimensions_mm':[48,36],'copper_layers':4,'autorouter_used':False}))
