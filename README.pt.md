<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen com Prometeo e Evaristo" width="300">
</p>

# report-gen 0.42.0

**Um editor local para transformar avaliações de segurança em relatórios claros.** Organize achados, vincule evidências, acompanhe a remediação e os retestes e produza **PDF, Word, Markdown com imagens e HTML portátil** a partir de uma revisão salva.

[Español](README.md) · [English](README.en.md) · [Guia completo em português](docs/guide.pt.md) · [Histórico de alterações](CHANGELOG.md)

## Instalar e abrir

O caminho principal é **Linux/Kali com Python 3.11 ou superior**. Baixe e extraia a [versão publicada mais recente](https://github.com/IphobiusS/report-gen/releases/latest) ou clone o repositório:

```bash
git clone https://github.com/IphobiusS/report-gen.git
cd report-gen
python3 scripts/install.py --desktop --lang pt
~/.local/bin/report-gen
```

O instalador prepara `.venv`, baixa as dependências limitadas por `requirements-audited.txt` e cria um atalho no menu de aplicativos. Ele não usa `sudo` nem instala pacotes do sistema. **Mantenha a pasta do aplicativo e sua `.venv`: o atalho depende delas; não é um executável independente.** Abrir o atalho depois não reinstala as dependências. O uso normal do editor não exige Node.js.

Os dados ficam fora do aplicativo, em `$XDG_DATA_HOME/report-gen` ou `~/.local/share/report-gen`. Para escolher outro local, use `--workspace /caminho/dados`. Sem essa opção, a variável `REPORT_GEN_WORKSPACE` é respeitada. O instalador não migra projetos anteriores automaticamente.

Abra **http://127.0.0.1:8080**. Encerre o servidor com `Ctrl+C`; use `--port 8081` para outra porta. O caminho `python3 start.py --ready --lang pt` também está disponível. Sem um espaço de trabalho externo, ele mantém os dados em `webapp/`.

O português é a variante **Brasil**. A chave interna é `pt`; os argumentos de idioma também aceitam `pt-BR`. O idioma da interface é uma preferência independente do idioma do relatório. Alterar a interface não traduz nem reescreve o conteúdo que você redigiu.

## Primeiro relatório

1. Na visão geral, experimente a demonstração fictícia Nimbus ou crie seu próprio projeto.
2. Na galeria, compare as páginas de exemplo e selecione um design. Confira os dados antes de criar o projeto.
3. Preencha o escopo, os ativos e os achados. Distinga observações, hipóteses e resultados realmente verificados; anexe as evidências correspondentes.
4. Salve uma revisão, abra o inspetor de publicação e escolha os formatos na área de entrega.
5. Abra os arquivos gerados antes de compartilhar e mantenha um backup privado do projeto editável.

O **tutorial visual** permanece no menu. Seus seis passos têm instruções e capturas reais em espanhol, inglês e português, com ampliação e progresso local. A apresentação inicial pode ser ignorada. Consultar o tutorial não modifica o relatório; ele também funciona quando o navegador não consegue salvar seu progresso.

## Fluxo de avaliação 0.42.0

A revisão conecta a fila filtrada, a evidência fixada ao lado do editor, as seleções da tabela e a pesquisa de ativos, evidências e comentários. **Salvar e próximo** mantém a sessão de revisão ativa.

Os achados aceitam **instâncias afetadas** com responsável, prazo, evidência e retestes independentes. O status geral deriva do conjunto: uma correção parcial não encerra os destinos pendentes. **Planos de testes** registram metodologia e versão, papéis, organizações e resultados; **caminhos de ataque** distinguem transições demonstradas, inferidas e bloqueadas.

A **evidência HTTP** separa originais privados de cópias revisadas para entrega técnica. Inclui importação HAR, comparação e extensão opcional do Burp para enviar somente mensagens selecionadas. Reimportações de scanners comparam e vinculam novas observações preservando as decisões do analista.

Perfis versionados de cliente e pacotes de revisão editorial mantêm requisitos e mudanças por campo. Jira Cloud e DefectDojo aceitam intercâmbios explícitos com registros existentes em servidores HTTPS públicos; o status externo não substitui o reteste. A revisão editorial com Ollama utiliza fontes selecionadas e preserva o julgamento do autor.

[Fluxo prático e limites da 0.42](docs/senior-workflow.pt.md) · [Caso fictício Aster ES/EN/PT](qa/aster/README.md) · [Extensão Burp](integrations/burp-report-gen/README.md). A aceitação nativa do Word e Burp, contas reais Jira/DefectDojo e inferência Ollama exigem seus próprios registros; esta lista de capacidades não comprova essas execuções.

## Integração 0.41.0

**Entregar** reúne revisão, destinatário, visualização e exportação. Os impedimentos levam à origem; mudanças de conteúdo ou opções invalidam a visualização. A exportação mantém a revisão examinada e exige nova confirmação quando necessário.

Tabelas extensas dentro dos achados podem continuar por linhas entre páginas, repetindo o cabeçalho. Tabelas curtas permanecem juntas. Uma célula ou título maior que a altura útil continua sendo rejeitado com diagnóstico; o conteúdo não é recortado para forçar a saída.

Os rascunhos recuperáveis abrangem edição em lote e formulários auxiliares de bibliotecas, importação, anotações e criação. A recuperação abre o formulário para revisão; não aplica mudanças nem restaura aprovações. Formulários do espaço de trabalho são separados dos formulários de cada relatório. Permanecem as cotas e a retenção de 30 dias do navegador.

A revisão visual oferece **Salvar progresso no projeto**: página atual, notas e pendências vinculadas ao SHA-256 do PDF e à revisão de origem. Salvar uma cópia privada do PDF é opcional. Sem ela, reabra o arquivo original exato. Os registros ficam fora dos relatórios publicados, mas são incluídos em backups e histórico. Excluir o registro atual não apaga versões anteriores.

Abra o assistente com `python scripts/install.py --gui --lang pt`. Exige Python 3.11 ou posterior, Tkinter e uma sessão gráfica. O assistente orienta diagnóstico, pastas, instalação e recuperação. Atualizações usam uma pasta nova; bloqueios do aplicativo e dos dados impedem atualizar com o editor aberto. Python e requisitos do sistema continuam necessários: o assistente não inclui todas as dependências em um pacote autônomo.

A aceitação nativa do Microsoft Word permanece separada. O corpus inclui espanhol, inglês e português; `--additional-projects CAMINHO` inclui três projetos complexos em `es/`, `en/` e `pt/`. Exige Windows com Word de desktop instalado e licenciado. Preparar o kit, validar DOCX ou renderizar com LibreOffice não executa o Word.

## Novidades da 0.40.0

A barra lateral mantém cinco grupos de ferramentas. As listas de seções e achados abrem em um **Índice** ao lado do editor, com busca, filtros de achados e páginas de 50 registros. Você pode fechar o painel ou ajustar sua largura sem alterar o relatório. Se um filtro ocultar o item aberto, **Mostrar seleção** permite localizá-lo novamente.

**Ordenar seções** ativa explicitamente os controles para movê-las. A lista normal mantém a ordem do projeto. No celular, selecionar um item fecha o índice; **Escape** devolve o foco ao botão. As preferências do índice ficam neste navegador, separadas por espaço de trabalho e projeto. [Uso do índice e navegação](docs/guide.pt.md#navegação-lateral-na-0400).

## Novidades da 0.39.0

*Histórico da 0.39.0: a organização em cinco grupos permanece; suas listas expansíveis dentro da barra foram substituídas pelo índice contextual na 0.40.0.*

A barra lateral organiza o trabalho em cinco grupos: **Projeto**, **Conteúdo**, **Evidências e escopo**, **Análise e acompanhamento** e **Entrega**. As linhas mantêm tamanho e espaçamento consistentes. Os índices expansíveis de seções e achados mostram suas quantidades e preservam a paginação dos projetos extensos.

Ao navegar para um item, seu grupo é aberto e a seleção fica visível. Esse ajuste da barra lateral preserva o foco e não rola o editor. Você pode recolher o grupo atual; as atualizações em segundo plano respeitam essa escolha. **Entrega → Ferramentas** reúne bibliotecas, backup integral, privacidade, diagnóstico e atualização do aplicativo. No celular, **Navegação** abre a barra e **Escape** a fecha, devolvendo o foco ao botão.

O novo caso fictício **Atlas Servicios Financieros** prepara uma avaliação ampla com conteúdo redigido em espanhol, inglês e português do Brasil. Seu [protocolo de aceitação](docs/QA-ATLAS-0390.md) distingue relatórios completos, amostras de modelos, percursos de API e verificações visuais. Os resultados são comprovados por execução; saídas pendentes não são consideradas aprovadas. [Percurso da barra lateral](docs/guide.pt.md#navegação-lateral-na-0390).

## Novidades da 0.38.0

**Erros com localização:** importações mostram o registro, campo e linha disponíveis; exportações com falha identificam o achado, tabela, linha, célula ou evidência quando o contrato pode localizá-los com segurança. Caso contrário, o erro geral é preservado. Esses detalhes privados ficam fora dos manifestos de entrega.

**Visualização DOCX com LibreOffice:** a partir de uma exportação concluída com Word, gere explicitamente uma vista PDF usando o LibreOffice instalado no computador. A vista está vinculada ao DOCX exato por SHA-256 e revisão, sem modificá-lo. É privada e temporária; mostra a diagramação do LibreOffice e não comprova equivalência com o Microsoft Word.

**Inspeção de anexos PDF:** examine texto extraível, metadados e estruturas do PDF dentro de limites explícitos. Os resultados mostram categorias e localizações, sem revelar valores sensíveis nem alterar o arquivo. O escopo sempre é parcial: não inclui OCR, inspeção de binários arbitrários nem reconstrução de versões anteriores do PDF. A autorização manual do anexo continua necessária.

A limpeza remove auxiliares privados, variáveis sem uso, constantes obsoletas e 20 regras CSS sem emissores atuais. Adaptadores públicos, callbacks de bibliotecas e recursos com funções documentadas são preservados. Isso não afirma ausência universal de código morto. [Uso e limites dos novos recursos](docs/guide.pt.md#revisar-erros-e-documentos-na-0380).

## Correções da 0.37.1

Imagens com links em tabelas Markdown preservam destinos e legendas no Word, incluindo fragmentos de URL e texto ao redor. A verificação de links permanece ativa. O caso fictício Banco Horizonte Austral amplia a aceitação de conteúdos e fluxos; consulte a matriz de cobertura em `qa/horizonte/`.

## Novidades da 0.37.0

**Parear páginas PDF:** relacione manualmente as páginas anteriores e posteriores após inserções ou mudanças de ordem. O editor mostra cada correspondência e as páginas sem equivalente; cada página deve aparecer exatamente uma vez.

**Registrar a revisão:** salve opcionalmente autor autodeclarado, decisão, nota, correspondências e hashes como um registro JSON privado do projeto. Ele só é salvo quando solicitado e fica excluído da entrega por padrão. Permanece no histórico e nos backups, sem exclusão automática. PDFs, HTML e imagens não são copiados para o registro; baixe o HTML separadamente para conservar as imagens da comparação.

**Extensões SARIF:** regras independentes de `tool.extensions` são aceitas com referências coerentes por índice ou GUID. A origem do componente é preservada e as observações continuam informativas e não verificadas.

## Recursos introduzidos na 0.36.0

**SARIF 2.1.0:** em **Importar resultados**, confira a origem e selecione o que deseja incorporar. Os resultados permanecem como observações informativas não verificadas; o nível do analisador não é convertido em CVSS.

**Comparar PDFs:** selecione dois arquivos no histórico para ver as páginas e as diferenças destacadas. Baixe a comparação como HTML independente. Por padrão, as páginas são pareadas por posição; mudanças visuais não comprovam mudanças de significado.

## Recursos

- Escopo, metodologia, inventário, cobertura e achados com etapas reproduzíveis; CVSS 3.1 e 4.0 quando apropriado.
- Evidências com legendas, vínculos a achados e cópias anotadas ou censuradas para publicação.
- Identidades estáveis, histórico recuperável, comparação de revisões, remediação e matriz de retestes.
- Seis designs gerais e 30 perfis especializados na galeria. Perfis de certificação não implicam afiliação nem garantem conformidade com as regras de um exame.
- Entregas técnicas, executivas e públicas com decisões explícitas de inclusão. A publicação exige texto aprovado e consentimento registrado.
- Backup do projeto, backup integral do espaço de trabalho e atualização guiada com verificação do pacote.

| Formato | Arquivo entregue |
| --- | --- |
| PDF | Relatório paginado `.pdf`. |
| Word | Documento editável `.docx` com campos próprios de sumário. |
| Markdown | ZIP com `report.md` e suas imagens. |
| HTML portátil | Arquivo `.html` independente com filtros de leitura. |

## Verificação e limites

As verificações apresentam revisão, SHA-256, tamanho e controles de cada arquivo. A comparação de conteúdo e referências tem um escopo diferente em cada formato. **Esses controles não certificam a correção da avaliação nem a apresentação visual.** Revise os documentos antes da entrega.

O PDF exige pelo menos um mecanismo disponível. Se nenhum estiver instalado, o editor e as exportações Word, Markdown e HTML continuam disponíveis. Execute `python3 start.py --diagnose --lang pt` e consulte as instruções de bibliotecas nativas no [guia](docs/guide.pt.md).

Word e LibreOffice podem paginar de maneira diferente. Há uma extensão opcional do LibreOffice para a quebra de literais técnicos ASCII marcados pelo report-gen, sem inserir caracteres nem alterar os links. Sua instalação e funcionamento foram verificados com **LibreOffice oficial 26.2.6.3 para Linux x86-64 e Python UNO**. O DOCX continua editável sem a extensão, mas certas URLs podem quebrar antes do fim da linha. Isso não comprova compatibilidade da extensão em Windows ou macOS. A revisão no Microsoft Word nativo e a avaliação humana com leitor de tela continuam fora da aceitação automatizada.

O sumário do DOCX é construído durante a exportação. A atualização de campos recalcula os números das páginas; mudanças na estrutura dos capítulos exigem uma nova exportação. O texto e o destino das URLs permanecem parte do contrato de verificação, mesmo quando um visualizador externo muda sua aparência.

## Privacidade e recuperação

O editor funciona em **`127.0.0.1`, em um único processo**, sem contas nem serviços externos para a edição normal. Após instalar as dependências, o trabalho cotidiano permanece local. A assistência com Ollama é opcional e depende de uma solicitação explícita; confira quais campos serão enviados antes de ativá-la.

O backup integral inclui projetos, imagens originais e histórico: trate-o como informação privada. Projetos em disco e rascunhos do navegador não são criptografados pelo aplicativo. O extra opcional `privacy` permite baixar um backup privado protegido por senha; ele criptografa somente esse arquivo.

Rascunhos são separados por espaço de trabalho, perfil do navegador, host e porta. O backup do espaço de trabalho não inclui esses rascunhos. Baixe os rascunhos pendentes antes de transferir os dados ou mudar o endereço de acesso.

O HTML portátil contém o relatório completo: seus filtros não são permissões de acesso. Detectores de possíveis segredos não substituem a revisão humana. A assinatura Ed25519 opcional verifica a integridade em relação a uma chave pública previamente fixada; ela não criptografa os documentos nem certifica as conclusões.

## Atualizar sem perder os dados

**Atualizar report-gen** permite conferir a nova versão e preparar um backup privado sem criptografia. A preparação não substitui a instalação em execução. Baixe as instruções privadas, pare o editor e siga os comandos indicados.

Se os dados já estiverem em um espaço de trabalho externo, extraia a nova versão em outra pasta e execute nela:

```bash
python3 scripts/install.py --desktop --workspace /caminho/dados-existentes --lang pt
```

Abra uma única instalação por vez e não copie a `.venv` antiga. Para migrar uma instalação que ainda utiliza `webapp/`, execute na pasta nova:

```bash
python3 start.py --ready --workspace /caminho/novos-dados --upgrade-from /caminho/report-gen-anterior --lang pt
```

O destino deve estar vazio. A migração preserva a origem e cria um backup privado. Confira projetos, imagens e histórico antes de desativar a instalação anterior.

## Terminal e desenvolvimento

Para exportar um projeto próprio:

```bash
.venv/bin/python export.py /caminho/projeto/engagement.yaml -f pdf -o out/relatorio.pdf --error-language pt
```

Use `pdf`, `docx`, `md` ou `html` em `-f`; `md` gera um ZIP. O idioma do relatório vem de `meta.lang` no projeto. `--error-language` controla as mensagens de execução e não traduz o conteúdo.

O desenvolvimento e os testes de interface exigem **Node.js 22 ou superior**:

```bash
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci
.venv/bin/python -m pytest
npm test
```

[Guia de uso](docs/guide.pt.md) · [Contribuição](CONTRIBUTING.md) · [Segurança](SECURITY.md) · [Licença MIT](LICENSE)
