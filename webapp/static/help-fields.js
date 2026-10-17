/* Optional writing guidance. Opening help never changes report content or technical state. */
const FieldHelpUI = (() => {
  'use strict';
  const guidance = {
    description_md: [
      ['Descripción y causa','Describe el control que falló, el componente, las condiciones y el resultado observado. Separa hechos de hipótesis. Sustituye los ejemplos por tu evidencia.','Con una cuenta de pruebas de la organización A, la API devolvió un registro de B al cambiar su identificador; se repitió con dos registros autorizados.','La API es insegura y permite acceder a todo.'],
      ['Description and cause','Describe the failed control, component, conditions and observed result. Separate facts from hypotheses. Replace examples with your own evidence.','Using a test account in organization A, the API returned a record from B when its identifier changed; this was repeated with two authorized test records.','The API is insecure and allows access to everything.'],
      ['Descrição e causa','Descreva o controle que falhou, o componente, as condições e o resultado observado. Separe fatos de hipóteses. Substitua os exemplos pelas suas evidências.','Com uma conta de teste da organização A, a API retornou um registro de B após alterar o identificador; o teste foi repetido com dois registros autorizados.','A API é insegura e permite acessar tudo.']
    ],
    impact_md: [
      ['Impacto','Relaciona la capacidad demostrada con los activos y el negocio. Delimita volumen, permisos y exposición. Expresa como posibilidad las consecuencias no comprobadas.','Se demostró lectura entre dos clientes de prueba. En producción podría comprometer la confidencialidad de registros accesibles por el mismo flujo; no se midió su volumen total.','Pérdida total de la empresa y multas aseguradas.'],
      ['Impact','Connect the demonstrated capability to affected assets and business processes. Bound volume, permissions and exposure. Describe untested consequences as possibilities.','Read access between two test tenants was demonstrated. In production, records reachable through the same flow could lose confidentiality; their total volume was not measured.','The entire company will be lost and fines are guaranteed.'],
      ['Impacto','Relacione a capacidade demonstrada aos ativos e processos de negócio. Delimite volume, permissões e exposição. Trate consequências não verificadas como possibilidades.','Foi demonstrada leitura entre dois clientes de teste. Em produção, registros acessíveis pelo mesmo fluxo poderiam perder confidencialidade; o volume total não foi medido.','Perda total da empresa e multas garantidas.']
    ],
    severity: [
      ['Severidad y CVSS','Valora el caso real. Registra versión y vector CVSS, justifica métricas y distingue severidad técnica de prioridad empresarial. Una categoría o ficha no determina una puntuación.','Se documentan privilegios requeridos, alcance comprobado y efecto en confidencialidad. Las métricas no comprobadas se revisan antes de asignar el vector.','Crítica, CVSS 10, porque es una inyección.'],
      ['Severity and CVSS','Assess the actual case. Record the CVSS version and vector, justify metrics and separate technical severity from business priority. A category or catalog entry does not determine a score.','Required privileges, demonstrated scope and confidentiality effects are documented. Unverified metrics are reviewed before assigning the vector.','Critical, CVSS 10, because it is an injection.'],
      ['Severidade e CVSS','Avalie o caso real. Registre versão e vetor CVSS, justifique métricas e diferencie severidade técnica de prioridade de negócio. A categoria ou ficha não determina uma pontuação.','Privilégios necessários, escopo comprovado e efeito na confidencialidade são documentados. Métricas não verificadas são revisadas antes de atribuir o vetor.','Crítica, CVSS 10, porque é uma injeção.']
    ],
    remediation_md: [
      ['Remediación','Propón un cambio aplicable al componente y a la causa. Distingue mitigación temporal de corrección y añade una comprobación posterior. Evita prometer que una única medida elimina todos los riesgos.','Validar en servidor la pertenencia del registro al cliente autenticado en cada operación. Añadir pruebas entre clientes y comprobar también las rutas de exportación.','Actualizar y aplicar buenas prácticas.'],
      ['Remediation','Propose a change that addresses the component and cause. Separate temporary mitigation from correction and include a follow-up check. Avoid promising that one measure eliminates every risk.','Validate record ownership against the authenticated tenant on the server for every operation. Add cross-tenant tests and check export routes as well.','Update and follow best practices.'],
      ['Correção','Proponha uma mudança aplicável ao componente e à causa. Diferencie mitigação temporária de correção e inclua uma verificação posterior. Evite prometer que uma medida elimina todos os riscos.','Validar no servidor se o registro pertence ao cliente autenticado em cada operação. Adicionar testes entre clientes e verificar também as rotas de exportação.','Atualizar e aplicar boas práticas.']
    ],
    evidence: [
      ['Evidencias','Registra identidad de prueba, fecha, precondiciones, solicitud/acción, respuesta y vínculo al hallazgo. Oculta secretos en la copia de entrega y revisa el original por separado. Un pantallazo aislado puede ser insuficiente.','La evidencia E-03 enlaza la petición y respuesta, identifica las dos cuentas de prueba y muestra el registro obtenido con datos ficticios y un pie explicativo.','Imagen sin contexto ni identificación del objetivo.'],
      ['Evidence','Record the test identity, date, preconditions, request/action, response and finding link. Redact secrets in the delivery copy and review the original separately. An isolated screenshot may be insufficient.','Evidence E-03 links the request and response, identifies both test accounts and shows the returned record with fictional data and an explanatory caption.','An image with no context or target identification.'],
      ['Evidências','Registre identidade de teste, data, precondições, solicitação/ação, resposta e vínculo com o achado. Oculte segredos na cópia de entrega e revise o original separadamente. Uma captura isolada pode ser insuficiente.','A evidência E-03 vincula a solicitação e a resposta, identifica as duas contas de teste e mostra o registro obtido com dados fictícios e legenda explicativa.','Imagem sem contexto ou identificação do alvo.']
    ],
    scope: [
      ['Alcance','Define activos, entornos, cuentas, fechas, exclusiones y restricciones acordadas. Distingue un activo incluido de una prueba realmente ejecutada. Usa Cobertura para registrar el estado de las pruebas.','Se incluye api.example.test en preproducción con dos cuentas facilitadas, del 5 al 7 de octubre. Se excluyen terceros y pruebas de disponibilidad.','Se revisó toda la seguridad de la empresa.'],
      ['Scope','Define agreed assets, environments, accounts, dates, exclusions and restrictions. Distinguish an in-scope asset from a test actually performed. Use Coverage to record test status.','api.example.test in staging is included with two supplied accounts, October 5–7. Third parties and availability tests are excluded.','All company security was reviewed.'],
      ['Escopo','Defina ativos, ambientes, contas, datas, exclusões e restrições acordadas. Diferencie um ativo incluído de um teste realmente executado. Use Cobertura para registrar o status dos testes.','Inclui api.example.test em homologação com duas contas fornecidas, de 5 a 7 de outubro. Terceiros e testes de disponibilidade estão excluídos.','Toda a segurança da empresa foi revisada.']
    ],
    limitations_md: [
      ['Limitaciones','Explica qué no pudiste comprobar, la causa y cómo afecta a la interpretación. Una prueba bloqueada no equivale a una prueba superada. Registra también dependencias de acceso o tiempo.','No se evaluó la autorización del rol administrador porque no se proporcionó esa cuenta. Las conclusiones se limitan a los roles disponibles.','No se detectaron problemas, por tanto no existen.'],
      ['Limitations','Explain what could not be checked, why, and how this affects interpretation. A blocked test is not a passed test. Record access and time dependencies as well.','Administrator authorization was not assessed because that account was not provided. Conclusions are limited to the available roles.','No issues were detected, so none exist.'],
      ['Limitações','Explique o que não foi verificado, a causa e como isso afeta a interpretação. Um teste bloqueado não equivale a um teste aprovado. Registre também dependências de acesso ou prazo.','A autorização do administrador não foi avaliada porque essa conta não foi fornecida. As conclusões se limitam aos perfis disponíveis.','Nenhum problema foi detectado, portanto não existe.']
    ],
    closure_criteria_md: [
      ['Criterios de retest','Define el resultado esperado, las variantes y la evidencia necesaria para cerrar. Conserva el estado sin verificar hasta ejecutar y registrar el retest; la respuesta del cliente no lo sustituye.','Repetir la petición original con las dos cuentas: cada una sólo obtiene sus registros. Revisar lectura, modificación y exportación, documentando respuestas y fecha.','Cerrar cuando el cliente diga que está arreglado.'],
      ['Retest criteria','Define the expected result, variants and evidence needed for closure. Keep the state unverified until the retest is performed and recorded; a client response does not replace it.','Repeat the original request with both accounts: each can obtain only its own records. Check reading, modification and export, recording responses and date.','Close when the client says it is fixed.'],
      ['Critérios de reteste','Defina resultado esperado, variantes e evidências necessárias para encerrar. Mantenha o estado sem verificação até executar e registrar o reteste; a resposta do cliente não o substitui.','Repetir a solicitação original com as duas contas: cada uma só obtém seus registros. Revisar leitura, alteração e exportação, documentando respostas e data.','Encerrar quando o cliente disser que corrigiu.']
    ]
  };
  function create(key) {
    if (!guidance[key]) return null;
    const w=uiText, index={es:0,en:1,pt:2}[S.uiLang]??0, [title,advice,good,bad]=guidance[key][index];
    const summary=h('summary',{},w('Qué escribir aquí','What to write here','O que escrever aqui')+' · '+title);
    const node=h('details',{class:'field-help','data-help':key},summary,
      h('p',{},advice),h('div',{class:'field-help-example'},h('strong',{},w('Ejemplo ficticio bien sustentado','Well-supported fictional example','Exemplo fictício bem fundamentado')),h('p',{},good)),
      h('div',{class:'field-help-example'},h('strong',{},w('Ejemplo insuficiente','Insufficient example','Exemplo insuficiente')),h('p',{},bad)));
    node.addEventListener('keydown',event=>{if(event.key==='Escape'&&node.open){event.preventDefault();event.stopPropagation();node.open=false;summary.focus({preventScroll:true});}});
    return node;
  }
  function append(container,key){const node=create(key);if(node)container.append(node);return container;}
  return {create,append,keys:()=>Object.keys(guidance)};
})();
