"""Self-contained client report: offline, no editor, no external assets."""
from base64 import b64encode
from hashlib import sha256
from html import escape
from pathlib import Path
from urllib.parse import unquote
import mimetypes
import re
from lxml import html
import engine
import publication

BOOTSTRAP="document.documentElement.classList.add('report-js');"
SCRIPT='''(()=>{'use strict';
const q=s=>document.querySelector(s),all=[...document.querySelectorAll('.finding')],toolbar=q('.report-toolbar');
if(!toolbar)return;
const fold=text=>text.normalize('NFC').toLocaleLowerCase();
const searchable=new Map(all.map(item=>[item,fold(item.textContent)]));
function toolbarOffset(){
 const height=getComputedStyle(toolbar).position==='sticky'?toolbar.getBoundingClientRect().height:0;
 document.documentElement.style.setProperty('--report-toolbar-offset',(height+16)+'px');
}
toolbarOffset();
if(window.ResizeObserver)new ResizeObserver(toolbarOffset).observe(toolbar);
window.addEventListener('resize',toolbarOffset);
function draw(){
 const term=fold(q('#query').value.trim()),kind=q('#kind').value,executive=q('#view').value==='executive';
 if(kind==='machine')q('#severity').value='';
 q('#severity').disabled=kind==='machine';const sev=q('#severity').value;let count=0;
 for(const item of all){
  const match=(!term||searchable.get(item).includes(term))&&(!kind||item.dataset.reportKind===kind)&&(!sev||item.dataset.reportSeverity===sev);
  item.hidden=executive||!match;if(match)count++;
 }
 q('#results').textContent=count+' / '+all.length;document.body.classList.toggle('executive',executive);
 q('#empty-results').hidden=executive||count>0;
}
for(const id of ['query','kind','severity','view'])q('#'+id).addEventListener('input',draw);
q('#clear-filters').addEventListener('click',()=>{for(const id of ['query','kind','severity'])q('#'+id).value='';q('#view').value='technical';draw();q('#query').focus();});
q('#print').addEventListener('click',()=>window.print());
function reveal(hash){let id;try{id=decodeURIComponent(hash.slice(1));}catch(_){return;}
 const el=document.getElementById(id);if(el?.closest('.finding')||el?.querySelector('.finding')){
  for(const id of ['query','kind','severity'])q('#'+id).value='';q('#view').value='technical';draw();toolbarOffset();el.scrollIntoView();
 }}
document.addEventListener('click',event=>{
 if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
 const link=event.target.closest?.('a[href^="#"]');
 if(link&&(!link.target||link.target==='_self')&&!link.hasAttribute('download'))reveal(link.getAttribute('href'));
});
window.addEventListener('hashchange',()=>reveal(location.hash));draw();toolbar.hidden=false;toolbarOffset();})();'''
STYLE='''@font-face{font-family:Report;font-display:swap;src:url(data:font/ttf;base64,FONT)}
*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#172435;font:17px/1.65 Calibri,Report,Arial,sans-serif}.report-content{max-width:1060px;margin:auto;padding:32px;overflow-wrap:anywhere}h1,h2,h3{line-height:1.25;color:#142b42}h1{font-size:2.2rem}h2{font-size:1.65rem}h3{font-size:1.25rem}a{color:#155a8a;overflow-wrap:anywhere}img{display:block;max-width:100%;height:auto;max-height:740px;object-fit:contain;margin:16px auto}figure{margin:24px 0}figcaption,.caption{color:#45566b}figcaption{white-space:pre-line}pre{background:#edf1f5;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere;border-left:3px solid #356483}code{font-family:Consolas,monospace;font-size:.88em}table{border-collapse:collapse;width:100%!important;table-layout:auto;margin:20px 0}td,th{padding:10px;border-bottom:1px solid #bbc8d4;text-align:left;overflow-wrap:anywhere}th{background:#e9eef3}.frontsec,.finding{background:white;border:1px solid #d5dee6;padding:28px;margin:24px 0;border-radius:6px}.cover{background:#132c40;color:white;padding:64px 32px;text-align:center;border-radius:6px}.cover h1,.cover h2,.cover h3{color:white}.cover table{margin-top:48px}.cover td,.cover th{background:transparent;color:white}.cover-top{display:flex;flex-wrap:wrap;justify-content:space-between;gap:24px;text-align:left}.cover-center{padding:40px 0 8px}.cv-field-label,.cv-field-value{display:block}.cv-field-label{font-size:13px;margin-bottom:6px;opacity:.85}.cover-foot{text-align:center}.profile-identity{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:24px;margin-top:24px}.provider-logo{max-width:100%;min-width:0}.provider-logo svg{display:block;width:170px;max-width:100%;height:auto;max-height:70px}.cover img{max-width:min(210px,100%);max-height:130px}.sevchart{max-width:500px}.toc .pg,.c-pg,.pm{display:none}.toc-list{list-style:none;padding:0}.toc-list a{display:block;padding:8px}.sev-chip,.severity{font-weight:bold}.sev-critical>.finding-intro,.sev-high>.finding-intro{border-left:4px solid #a82b36;padding-left:16px}.sec-num{color:#49647b;margin-right:8px}.report-toolbar{position:sticky;top:0;z-index:10;background:white;border-bottom:1px solid #bcc9d5;padding:12px 24px;display:flex;align-items:end;gap:16px;flex-wrap:wrap}.report-toolbar label{font-size:14px;display:grid;gap:4px;min-width:0;max-width:100%}.report-toolbar input,.report-toolbar select,.report-toolbar button{font:inherit;border:1px solid #64778b;background:white;color:#172435;border-radius:4px;min-height:44px;padding:8px 12px;max-width:100%}.report-toolbar input,.report-toolbar select{width:100%;min-width:0}.report-toolbar button{cursor:pointer}.report-note{max-width:1000px;margin:20px auto;padding:0 24px;color:#43576b;font-size:14px}.report-toolbar :focus-visible,a:focus-visible{outline:3px solid #007f63;outline-offset:3px}[hidden]{display:none!important}.executive .sect-findings{display:none}html{scroll-padding-top:var(--report-toolbar-offset,16px)}section,div[id]{scroll-margin-top:0}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}@media(max-width:600px){.report-content{padding:12px}.frontsec,.finding{padding:16px}.cover{padding:40px min(16px,3%)}.report-toolbar{position:static;padding:12px;gap:8px}.report-toolbar label{flex:1 1 12em;min-width:min(100%,12em)}h1{font-size:1.75rem}td,th{padding:6px;font-size:14px}}@media print{@page{size:A4;margin:16mm}body{background:white;font-size:11pt}.report-toolbar,.report-note{display:none}.report-content{padding:0;max-width:none}.frontsec,.finding{border:0;padding:0}.cover{background:white;color:#172435;break-after:page}.cover h1,.cover h2,.cover h3,.cover td,.cover th{color:#172435}h1,h2,h3{break-after:avoid}img{max-height:160mm}pre{white-space:pre-wrap}a{color:inherit}}'''

TABLE_STYLE = '''
@media screen{html.report-js .report-toolbar[hidden]{display:flex!important;visibility:hidden}
 .report-data td,.report-data th{overflow-wrap:break-word;word-break:normal}
}
td,th{vertical-align:top}
table.report-fields{table-layout:fixed}
.report-fields>tbody>tr>th,.report-fields>tr>th{width:24%}
.report-table-region{max-width:100%;min-width:0;overflow-x:auto;overscroll-behavior-inline:contain;margin:20px 0}
.report-table-region:focus-visible{outline:3px solid #007f63;outline-offset:3px}
.report-table-region>table{margin:0}
.report-data td,.report-data th{min-width:9ch}
@media screen and (max-width:600px){
 h2{font-size:1.4rem}
 .report-table-region::before{content:attr(data-scroll-hint);display:block;padding:6px 0;color:#43576b;font-size:13px;line-height:1.5}
 .report-fields,.report-fields>tbody,.report-fields>tr,.report-fields>tbody>tr{display:block;width:100%}
 .report-fields>tr>th,.report-fields>tr>td,.report-fields>tbody>tr>th,.report-fields>tbody>tr>td{display:block;width:100%}
 .report-fields>tr>th,.report-fields>tbody>tr>th{border-bottom:0;padding-top:10px}
 .report-fields>tr>td,.report-fields>tbody>tr>td{padding-bottom:12px}
}
@media print{
 .report-fields>tbody>tr>th,.report-fields>tr>th{width:25%}
 .report-table-region{overflow:visible;max-width:none;outline:0}
 .report-data{min-width:0!important;font-size:9pt}
 .report-data td,.report-data th{min-width:0;font-size:inherit;overflow-wrap:anywhere}
}
'''

# Prefer existing word boundaries in inline code, while literal commands and
# URL labels fill the available width. CSS changes only visual wrapping, so
# copied text and link destinations stay exact.
TEXT_FLOW_STYLE = '''
code{overflow-wrap:anywhere;word-break:normal;line-break:auto}
pre,pre code,.report-literal-url,.report-literal-url code{overflow-wrap:anywhere;word-break:break-all;line-break:anywhere}
.report-literal-token{overflow-wrap:anywhere;word-break:break-all}
.report-content blockquote{margin-inline:0;border-inline-start:3px solid #64778b;padding-inline-start:min(1em,5%)}
.report-content ol:not(.report-counter-list){padding-inline-start:max(40px,calc((var(--report-counter-digits,1) + 1)*1ch))}
@media(max-width:600px){
 .report-content ul:not(.toc-list){padding-inline-start:1.5em}
 .report-content ol:not(.report-counter-list){padding-inline-start:max(24px,calc((var(--report-counter-digits,1) + 1)*1ch))}
 pre{padding:12px}
}
.report-list-region{max-width:100%;min-width:0;overflow-x:auto;overscroll-behavior-inline:contain;margin:1em 0}
.report-list-region:focus-visible{outline:3px solid #007f63;outline-offset:3px}
.report-content .report-counter-list{margin:0;padding-inline-start:calc((var(--report-counter-digits) + 2)*1ch);min-width:calc((var(--report-counter-digits) + 10)*1ch)}
@media screen and (max-width:600px){.report-list-region::before{content:attr(data-scroll-hint);display:block;padding:6px 0;color:#43576b;font-size:13px;line-height:1.5}}
@media print{.report-list-region{overflow:visible;max-width:none}.report-content .report-counter-list{min-width:0}}
'''


# Media queries use the viewport before CSS zoom. Query the report's actual
# available line width as well, so nested frames never take most of a narrow
# page, including when only text is enlarged. Keep type sizes, native lists,
# data tables and source text unchanged.
REFLOW_STYLE = '''
@media screen{
 body{container:report-page / inline-size}
 .report-content{container-type:inline-size}
 @container report-page (max-width:600px){
  .report-toolbar{position:static;padding:12px;gap:8px}
  .report-toolbar label{flex:1 1 12em;min-width:min(100%,12em)}
  .report-fields,.report-fields>tbody,.report-fields>tr,.report-fields>tbody>tr{display:block;width:100%}
  .report-fields>tr>th,.report-fields>tr>td,.report-fields>tbody>tr>th,.report-fields>tbody>tr>td{display:block;width:100%}
  .report-fields>tr>th,.report-fields>tbody>tr>th{border-bottom:0}
 }
 @container(max-width:14em){
  .cover-grid,.cover-grid>tbody,.cover-grid>tbody>tr,.cover-grid>tbody>tr>td{display:block;width:100%}
  .cover-grid>tbody>tr>td:empty{display:none}
  .frontsec,.finding{padding-inline:min(8px,3%)}
  .frontsec>.finding{border:0;border-radius:0;padding-inline:0}
  .sev-critical>.finding-intro,.sev-high>.finding-intro{padding-inline-start:min(8px,3%)}
  .remsum dd{margin-inline-start:1.5ch}
  pre{padding-inline:min(8px,4%);white-space:break-spaces}
 }
}
@media screen and (max-width:600px){.report-content{padding-inline:min(12px,3%)}}
@media print{.report-content .frontsec,.report-content .finding{padding:0}}
'''


# A record view uses the same native cells, with visual copies of their column
# labels. No source text or cell order is duplicated in the DOM. Explicit roles
# retain table semantics when display changes, including without JavaScript.
_RECORD_RULES = """
 .report-table-region:has(>.report-records)::before{content:attr(data-record-hint);display:block;padding:6px 0;color:#43576b;font-size:.85em;line-height:1.5}
 .report-records,.report-records>tbody,.report-records>tfoot,.report-records>tbody>tr,.report-records>tfoot>tr{display:block;width:100%;min-width:0!important}
 .report-records>thead{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip-path:inset(50%)}
 .report-records>tbody>tr,.report-records>tfoot>tr{border:1px solid #bbc8d4;border-radius:4px;margin-block:0 16px;padding:8px}
 .report-records>tbody>tr>td,.report-records>tbody>tr>th,.report-records>tfoot>tr>td,.report-records>tfoot>tr>th{display:block;width:100%;min-width:0;padding:8px 0;overflow-wrap:anywhere;white-space:normal}
 .report-records>tbody>tr>:last-child,.report-records>tfoot>tr>:last-child{border-bottom:0}
 .report-records .c-pg{display:none!important}
 .report-records [data-column-label]::before{content:attr(data-column-label) / "";display:block;font:inherit;font-weight:700;text-align:left;margin-bottom:.2em;color:#43576b;overflow-wrap:anywhere}
"""
RECORD_STYLE = ("""
@media screen{
 .report-table-region{container:report-table / inline-size}
 .report-list-region{container:report-list / inline-size}
 @container report-table (max-width:38em){
""" + _RECORD_RULES + """
 }
 @container report-list (max-width:38em){
  .report-content .report-counter-list{padding-inline-start:0;min-width:0;list-style-position:inside}
  .report-counter-list>li::marker{content:counter(list-item) ".\\a";white-space:pre}
 }
}
@media screen and (max-width:600px){
""" + _RECORD_RULES + """
 .report-list-region::before{content:none}
 .report-content .report-counter-list{padding-inline-start:0;min-width:0;list-style-position:inside}
 .report-counter-list>li::marker{content:counter(list-item) ".\\a";white-space:pre}
}
""")


def prepare_text_flow(tree, en=False):
    """Wrap literal runs while preserving authored text and ordinary prose."""
    for node in tree.xpath('//a[@href]|//code[not(ancestor::pre)]|//ul[contains(concat(" ",normalize-space(@class)," ")," refs ")]/li'):
        if re.fullmatch(r'(?:https?|ftp)://\S+', ''.join(node.itertext()).strip(), re.IGNORECASE):
            node.set('class', ' '.join([*(node.get('class') or '').split(), 'report-literal-url']))
    # Emergency overflow wrapping first moves a bare, overlong token to a new
    # line. Give only literal URLs and long ASCII runs normal break opportunities
    # so they can use the space after a prose label. DOM text nodes retain exact
    # characters: no soft hyphens, hidden separators or authored HTML parsing.
    literal = re.compile(r'\b(?:https?|ftps?)://[^\s<>"\'`]+|'
                         r'(?<!\S)[\x21-\x7e]{64,}(?!\S)', re.IGNORECASE)
    for slot in tree.xpath('.//text()[not(ancestor::head or ancestor::pre or '
                           'ancestor::code or ancestor::script or ancestor::style or '
                           'ancestor::textarea or ancestor::svg or ancestor::math) and '
                           'not(ancestor::*[contains(concat(" ",normalize-space(@class)," "),'
                           '" report-literal-url ") or contains(concat(" ",normalize-space(@class)," "),'
                           '" report-literal-token ")])]'):
        text = str(slot)
        matches = list(literal.finditer(text))
        if not matches:
            continue
        parent = slot.getparent()
        if slot.is_text:
            parent.text = text[:matches[0].start()]
            container, index = parent, 0
        elif slot.is_tail:
            parent.tail = text[:matches[0].start()]
            container = parent.getparent()
            index = container.index(parent) + 1
        else:
            continue
        for number, match in enumerate(matches):
            span = html.Element('span', {'class': 'report-literal-token'})
            span.text = match.group()
            end = matches[number + 1].start() if number + 1 < len(matches) else len(text)
            span.tail = text[match.end():end]
            container.insert(index, span)
            index += 1
    # Native list markers sit outside their element's box. Large, valid starts
    # can otherwise lose their leading digits beyond the viewport without
    # producing a detectable element overflow. Keep native counters and roles;
    # provide enough marker space and local keyboard scrolling when necessary.
    for ordered in tree.xpath('//ol'):
        count = len(ordered.xpath('./li'))
        start = int(ordered.get('start', '1'))
        digits = max(len(str(start)), len(str(start + max(0, count - 1))))
        ordered.set('style', ordered.get('style', '').rstrip(';') + f';--report-counter-digits:{digits}')
        if digits <= 3:
            continue
        ordered.set('class', ' '.join([*(ordered.get('class') or '').split(), 'report-counter-list']))
        region = html.Element('div', {'class': 'report-list-region', 'role': 'region', 'tabindex': '0',
                              'aria-label': ('Numbered list' if en else 'Lista numerada'),
                              'data-scroll-hint': ('Scroll horizontally to read the complete numbered list.' if en else
                                                   'Desplázate horizontalmente para leer toda la lista numerada.')})
        region.tail, ordered.tail = ordered.tail, None
        ordered.addprevious(region)
        region.append(ordered)


def prepare_tables(tree, en=False):
    """Keep native table content; give field rows and wide data distinct layouts."""
    for number, table in enumerate(tree.xpath('//table'), 1):
        rows = table.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')
        def span(cell):
            try:
                return max(1, min(100, int(cell.get('colspan', '1'))))
            except ValueError:
                return 1
        columns = max((sum(span(cell) for cell in row if cell.tag in ('th', 'td'))
                       for row in rows), default=0)
        fields = (columns == 2 and rows and
                  all(len(row) == 2 and row[0].tag == 'th' and row[1].tag == 'td'
                      for row in rows))
        classes = (table.get('class') or '').split()
        if fields:
            table.set('class', ' '.join([*classes, 'report-fields']))
            # Explicit native roles retain table semantics when CSS stacks its
            # cells on small screens, including browsers with display remapping.
            table.set('role', 'table')
            for group in table.xpath('./thead|./tbody|./tfoot'):
                group.set('role', 'rowgroup')
            for row in rows:
                row.set('role', 'row')
                row[0].set('scope', 'row')
                row[0].set('role', 'rowheader')
                row[1].set('role', 'cell')
        elif columns >= 3 or (columns == 2 and table.xpath("./thead/tr/th")):
            table.set('class', ' '.join([*classes, 'report-data']))
            headers = table.xpath('./thead/tr')
            # Markdown and generated report tables have a simple column header.
            # Complex authored spans retain the native two-dimensional fallback.
            if (len(headers) == 1 and len(headers[0]) == columns
                    and all(cell.tag == 'th' for cell in headers[0])
                    and all(len(row) == columns and all(span(cell) == 1 and cell.get('rowspan', '1') == '1'
                                                       for cell in row) for row in rows)):
                table.set('class', table.get('class') + ' report-records')
                table.set('role', 'table')
                # All native cells remain present; let the accessibility tree
                # infer totals, excluding the screen-hidden PDF page column.
                for group in table.xpath('./thead|./tbody|./tfoot'):
                    group.set('role', 'rowgroup')
                labels = [' '.join(cell.text_content().split()) or
                          (('Column ' if en else 'Columna ') + str(index + 1))
                          for index, cell in enumerate(headers[0])]
                for row in rows:
                    row.set('role', 'row')
                    for index, cell in enumerate(row):
                        cell.set('role', 'columnheader' if row is headers[0] else
                                 'rowheader' if cell.tag == 'th' else 'cell')
                        cell.set('aria-colindex', str(index + 1))
                        if row is not headers[0]:
                            cell.set('data-column-label', labels[index])
            table.set('style', (table.get('style', '').rstrip(';') + ';'
                               if table.get('style') else '') + f'min-width:{columns * 9}rem')
            for header in table.xpath('./thead/tr/th'):
                if header.get('scope') is None:
                    header.set('scope', 'col')
            heading = next((ancestor.xpath('string(.//h1|.//h2|.//h3)').strip()
                            for ancestor in table.iterancestors()
                            if ancestor.tag == 'section'), '')
            label = ('Data table ' if en else 'Tabla de datos ') + str(number)
            if heading:
                label += ': ' + ' '.join(heading.split())[:160]
            if 'report-records' not in table.get('class', '').split():
                label += '; horizontal scrolling' if en else '; desplazamiento horizontal'
            region = html.Element('div', {'class': 'report-table-region',
                                  'role': 'region', 'tabindex': '0', 'aria-label': label,
                                  'data-record-hint': ('Table shown by record; each value follows its column heading.' if en else
                                                       'Tabla por registros: cada valor aparece bajo su columna.'),
                                  'data-scroll-hint': ('Scroll horizontally to see every column.' if en
                                      else 'Desplázate horizontalmente para ver todas las columnas.')})
            region.tail, table.tail = table.tail, None
            table.addprevious(region)
            region.append(table)


def build(directory):
    from version import __version__
    directory=Path(directory)
    data=engine.load_engagement(directory/'engagement.yaml')
    tree=publication.render(data,directory)
    en=engine.report_language(data)=='en'
    w=lambda es,eng:eng if en else es
    resources=publication.images(tree,directory)
    for image in tree.xpath('//img[@src]'):
        path=next(p for p in resources.values() if unquote(p.as_uri())==unquote(image.get('src')))
        blob=publication.clean_image(path.read_bytes())
        image.set('src','data:'+(mimetypes.guess_type(path.name)[0] or 'image/png')+';base64,'+b64encode(blob).decode())
        image.set('loading','eager')
    for link in tree.xpath('//a[@href]'):
        if link.get('href').startswith(('http:','https:')): link.set('rel','noopener noreferrer')
    by_id={f.get('id'):f for f in data.get('findings',[])}
    for node in tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," finding ")]'):
        finding=by_id.get(node.get('id'),{})
        node.set('data-report-kind',finding.get('mode','vuln'))
        node.set('data-report-severity',finding.get('severity') or ('pending' if finding.get('mode')!='machine' else ''))
    prepare_tables(tree, en)
    prepare_text_flow(tree, en)
    body=tree.find('body')
    contents=''.join(html.tostring(child,encoding='unicode') for child in body)
    font=b64encode((Path(__file__).parent/'themes/fonts/Carlito-Regular.ttf').read_bytes()).decode()
    style=STYLE.replace('FONT',font) + TABLE_STYLE + TEXT_FLOW_STYLE
    if data['meta'].get('design'):
        from design_render import palette, ink_on
        design=data['meta']['design'];pal=palette(design)
        bg=pal['--profile-dark'] if design['layout']=='split' else pal['--cover-bg'];fg=ink_on(bg)
        style+='\n@media screen{.cover{background:'+bg+';color:'+fg+';border-top:5px solid '+pal['--cover-rule']+'}.cover h1,.cover h2,.cover h3,.cover td,.cover th{color:'+fg+'}}'
        if design['layout'] == 'editorial':
            style+='\n.cover.layout-editorial,.layout-editorial .cover-foot{text-align:left}.layout-editorial .cover-main{border-top:3px solid '+pal['--cover-rule']+';padding-top:24px}'
    script_hashes=' '.join("'sha256-"+b64encode(sha256(script.encode()).digest()).decode()+"'"
                           for script in (BOOTSTRAP, SCRIPT))
    toolbar='<nav hidden class="report-toolbar" aria-label="'+w('Lectura del informe','Report reading')+'">'
    toolbar+='<label>'+w('Vista','View')+'<select id="view"><option value="technical">'+w('Completo','Full report')+'</option><option value="executive">'+w('Ejecutivo','Executive view')+'</option></select></label>'
    toolbar+='<label>'+w('Tipo','Type')+'<select id="kind"><option value="">'+w('Todos','All')+'</option><option value="vuln">'+w('Hallazgos','Findings')+'</option><option value="machine">'+w('Máquinas','Machines')+'</option></select></label>'
    toolbar+='<label>'+w('Buscar en hallazgos','Search findings')+'<input id="query" type="search"></label><label>'+w('Severidad','Severity')+'<select id="severity"><option value="">'+w('Todas','All')+'</option>'
    toolbar+=''.join('<option value="'+key+'">'+value+'</option>' for key,value in engine.load_lang('en' if en else 'es')['severity'].items())+'<option value="pending">'+w('Pendiente','Pending')+'</option></select></label>'
    finding_count=len(tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," finding ")]'))
    toolbar+='<button id="clear-filters" type="button">'+w('Limpiar filtros','Clear filters')+'</button><output id="results" aria-live="polite">'+str(finding_count)+' / '+str(finding_count)+'</output><button id="print" type="button">'+w('Imprimir vista','Print view')+'</button></nav>'
    if not finding_count:
        toolbar=''
    if data['meta'].get('report_density')=='compact':style+='\n.finding,.frontsec{padding:18px;margin:16px 0}td,th{padding:7px}p{margin-top:6px;margin-bottom:8px}'
    style += REFLOW_STYLE + RECORD_STYLE
    note=w('Documento de solo lectura. Las vistas y los filtros cambian la presentación; el archivo contiene el informe completo. Sin JavaScript, se muestra todo.','Read-only document. Views and filters change presentation; the file contains the full report. Without JavaScript, everything remains visible.')
    if not finding_count:
        note=w('Documento de solo lectura. Se conserva el contenido de las secciones incluidas.','Read-only document. The included sections retain their content.')
    note+=' '+w('HTML exportado con report-gen ','HTML exported with report-gen ')+__version__+'.'
    empty='<p id="empty-results" class="report-note" hidden role="status">'+w('No hay hallazgos que coincidan. Prueba otros filtros o límpialos.','No matching findings. Try other filters or clear them.')+'</p>'
    return '<!doctype html><html lang="'+('en' if en else 'es')+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; font-src data:; style-src \'unsafe-inline\'; script-src '+script_hashes+'; base-uri \'none\'; form-action \'none\'"><title>'+escape(engine.report_title(data))+'</title><script>'+BOOTSTRAP+'</script><style>'+style+'</style></head><body>'+toolbar+'<main><p class="report-note">'+note+'</p>'+empty+'<div class="report-content">'+contents+'</div></main><script>'+SCRIPT+'</script></body></html>'
