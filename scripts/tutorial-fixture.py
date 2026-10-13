#!/usr/bin/env python3
"""Seed only a sentinel-protected, disposable tutorial capture workspace."""
from pathlib import Path
import argparse
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont
import project_history

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
workspace = args.workspace.resolve()
if not workspace.name.startswith('report-gen-acceptance-0211-') or (workspace / '.test-only').read_text() != 'synthetic acceptance workspace':
    raise SystemExit('A dedicated disposable acceptance workspace is required')

for index, lang in enumerate(('es', 'en', 'pt')):
    def tr(es, en, pt):
        return (es, en, pt)[index]
    folder = workspace / 'projects' / ('tutorial-' + lang)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'img').mkdir()
    image = Image.new('RGB', (960, 480), '#122436')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(ROOT / 'exporters/fonts/DejaVuSans.ttf'), 27)
    mono = ImageFont.truetype(str(ROOT / 'exporters/fonts/DejaVuSansMono.ttf'), 25)
    draw.text((42, 35), tr('ESQUEMA SINTÉTICO · SIN PRUEBA REAL', 'SYNTHETIC DIAGRAM · NO REAL TEST', 'DIAGRAMA SINTÉTICO · SEM TESTE REAL'), font=font, fill='#7CDFB4')
    for row, text in enumerate(('LAB / DEMO', 'GET /records/42  →  HTTP 200', 'account-a  →  record-b', 'portal.example / 192.0.2.42')):
        draw.text((42, 125 + 66 * row), text, font=mono, fill='#F4F8FC')
    image.save(folder / 'img' / 'evidence.png')
    evidence_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'report-gen/tutorial/' + lang + '/evidence'))
    finding_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'report-gen/tutorial/' + lang + '/finding'))
    title = tr('Lectura de un registro de otra cuenta [SIMULADO]', 'Reading another account’s record [SIMULATED]', 'Leitura de um registro de outra conta [SIMULADO]')
    data = {
        'meta': {'lang': lang, 'theme': 'corporativo', 'report_title': tr('Evaluación de seguridad · tutorial', 'Security assessment · tutorial', 'Avaliação de segurança · tutorial'),
                 'report_subtitle': tr('Ejemplo ficticio para aprender el editor', 'Fictional example for learning the editor', 'Exemplo fictício para aprender a usar o editor'),
                 'client': tr('Laboratorio Aurora [FICTICIO]', 'Aurora Lab [FICTIONAL]', 'Laboratório Aurora [FICTÍCIO]'),
                 'assessor': tr('Equipo de ejemplo', 'Example team', 'Equipe de exemplo'), 'date': '2026-10-13', 'version': '1.0',
                 'branding': {'wordmark': 'AURORA LAB', 'confidential_text': 'DEMO'}},
        'report': {'sections': [
            {'key': 'executive_summary', 'summary': tr('Caso ficticio. No se evaluó ningún sistema real. La observación siguiente es una hipótesis pendiente.', 'Fictional case. No real system was assessed. The following observation is a pending hypothesis.', 'Caso fictício. Nenhum sistema real foi avaliado. A observação a seguir é uma hipótese pendente.')},
            {'key': 'scope', 'objectives': tr('Documentar una hipótesis de autorización en un portal de laboratorio.', 'Document an authorization hypothesis in a lab portal.', 'Documentar uma hipótese de autorização em um portal de laboratório.'), 'assumptions': tr('Sin pruebas en producción. Datos sintéticos.', 'No production tests. Synthetic data.', 'Sem testes em produção. Dados sintéticos.')},
            {'key': 'findings_summary'}, {'key': 'findings'}]},
        'findings': [{'id': 'F01', 'uid': finding_uid, 'mode': 'vuln', 'title': title, 'severity': 'high', 'verification': 'unverified',
            'affected': 'https://portal.example/records/42',
            'description_md': tr('La cuenta de prueba A recibe un registro asociado a B en este escenario sintético. Debe comprobarse el control de autorización por objeto en un entorno autorizado.', 'Test account A receives a record associated with B in this synthetic scenario. Object-level authorization must be checked in an authorized environment.', 'A conta de teste A recebe um registro associado a B neste cenário sintético. A autorização no nível do objeto deve ser verificada em um ambiente autorizado.'),
            'impact_md': tr('Hipótesis: lectura entre cuentas. El ejemplo no demuestra exposición real ni cuantifica pérdidas.', 'Hypothesis: cross-account reading. This example demonstrates no real exposure and quantifies no loss.', 'Hipótese: leitura entre contas. O exemplo não demonstra exposição real nem quantifica perdas.'),
            'remediation_md': tr('Verificar la autorización para cada objeto y repetir los casos permitidos y denegados.', 'Verify authorization for each object and repeat allowed and denied cases.', 'Verifique a autorização de cada objeto e repita os casos permitidos e negados.'),
            'evidence_uids': [evidence_uid], 'references': ['https://cwe.mitre.org/data/definitions/639.html']}],
        'evidence': [{'uid': evidence_uid, 'title': tr('EV-01 · Respuesta sintética', 'EV-01 · Synthetic response', 'EV-01 · Resposta sintética'),
            'src': 'img/evidence.png', 'caption': tr('Diagrama ficticio: A recibe el registro de B. No es una captura de una prueba ejecutada.', 'Fictional diagram: A receives B’s record. It is not a screenshot of an executed test.', 'Diagrama fictício: A recebe o registro de B. Não é uma captura de um teste executado.')}],
    }
    project_history.save(folder, data)
print('Created three explicitly fictional tutorial projects')
