"""Explicit delivery annexes. Private until individually reviewed and selected."""
from error_messages import message as backend_message
from hashlib import sha256
from pathlib import Path
import re
import unicodedata

MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
SUFFIXES = {'.txt', '.json', '.csv', '.md', '.pdf', '.png', '.jpg', '.jpeg', '.webp'}
MEMBER = re.compile(r'^attachments/[a-f0-9]{32}\.(?:txt|json|csv|md|pdf|png|jpg|jpeg|webp)$')


def valid_name(name):
    if not isinstance(name, str) or not 1 <= len(name) <= 120:
        return False
    if any(unicodedata.category(c) in {'Cc','Cf','Cs','Zl','Zp'} for c in name): return False
    if len(name.encode('utf-8')) > 200: return False
    if name != name.strip() or name.endswith('.') or re.search(r'[\x00-\x1f\x7f/\\:*?"<>|]', name):
        return False
    stem = name.split('.')[0].upper()
    return stem not in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} and Path(name).suffix.lower() in SUFFIXES


def validate_rows(rows):
    from workflows import UID
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError(backend_message('Anexos: máximo 100 registros / Annexes: maximum 100 records'))
    names, uids = set(), set()
    for row in rows:
        if not isinstance(row,dict) or set(row)-{'uid','name','member','sha256','include','reviewed','required'}:
            raise ValueError(backend_message('Anexo inválido / Invalid annex'))
        if not isinstance(row.get('uid'),str) or not UID.fullmatch(row['uid']) or row['uid'] in uids:
            raise ValueError(backend_message('Identificador de anexo inválido o duplicado / Invalid or duplicate annex ID'))
        uids.add(row['uid'])
        name=row.get('name')
        canonical=unicodedata.normalize('NFC',name).casefold() if isinstance(name,str) else ''
        if not valid_name(name) or canonical in names:
            raise ValueError(backend_message('Nombre de anexo no portable o duplicado / Nonportable or duplicate annex name'))
        names.add(canonical)
        for key in ('include','reviewed','required'):
            if type(row.get(key,False)) is not bool: raise ValueError(backend_message('Decisión de anexo inválida / Invalid annex decision'))
        member=row.get('member','')
        if not isinstance(member,str) or (member and (not MEMBER.fullmatch(member) or Path(member).suffix!=Path(name).suffix.lower())):
            raise ValueError(backend_message('Ruta de anexo inválida / Invalid annex path'))
        if member and (not isinstance(row.get('sha256'),str) or not re.fullmatch(r'[a-f0-9]{64}',row['sha256'])):
            raise ValueError(backend_message('Hash de anexo inválido / Invalid annex hash'))
        if row.get('include') and not row.get('reviewed'):
            raise ValueError(backend_message('Revisa el anexo antes de incluirlo / Review the annex before including it'))


def validate_blob(member, blob):
    if not MEMBER.fullmatch(member) or not 0 < len(blob) <= MAX_FILE:
        raise ValueError(backend_message('Anexo vacío, demasiado grande o no permitido / Empty, oversized or unsupported annex'))
    suffix=Path(member).suffix
    if suffix in {'.png','.jpg','.jpeg','.webp'}:
        from project_history import validate_image_blob
        validate_image_blob(member,blob)
    elif suffix=='.pdf':
        if not blob.startswith(b'%PDF-'): raise ValueError(backend_message('Cabecera PDF inválida / Invalid PDF header'))
    else:
        try: text=blob.decode('utf-8-sig')
        except UnicodeDecodeError as exc: raise ValueError(backend_message('Anexo de texto: usa UTF-8 / Text annex: use UTF-8')) from exc
        if '\x00' in text: raise ValueError(backend_message('Anexo de texto con bytes nulos / Text annex has null bytes'))


def read(directory, row):
    if not row.get('member'): raise ValueError(backend_message('Anexo declarado sin archivo / Declared annex has no file'))
    root=Path(directory).resolve();path=root/row['member']
    if (root/'attachments').is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError(backend_message('Anexo ausente o enlazado / Annex missing or symlinked'))
    if not path.resolve().is_relative_to(root): raise ValueError(backend_message('Anexo fuera del proyecto / Annex outside project'))
    if path.stat().st_size > MAX_FILE: raise ValueError(backend_message('Anexo mayor que 16 MiB / Annex exceeds 16 MiB'))
    with path.open('rb') as source: blob=source.read(MAX_FILE+1)
    validate_blob(row['member'],blob)
    if sha256(blob).hexdigest()!=row['sha256']: raise ValueError(backend_message('Anexo alterado / Annex changed'))
    return blob


def inventory(data, directory):
    rows=data.get('attachments',[]);validate_rows(rows)
    out=[];total=0
    for row in rows:
        item=dict(uid=row['uid'],name=row['name'],include=row.get('include',False),reviewed=row.get('reviewed',False),required=row.get('required',False),bytes=0,status='declared')
        if row.get('member'):
            try:
                blob=read(directory,row);total+=len(blob)
                item.update(bytes=len(blob),sha256=sha256(blob).hexdigest(),status='included' if item['include'] else 'excluded')
            except ValueError as exc: item.update(status='missing',error=str(exc))
        out.append(item)
    if total > MAX_TOTAL: raise ValueError(backend_message('Anexos mayores que 64 MiB / Annexes exceed 64 MiB'))
    return out


def capture(data, directory, target):
    states=inventory(data,directory);result={}
    for row,state in zip(data.get('attachments',[]),states):
        if row.get('required') and state['status']!='included':
            raise ValueError(backend_message('Anexo obligatorio pendiente: {p0} / Required annex not included', p0=row['name']))
        if not row.get('include'): continue
        if state['status']!='included': raise ValueError(state.get('error', backend_message('Anexo seleccionado sin archivo / Selected annex has no file', en='Selected annex has no file', pt='O anexo selecionado não possui arquivo')))
        blob=read(directory,row);name='anexos/'+row['name']
        dest=Path(target)/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob)
        result[name]={'sha256':sha256(blob).hexdigest(),'bytes':len(blob)}
    return result


def scan(directory, row):
    """Advisory inspection bound to a validated hash. Never return matched secrets.

    UTF-8 text: bounded pattern scan. Images: metadata keys, no OCR. PDF text
    and structural objects are inspected in a separate resource-limited worker.
    No type is certified free of private information; PDF coverage is partial.
    """
    from io import BytesIO
    from collections import Counter
    import publication
    blob=read(directory,row);suffix=Path(row['member']).suffix
    result=dict(sha256=sha256(blob).hexdigest(),bytes=len(blob),bytes_inspected=0,
                complete=False,alerts=[],scope='manual',manual_review_required=True)
    if suffix in {'.txt','.json','.csv','.md'}:
        limit=1024*1024; text=blob[:limit].decode('utf-8-sig',errors='ignore')
        counts=Counter()
        patterns=[*publication.PATTERNS,
                  ('possible_email',re.compile(r"[\w.+-]{1,64}@[\w.-]{1,127}\.[A-Za-z]{2,24}")),
                  ('possible_rut',re.compile(r"(?<![\w])(?:\d{1,2}\.\d{3}\.\d{3}|\d{7,8})-[0-9kK](?![\w])"))]
        for kind,pattern in patterns:
            for match in pattern.finditer(text):
                if re.search(r'(?i)\[(?:redacted|censurado)\]$',match[0]):continue
                counts[kind]+=1
        result.update(scope='utf8_patterns',bytes_inspected=min(limit,len(blob)),complete=len(blob)<=limit,
                      alerts=[dict(kind=k,count=v) for k,v in sorted(counts.items())])
    elif suffix == '.pdf':
        from pdf_attachment_inspection import inspect_pdf
        result.update(inspect_pdf(blob))
    elif suffix in {'.png','.jpg','.jpeg','.webp'}:
        from PIL import Image
        with Image.open(BytesIO(blob)) as image:
            keys=set(image.info)-{'duration','loop','transparency'}
            count=len(keys)+len(image.getexif())
        result.update(scope='image_metadata',bytes_inspected=len(blob),complete=False,
                      alerts=[dict(kind='image_metadata',count=count)] if count else [])
    return result
