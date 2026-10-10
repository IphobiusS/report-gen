"""Deterministic fictional data for real report previews; never used as new-project content."""
from design_library import new_report, localized


def sample_data(profile,variant='brand',lang='es'):
    en=lang=='en'
    data=new_report(profile,'Security assessment' if en else 'Evaluación de seguridad',lang,variant)
    data['meta'].update(client='Aurora Lab' if en else 'Laboratorio Aurora',assessor='Example Analyst' if en else 'Analista de ejemplo',email='analista@example.test',osid='LAB-042',date='2026-10-03',version='1.0',report_subtitle=profile['name']+' / '+('Fictional sample' if en else 'Muestra ficticia'))
    data['meta']['branding']['wordmark']='AURORA LAB'
    summary=('This fictional sample demonstrates the report layout. No customer was assessed. The scope is an isolated training environment. Replace this text with the demonstrated results of your own work.\n\n'
             'The example documents one permitted validation, the evidence collected and the remaining verification. Technical conclusions require reproducible evidence and explicit limitations.' if en else
             'Esta muestra ficticia permite revisar la composición del informe. No se evaluó a un cliente. El alcance es un entorno aislado de aprendizaje. Sustituye este texto por los resultados demostrados de tu trabajo.\n\n'
             'El ejemplo documenta una comprobación autorizada, la evidencia recogida y la verificación pendiente. Las conclusiones técnicas necesitan evidencias reproducibles y límites explícitos.')
    second=next((s for s in profile['sections'][1:] if s['key']!='findings'),
                {'title': {'es':'Verificación técnica','en':'Technical verification'}})
    technical=('Record the test conditions, version and timestamp before comparing results. In this example, the command inventories a local evidence directory without contacting a target.\n\n' if en else
               'Registra las condiciones de prueba, la versión y la fecha antes de comparar resultados. En este ejemplo, el comando enumera una carpeta local de evidencias sin contactar a un objetivo.\n\n')
    technical+='```sh\nfind ./evidence -type f -print\nsha256sum ./evidence/session.txt\n```\n\n'
    technical+=('The example output is illustrative. Preserve the original files and connect every conclusion to its evidence identifier.\n\n| Evidence | Source | Status |\n|---|---|---|\n| EV-001 | Local session | Illustrative |\n| EV-002 | Configuration snapshot | Illustrative |' if en else
                'La salida del ejemplo es ilustrativa. Conserva los originales y relaciona cada conclusión con el identificador de su evidencia.\n\n| Evidencia | Origen | Estado |\n|---|---|---|\n| EV-001 | Sesión local | Ilustrativo |\n| EV-002 | Copia de configuración | Ilustrativo |')
    data['report']['sections']=[{'key':'sample-summary','title':'Work summary' if en else 'Resumen del trabajo','body':summary},{'key':'sample-technical','title':localized(second.get('title'),lang),'body':technical}]
    return data
