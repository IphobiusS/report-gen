"""Deterministic fictional data for real report previews; never new-project content."""
from design_library import new_report, localized, profile_name
from languages import normalize_language, language_index


def general_sample_name(theme, lang='es'):
    names = {'serio': ('Serio', 'Serious', 'Sóbrio'),
             'corporativo': ('Corporativo', 'Corporate', 'Corporativo'),
             'offsec': ('OffSec', 'OffSec', 'OffSec'), 'htb': ('HTB', 'HTB', 'HTB'),
             'ejecutivo': ('Ejecutivo', 'Executive', 'Executivo'),
             'laboratorio': ('Laboratorio', 'Laboratory', 'Laboratório')}
    return names[theme][language_index(lang)]


def sample_data(profile, variant='brand', lang='es'):
    lang = normalize_language(lang, None)
    # Validate through the public factory before selecting any localized text.
    data = new_report(profile, 'Sample', lang, variant)
    def tr(es, en, pt):
        return (es, en, pt)[language_index(lang)]
    data['meta'].update(
        report_title=tr('Evaluación de seguridad', 'Security assessment', 'Avaliação de segurança'),
        client=tr('Laboratorio Aurora', 'Aurora Lab', 'Laboratório Aurora'),
        assessor=tr('Analista de ejemplo', 'Example Analyst', 'Analista de exemplo'),
        email='analista@example.test', osid='LAB-042', date='2026-10-03', version='1.0',
        report_subtitle=profile_name(profile, lang)+' / '+tr('Muestra ficticia', 'Fictional sample', 'Amostra fictícia'))
    data['meta']['branding']['wordmark']='AURORA LAB'
    summary=tr(
        'Esta muestra ficticia permite revisar la composición del informe. No se evaluó a un cliente. El alcance es un entorno aislado de aprendizaje. Sustituye este texto por los resultados demostrados de tu trabajo.\n\nEl ejemplo documenta una comprobación autorizada, la evidencia recogida y la verificación pendiente. Las conclusiones técnicas necesitan evidencias reproducibles y límites explícitos.',
        'This fictional sample demonstrates the report layout. No customer was assessed. The scope is an isolated training environment. Replace this text with the demonstrated results of your own work.\n\nThe example documents one permitted validation, the evidence collected and the remaining verification. Technical conclusions require reproducible evidence and explicit limitations.',
        'Esta amostra fictícia demonstra a diagramação do relatório. Nenhum cliente foi avaliado. O escopo é um ambiente isolado de aprendizado. Substitua este texto pelos resultados demonstrados do seu trabalho.\n\nO exemplo documenta uma verificação autorizada, as evidências coletadas e a verificação pendente. As conclusões técnicas exigem evidências reproduzíveis e limites explícitos.')
    second=next((s for s in profile['sections'][1:] if s['key']!='findings'),
                {'title': {'es':'Verificación técnica','en':'Technical verification','pt':'Verificação técnica'}})
    technical=tr(
        'Registra las condiciones de prueba, la versión y la fecha antes de comparar resultados. En este ejemplo, el comando enumera una carpeta local de evidencias sin contactar a un objetivo.\n\n',
        'Record the test conditions, version and timestamp before comparing results. In this example, the command inventories a local evidence directory without contacting a target.\n\n',
        'Registre as condições de teste, a versão e a data antes de comparar os resultados. Neste exemplo, o comando lista uma pasta local de evidências sem contatar um alvo.\n\n')
    technical+='```sh\nfind ./evidence -type f -print\nsha256sum ./evidence/session.txt\n```\n\n'
    technical+=tr(
        'La salida del ejemplo es ilustrativa. Conserva los originales y relaciona cada conclusión con el identificador de su evidencia.\n\n| Evidencia | Origen | Estado |\n|---|---|---|\n| EV-001 | Sesión local | Ilustrativo |\n| EV-002 | Copia de configuración | Ilustrativo |',
        'The example output is illustrative. Preserve the original files and connect every conclusion to its evidence identifier.\n\n| Evidence | Source | Status |\n|---|---|---|\n| EV-001 | Local session | Illustrative |\n| EV-002 | Configuration snapshot | Illustrative |',
        'A saída do exemplo é ilustrativa. Preserve os originais e relacione cada conclusão ao identificador da evidência.\n\n| Evidência | Origem | Estado |\n|---|---|---|\n| EV-001 | Sessão local | Ilustrativo |\n| EV-002 | Cópia da configuração | Ilustrativo |')
    data['report']['sections']=[
        {'key':'sample-summary','title':tr('Resumen del trabajo','Work summary','Resumo do trabalho'),'body':summary},
        {'key':'sample-technical','title':localized(second.get('title'),lang),'body':technical}]
    return data
