"""Publication boundary. Originals and author data never change here."""
from error_messages import message as backend_message
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote, urlsplit
from urllib.request import url2pathname
import re
from lxml import html
from PIL import Image, ImageOps
from image_integrity import jpeg_without_metadata as _jpeg_without_metadata, verify_container

# Literal substitutions are opt-in and operate on content, never file names or IDs.
PRIVATE = {'attachments', 'capture_inbox', 'publication', 'import_source', 'original', 'provenance', 'insights',
           'remediation_exchanges', 'project_management', 'import_observations', 'review_exchange',
           'client_profile', 'external_tickets', 'http_evidence'}
STRUCTURAL = {'src','uid','id','key','mode','theme','lang','severity','status','state','specialty','result','verification','type','kind','layout','family','provider','profile','variant','sha256','capture_uid','asset_uid','logo','client_logo','cover_image','cvss_vector','cvss_version','report_density','accent','background','foreground'}

def validate_config(config):
    if not isinstance(config, dict) or set(config)-{'redactions','exceptions'}:
        raise ValueError(backend_message('Publicación inválida / Invalid publication settings'))
    for key in ('redactions','exceptions'):
        rows=config.get(key,[])
        if not isinstance(rows,list) or len(rows)>200: raise ValueError(backend_message('Máximo 200 decisiones / Maximum 200 decisions'))
        for row in rows:
            keys=('needle','replacement') if key=='redactions' else ('id','reason')
            if not isinstance(row,dict) or set(row)!=set(keys) or any(not isinstance(row[k],str) for k in keys): raise ValueError(backend_message('Decisión inválida / Invalid decision'))
            if key=='redactions' and not 4<=len(row['needle'])<=2000: raise ValueError(backend_message('Texto literal: 4–2000 caracteres / Literal text: 4–2000 characters'))
            if any(len(row[k])>4000 for k in keys) or (key=='exceptions' and not row['reason'].strip()): raise ValueError(backend_message('Justificación obligatoria / A reason is required'))

class LiteralRedactions:
    """Bound every intermediate substitution before allocating its result.

    Decisions stay literal and sequential. UTF-8 accounting covers final
    strings cumulatively; a single intermediate string may never exceed the
    same 16 MiB document budget. It is an integrity/resource guard, not a
    classifier of secrets or authorization.
    """
    def __init__(self, rules):
        from input_guard import MAX_EXPANDED_TEXT, ensure_data_tree
        validate_config({'redactions': rules})
        ensure_data_tree(rules)
        self.limit = MAX_EXPANDED_TEXT
        self.used = 0
        self.rules = [(row['needle'], row['replacement'], len(row['needle'].encode('utf-8')),
                       len(row['replacement'].encode('utf-8'))) for row in rules]

    def text(self, value, apply_rules=True):
        if not isinstance(value, str):
            raise ValueError(backend_message('La sustitución literal requiere texto / Literal substitution requires text'))
        if len(value) > self.limit:
            raise ValueError(backend_message('La publicación supera 16 MiB de texto / Publication exceeds 16 MiB of text'))
        size = len(value.encode('utf-8'))
        if size > self.limit:
            raise ValueError(backend_message('La publicación supera 16 MiB de texto / Publication exceeds 16 MiB of text'))
        if apply_rules:
            for needle, replacement, needle_bytes, replacement_bytes in self.rules:
                count = value.count(needle)
                if not count:
                    continue
                predicted = size + count * (replacement_bytes - needle_bytes)
                if predicted > self.limit:
                    raise ValueError(backend_message('La sustitución literal expandiría el texto por encima de 16 MiB / Literal substitution would expand text beyond 16 MiB'))
                value = value.replace(needle, replacement)
                size = predicted
        if size > self.limit - self.used:
            raise ValueError(backend_message('La publicación supera 16 MiB de texto acumulado / Publication exceeds 16 MiB of cumulative text'))
        self.used += size
        return value


def project(source):
    from input_guard import ensure_data_tree
    # Reject oversized/recursive/nonportable source before copying or replacing.
    ensure_data_tree(source)
    from http_evidence import project_for_export
    data=project_for_export(source)
    config=data.pop('publication',{})
    validate_config(config)
    substitutions=LiteralRedactions(config.get('redactions',[]))

    def visit(node, key='', apply_rules=True, filter_private=True):
        if key in ('design','workflow'):
            apply_rules=False
            filter_private=False
        if isinstance(node,dict):
            return {substitutions.text(k,False):visit(v,k,apply_rules,filter_private)
                    for k,v in node.items() if not filter_private or k not in PRIVATE}
        if isinstance(node,list):
            return [visit(v,key,apply_rules,filter_private) for v in node]
        if isinstance(node,str):
            return substitutions.text(node,apply_rules and key not in STRUCTURAL and not key.endswith(('_uid','_uids')))
        return node
    result=visit(data)
    ensure_data_tree(result)
    return result

def _image_format(source):
    fmt=source.format
    if fmt not in ('PNG','JPEG','WEBP','GIF'): raise ValueError(backend_message('Imagen no admitida / Unsupported image'))
    if source.width*source.height>25_000_000: raise ValueError(backend_message('Imagen demasiado grande / Image too large'))
    if source.width*source.height*getattr(source,'n_frames',1)>50_000_000: raise ValueError(backend_message('Animación demasiado grande / Animation too large'))
    if getattr(source,'n_frames',1)>200: raise ValueError(backend_message('Máximo 200 fotogramas / Maximum 200 image frames'))
    return fmt


def validate_image(blob):
    """Decode the bounded image without creating a sanitized export copy.

    A text-only preparation check still rejects missing/invalid rendered images,
    but does not recompress every image just to count outgoing text alerts.
    """
    with Image.open(BytesIO(blob)) as source:
        fmt=_image_format(source)
        if fmt=='JPEG' and source.getexif().get(274,1)==1:
            _jpeg_without_metadata(blob)
            return
        verify_container(blob,fmt)
        for index in range(getattr(source,'n_frames',1)):
            source.seek(index)
            ImageOps.exif_transpose(source).load()


def clean_image(blob):
    """New pixels, no EXIF/PNG comments/XMP/ICC. Orientation and GIF frames retained."""
    with Image.open(BytesIO(blob)) as source:
        fmt=_image_format(source)
        if fmt=='JPEG' and source.getexif().get(274,1)==1: return _jpeg_without_metadata(blob)
        verify_container(blob,fmt)
        frames=[]
        durations=[]
        for index in range(getattr(source,'n_frames',1)):
            source.seek(index)
            oriented=ImageOps.exif_transpose(source)
            mode='RGB' if fmt=='JPEG' or (source.mode=='RGB' and 'transparency' not in source.info) else 'RGBA'
            pixels=oriented.convert(mode)
            fresh=Image.new(mode,pixels.size)
            fresh.paste(pixels)
            frames.append(fresh)
            durations.append(source.info.get('duration',100))
        out=BytesIO()
        opts={'quality':95,'subsampling':0} if fmt=='JPEG' else {'lossless':True} if fmt=='WEBP' else {}
        if len(frames)>1 and fmt in ('GIF','WEBP','PNG'):
            opts.update(save_all=True,append_images=frames[1:],duration=durations,loop=source.info.get('loop',0))
        frames[0].save(out,format=fmt,**opts)
        return _jpeg_without_metadata(out.getvalue()) if fmt=='JPEG' else out.getvalue()

def render(data,directory):
    import engine
    return html.fromstring(engine.render_html(engine.build_env(),project(data),Path(directory).resolve(),{},False,engine.load_lang(engine.report_language(data))))

def images(tree,directory):
    from resources import local_image
    directory=Path(directory).resolve()
    out={}
    for src in tree.xpath('//img/@src'):
        relative=Path(url2pathname(urlsplit(src).path)).relative_to(directory).as_posix()
        out[relative]=local_image(quote(relative,safe='/'),directory)
    return out

def snapshot(directory,target,data=None):
    import engine
    from wizard import dump_yaml
    source=data if data is not None else engine.load_engagement(Path(directory)/'engagement.yaml')
    data=project(source)
    # Graph images are derived from this exact publication, never reused from
    # stale presentation metadata embedded in a source or an earlier capture.
    data.pop('attack_path_figures', None)
    tree=render(data,directory)
    target=Path(target);target.mkdir(parents=True,exist_ok=True)
    from urllib.parse import unquote
    ids=set(tree.xpath('//*[@id]/@id'))
    for ref in tree.xpath('//a[starts-with(@href,"#")]/@href'):
        if ref!="#" and unquote(ref[1:]) not in ids:
            raise ValueError(backend_message('Referencia interna sin destino: {p0} / Missing internal destination', p0=ref))
    inventory={}
    from exporters.images import word_image_blob
    for name,path in images(tree,directory).items():
        original=path.read_bytes(); blob=clean_image(original)
        dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob)
        word_blob, _ = word_image_blob(blob)
        inventory[name]={'original_sha256':sha256(original).hexdigest(),'sha256':sha256(blob).hexdigest(),
                         'docx_sha256':sha256(word_blob).hexdigest(),'bytes':len(blob),'metadata_removed':True}
    resource_directory = directory
    if data.get('attack_paths') and data.get('report', {}).get('workflow', {}).get('include_attack_paths', True):
        from attack_paths import stage_graphs
        data = stage_graphs(data, target)
        tree = render(data, target)
        resource_directory = target
        for name, path in images(tree, target).items():
            if name in inventory:
                continue
            # Fresh pixels from our deterministic graph renderer already have
            # no source metadata. Preserve its content-addressed filename.
            blob = path.read_bytes()
            word_blob, _ = word_image_blob(blob)
            inventory[name] = {'original_sha256': sha256(blob).hexdigest(), 'sha256': sha256(blob).hexdigest(),
                               'docx_sha256': sha256(word_blob).hexdigest(), 'bytes': len(blob),
                               'metadata_removed': True, 'generated': 'analyst_declared_attack_path'}
    dump_yaml(data,target/'engagement.yaml')
    return {'images':{k:v['sha256'] for k,v in inventory.items()},
            'docx_images':{k:v['docx_sha256'] for k,v in inventory.items()},
            'resources':inventory,'image_placements':len(tree.xpath('//img')),
            'contract':__import__('export_contract').from_tree(
                tree,{unquote(path.as_uri()):inventory[name]['sha256'] for name,path in images(tree,resource_directory).items()},
                {v['sha256']:v['docx_sha256'] for v in inventory.values()})}

PATTERNS = [
 ('private_key',re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
 ('credential',re.compile(r'(?i)(?:password|passwd|api[_-]?key|secret|token)["\']?\s*[=:]\s*["\']?[^\s"\'<>]{8,}')),
 ('bearer',re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}')),
 ('aws_key',re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
]

def rendered_text(node):
    """Readable block boundaries; literal preformatted commands stay unchanged."""
    def walk(el):
        if el.tag in ('script','style'): return ''
        if el.tag=='pre': return '\n'+el.text_content()+'\n'
        parts=[]
        def text(value):
            return re.sub(r'\s+',' ',value) if value and not value.isspace() else ''
        parts.append(text(el.text))
        for child in el:
            parts.extend((walk(child),text(child.tail)))
        end='\n' if el.tag in ('section','div','p','tr','h1','h2','h3','h4','li','figure','figcaption') or el.get('class') in ('cv-field-label','cv-field-value','cv-wordmark','cv-tag') else '\t' if el.tag in ('td','th') else ''
        return ''.join(parts)+end
    return walk(node).strip()


def _inspect_text(data, tree):
    body=tree.find('body')
    text=rendered_text(body)
    decisions={x['id']:x['reason'] for x in data.get('publication',{}).get('exceptions',[])}
    alerts=[]
    for kind,pattern in PATTERNS:
        for m in pattern.finditer(text):
            if re.search(r'(?i)\[(?:redacted|censurado)\]$',m[0]): continue
            identity=sha256((kind+'\0'+m[0]).encode()).hexdigest()
            if any(x['id']==identity for x in alerts): continue
            alerts.append({'id':identity,'kind':kind,'preview':m[0][:min(6,len(m[0]))]+'…','reason':decisions.get(identity,'')})
    return dict(text=text,alerts=alerts,redactions=len(data.get('publication',{}).get('redactions',[])),private_captures=len(data.get('capture_inbox',[])))


def inspect_text(data,directory):
    """Outgoing text patterns with bounded image validity, without image export."""
    tree=render(data,directory)
    for path in images(tree,directory).values():
        validate_image(path.read_bytes())
    return _inspect_text(data,tree)


def inspect(data,directory):
    tree=render(data,directory)
    result=_inspect_text(data,tree)
    inventory=[]
    for name,path in images(tree,directory).items():
        original=path.read_bytes();clean=clean_image(original)
        with Image.open(BytesIO(original)) as im: metadata=sorted(k for k in im.info if k not in ('duration','loop','transparency'))
        inventory.append(dict(name=name,bytes=len(clean),original_sha256=sha256(original).hexdigest(),sha256=sha256(clean).hexdigest(),metadata=metadata,metadata_removed=True))
    return dict(result,images=inventory)

def comparison_projection(data,files):
    """Use actual rendered output, not every YAML field or every stored image."""
    from resources import relative_image
    with TemporaryDirectory(prefix='rg-comparison-') as tmp:
        directory=Path(tmp)
        for name,blob in files.items():
            if name=='engagement.yaml' or name.startswith('originals/'): continue
            try: member=relative_image(name)
            except ValueError: continue
            path=directory/member;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob)
        tree=render(data,directory)
        public_images={name:clean_image(p.read_bytes()) for name,p in images(tree,directory).items()}
        findings=[]
        source={f['id']:f for f in data.get('findings',[])}
        for node in tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," finding ")]'):
            f=source.get(node.get('id'),{})
            findings.append(dict(id=node.get('id'),uid=f.get('uid',node.get('id')),title=project({'title':f.get('title',''),'publication':data.get('publication',{})})['title'],content=rendered_text(node)))
            node.drop_tree()
        return dict(meta={'report_title':tree.xpath('string(//title)')},findings=findings,report=rendered_text(tree.find('body'))),public_images
