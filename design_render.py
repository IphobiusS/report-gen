"""Bounded palette and original geometric marks shared by PDF and Word covers."""
from design_library import validate_design


def rgb(c): return tuple(int(c[i:i+2],16) for i in (1,3,5))
def luminance(c):
    vals=[x/255 for x in rgb(c)]
    vals=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in vals]
    return sum(a*b for a,b in zip(vals,(.2126,.7152,.0722)))
def contrast(a,b):
    a,b=sorted((luminance(a),luminance(b)))
    return (b+.05)/(a+.05)
def ink_on(bg): return '#FFFFFF' if contrast('#FFFFFF',bg)>contrast('#182B3B',bg) else '#182B3B'
def text_accent(c):
    while contrast(c,'#FFFFFF')<4.5:
        c='#'+''.join(f'{int(n*.9):02X}' for n in rgb(c))
    return c


def palette(design):
    d=validate_design(design)
    quiet=d['variant']=='quiet'; layout=d['layout']
    accent='#4B5E72' if quiet else d['accent']
    dark='#EDF1F5' if quiet else d['background']
    bg=dark if layout=='frame' else '#FFFFFF'
    middle=dark if layout in ('band','split','frame') else bg
    fg=ink_on(bg); title=ink_on(middle)
    return {'--accent':text_accent(accent),'--accent-ink':text_accent(accent),'--cyan':text_accent(accent),'--cyan-ink':text_accent(accent),
            '--ink':'#182B3B','--muted':'#536273', '--cover-bg':bg,'--cover-fg':fg,
            '--cover-title':title,'--cover-subtitle':title,'--cover-muted':fg,
            '--cover-rule':accent,'--cover-wordmark':ink_on(dark) if layout=='split' else fg,
            '--cover-tag-fg':ink_on(dark) if layout=='split' else fg,
            '--cover-meta-border':'#ABB5C0','--profile-dark':dark,'--profile-middle':middle,
            '--cover-foot-ink':fg,'--cover-mark-ink':text_accent(accent) if layout not in ('split','frame') else ink_on(dark)}


def css(design):
    d=validate_design(design); p=palette(d)
    root=':root{'+''.join(k+':'+v+';' for k,v in p.items())+'}'
    return root+'''
.cover.profile-cover{border:0;background:var(--cover-bg);}
.profile-cover .cover-header{z-index:1;}
.profile-cover .cover-main{padding:0 5mm;text-align:center;}
.profile-cover .cover-bottom{border:0;padding:0;}
.profile-cover .cover-center{top:70mm;height:120mm;}
.profile-cover .cv-title{font-size:32pt;}
.profile-cover.has-illustration .cv-title{font-size:27pt;}
.profile-cover .cv-field-label{opacity:1;}
.profile-cover .cover-foot{letter-spacing:0;}
.profile-identity{font-family:"Report Cover","Carlito",sans-serif;font-size:10pt;margin-top:6mm;color:var(--cover-mark-ink);}
.profile-identity{display:table;width:100%;table-layout:fixed;}
.profile-certificate{display:table-cell;vertical-align:middle;padding-right:8mm;overflow-wrap:anywhere;}
.provider-logo{display:table-cell;width:42mm;vertical-align:middle;}
.provider-logo svg{display:block;width:42mm;height:11mm;}
.profile-cover .cv-logos{margin-top:4mm;}
.profile-cover .cv-logo{max-height:16mm;}
.profile-motif{position:absolute;right:24mm;top:43mm;width:45mm;height:12mm;color:var(--cover-mark-ink);}
.profile-motif svg{display:block;width:100%;height:100%;}
.profile-cover.layout-rail{border-left:12mm solid var(--cover-rule);}
.profile-cover.layout-rail .cover-header,.profile-cover.layout-rail .cover-bottom{left:16mm;right:24mm;}
.profile-cover.layout-rail .cover-center{left:16mm;width:158mm;}
.profile-cover.layout-band .cover-center{left:0;width:210mm;background:var(--profile-middle);height:125mm;}
.profile-cover.layout-band .cover-content{left:24mm;right:24mm;}
.profile-cover.layout-band .cover-center:before{content:"";position:absolute;left:0;top:0;width:100%;height:3mm;background:var(--cover-rule);}
.profile-cover.layout-split:before{content:"";position:absolute;left:0;top:0;right:0;height:190mm;background:var(--profile-dark);border-bottom:4mm solid var(--cover-rule);}
.profile-cover.layout-frame{border:3mm solid var(--cover-rule);}
.profile-cover.layout-frame .cover-bottom{bottom:18mm;}
.profile-cover.layout-timeline:before{content:"";position:absolute;left:13mm;top:20mm;width:1mm;height:253mm;background:var(--cover-rule);}
.profile-cover.layout-timeline .cover-bottom{left:30mm;right:24mm;}
.profile-cover.layout-timeline .cv-field-label{border-top:1px solid #ABB5C0;padding-top:2mm;}
.profile-cover .cover-meta td{border-color:var(--cover-meta-border);}
'''


def primitives(motif):
    # Original line art, no provider logos or certificate badges.
    if motif in ('network','ai'):
        points=[(14,24),(45,9),(45,39),(78,16),(78,34),(111,24),(142,9),(142,39)]
        edges=[(0,1),(0,2),(1,3),(2,4),(3,5),(4,5),(5,6),(5,7)]
        return [('line',(*points[a],*points[b])) for a,b in edges]+[('rect',(x-3,y-3,x+3,y+3)) for x,y in points]
    if motif=='wifi':
        return [('line',(45,9,80,3)),('line',(80,3,115,9)),('line',(55,20,80,14)),('line',(80,14,105,20)),('line',(66,31,80,26)),('line',(80,26,94,31)),('rect',(77,38,83,44))]
    if motif=='code':
        return [('line',(42,9,26,24)),('line',(26,24,42,39)),('line',(118,9,134,24)),('line',(134,24,118,39)),('line',(90,4,70,44))]
    if motif=='events':
        return [('line',(10,24,150,24))]+[('rect',(x,10,x+7,38)) for x in (20,51,82,113)]
    if motif=='web':
        return [('rect',(20,5,140,43)),('line',(20,15,140,15)),('rect',(26,9,28,11)),('line',(33,25,72,25)),('line',(33,33,108,33))]
    return [('rect',(x,y,x+17,y+17)) for x,y in ((35,4),(59,4),(83,4),(59,28),(83,28),(107,28))]


def svg(design):
    d=validate_design(design)
    color=palette(d)['--cover-mark-ink']
    out=['<svg viewBox="0 0 160 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">']
    for kind,v in primitives(d['motif']):
        a,b,c,e=v
        if kind=='line': out.append(f'<line x1="{a}" y1="{b}" x2="{c}" y2="{e}" stroke="{color}" stroke-width="1.5"/>')
        else: out.append(f'<rect x="{a}" y="{b}" width="{c-a}" height="{e-b}" stroke="{color}" fill="none" stroke-width="1.5"/>')
    return ''.join(out)+'</svg>'
