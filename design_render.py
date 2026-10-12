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
.profile-cover.layout-editorial .cover-main{text-align:left;padding:8mm 0 0;border-top:1.1mm solid var(--cover-rule);}
.profile-cover.layout-editorial .cover-bottom{border-top:1px solid var(--cover-meta-border);padding-top:4mm;}
.profile-cover.layout-editorial .cover-foot{text-align:left;}
.profile-cover .cover-meta td{border-color:var(--cover-meta-border);}
'''
