import pygame as p
import math, os, random, tempfile, wave, struct
from math import sin as sn, cos as co, pi

# py_32bk_scenedemo.py
# source: github.com/zeittresor

# --- helpers & globals ---

rr = random.random
ru = random.uniform

CO = [rr()*6.28 for _ in range(3)]
SW1 = ru(-0.3, 0.3)
SW2 = ru(-0.3, 0.3)

# placeholders, will be set in main()
W, H = 1280, 720
S = None
VIGNETTE = None
GLOBAL_DT = 0.0

# 3D objects
CBV=[(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
CBF=[(0,1,2,3),(4,5,6,7),(0,1,5,4),(2,3,7,6),(0,3,7,4),(1,2,6,5)]

THV=[(1,1,1),(-1,-1,1),(-1,1,-1),(1,-1,-1)]
THF=[(0,1,2),(0,1,3),(0,2,3),(1,2,3)]

OCV=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
OCF=[(0,2,4),(2,1,4),(1,3,4),(3,0,4),(0,2,5),(2,1,5),(1,3,5),(3,0,5)]

PYV=[(1,1,1),(-1,1,1),(-1,-1,1),(1,-1,1),(0,0,-1)]
PYF=[(0,1,2,3),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]

phi = (1+5**0.5)/2
ICV=[(0,1,phi),(0,-1,phi),(0,1,-phi),(0,-1,-phi),
     (1,phi,0),(-1,phi,0),(1,-phi,0),(-1,-phi,0),
     (phi,0,1),(phi,0,-1),(-phi,0,1),(-phi,0,-1)]
ICF=[(0,1,8),(0,8,5),(5,8,4),(4,8,1),(1,5,4),
     (1,7,10),(1,10,0),(0,10,11),(0,11,1),(1,11,7),
     (2,3,9),(2,9,6),(6,9,7),(7,9,3),(3,6,7),
     (2,4,5),(2,5,6),(6,5,3),(3,5,4),
     (2,4,10),(2,10,11),(2,11,4),(4,11,1),
     (3,7,8),(3,8,9),(8,7,6),(8,6,9),(0,8,2),(2,8,4)]

# palettes – a few „nice“ base moods
PALETTES = [
    (255, 60, 200),  # magenta
    (60, 255, 140),  # neon green
    (80, 130, 255),  # blue
    (240, 200, 80),  # warm
]
PAL = list(random.choice(PALETTES))

def pc(v: int):
    """Convert intensity 0-255 into current palette RGB."""
    v = max(0, min(255, int(v)))
    return (v*PAL[0]//255, v*PAL[1]//255, v*PAL[2]//255)

# textures & particles
IMS = []
STARS = []

# --- drawing helpers ---

def make_vignette():
    global VIGNETTE
    VIGNETTE = p.Surface((W, H), p.SRCALPHA)
    r = min(W, H) / 2.0
    for y in range(H):
        dy = y - H/2
        for x in range(W):
            dx = x - W/2
            d = (dx*dx + dy*dy)**0.5 / r
            a = int(max(0, min(255, (d-0.3)*255)))
            VIGNETTE.set_at((x,y), (0,0,0,a))

def draw_wait(screen, font_big, font_small, progress, info_text):
    screen.fill((10, 8, 20))
    txt = font_big.render("Generating music...", True, (230, 230, 245))
    screen.blit(txt, (W//2 - txt.get_width()//2, H//3 - txt.get_height()//2))

    bar_w = int(W * 0.7)
    bar_h = int(H * 0.04)
    bx = W//2 - bar_w//2
    by = H//2
    p.draw.rect(screen, (60, 60, 90), (bx, by, bar_w, bar_h), 2)
    fill_w = int((bar_w-4) * progress)
    if fill_w > 0:
        p.draw.rect(screen, (120, 210, 120), (bx+2, by+2, fill_w, bar_h-4))

    pct = font_small.render(f"{int(progress*100)}%", True, (220,220,230))
    screen.blit(pct, (W//2 - pct.get_width()//2, by + bar_h + 10))

    info = font_small.render(info_text, True, (180,180,200))
    screen.blit(info, (W//2 - info.get_width()//2, by + bar_h + 35))

    p.display.flip()
    p.event.pump()

def sh(sf, t, verts, faces):
    """Generic 3D shape renderer."""
    sfactor = min(W, H) / 3
    angx = t * 0.3
    angy = t * 0.4
    cax = math.cos(angx); six = math.sin(angx)
    cay = math.cos(angy); siy = math.sin(angy)
    bg  = t * 0.2
    cbg = math.cos(bg); sbg = math.sin(bg)
    ps = []
    for vx,vy,vz in verts:
        # rotate
        y1 = vy*cax - vz*six
        z1 = vy*six + vz*cax
        x1 = vx*cay + z1*siy
        z2 = -vx*siy + z1*cay
        y2 = y1*cbg - z2*sbg
        z3 = y1*sbg + z2*cbg
        sc = sfactor / (z3 + 3.0)
        ps.append((int(W/2 + x1*sc), int(H/2 + y2*sc), z3))
    sf.fill((0,0,0))
    for face in faces:
        z = sum(ps[i][2] for i in face) / len(face)
        col = int(max(0, min(255, 200 + z*40)))
        pg = [ps[i][:2] for i in face]
        p.draw.polygon(sf, (col, int(col*0.6), int(col*0.3)), pg)

# --- demoscene visual effects ---

def lc(sf, t):
    sf.fill((0,0,0))
    for x in range(0, W, 4):
        h = int(H*0.4 + sn(x*0.01+t*0.3)*H*0.1 + sn(x*0.05+t*0.4)*H*0.05)
        col = (int(100+80*sn(x*0.02+t*0.5)),
               int(50+40*sn(x*0.03-t*0.4)),
               int(150+80*sn(x*0.04+t*0.3)))
        p.draw.line(sf, col, (x,H), (x,H-h))

def th(sf,t): sh(sf,t,THV,THF)
def oc(sf,t): sh(sf,t,OCV,OCF)
def py(sf,t): sh(sf,t,PYV,PYF)
def ic(sf,t): sh(sf,t,ICV,ICF)
def cb(sf,t): sh(sf,t,CBV,CBF)

def tn(sf,t):
    sf.fill((0,0,0))
    for i in range(200):
        a = i*0.07 + t*0.4
        r = min(W,H)*0.4*(i/200)
        x = int(W/2 + math.cos(a)*r)
        y = int(H/2 + math.sin(a)*r*0.7)
        v = 120+100*sn(i*0.3+t*0.6)
        p.draw.circle(sf, pc(v), (x,y), 2)

def hx(sf,t):
    sf.fill((0,0,0))
    w = 40; h = 40
    for y in range(-h, H+h, w):
        for x in range(-w, W+w, w):
            xx = x + (y//w % 2) * (w//2)
            ang = t*0.3 + (x+y)*0.01
            v = 120+100*sn(ang)
            pts = []
            for i in range(6):
                a = i*pi/3 + ang
                px = int(xx + math.cos(a)*w/2)
                py = int(y + math.sin(a)*h/2)
                pts.append((px,py))
            p.draw.polygon(sf, pc(v), pts, 1)

def bw(sf,t):
    sf.fill((0,0,0))
    br = int(128+127*sn(t*0.1+CO[0]))
    bg = int(128+127*sn(t*0.1+2+CO[1]))
    bb = int(128+127*sn(t*0.1+4+CO[2]))
    CO[0]+=0.001; CO[1]+=0.0015; CO[2]+=0.002
    for y in range(0, H, 4):
        h = int(128*(sn(y*0.03+t*0.4)+1))
        p.draw.line(sf, (br*h//255,bg*h//255,bb*h//255), (0,y), (W,y))

def ss(surface, sw, dt, t):
    """Particle swirl / starfield."""
    global STARS
    surface.fill((0,0,0))
    for s in STARS:
        x,y,vx,vy,r,shape = s
        if sw:
            dx = x - W/2
            dy = y - H/2
            vx += sw*dy*dt
            vy -= sw*dx*dt
        x += vx*dt
        y += vy*dt
        r += dt*50
        s[0]=x; s[1]=y; s[2]=vx; s[3]=vy; s[4]=r
    STARS = [s for s in STARS if 0<=s[0]<W and 0<=s[1]<H]
    cx = W/2 + sn(t*0.2)*W*0.25
    cy = H/2 + math.cos(t*0.17)*H*0.25
    for _ in range(5):
        a = rr()*2*pi
        spd = ru(50,200)
        shape = int(rr()*3)
        STARS.append([cx,cy,math.cos(a)*spd,math.sin(a)*spd,1,shape])
    for s in STARS:
        c = min(255, int(s[4]*10))
        rad = max(1, int(s[4]*0.05))
        shape = s[5]
        if shape==0:
            p.draw.circle(surface,(c,c,c),(int(s[0]),int(s[1])),rad)
        elif shape==1:
            p.draw.rect(surface,(c,c,c),(int(s[0])-rad,int(s[1])-rad,rad*2,rad*2))
        else:
            x0=int(s[0]);y0=int(s[1])
            pts=[(x0,y0-rad),(x0+rad,y0+rad),(x0-rad,y0+rad)]
            p.draw.polygon(surface,(c,c,c),pts)

def s1(sf,t): ss(sf,SW1,GLOBAL_DT,t)
def s2(sf,t): ss(sf,SW2,GLOBAL_DT,t)
def s0(sf,t): ss(sf,0,GLOBAL_DT,t)

def init_textures():
    """Create some procedural textures and save them to 'd/'."""
    dd = "d"
    os.makedirs(dd, exist_ok=True)
    for idx in range(6):
        m = p.Surface((64,64))
        r1 = rr()*pi*2
        r2 = rr()*pi*2
        for x in range(32):
            for y in range(32):
                val = int(128+127*sn(x*0.15+r1)+127*sn(y*0.15+r2))
                val = max(0,min(255,val))
                col = (val, val//2, 255-val)
                m.set_at((x,y),col)
                m.set_at((63-x,y),col)
                m.set_at((x,63-y),col)
                m.set_at((63-x,63-y),col)
        IMS.append(m)
        fname = os.path.join(dd, f"tex_{idx}_{int(rr()*1e6)}.png")
        try:
            p.image.save(m, fname)
        except Exception:
            pass

def tx(sf,t):
    idx = int((t*0.15) % len(IMS))
    r = p.transform.smoothscale(IMS[idx], (W//2, H//2))
    sf.blit(r, (0,0))
    sf.blit(p.transform.flip(r,1,0), (W//2,0))
    sf.blit(p.transform.flip(r,0,1), (0,H//2))
    sf.blit(p.transform.flip(r,1,1), (W//2,H//2))

def spn(sf,t):
    sf.fill((0,0,0))
    cx=int(W/2+sn(t*SW1)*W*0.2)
    cy=int(H/2+math.cos(t*SW2)*H*0.2)
    R=min(W,H)/2
    for i in range(800):
        a=i*0.01+t*0.7
        r=(i/800)*R
        x=int(cx+math.cos(a)*r)
        y=int(cy+math.sin(a)*r)
        v=int(100+80*sn(a*1.5+t*0.3))
        sf.set_at((x,y),pc(v))

def bars(sf,t):
    sf.fill((0,0,0))
    n=40
    for i in range(n):
        h=int(H*(0.2+0.4*sn(t*0.6+i*0.3)**2))
        x=i*W//n
        v=int(100+80*sn(t*0.7+i*0.4))
        p.draw.rect(sf,pc(v),(x,H-h,W//n-2,h))

def fld(sf,t):
    sf.fill((0,0,0))
    for y in range(0,H,3):
        yy=y/H
        for x in range(0,W,3):
            xx=x/W
            v=int(128+127*sn((xx*4+sn(t*0.3))*2+sn(yy*3+t*0.4)))
            sf.fill(pc(v),((x,y,3,3)))

def cld(sf,t):
    sf.fill((0,0,0))
    cx=W/2+sn(t*0.2)*W*0.2
    cy=H/2+math.cos(t*0.23)*H*0.2
    for i in range(60):
        a=i*0.11+t*0.4
        r=min(W,H)*0.3*(0.3+0.7*sn(i*0.2+t*0.3)**2)
        x=int(cx+math.cos(a)*r)
        y=int(cy+math.sin(a)*r*0.6)
        rad=int(40+30*sn(i*0.3+t*0.6)**2)
        v=int(120+100*sn(i*0.25+t*0.5))
        s=p.Surface((rad*2,rad*2),p.SRCALPHA)
        p.draw.circle(s,(*pc(v),130),(rad,rad),rad)
        sf.blit(s,(x-rad,y-rad))

def cp(sf,t):
    sf.fill((0,0,0))
    cx=W/2;cy=H/2
    for i in range(120):
        a=i*0.05+t*0.5
        r=min(W,H)*0.4*(i/120)
        x=int(cx+math.cos(a)*r)
        y=int(cy+math.sin(a)*r*0.7)
        v=int(120+100*sn(i*0.2+t*0.6))
        p.draw.circle(sf,pc(v),(x,y),int(5+4*sn(i*0.4+t*0.8)**2))

def pl(tm):
    # soft overlay plasma
    P = p.Surface((80,80))
    for x in range(80):
        for y in range(80):
            v=int(128+127*sn(0.13*x+tm*0.5)+127*sn(0.14*y-tm*0.5))
            v=max(0,min(255,v))
            P.set_at((x,y),(v,v//2,v))
    Q=p.transform.smoothscale(P,(W,H))
    Q.set_alpha(80)
    S.blit(Q,(0,0))

def mg(sf,t):
    sf.fill((0,0,0))
    for i in range(400):
        a=i*0.05+t*0.4
        r=min(W,H)*0.45*(0.3+0.7*sn(i*0.23+t*0.5)**2)
        x=int(W/2+math.cos(a)*r)
        y=int(H/2+math.sin(a)*r*0.7)
        v=int(120+100*sn(i*0.3+t*0.6))
        p.draw.circle(sf,pc(v),(x,y),int(3+2*sn(i*0.5+t*0.9)**2))

def wall(sf,t):
    sf.fill((0,0,0))
    for x in range(0,W,8):
        h=int(H*0.5+sn(t*0.7+x*0.02)*H*0.2)
        col=(int(80+60*sn(t*0.4+x*0.03)),
             int(40+40*sn(t*0.25+x*0.05)),
             int(150+80*sn(t*0.3+x*0.04)))
        p.draw.line(sf,col,(x,h),(x,H))

def wave2(sf,t):
    sf.fill((0,0,0))
    h=int(H*0.4)
    for x in range(W):
        y=int(H*0.3+sn(t*0.7+x*0.02)*h+sn(t*0.3+x*0.05)*h*0.3)
        col=(int(100+80*sn(t*0.2+x*0.02)),
             int(60+50*sn(t*0.1+x*0.03)),
             int(150+80*sn(t*0.15+x*0.04)))
        p.draw.line(sf,col,(x,0),(x,y))
        g=int(50+40*sn(t*0.25+x*0.05))
        p.draw.line(sf,(g,int(g*0.5),255-g),(x,y),(x,H))

def sfld(sf,t):
    sf.fill((0,0,0))
    cx=W/2;cy=H/2
    for i in range(200):
        a=i*0.09+t*0.5
        r=min(W,H)*0.5*(0.1+0.9*sn(i*0.27+t*0.6)**2)
        x=int(cx+math.cos(a)*r)
        y=int(cy+math.sin(a)*r*0.75)
        v=int(120+100*sn(i*0.33+t*0.7))
        p.draw.circle(sf,pc(v),(x,y),2)

def rings2(sf,t):
    sf.fill((0,0,0))
    m=min(W,H)/2
    ox=sn(t*SW1)*W*0.2
    oy=math.cos(t*SW2)*H*0.2
    for i in range(50):
        z=i/50
        rad=int((1-z)*m)
        off=sn(t*0.6+i*0.3)*50
        col=int(128+127*sn(i*0.2+t*0.3))
        p.draw.circle(sf,pc(col),(int(W/2+off+ox),int(H/2+off*0.5+oy)),rad,1)

def swp(sf,t):
    sf.fill((0,0,0))
    cx=W/2+sn(t*SW1)*W*0.3
    cy=H/2+math.cos(t*SW2)*H*0.3
    for i in range(70):
        ang=i*0.1+t*0.5
        x=int(cx+math.cos(ang)*W*0.6)
        y=int(cy+math.sin(ang)*H*0.6)
        col=int(128+127*sn(i*0.2+t*0.3))
        p.draw.circle(sf,pc(col),(x,y),int(i*0.1+2))

def vr(sf,t):
    sf.fill((0,0,0))
    m=min(W,H)/2
    cx=W/2+sn(t*SW1)*W*0.25
    cy=H/2+math.cos(t*SW2)*H*0.25
    for i in range(80):
        z=i/80
        r=z*m
        a=t*0.8+z*10
        x=int(cx+math.cos(a)*r)
        y=int(cy+math.sin(a)*r)
        col=int(128+127*sn(t*0.5+i*0.1))
        p.draw.circle(sf,pc(col),(x,y),2)

def ln2(sf,t):
    sf.fill((0,0,0))
    for i in range(300):
        a=i*0.1+t*0.8
        r=min(W,H)*0.5*(i/300)
        x=int(W/2+math.cos(a)*r)
        y=int(H/2+math.sin(a)*r*0.6)
        v=int(120+100*sn(i*0.25+t*0.7))
        p.draw.circle(sf,pc(v),(x,y),1)

def frc(sf,t):
    sf.fill((0,0,0))
    for y in range(0,H,3):
        for x in range(0,W,3):
            xx=(x-W/2)/min(W,H)
            yy=(y-H/2)/min(W,H)
            v=int(128+127*sn(5*(xx*xx-yy*yy)+t*0.5))
            sf.fill(pc(v),((x,y,3,3)))

def pxl(sf,t):
    sf.fill((0,0,0))
    for y in range(0,H,4):
        for x in range(0,W,4):
            v=int(128+127*sn(x*0.15+t*0.5)+127*sn(y*0.11-t*0.3))
            sf.fill(pc(v),((x,y,4,4)))

def spin2(sf,t):
    sf.fill((0,0,0))
    cx=W/2;cy=H/2
    for i in range(120):
        a=i*0.12+t*0.9
        r=min(W,H)*0.45*(0.2+0.8*sn(i*0.3+t*0.5)**2)
        x=int(cx+math.cos(a)*r)
        y=int(cy+math.sin(a)*r*0.7)
        v=int(120+100*sn(i*0.4+t*0.6))
        p.draw.circle(sf,pc(v),(x,y),3)

def wave3(sf,t):
    sf.fill((0,0,0))
    for x in range(W):
        y=int(H/2+sn(t*0.9+x*0.02)*H*0.25+sn(t*0.5+x*0.04)*H*0.1)
        v=int(120+100*sn(t*0.7+x*0.03))
        p.draw.circle(sf,pc(v),(x,y),2)

def tube(sf,t):
    sf.fill((0,0,0))
    cx=W/2;cy=H/2;m=min(W,H)/2
    for i in range(150):
        z=i/150
        rad=int(m*z)
        a=t*1.2+z*15
        x=int(cx+math.cos(a)*rad)
        y=int(cy+math.sin(a)*rad)
        v=int(120+100*sn(t*0.8+z*6))
        p.draw.circle(sf,pc(v),(x,y),2)

def eq(sf,t):
    sf.fill((0,0,0))
    bn=50
    for i in range(bn):
        v=int(H*(0.1+0.4*(sn(t*0.6+i*0.3)**2)))
        x=i*W//bn
        c=int(120+100*sn(t*0.7+i*0.2))
        p.draw.rect(sf,pc(c),(x,H-v,W//bn-2,v))

def np_overlay(sf,t):
    """Neon-plasma overlay."""
    overlay = p.Surface((W,H), p.SRCALPHA)
    step = 4
    for y in range(0,H,step):
        for x in range(0,W,step):
            v1 = sn(x*0.02 + t*0.7)
            v2 = sn(y*0.03 - t*0.4)
            v3 = sn((x+y)*0.015 + t*0.5)
            v = int(127*(v1+v2+v3)/3 + 128)
            col = pc(v)
            overlay.fill((*col, 35), (x,y,step,step))
    S.blit(overlay, (0,0), special_flags=p.BLEND_ADD)

# --- music generation with progress bar ---

def generate_music_with_progress(screen, font_big, font_small):
    # rhythm / tempo
    bpm_options = [72, 86, 98, 112, 126, 140]
    bpm = random.choice(bpm_options)
    beat = 60.0 / bpm           # quarter note
    rd = beat / 4.0             # 16th note

    major = [0,2,4,5,7,9,11]
    minor = [0,2,3,5,7,8,10]
    pgs   = [[0,4,5,3],[0,5,3,4],[0,3,4,5],[0,5,2,6],[0,2,4,5]]
    pn = 4 + int(rr()*3)

    patterns = []
    pattern_modes = []  # 0=full,1=mellow,2=percussive

    for _ in range(pn):
        base = 48 + int(rr()*12)
        sc   = major if rr()<0.5 else minor
        cp   = random.choice(pgs)
        chd=[];mel=[];bas=[];dr=[]
        chords=[]
        for ci in cp:
            r  = base + sc[ci % len(sc)]
            t3 = base + sc[(ci+2)%len(sc)]
            t5 = base + sc[(ci+4)%len(sc)]
            chords.append((r,t3,t5))
        for r_i in range(64):
            b = r_i//16
            note_tuple = chords[b]
            chd.append(note_tuple)
            if r_i%4==0:
                mel.append(note_tuple[int(rr()*3)])
            else:
                mel.append(note_tuple[int(rr()*3)] if rr()<0.7 else 0)
            bas.append(base-12+sc[cp[b]%len(sc)] if r_i%8==0 else 0)
            if r_i%16==0: dr.append(1)
            elif r_i%16==8: dr.append(2)
            elif r_i%2==0: dr.append(3)
            else: dr.append(0)
        patterns.append((chd,mel,bas,dr))
        pattern_modes.append(random.choice([0,0,1,1,2]))

    # song order, each pattern mostly 2x, sometimes 1x or 3x
    order=[]
    for i in range(pn):
        if random.random() < 0.15:
            rp = 1   # short break
        elif random.random() < 0.2:
            rp = 3   # small intermezzo
        else:
            rp = 2
        for _ in range(rp):
            order.append(i)

    tot_rows = len(order) * 64
    total_seconds = tot_rows * rd

    # limit to ~3.5 minutes
    if total_seconds > 210:
        max_rows = int(210/rd)
        max_patterns = max_rows // 64
        order = order[:max(1,max_patterns)]
        tot_rows = len(order)*64
        total_seconds = tot_rows*rd

    rows=[]
    for idx in order:
        for r_i in range(64):
            rows.append((idx,r_i))
    tot = len(rows)

    sr = 16000
    total_samples = int(tot * rd * sr)

    # output file
    try:
        dd = "d"
        os.makedirs(dd, exist_ok=True)
        fn = os.path.join(dd, "m"+str(int(rr()*1e6))+".wav")
    except Exception:
        fn = os.path.join(tempfile.gettempdir(), "m.wav")

    wv = wave.open(fn, "wb")
    wv.setnchannels(1)
    wv.setsampwidth(2)
    wv.setframerate(sr)

    chord_base_vol = 0.15
    melody_base_vol = 0.34
    bass_base_vol = 0.28

    sample = 0
    chunk = max(1, total_samples//300)

    while sample < total_samples:
        end = min(total_samples, sample + chunk)
        while sample < end:
            t = sample / sr
            ri = int(t / rd)
            if ri >= tot:
                ri = tot-1
            pidx, pr = rows[ri]
            chd, mel, bas, drp = patterns[pidx]
            notes = chd[pr]
            mn    = mel[pr]
            bn    = bas[pr]
            drum  = drp[pr]
            mode  = pattern_modes[pidx]

            if mode == 0:   # full
                cv = chord_base_vol
                mv = melody_base_vol
                bv = bass_base_vol
                dv = 1.0
            elif mode == 1: # mellow / pad
                cv = chord_base_vol*1.2
                mv = melody_base_vol*0.4
                bv = bass_base_vol*0.8
                dv = 0.4
            else:           # percussive
                cv = chord_base_vol*0.6
                mv = melody_base_vol*0.7
                bv = bass_base_vol*0.4
                dv = 1.3

            val = 0.0
            for f in notes:
                freq = 440*(2**((f-69)/12))
                val += sn(2*pi*freq*t) * cv

            if mn:
                freq = 440*(2**((mn-69)/12))
                val += sn(2*pi*freq*t) * mv

            if bn:
                freq = 440*(2**((bn-69)/12))
                val += sn(2*pi*freq*t) * bv

            if drum == 1:
                dt = t - (ri*rd)
                amp = (1 - dt/(rd*0.3)) if dt < rd*0.3 else 0
                val += sn(2*pi*60*t) * amp * 0.7 * dv
            elif drum == 2:
                dt = t - (ri*rd)
                amp = (1 - dt/(rd*0.2)) if dt < rd*0.2 else 0
                val += sn(2*pi*900*t) * amp * 0.6 * dv
            elif drum == 3:
                dt = t - (ri*rd)
                amp = (1 - dt/(rd*0.1)) if dt < rd*0.1 else 0
                val += sn(2*pi*3000*t) * amp * 0.4 * dv

            if val > 1: val = 1
            if val < -1: val = -1

            wv.writeframes(struct.pack("<h", int(val*32767)))
            sample += 1

        progress = sample / total_samples
        info = f"BPM {bpm} | duration ~ {int(total_seconds)} s"
        draw_wait(screen, font_big, font_small, progress, info)

    wv.close()
    return fn, total_seconds, bpm

# --- main ---

def main():
    global W,H,S,GLOBAL_DT,PAL

    p.init()
    p.mixer.init(16000, -16, 1)

    info = p.display.Info()
    W, H = info.current_w, info.current_h
    S = p.display.set_mode((W,H), p.FULLSCREEN)
    p.mouse.set_visible(False)

    font_big = p.font.Font(None, int(H*0.08))
    font_small = p.font.Font(None, int(H*0.04))

    # initial wait screen
    draw_wait(S, font_big, font_small, 0.0, "Initializing...")

    # textures & vignette
    init_textures()
    make_vignette()

    # generate music with progress bar
    music_file, duration, bpm = generate_music_with_progress(S, font_big, font_small)

    # start playback after generation
    try:
        snd = p.mixer.Sound(music_file)
        snd.play(-1)
    except Exception:
        try:
            p.mixer.music.load(music_file)
            p.mixer.music.play(-1)
        except Exception:
            pass

    clock = p.time.Clock()
    t = 0.0
    sd = 8.0
    fd = 2.0
    last_i = -1

    effects = [
        bw,s0,s1,s2,cb,tn,hx,lc,th,oc,py,
        cld,cp,tx,spn,bars,fld,mg,wall,wave2,
        sfld,rings2,swp,vr,ln2,frc,pxl,spin2,
        wave3,tube,eq,ic
    ]
    random.shuffle(effects)

    surf_a = p.Surface((W,H))
    surf_b = p.Surface((W,H))

    running = True
    while running:
        for e in p.event.get():
            if e.type == p.QUIT:
                running = False
            elif e.type == p.KEYDOWN and e.key == p.K_ESCAPE:
                running = False

        dt = clock.tick(60) / 1000.0
        GLOBAL_DT = dt
        t += dt

        seg_t = t % sd
        i = int(t/sd) % len(effects)
        j = (i+1) % len(effects)

        if i != last_i:
            PAL[:] = random.choice(PALETTES)
            last_i = i

        blend = 0.0
        if seg_t > sd - fd:
            blend = (seg_t - (sd - fd)) / fd

        effects[i](surf_a, t)
        effects[j](surf_b, t)

        surf_a.set_alpha(int(255*(1-blend)))
        surf_b.set_alpha(int(255*blend))

        S.blit(surf_a, (0,0))
        S.blit(surf_b, (0,0))

        pl(t)
        np_overlay(S, t)
        if VIGNETTE is not None:
            S.blit(VIGNETTE, (0,0))

        p.display.flip()

    p.quit()

if __name__ == "__main__":
    main()
