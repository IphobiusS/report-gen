"""Authored engagement starters and annotations for the existing Nimbus example.

A package creates preparation work, never observed results or coverage claims.
"""
from copy import deepcopy

from knowledge import catalog
from languages import language_index
import sections
import test_plans
import workflows

REVISION = '2026.10'
_PACKAGES = {
    'web': (
        ('Aplicaciones web', 'Web applications', 'Aplicações web'),
        ('Delimita sesiones, entradas y fronteras de confianza antes de documentar el comportamiento.', 'Define sessions, inputs and trust boundaries before documenting behavior.', 'Defina sessões, entradas e fronteiras de confiança antes de documentar o comportamento.'),
        ('Dominios, rutas, roles y versiones autorizadas; exclusiones de terceros.', 'Authorized domains, routes, roles and versions; third-party exclusions.', 'Domínios, rotas, papéis e versões autorizados; exclusões de terceiros.'),
        ('Identidades y datos canario; comportamiento legítimo de comparación.', 'Canary identities and data; legitimate comparison behavior.', 'Identidades e dados canário; comportamento legítimo de comparação.')),
    'api': (
        ('API y aislamiento de organizaciones', 'APIs and tenant isolation', 'APIs e isolamento entre organizações'),
        ('Relaciona objetos, propiedades y operaciones con la identidad que puede utilizarlos.', 'Relate objects, properties and operations to the identity allowed to use them.', 'Relacione objetos, propriedades e operações à identidade autorizada a utilizá-los.'),
        ('Versiones de API, contrato, roles, organizaciones y objetos de prueba.', 'API versions, contract, roles, tenants and test objects.', 'Versões da API, contrato, papéis, organizações e objetos de teste.'),
        ('Operaciones de lectura y escritura; límites de consumo y limpieza de cambios.', 'Read and write operations; consumption limits and cleanup of changes.', 'Operações de leitura e escrita; limites de consumo e limpeza de alterações.')),
    'identity': (
        ('Identidad y Active Directory', 'Identity and Active Directory', 'Identidade e Active Directory'),
        ('Distingue permisos concedidos, permisos efectivos y rutas de privilegio comprobadas.', 'Distinguish granted permissions, effective permissions and verified privilege paths.', 'Diferencie permissões concedidas, permissões efetivas e caminhos de privilégio verificados.'),
        ('Dominios, relaciones de confianza, cuentas autorizadas y nivel inicial de acceso.', 'Domains, trust relationships, authorized accounts and initial access level.', 'Domínios, relações de confiança, contas autorizadas e nível inicial de acesso.'),
        ('Privilegios necesarios, ventanas de prueba y restauración de membresías.', 'Required privileges, testing windows and membership restoration.', 'Privilégios necessários, janelas de teste e restauração de associações.')),
    'infrastructure': (
        ('Infraestructura y servicios', 'Infrastructure and services', 'Infraestrutura e serviços'),
        ('Documenta exposición, configuración efectiva y límites entre servicios y hosts.', 'Document exposure, effective configuration and boundaries between services and hosts.', 'Documente exposição, configuração efetiva e limites entre serviços e hosts.'),
        ('Hosts, puertos, segmentos, versiones y acceso permitido para cada servicio.', 'Hosts, ports, segments, versions and permitted access for each service.', 'Hosts, portas, segmentos, versões e acesso permitido para cada serviço.'),
        ('Disponibilidad requerida, límites de carga y cambios reversibles permitidos.', 'Required availability, load limits and permitted reversible changes.', 'Disponibilidade necessária, limites de carga e alterações reversíveis permitidas.')),
    'cloud': (
        ('Cloud y contenedores', 'Cloud and containers', 'Cloud e contêineres'),
        ('Conecta identidad, política, recurso y región para valorar el alcance real.', 'Connect identity, policy, resource and region to assess effective scope.', 'Conecte identidade, política, recurso e região para avaliar o alcance efetivo.'),
        ('Proveedores, cuentas, suscripciones, regiones y clústeres autorizados.', 'Authorized providers, accounts, subscriptions, regions and clusters.', 'Provedores, contas, assinaturas, regiões e clusters autorizados.'),
        ('Políticas heredadas, identidad de carga, datos canario y límites de gasto.', 'Inherited policies, workload identity, canary data and spending limits.', 'Políticas herdadas, identidade da carga de trabalho, dados canário e limites de gastos.')),
    'mobile': (
        ('Aplicaciones móviles', 'Mobile applications', 'Aplicativos móveis'),
        ('Separa las propiedades del dispositivo, la aplicación y sus servicios remotos.', 'Separate device, application and remote service properties.', 'Separe as propriedades do dispositivo, do aplicativo e dos serviços remotos.'),
        ('Plataforma, versión de aplicación, dispositivo y estado de integridad acordados.', 'Agreed platform, application version, device and integrity state.', 'Plataforma, versão do aplicativo, dispositivo e estado de integridade acordados.'),
        ('Datos locales de prueba, flujos de enlace y controles de transporte esperados.', 'Local test data, link flows and expected transport controls.', 'Dados locais de teste, fluxos de links e controles de transporte esperados.')),
    'ai': (
        ('IA, LLM y agentes', 'AI, LLMs and agents', 'IA, LLMs e agentes'),
        ('Prueba fronteras de autorización y efectos observables; una respuesta extraña no demuestra explotación.', 'Test authorization boundaries and observable effects; an unusual response does not demonstrate exploitation.', 'Teste fronteiras de autorização e efeitos observáveis; uma resposta estranha não demonstra exploração.'),
        ('Modelo, versión, fuentes RAG, herramientas, memoria y principales identidades.', 'Model, version, RAG sources, tools, memory and principal identities.', 'Modelo, versão, fontes RAG, ferramentas, memória e identidades principais.'),
        ('Datos canario, acciones permitidas, aprobación humana, presupuesto y condiciones de parada.', 'Canary data, permitted actions, human approval, budget and stop conditions.', 'Dados canário, ações permitidas, aprovação humana, orçamento e condições de parada.')),
}


def package(identity, lang='es'):
    lang = catalog.language(lang)
    if identity not in _PACKAGES:
        raise KeyError(identity)
    index = language_index(lang)
    title, summary, *prompts = _PACKAGES[identity]
    entries = catalog.search(lang=lang, category=identity, limit=100)['entries']
    return dict(id=identity, lang=lang, revision=REVISION, title=title[index], summary=summary[index],
                scope_prompts=[text[index] for text in prompts],
                entries=[{key: item[key] for key in ('id', 'title', 'summary')} for item in entries])


def packages(lang='es'):
    lang = catalog.language(lang)
    return dict(revision=REVISION, lang=lang, packages=[package(key, lang) for key in _PACKAGES])


def project(identity, *, lang='es', title='', client='', finding_ids=None):
    """Build a new draft. Suggested findings are included only by explicit ID."""
    item = package(identity, lang)
    lang = item['lang']
    index = language_index(lang)
    if any(not isinstance(value, str) or len(value) > 500 for value in (title, client)):
        raise ValueError(catalog.tr('Título o cliente inválido', 'Invalid title or client', 'Título ou cliente inválido'))
    selected = [] if finding_ids is None else finding_ids
    allowed = {row['id'] for row in item['entries']}
    if (not isinstance(selected, list) or len(selected) > len(allowed) or
            any(not isinstance(value, str) or value not in allowed for value in selected) or
            len(set(selected)) != len(selected)):
        raise ValueError(catalog.tr('Selección de fichas inválida', 'Invalid entry selection', 'Seleção de fichas inválida'))
    notice = (
        'Preparación pendiente: este paquete propone hipótesis y pruebas, no acredita cobertura ni resultados. Completa el alcance, ejecuta las comprobaciones autorizadas y documenta observaciones antes de emitir conclusiones.',
        'Preparation pending: this package proposes hypotheses and tests; it does not establish coverage or results. Complete the scope, perform authorized checks and document observations before drawing conclusions.',
        'Preparação pendente: este pacote propõe hipóteses e testes; não comprova cobertura nem resultados. Complete o escopo, execute verificações autorizadas e documente observações antes de tirar conclusões.')[index]
    report_sections = sections.preset_sections('client', lang)
    report_sections.insert(0, dict(key='work_package_preparation', title=(
        'Preparación del trabajo', 'Engagement preparation', 'Preparação do trabalho')[index],
        body=notice + '\n\n' + '\n\n'.join('- ' + prompt for prompt in item['scope_prompts'])))
    data = dict(meta=dict(lang=lang, report_title=title.strip() or item['title'], report_subtitle=item['summary'],
                         client=client.strip(), assessor='', assessor_title='', date='', version='0.1',
                         theme='corporativo', scope=[], contacts=dict(client=[], assessor=[])),
                report=dict(sections=report_sections), findings=[], test_cases=[])
    for record in item['entries']:
        detail = catalog.entry(record['id'], lang)
        finding_uids = []
        if record['id'] in selected:
            # A new preparation project has no assessed target yet. Retain the
            # visible marker, which preflight reports, instead of inventing one.
            finding = catalog.instantiate(record['id'], {'objetivo': '{{objetivo}}'}, lang)
            finding['id'] = workflows.allocate_finding_id(data)
            data['findings'].append(finding)
            finding_uids.append(finding['uid'])
        data['test_cases'].append(test_plans.create(dict(
            title=detail['title'], test_id=detail['id'], methodology='report-gen', methodology_version=REVISION,
            specialty={'identity': 'ad', 'infrastructure': 'custom'}.get(identity, identity),
            prerequisites=detail['prerequisites'], expected=detail['retest'],
            notes=detail['required_evidence'] + '\n\n' + detail['false_positives'] + '\n\n' + notice,
            finding_uids=finding_uids)))
    return deepcopy(data)


# Each note addresses a concrete part of the existing, explicitly fictional
# Nimbus report. Notes remain outside customer exports and never rewrite them.
_LESSONS = [
    ('provenance', ('Procedencia y límites', 'Provenance and limitations', 'Procedência e limitações'),
     ('Empieza por «Naturaleza del documento». Nimbus declara que la organización, las imágenes y los resultados son ficticios. Mantén esa identificación cuando reutilices la muestra; exportar un informe no demuestra que las pruebas ocurrieron.',
      'Start with “Document status and use of this sample”. Nimbus declares that the organization, images and results are fictional. Keep that identification when reusing the sample; exporting a report does not establish that tests occurred.',
      'Comece por “Natureza do documento”. Nimbus declara que a organização, as imagens e os resultados são fictícios. Mantenha essa identificação ao reutilizar a amostra; exportar um relatório não comprova a realização de testes.')),
    ('executive', ('Resumen que permite decidir', 'A decision-oriented summary', 'Resumo que permite decidir'),
     ('El resumen distingue 12 hallazgos iniciales de ocho sin cierre verificado y propone decisiones concretas. No inventa pérdidas monetarias. En tu informe, vincula la prioridad con datos, operación y responsables; no copies únicamente la tabla de severidades.',
      'The summary distinguishes 12 initial findings from eight without verified closure and proposes concrete decisions. It invents no monetary losses. In your report, connect priority to data, operations and owners instead of merely repeating the severity table.',
      'O resumo distingue 12 achados iniciais de oito sem encerramento verificado e propõe decisões concretas. Não inventa perdas monetárias. No seu relatório, conecte prioridades a dados, operação e responsáveis, sem apenas repetir a tabela de severidades.')),
    ('scope', ('Alcance reproducible', 'Reproducible scope', 'Escopo reproduzível'),
     ('El alcance identifica portal, API, identidad, CI y AD; excluye terceros, producción y acciones destructivas. La metodología separa el acceso inicial de cada escenario. Registra versiones, ventanas y restricciones para que otro analista interprete correctamente tus resultados.',
      'Scope identifies the portal, API, identity, CI and AD; it excludes third parties, production and destructive actions. Methodology separates initial access for each scenario. Record versions, windows and restrictions so another analyst can interpret your results correctly.',
      'O escopo identifica portal, API, identidade, CI e AD; exclui terceiros, produção e ações destrutivas. A metodologia separa o acesso inicial de cada cenário. Registre versões, janelas e restrições para outro analista interpretar os resultados corretamente.')),
    ('evidence', ('Evidencia y control de comparación', 'Evidence and comparison controls', 'Evidências e controles de comparação'),
     ('En F03, la frontera entre organizaciones necesita una identidad, un objeto y una operación identificados. Una respuesta HTTP por sí sola no explica el acceso efectivo. Relaciona el control legítimo con la variación mínima, el resultado observable y los límites de esa observación.',
      'In F03, the tenant boundary requires an identified identity, object and operation. An HTTP response alone does not explain effective access. Relate a legitimate control to the minimal variation, observable result and limits of that observation.',
      'Em F03, a fronteira entre organizações exige identidade, objeto e operação identificados. Uma resposta HTTP isolada não explica o acesso efetivo. Relacione o controle legítimo à variação mínima, ao resultado observável e aos limites dessa observação.')),
    ('impact', ('Impacto sin extrapolaciones', 'Impact without extrapolation', 'Impacto sem extrapolações'),
     ('La narrativa no convierte lectura de archivos en ejecución remota ni administración local en compromiso probado del dominio. Explica primero la capacidad demostrada dentro del escenario y después las consecuencias potenciales con sus condiciones. Conserva también lo que no se pudo comprobar.',
      'The narrative does not turn file reads into remote execution or local administration into proven domain compromise. Explain the capability demonstrated within the scenario first, then potential consequences and their conditions. Preserve what could not be established as well.',
      'A narrativa não transforma leitura de arquivos em execução remota nem administração local em comprometimento comprovado do domínio. Explique primeiro a capacidade demonstrada no cenário e depois as consequências potenciais e suas condições. Preserve também o que não foi possível verificar.')),
    ('risk', ('Severidad y prioridad', 'Severity and priority', 'Severidade e prioridade'),
     ('F07 usa una puntuación técnica de 8,8 y una prioridad operativa P0 por el alcance del dominio. La muestra explica esa diferencia. Justifica cada métrica del vector y valora por separado exposición, activos y urgencia; una categoría de biblioteca nunca fija automáticamente la severidad.',
      'F07 uses a technical score of 8.8 and operational priority P0 because of domain scope. The sample explains that distinction. Justify each vector metric and assess exposure, assets and urgency separately; a library category never automatically sets severity.',
      'F07 usa pontuação técnica de 8,8 e prioridade operacional P0 pelo alcance no domínio. A amostra explica essa diferença. Justifique cada métrica do vetor e avalie exposição, ativos e urgência separadamente; uma categoria da biblioteca nunca define a severidade automaticamente.')),
    ('remediation', ('Corrección de causa raíz', 'Root-cause remediation', 'Correção da causa raiz'),
     ('F01 separa la consulta vulnerable de los permisos excesivos de la cuenta. La recomendación debe cubrir la causa y los factores que amplifican el impacto, con un responsable y un criterio de cierre comprobable. «Actualizar» o «validar entradas» sin contexto no bastan.',
      'F01 separates the vulnerable query from excessive account permissions. Remediation should address the cause and impact-amplifying factors, with an owner and a testable closure criterion. “Update” or “validate inputs” without context is insufficient.',
      'F01 separa a consulta vulnerável das permissões excessivas da conta. A recomendação deve tratar a causa e os fatores que ampliam o impacto, com responsável e critério de encerramento verificável. “Atualizar” ou “validar entradas” sem contexto é insuficiente.')),
    ('retest', ('Corrección comunicada frente a verificada', 'Reported versus verified remediation', 'Correção informada e verificada'),
     ('Los retests parciales de F03 y F05 conservan trabajo pendiente: una ruta mejora y otra sigue abierta. Mantén la severidad inicial para trazabilidad y registra fecha, versión, control negativo y flujo legítimo. Un anuncio de despliegue no sustituye una comprobación.',
      'The partial retests of F03 and F05 retain pending work: one route improves while another remains open. Preserve initial severity for traceability and record date, version, negative control and legitimate flow. A deployment announcement cannot replace verification.',
      'Os retestes parciais de F03 e F05 mantêm trabalho pendente: uma rota melhora e outra permanece aberta. Preserve a severidade inicial para rastreabilidade e registre data, versão, controle negativo e fluxo legítimo. Um anúncio de implantação não substitui a verificação.')),
    ('delivery', ('Revisión antes de entregar', 'Review before delivery', 'Revisão antes da entrega'),
     ('Comprueba índice, referencias, evidencias, estado de seguimiento y formato exportado. La validación estructural detecta incoherencias, pero no demuestra exactitud técnica ni calidad visual de todas las páginas. Usa la lista de entrega y revisa el PDF o DOCX que recibirá el destinatario.',
      'Check contents, references, evidence, follow-up state and the exported format. Structural validation detects inconsistencies but does not establish technical accuracy or visual quality on every page. Use the delivery checklist and inspect the PDF or DOCX the recipient will receive.',
      'Confira índice, referências, evidências, estado de acompanhamento e formato exportado. A validação estrutural detecta inconsistências, mas não comprova exatidão técnica nem qualidade visual de todas as páginas. Use a lista de entrega e revise o PDF ou DOCX destinado ao destinatário.')),
]


def example(lang='es'):
    lang = catalog.language(lang)
    index = language_index(lang)
    return dict(lang=lang, revision=REVISION, example='nimbus', fictional=True, readonly=True,
                title=('Nimbus · informe comentado', 'Nimbus · annotated report', 'Nimbus · relatório comentado')[index],
                lessons=[dict(id=identity, title=title[index], text=text[index]) for identity, title, text in _LESSONS])
