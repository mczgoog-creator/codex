#!/usr/bin/python3
"""Explicit, manually planned placement and copper paths. No autorouter or pathfinder."""
import json, math, os
from pathlib import Path
os.environ.setdefault('KICAD_CONFIG_HOME','/workspace/scratch/kicad-config')
Path(os.environ['KICAD_CONFIG_HOME']).mkdir(parents=True,exist_ok=True)
import pcbnew as p

ROOT=Path(__file__).resolve().parents[1]
SOURCE=json.loads((ROOT/'design_netlist.json').read_text())
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
    # Only bevel right-angle corners in an explicitly specified polyline.
    # This performs no obstacle search or automatic routing.
    smooth=[points[0]]
    for i,b in enumerate(points[1:-1],1):
        a,c=points[i-1],points[i+1]
        ab=(a[0]-b[0],a[1]-b[1]); cb=(c[0]-b[0],c[1]-b[1])
        la,lc=math.hypot(*ab),math.hypot(*cb)
        if la and lc and abs(ab[0]*cb[0]+ab[1]*cb[1])<1e-7:
            d=min(.4 if width>=.65 else .25,la*.25,lc*.25)
            smooth.extend([(b[0]+ab[0]/la*d,b[1]+ab[1]/la*d),
                           (b[0]+cb[0]/lc*d,b[1]+cb[1]/lc*d)])
        else:smooth.append(b)
    smooth.append(points[-1]); points=smooth
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

# Rev B functional floorplan. All components and all copper paths below are
# explicit human-chosen coordinates. Corner chamfering only rounds the chosen
# polyline; it neither finds paths nor places vias.
W,H=36,60
LEFT=-3
place('P2','AMASS_XT30UPB_M_SourceNumbering',(7,4.0))
place('SW1','SS12D10G4',(8.5,29.5))
place('U6','TPS25910_RSA16',(21,29.5))
place('C15','CP_Radial_D10.0mm_P5.00mm',(30,29.5))
place('C18','C_0805_2012Metric',(16.4,28.5),90)
place('C19','C_0603_1608Metric',(16.8,32.5),180)
for ref,at in [('R10',(17.1,25.85)),('R11',(20.3,25.8)),('R12',(21.6,33.25))]:
    place(ref,'R_0603_1608Metric',at)
place('CN3','XH2.54_1x04_Vertical',(9,56))
place('U5','SS12D10G4',(25,56))
for off,u,qs,cs,cn,sc,sr in [
    (0,'U1',['Q1','Q2','Q3','Q4'],['C1','C2','C3','C4','C5','C6'],'CN1','C16','R8'),
    (27,'U2',['Q5','Q6','Q7','Q8'],['C8','C9','C10','C11','C12','C13'],'CN2','C17','R9')]:
    place(u,'DRV8701_RGE24',(5.2,16.5+off),270)
    for ref,at in zip(qs,[(20.5,10+off),(12.5,10+off),(20.5,22+off),(12.5,22+off)]):
        place(ref,'TPH1R403NL_SOPAdvance',at,270)
    for ref,(x,y,a) in zip(cs,[(3.7,12.8,0),(6.8,13.2,0),(9.9,14,0),(25,10,270),(1.6,15.4,270),(1.6,18.46,270)]):
        place(ref,'C_0603_1608Metric',(x,y+off),a)
    place(cn,'AMASS_XT30UPB_M_SourceNumbering',(31,16.5+off),90)
    place(sc,'C_0603_1608Metric',(18,16.5+off))
    place(sr,'R_1210_3225Metric',(21.5,16.5+off),90)
place('R1','R_0603_1608Metric',(17.8,4.6))
place('D1','D_SOD123',(21.8,4.6))
for ref,at in [('R7',(27.3,2.1)),('R5',(27.3,6))]:
    place(ref,'R_0603_1608Metric',at)
place('LED2','LED_0603_1608Metric',(31.3,2.1),180)
place('LED1','LED_0603_1608Metric',(31.3,6),180)

def array(name,center,step=.8,diam=.65,drill=.3,layers=None):
    x,y=center
    sites=[(x-step/2,y-step/2),(x+step/2,y-step/2),
           (x-step/2,y+step/2),(x+step/2,y+step/2)]
    for at in sites:via(name,at,diam,drill)
    # Explicit collectors give all four barrels a copper path on both sides.
    for layer in (layers or [p.F_Cu,p.B_Cu]):
        route(name,layer,.7,sites[0],sites[1],sites[3],sites[2],sites[0])
        route(name,layer,.7,sites[0],sites[3])
    return sites

# Continuous source return plane: In1.Cu, no signal routes on that layer.
array('GND',(4.5,4.5),2.8)
array('GND',(32.5,29.5),1.8)
# Raw input power uses the bottom LEFT edge; motor outputs occupy the right.
raw_sites=array('VM_RAW',(16.5,29.5),1.0)
route('VM_RAW',p.B_Cu,1.8,loc('P2',1),(9.5,5),(7,7.5),(3.5,7.5),(1.8,7.5),(-1.2,10.5),
      (-1.2,29.2),(2.4,32.8),(14.8,32.8),(16.5,31.1),(16.5,29.5))
route('VM_RAW',p.F_Cu,1.8,(16.5,29.5),loc('C18',1))
route('VM_RAW',p.F_Cu,1.8,loc('C18',1),(17.95,29.5))
for i in [1,2,3]:
    a=loc('U6',i)
    route('VM_RAW',p.F_Cu,.45,a,(18.2,a[1]),(17.95,a[1]+.25 if i==1 else a[1]-.25)) if i!=2 else route('VM_RAW',p.F_Cu,.45,a,(17.95,a[1]))
route('VM_RAW',p.F_Cu,1.1,(17.95,28.775),(17.95,29.575))
for i in [10,11,12]:
    a=loc('U6',i)
    route('VM',p.F_Cu,.45,a,(23.75,a[1]),(24,a[1]+.25 if i==12 else a[1]-.25)) if i!=11 else route('VM',p.F_Cu,.45,a,(24,a[1]))
route('VM',p.F_Cu,1.1,(24,28.775),(24,29.575))
# C15's positive pin is the actual feed/split point, not a remote tee.
route('VM',p.F_Cu,1.8,(24,29.5),loc('C15',1))
route('VM',p.F_Cu,1.8,(27.5,8.595),loc('C15',1),(27.5,46.595))
array('VM',(27.5,29.5),1.8)
for x in [20.2,21.8]:
    for y in [28.7,30.3]:via('GND',(x,y),.4,.2)
for i in [5,6,8,9,13,14]:
    a=loc('U6',i)
    if i in [5,6,8]: end=(a[0],a[1]+.55)
    elif i==9:end=(a[0],a[1]+.7)
    else:end=(a[0],a[1]-.55)
    route('GND',p.F_Cu,.2,a,end);via('GND',end,.4,.2)
escape('C18',2,(15.5,27.5))
route('PWR_GATE',p.F_Cu,.2,loc('U6',4),(18.8,30.475),(17.6,31.675),loc('C19',1))
route('GND',p.F_Cu,.2,loc('C19',2),(16,32.7),(16.6,33.3),(16.8,33.3));via('GND',(16.8,33.3))
route('PWR_ILIM',p.F_Cu,.2,loc('U6',7),(21.325,32.725),loc('R12',1))
escape('R12',2,(22.4,34))
escape('R11',2,(21.1,25.0))
route('PWR_EN',p.F_Cu,.2,loc('R10',2),(18.5,25.8),loc('R11',1))
route('PWR_EN',p.F_Cu,.2,loc('R11',1),(20.025,26.325),loc('U6',16))
e=escape('R10',2,(18.1,25.3))
route('PWR_EN',p.B_Cu,.2,loc('SW1',2),(8.5,26.8),(10.25,25.3),e)
escape('R10',1,(15.55,25.85))
route('VM_RAW',p.B_Cu,.25,(15.55,25.85),(14.8,26.6),(14.8,27.8),(16.5,29.5))

# The inner VM copper parallels the external rated bus and its short taps.
# Inner width >=4.6 mm at the common rail (IPC-2221 inner-layer 3.6 A basis).
def zone(name,layer,points):
    z=p.ZONE(BOARD);z.SetLayer(layer);z.SetNet(NETS[name]);z.SetAssignedPriority(2 if name!='GND' else 0)
    z.SetLocalClearance(MM(.15));z.SetThermalReliefGap(MM(.25))
    z.SetThermalReliefSpokeWidth(MM(.5));z.SetPadConnection(p.ZONE_CONNECTION_FULL)
    z.SetMinThickness(MM(.15));z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
    poly=z.Outline();poly.NewOutline()
    for q in points:poly.Append(xy(q))
    BOARD.Add(z)
zone('VM',p.In2_Cu,[(24.2,7.3),(28.8,7.3),(28.8,51),(24.2,51)])
for off,u,qs,cs,cn,sc,sr,prefix in [
    (0,'U1',['Q1','Q2','Q3','Q4'],['C1','C2','C3','C4','C5','C6'],'CN1','C16','R8','L'),
    (27,'U2',['Q5','Q6','Q7','Q8'],['C8','C9','C10','C11','C12','C13'],'CN2','C17','R9','R')]:
    def q(x,y):return (x,y+off)
    ha,la,hb,lb=qs; cp,vc,dc,far,av,dv=cs
    for hi,lo,y in [(ha,la,10),(hb,lb,22)]:
        # The high-source collector is adjacent to the low-drain exposed pad.
        for i in [1,2,3]:
            a=loc(hi,i);route(net(hi,i),p.F_Cu,.5,a,(17.23,a[1]))
            b=loc(lo,i);route('GND',p.F_Cu,.5,b,(9.23,b[1]))
        name=net(hi,1)
        route(name,p.F_Cu,.9,q(17.23,y-1.905),q(17.23,y+.635))
        route('GND',p.F_Cu,.9,q(9.23,y-1.905),q(9.23,y+.635))
        route(name,p.F_Cu,1.0,q(14.4,y-.635),q(17.23,y-.635))
        # Four barrels at every phase transition; each has a local collector.
        array(name,q(16.2,y-.5),.8)
        route(name,p.F_Cu,.9,q(16.2,y-.5),q(17.23,y-.5))
        route(name,p.B_Cu,.7,q(16.2,y-.5),q(16.2,y))
        array('GND',q(8.6,y-.8),.8)
        route('GND',p.F_Cu,.9,q(8.6,y-.8),q(9.23,y-.8))
        # Power-drain four-via array in the large exposed drain pad.
        array('VM',q(20.95,y),1.5,layers=[p.F_Cu,p.In2_Cu])
        zone('VM',p.In2_Cu,[q(19.2,y-2.125),q(27.5,y-2.125),q(27.5,y+2.125),q(19.2,y+2.125)])
        zone(name,p.F_Cu,[q(14.4,y-2.25),q(17.5,y-2.25),q(17.5,y+.95),q(14.4,y+.95)])
        # Direct rated outer tap, covering the combined high-FET drain leads.
        tap=q(23.27,y-1.905)
        if off==0 and y==10:route('VM',p.F_Cu,1.0,tap,q(27,y-1.905),q(27.5,y-1.405))
        elif off==27 and y==22:route('VM',p.F_Cu,1.0,tap,q(27,y-1.905),q(27.5,y-2.405))
        else:route('VM',p.F_Cu,1.0,tap,q(27.5,y-1.905))
        route('VM',p.F_Cu,.9,q(23.27,y-1.905),q(23.27,y+1.905))
    # QFN ground vias and short bonds stay inside/adjacent to the EP.
    for x in [4.4,6]:
        for y in [15.7,17.3]:via('GND',q(x,y),.4,.2)
    for i,end in [(5,q(4.45,15.2)),(16,q(5.45,19.05)),(20,q(7.6,17.25)),(21,q(7.6,16.75))]:
        route('GND',p.F_Cu,.2,loc(u,i),end)
        via('GND',end,.4,.2)
    # Pump, LDO and VM capacitors: top-only, no vias in cap-to-pin paths.
    route(prefix+'_CPL',p.F_Cu,.2,loc(u,4),q(4.95,14.3),q(4.2,13.55),q(3.65,13.55),loc(cp,1))
    route(prefix+'_CPH',p.F_Cu,.2,loc(u,3),q(5.45,14.2),q(5.25,14.0),q(5.25,13.55),loc(cp,2))
    route(prefix+'_VCP',p.F_Cu,.2,loc(u,2),q(5.95,13.25),loc(vc,1))
    # Supply enters C3/C10 first, leaves toward VM pin, then serves VCP cap.
    route('VM',p.F_Cu,.3,q(27.5,13.1),q(10,13.1),loc(dc,1))
    route('VM',p.F_Cu,.3,loc(dc,1),q(8.5,14.6),loc(u,1))
    route('VM',p.F_Cu,.3,loc(vc,2),q(7.6,14.6))
    escape(dc,2,q(10.7,14.8))
    route('VM',p.F_Cu,.3,loc(far,1),q(25,8.095))
    escape(far,2,q(25,11.5))
    route(prefix+'_AVDD',p.F_Cu,.2,loc(u,7),q(2.65,14.6),loc(av,1))
    route(prefix+'_AVDD',p.F_Cu,.2,loc(u,6),loc(av,1))
    a=escape(av,1,q(1.6,13.9));b=escape(u,12,q(2.5,17.75))
    route(prefix+'_AVDD',p.In2_Cu,.2,a,q(.5,15),q(.5,17),q(1.25,17.75),b)
    escape(av,2,q(1,16.6))
    route(prefix+'_DVDD',p.F_Cu,.2,loc(u,8),q(2.6,15.75),q(2.6,16.66),loc(dv,1))
    escape(dv,2,q(1.6,20.3))
    # Gate and independent SH reference return to the actual high-source pad.
    gh2=escape(u,24,q(7.9,15.25),.25)
    gl2=escape(u,22,q(7.9,16.25),.25)
    sh2=escape(u,23,q(8.5,15.75),.2)
    gh1=escape(u,17,q(5.95,19.6),.25)
    gl1=escape(u,19,q(8,17.75),.25)
    sh1=escape(u,18,q(6.7,20.2),.2)
    for hi,lo,y,gh,gl,sh in [(ha,la,10,gh2,gl2,sh2),(hb,lb,22,gh1,gl1,sh1)]:
        hg=escape(hi,4,q(18.5,y+1.905),.25)
        lg=escape(lo,4,q(10.5,y+1.905),.25)
        sense=escape(hi,3,q(17.73,y+1.26),.2)
        if y==10:
            route(prefix+'_GH2',p.In2_Cu,.25,gh,q(8.7,15.25),q(12.045,11.905),hg)
            route(prefix+'_GL2',p.In2_Cu,.25,gl,q(7.3,15.65),q(7.3,15.105),lg)
            route(prefix+'_A',p.B_Cu,.2,sh,q(8.7,15.75),q(13.19,11.26),sense)
        else:
            route(prefix+'_GH1',p.B_Cu,.25,gh,q(5.95,23.6),q(6.95,24.6),q(17.805,24.6),hg)
            route(prefix+'_GL1',p.In2_Cu,.25,gl,q(10.5,20.25),lg)
            route(prefix+'_B',p.B_Cu,.2,sh,q(6.7,22.26),q(7.7,23.26),sense)
    # Outputs go directly to the neighbouring connector, with 135-degree bends.
    route(prefix+'_A',p.B_Cu,.7,q(16.2,9.5),q(17.5,9.5),q(22,14),loc(cn,1))
    route(prefix+'_B',p.B_Cu,.7,q(16.2,21.5),q(17.5,21.5),q(20,19),loc(cn,2))
    # Local snubber at phase ends, not at the distant board edge.
    route(prefix+'_SNUBBER',p.F_Cu,.25,loc(sc,2),q(19.95,16.5),loc(sr,1))
    s=escape(sc,1,q(17.2,15.7),.25)
    route(prefix+'_A',p.B_Cu,.25,s,q(17.2,13.3),q(16.2,12.3),q(16.2,10))
    t=escape(sr,2,q(23.5,14.95),.25)
    route(prefix+'_B',p.B_Cu,.25,t,q(23.5,19))
    # Signals escape directly away from the chip before entering low-current layers.
    escape(u,13,q(3.95,19.25))
    escape(u,14,q(4.45,20))
    escape(u,15,q(4.95,20.6))

# Original Zener and indicator circuits, supplied from SWITCHED VM.
a=escape('R1',1,(16.1,4.6),.25)
b=via('VM',(27.5,8.7))
route('VM',p.In2_Cu,.25,a,(18.9,7.4),(26.2,7.4),b)
route('3V3',p.F_Cu,.25,loc('R1',2),loc('D1',1))
escape('D1',2,(23.45,5.35))
route('3V3',p.F_Cu,.2,loc('R1',2),(18.6,3.3),(20.1,1.8),(24.5,1.8),(24.8,2.1),loc('R7',1))
for r,l in [('R5','LED1'),('R7','LED2')]:
    route(net(r,2),p.F_Cu,.2,loc(r,2),loc(l,2))
    escape(l,1,(loc(l,1)[0],loc(l,1)[1]+.9))
a=escape('R7',1,(26.5,3))
route('3V3',p.In2_Cu,.2,a,(28.5,1),(34,1),(34.8,1.8),(34.8,52),(31.8,55),loc('U5',3))
a=escape('R5',1,(25.8,6))
route('NSLEEP',p.B_Cu,.2,a,(33.1,6),(34.2,7.1),(34.2,52.5),(33.2,53.5),(27.5,53.5),loc('U5',2))
route('NSLEEP',p.B_Cu,.2,(3.95,19.25),(.3,22.9),(.3,28.7))
via('NSLEEP',(.3,28.7));via('NSLEEP',(.3,32.7))
route('NSLEEP',p.F_Cu,.2,(.3,28.7),(.3,32.7))
route('NSLEEP',p.B_Cu,.2,(.3,32.7),(.3,56.2),(3.1,59),(22,59),loc('U5',2))
route('NSLEEP',p.B_Cu,.2,(3.95,46.25),(.3,49.9))
route('L_EN_IN',p.In2_Cu,.2,(4.45,20),(-2,26.45),(-2,53),(3.2,58.2),(12.2,58.2),(12.81,57.59),loc('CN3',4))
route('L_PH_IN',p.In2_Cu,.2,(4.95,20.6),(-.5,26.05),(-.5,49.77),(3.73,54),(8.27,54),loc('CN3',3))
route('R_EN_IN',p.B_Cu,.2,(4.45,47),(4.45,53.5),(5.19,54.24),loc('CN3',1))
route('R_PH_IN',p.B_Cu,.2,(4.95,47.6),(4.95,52.2),(7.73,54.98),loc('CN3',2))

# Outline and reference text are designed independently of component orientation.
# The QFN top corners in the library conflict with the adjacent, intentionally
# close bypass capacitors. Keep the complete marks on the assembly layer, and
# place a visible pin-1 dot in the open space beyond the same top-right corner.
# This changes only printed artwork, not a pad, placement or copper object.
for ref,off in [('U1',0),('U2',27)]:
    for graphic in PARTS[ref].GraphicalItems():
        if graphic.GetLayer()==p.F_SilkS:
            graphic.SetLayer(p.F_Fab)
    mark=p.PCB_SHAPE(BOARD);mark.SetShape(p.SHAPE_T_CIRCLE)
    mark.SetStart(xy((8.0,14.1+off)));mark.SetEnd(xy((8.12,14.1+off)))
    mark.SetWidth(MM(.10));mark.SetLayer(p.F_SilkS);BOARD.Add(mark)
for a,b in [((LEFT,0),(W,0)),((W,0),(W,H)),((W,H),(LEFT,H)),((LEFT,H),(LEFT,0))]:
    d=p.PCB_SHAPE(BOARD);d.SetShape(p.SHAPE_T_SEGMENT);d.SetStart(xy(a));d.SetEnd(xy(b));d.SetWidth(MM(.05));d.SetLayer(p.Edge_Cuts);BOARD.Add(d)
for off,u,qs,cs,cn,sc,sr in [
    (0,'U1',['Q1','Q2','Q3','Q4'],['C1','C2','C3','C4','C5','C6'],'CN1','C16','R8'),
    (27,'U2',['Q5','Q6','Q7','Q8'],['C8','C9','C10','C11','C12','C13'],'CN2','C17','R9')]:
    label(u,(5.2,22.0+off),.6)
    for ref,x,y in zip(qs,[20.5,12.5,25.0,10.3 if off==0 else 12.5],[13.3,13.3,23.5,25.3]):label(ref,(x,y+off),.6)
    for ref,(x,y) in zip(cs,[(3.7,11.4),(6.8,11.5),(10,15.8),(25,12.4),(-.25,15.4),(-.25,18.46)]):label(ref,(x,y+off),.6)
    label(cn,(34.8,16.5+off),.6,angle=90)
    label(sc,(18,18.1+off),.6);label(sr,(24.5,16.5+off),.6)
for ref,at in [('P2',(7,.6)),('SW1',(8.5,33.7)),('U6',(24.4,26.5)),('C15',(30.4,35.5)),
               ('C18',(13.7,25.35)),('C19',(16.8,34.3)),('R10',(17.1,26.8)),('R11',(25.1,24.55)),
               ('R12',(24.2,34.0)),('R1',(17.8,3.1)),('D1',(21.8,6.8)),
               ('R7',(29.3,3.8)),('R5',(27.3,4.6)),('LED2',(31.5,.65)),('LED1',(31.3,7.8))]:
    label(ref,at,.6,p.B_SilkS if ref=='R10' else p.F_SilkS)
label('CN3',(9,52.1),.6);label('U5',(33.2,56.0),.6)
label('MAIN POWER',(8.5,25.35),.6,p.B_SilkS);label('ON',(13.3,33.7),.6);label('OFF',(3.7,33.7),.6)
label('SLEEP ENABLE',(25,52.0),.6,p.B_SilkS)
label('DRV8701 DUAL / REV B',(18,59.25),.7,p.B_SilkS)
label('12V / 1.8A x2',(18,1.5),.7,p.B_SilkS)
for layer in [p.F_Cu,p.In1_Cu,p.B_Cu]:
    zone('GND',layer,[(LEFT+.4,.4),(W-.4,.4),(W-.4,H-.4),(LEFT+.4,H-.4)])

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
print(json.dumps({'board':str(filename),'components':len(PARTS),'nets':len(NETS),'segments':len(ROUTES),'vias':sum(isinstance(x,p.PCB_VIA) for x in BOARD.GetTracks()),'dimensions_mm':[W-LEFT,H],'copper_layers':4,'autorouter_used':False}))
