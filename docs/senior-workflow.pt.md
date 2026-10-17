# Fluxo de avaliação e revisão no report-gen 0.42.0

[Guia geral](guide.pt.md) · [Español](senior-workflow.es.md) · [English](senior-workflow.en.md)

## Revisar mantendo a evidência visível

Filtre os achados pela tarefa que deseja resolver e inicie uma sessão de
revisão. A fila mantém as identidades selecionadas: **Salvar e próximo** avança
dentro dessa sessão e mostra sua posição. Fixe uma evidência ao lado do texto
enquanto escreve impacto ou remediação. Preferências de navegação não alteram o
conteúdo do relatório. A pesquisa alcança ativos, evidências e comentários; as
seleções da tabela alimentam a comparação de atribuições em lote antes de salvar.

Escolha um objetivo específico, como revisar os achados de uma API com seu
responsável técnico. Salve as alterações do relatório e trate formulários
pendentes como propostas separadas. Recuperar um formulário não aplica mudanças
nem restaura consentimentos anteriores. Confira o conteúdo recuperado contra o
projeto atual.

## Separar as instâncias afetadas

Dentro do achado, **Instâncias afetadas** registra destino, parâmetro,
identidade ou papel, ambiente, ativo, responsável, prazo, evidência e notas.
Cada instância possui seu próprio histórico de retestes. Uma lista de ativos
vinculados não cria instâncias automaticamente: declare a combinação que
representa uma exposição concreta.

Registre o reteste na instância avaliada. Data, avaliador e resultado observado
são obrigatórios. Um registro com data anterior permanece no histórico sem
substituir o resultado mais recente; na mesma data prevalece o último registro
adicionado. O status geral deriva do conjunto. Quinze instâncias corrigidas,
duas abertas e uma bloqueada ainda deixam trabalho pendente. Uma observação
geral do achado não verifica todos os destinos. O limite é de 500 instâncias
por achado, 10.000 por projeto e 200 retestes por instância. Projetos antigos
sem instâncias preservam seu comportamento.

## Capturar HTTP e preparar uma cópia publicável

**Evidência HTTP** mantém requisição, resposta, cabeçalhos, corpo e procedência.
Importe entradas HAR selecionadas ou use a extensão opcional do Burp. Compare
dois registros para revisar papéis ou um antes/depois. O original privado e a
cópia publicável possuem verificações de integridade separadas. O hash não
autentica quem forneceu a evidência, e uma representação estruturada não é uma
captura exata de pacotes.

Edite e confirme explicitamente a cópia destinada à entrega técnica. Revise
credenciais, cookies, identificadores e corpos; aprovar uma derivada não aprova
o original privado. Entregas executivas e públicas não recebem esses corpos
automaticamente. Os limites incluem 100 pares por importação, 500 por projeto,
200 cabeçalhos por mensagem e 256 KiB por corpo, além dos limites agregados.

Para usar o Burp, salve o projeto, gere um código de pareamento e selecione
explicitamente as mensagens pelo menu contextual. O código expira e fica
vinculado à revisão do projeto. A extensão não percorre todo o histórico nem
inicia uma varredura. Consulte [compilação, uso e limites](../integrations/burp-report-gen/README.md).

## Documentar cobertura e causalidade

Em **Plano de testes**, registre metodologia e versão, especialidade,
pré-condições, resultado esperado, resultado observado e vínculos com ativos,
achados e evidências. A matriz papel × organização × operação cria casos
pendentes; não multiplica resultados nem testes realizados. São permitidas 300
combinações por matriz e 3.000 casos por projeto. Os planos iniciais são auxílios
de autoria, não catálogos oficiais nem certificados de conformidade. Distinga
um teste sem falha observada de um teste que não foi realizado.

**Caminhos de ataque** relaciona etapas com transições declaradas como
demonstradas, inferidas ou bloqueadas. Uma transição demonstrada exige observação
e evidência vinculada. Explique as pré-condições, consequências e a medida que
interrompe o caminho. Cada caminho aceita 40 etapas e 100 transições, sem
ciclos; o projeto aceita 100 caminhos. A ferramenta verifica a estrutura, mas
não deduz exploração ou causalidade técnica pelo autor.

## Conciliar importações e receber revisão

Ao importar uma nova varredura, compare observações com os achados existentes e
decida o que vincular e quais campos incorporar. Preserve a avaliação manual.
Desaparecer de um scanner não equivale a um reteste com correção verificada.
As observações armazenadas são limitadas a 100 por achado, 500 no total e
4 MiB de conteúdo agregado.

Pacotes de revisão editorial levam campos selecionados e sua base. Compare
base, texto atual e proposta recebida antes de aceitar cada campo. O nome do
revisor é declarado, não uma identidade autenticada. Perfis versionados de
cliente mantêm terminologia, seções obrigatórias, critérios de aceitação e
preferências de entrega; revise suas mudanças antes de aplicar um perfil.

Jira Cloud e DefectDojo aceitam vínculos com registros existentes e intercâmbios
explícitos de campos. Os conectores atuais aceitam apenas HTTPS público, não
servidores internos. Tokens não são armazenados nos projetos nem nos rascunhos.
O status externo descreve acompanhamento sem verificar a correção local. A
revisão editorial opcional com Ollama utiliza somente textos e legendas
selecionados; suas sugestões continuam exigindo julgamento do autor.

## Conferir a entrega

Use **Entregar**, confira o destinatário e o conteúdo e abra os arquivos finais.
O caso [Aster](../qa/aster/README.md) permite repetir um exercício extenso em
ES/EN/PT somente com os exportadores do report-gen. Os resultados sintéticos
não são uma avaliação real. A aceitação nativa no Word exige Windows e Word
licenciado; o procedimento existe e a execução deve ser registrada
separadamente. Carregar a extensão no Burp em execução, utilizar contas reais
Jira/DefectDojo e executar inferência com um modelo Ollama também requerem
aceitação do ambiente. Os testes documentados não garantem ausência universal
de erros nem compatibilidade com qualquer relatório possível.
