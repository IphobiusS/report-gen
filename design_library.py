"""Versioned, portable report appearances and original certification writing aids."""
from error_messages import message as backend_message
from copy import deepcopy
from pathlib import Path
import json
import re
import uuid
from input_guard import load_json_file, load_json
from storage import atomic_write

CATALOG = Path(__file__).parent / 'designs' / 'certifications.json'
LAYOUTS = ('rail', 'split', 'frame', 'band', 'timeline')
MOTIFS = ('network', 'web', 'code', 'wifi', 'events', 'ai', 'blocks')
VARIANTS = ('brand', 'quiet')
FIELDS = {'schema', 'id', 'name', 'provider', 'certificate', 'accent', 'background', 'layout', 'motif', 'variant', 'base_theme', 'guidance_id'}


def catalog():
    return load_json_file(CATALOG)


def localized(value, lang='es'):
    return value.get(lang, value.get('es', '')) if isinstance(value, dict) else value


def text(value, name, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c)<32 for c in value):
        raise ValueError(backend_message('{p0}: texto requerido de hasta {p1} caracteres', p0=name, p1=limit))
    return value.strip()


def validate_design(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError(backend_message('meta.design: configuración de diseño incompleta o desconocida'))
    d = deepcopy(value)
    if type(d['schema']) is not int or d['schema'] != 1: raise ValueError(backend_message('Versión de diseño no soportada'))
    for key in ('id', 'name', 'provider', 'certificate'):
        d[key] = text(d[key], key)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', d['id']): raise ValueError(backend_message('Identificador de diseño inválido'))
    for key in ('accent', 'background'):
        if not isinstance(d[key], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', d[key]): raise ValueError(backend_message('{p0}: usa #RRGGBB', p0=key))
        d[key] = d[key].upper()
    if d['layout'] not in LAYOUTS or d['motif'] not in MOTIFS or d['variant'] not in VARIANTS or d['base_theme'] != 'ejecutivo':
        raise ValueError(backend_message('Composición o variante de diseño no soportada'))
    if not isinstance(d['guidance_id'],str) or d['guidance_id'] not in {p['id'] for p in catalog()['profiles']}:
        raise ValueError(backend_message('Referencia de orientación desconocida'))
    return d


def profile(ident, personal=None):
    for p in catalog()['profiles'] + (personal or {}).get('templates', []):
        if p['id'] == ident: return deepcopy(p)
    raise ValueError(backend_message('Plantilla inexistente'))


def appearance(p, variant=None):
    if variant is None:
        variant = p.get('design', {}).get('variant', 'brand')
    if variant not in VARIANTS: raise ValueError(backend_message('Variante inválida'))
    if 'design' in p:
        d=deepcopy(p['design']); d['variant']=variant
    else:
        d={k:p[k] for k in ('id','name','provider','certificate','accent','background','layout','motif')}
        d.update(schema=1,variant=variant,base_theme='ejecutivo',guidance_id=p['id'])
    return validate_design(d)


def starter_sections(p, lang='es'):
    return [{k:localized(v,lang) for k,v in s.items()} for s in p['sections']]


def apply(data, p, variant=None):
    result=deepcopy(data)
    result.setdefault('meta', {}).update(theme='ejecutivo', design=appearance(p,variant))
    return result


def new_report(p, title, lang='es', variant=None):
    if lang not in ('es','en'): raise ValueError(backend_message('Idioma no soportado'))
    return {'meta':{'lang':lang,'theme':'ejecutivo','report_title':text(title,'Título',300),
                    'report_subtitle':p['name'], 'client':'','assessor':'','date':'','version':'1.0',
                    'branding':{'wordmark':'report-gen','confidential_text':'CONFIDENCIAL' if lang=='es' else 'CONFIDENTIAL'},
                    'design':appearance(p,variant)},
            'report':{'sections':starter_sections(p,lang)},'findings':[]}


def guidance(data):
    d=(data.get('meta') or {}).get('design')
    if not d: return None
    d=validate_design(d); p=profile(d['guidance_id']); g=deepcopy(p['guidance'])
    g['note']=localized(g['note'],data['meta'].get('lang','es')); g['name']=p['name']
    return g


def load_personal(path):
    path=Path(path)
    result=load_json_file(path) if path.is_file() else {'format':'report-gen-designs','version':1,'templates':[]}
    if not isinstance(result,dict) or result.get('format')!='report-gen-designs' or type(result.get('version')) is not int or result['version']!=1 or not isinstance(result.get('templates'),list) or len(result['templates'])>200:
        raise ValueError(backend_message('Biblioteca de diseños inválida'))
    seen = set()
    for p in result['templates']:
        if not isinstance(p,dict) or not re.fullmatch(r'custom-[a-f0-9]{32}',str(p.get('id',''))): raise ValueError(backend_message('Plantilla personal inválida'))
        if p['id'] in seen: raise ValueError(backend_message('Plantilla personal inválida'))
        seen.add(p['id'])
        text(p.get('name'), 'Nombre')
        # Older personal templates may omit the counter (the next edit starts
        # at one); a present counter must be safe to increment after restore.
        if 'revision' in p and (type(p['revision']) is not int or p['revision'] < 1):
            raise ValueError(backend_message('Plantilla personal inválida'))
        validate_design(p.get('design'))
        validate_sections(p.get('sections'))
    return result


def validate_sections(sections):
    if not isinstance(sections,list) or not 1<=len(sections)<=40: raise ValueError(backend_message('Usa entre 1 y 40 secciones'))
    result=[]; seen=set()
    for s in sections:
        if not isinstance(s,dict) or set(s)-{'key','title','body'}: raise ValueError(backend_message('Estructura de sección inválida'))
        key=s.get('key')
        if not isinstance(key,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,79}',key) or key in seen: raise ValueError(backend_message('Clave de sección inválida o repetida'))
        seen.add(key)
        row={'key':key}
        for k in ('title','body'):
            if k in s:
                value=s[k]
                if isinstance(value,dict):
                    if set(value)-{'es','en'}: raise ValueError(backend_message('Idioma de sección inválido'))
                    value={lang:text(v,k,200 if k=='title' else 4000) for lang,v in value.items()}
                else: value=text(value,k,200 if k=='title' else 4000)
                row[k]=value
        if key!='findings' and not row.get('title'): raise ValueError(backend_message('Escribe el título de cada sección'))
        result.append(row)
    return result


def put_personal(path, body, ident=None):
    if not isinstance(body,dict) or set(body)-{'name','design','sections'}: raise ValueError(backend_message('Plantilla personal inválida'))
    lib=load_personal(path)
    old=next((p for p in lib['templates'] if p['id']==ident),None)
    if ident and not old: raise ValueError(backend_message('Plantilla inexistente'))
    if not old and len(lib['templates'])>=200: raise ValueError(backend_message('Límite de 200 plantillas'))
    name=text(body.get('name'),'Nombre')
    d=validate_design(body.get('design'))
    uid=ident or 'custom-'+uuid.uuid4().hex
    d.update(id=uid,name=name,provider='Personal')
    from sections import catalog_by_key
    known=catalog_by_key()
    prepared=validate_sections(body.get('sections'))
    for section in prepared:
        if section['key'] in known and section['key']!='findings':
            section['key']='personal-'+section['key']
    prepared=validate_sections(prepared)
    entry={'id':uid,'name':name,'provider':'Personal','certificate':d['certificate'],'design':d,
           'sections':prepared,'revision':(old or {}).get('revision',0)+1}
    lib['templates']=[entry if p['id']==uid else p for p in lib['templates']]
    if not old: lib['templates'].append(entry)
    blob=(json.dumps(lib,ensure_ascii=False,indent=2)+'\n').encode()
    load_json(blob)  # Do not commit a library that the bounded reader cannot reopen.
    atomic_write(path,blob,backup=True)
    return entry
