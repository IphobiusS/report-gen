# Guia do usuário do report-gen 0.40.0

[Boas-vindas](../README.pt.md) · [Español](guide.es.md) · [English](guide.en.md) · [Histórico de alterações](../CHANGELOG.md)

Execute os comandos na raiz do projeto, onde está `start.py`, salvo indicação diferente. A instalação e os downloads opcionais precisam de conexão; a edição e as exportações normais são locais. O português disponível é a variante Brasil: chave `pt`, com `pt-BR` também aceito nos argumentos de idioma.

## Instalar e abrir

O caminho principal de instalação é Linux/Kali com Python 3.11 ou superior. Baixe e extraia o ZIP da [versão publicada](https://github.com/IphobiusS/report-gen/releases/latest). Na pasta extraída:

```bash
python3 scripts/install.py --desktop --lang pt
~/.local/bin/report-gen
```

O instalador prepara `.venv` com as versões limitadas por `requirements-audited.txt` e cria `~/.local/bin/report-gen`. A opção `--desktop` adiciona um atalho ao menu de aplicativos que abre um terminal. A instalação exige Python com suporte a venv e conexão; não usa `sudo` nem instala pacotes do sistema. Mantenha a pasta extraída e a `.venv`: o atalho depende desse local e não é um executável independente. As aberturas seguintes não reinstalam as dependências. Se mover o aplicativo, execute o instalador novamente no novo local.

O diretório de dados é escolhido nesta ordem: `--workspace`, `REPORT_GEN_WORKSPACE`, `$XDG_DATA_HOME/report-gen` ou `~/.local/share/report-gen`. Para definir outro destino:

```bash
python3 scripts/install.py --desktop --workspace /caminho/dados --lang pt
```

Os dados anteriores não são migrados automaticamente. Uma lista vazia pode indicar outro diretório de trabalho; leia a seção de migração antes de excluir ou mover arquivos.

`--lang pt` define as mensagens do lançador e o idioma inicial da interface. Uma preferência já salva no navegador tem precedência. Em **Mais → Preferências**, o seletor oferece **Español**, **English** e **Português (Brasil)**. Alterar essa preferência não traduz o texto redigido, não troca o idioma do relatório nem modifica a revisão salva. O idioma do relatório é escolhido nos dados do projeto.

O caminho `python3 start.py --ready --lang pt` continua disponível. Sem diretório externo ou variável de ambiente, ele conserva o local tradicional `webapp/`. `--ready` permite preparar dependências ausentes, executa o diagnóstico e abre o editor quando os requisitos estão disponíveis. Acesse **http://127.0.0.1:8080**; encerre o servidor com `Ctrl+C`. Use `--port 8081` para outra porta.

| Objetivo | Comando |
| --- | --- |
| Instalar com atalho, sem abrir | `python3 scripts/install.py --desktop --lang pt` |
| Abrir a instalação preparada | `~/.local/bin/report-gen` |
| Preparar, verificar e abrir | `python3 start.py --ready --lang pt` |
| Reinstalar as dependências e parar | `python3 start.py --setup --lang pt` |
| Diagnosticar sem instalar ou abrir | `python3 start.py --diagnose --lang pt` |
| Abrir o ambiente existente | `python3 start.py --lang pt` |

O diagnóstico distingue o editor de cada mecanismo de exportação. Abrir o editor não comprova a disponibilidade de todos os formatos. O uso normal não exige Node.js.

No Debian/Kali, as dependências nativas ausentes podem ser instaladas com:

```bash
sudo apt install python3-venv python3-dev libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
```

O Chromium é um mecanismo alternativo opcional para PDF:

```bash
.venv/bin/python -m pip install playwright -c requirements-audited.txt
.venv/bin/python -m playwright install chromium
```

Leia o estado de cada mecanismo no diagnóstico; o código de saída isolado não comprova que todos estejam disponíveis. Os seletores nativos acompanham o tema claro ou escuro; a aparência do menu aberto depende do navegador e do sistema operacional.

## Primeiro relatório

Na visão geral, escolha a demonstração fictícia Nimbus ou crie seu projeto. **Próxima ação sugerida** considera título, cliente, objetivos de escopo, achados, vínculos de evidências e a última revisão salva. A recomendação ajuda a redigir; não aprova o relatório nem exige inventar achados ou capturas. Você pode seguir diretamente para a revisão quando a sugestão não se aplicar.

Abra **Tutorial visual** no menu **Mais**, em desktop ou celular. A primeira visita oferece **Iniciar tutorial** e **Agora não**, sem bloquear o editor. Os seis passos têm instruções e capturas reais de dados fictícios em espanhol, inglês e português. É possível ampliar as imagens ou vê-las em tamanho real. **Escape** fecha a imagem e devolve o foco ao botão que a abriu. O progresso pertence ao navegador; **Reiniciar tutorial** não altera projetos. Com armazenamento bloqueado, o percurso continua funcionando durante a sessão. Nenhuma captura é enviada a um serviço externo.

1. **Comece.** Abra a galeria por **Criar meu projeto** ou **Novo projeto**. Compare modelos e páginas de amostra; continue para informar título, cliente, pasta e idioma do relatório. Voltar à galeria preserva os dados digitados. A demonstração Nimbus cria uma cópia editável; abrir um backup permite continuar um trabalho anterior.
2. **Defina o escopo.** Preencha cliente, avaliador, datas e metadados. Registre objetivos, ativos incluídos, exclusões e limitações. Use **Ativos** e **Cobertura** quando forem pertinentes à avaliação.
3. **Redija um achado.** Explique qual controle falhou, o comportamento observado, as etapas de reprodução, o impacto demonstrado e a correção proposta. Registre severidade, vetor CVSS e verificação técnica somente quando houver fundamento.
4. **Conecte as evidências.** Em **Evidências**, envie a imagem, preencha título e legenda e selecione os vínculos em **Usada em achados**. Revise e censure a cópia de publicação. Notas de captura rápida ficam fora do relatório até serem incorporadas.
5. **Revise o que compartilha.** Leia erros, avisos e explicações da revisão e abra o **Inspetor de publicação** para conferir texto e imagens. Confirme o salvamento em disco: um rascunho recuperável do navegador não equivale a uma revisão salva. Os controles detectam omissões; não confirmam vulnerabilidades.
6. **Entregue e preserve.** Revise anexos e escolha explicitamente os arquivos a incluir. Selecione formatos, gere o pacote e abra as exportações. Verifique apresentação, links e sumário. Alterações posteriores não mudam a revisão já colocada na fila. Baixe também o **Backup do projeto**, privado e separado da entrega ao cliente. Registre as verificações efetivas em **Correções e retestes**.

O CVSS descreve severidade técnica; sozinho, não representa risco de negócio. As seções **Postura de risco e impacto no negócio** e **Recomendações estratégicas** permitem documentar contexto, prioridades e apetite ao risco acordados com a organização. Ative-as em **Gerenciar seções**. O modelo não calcula nem aprova suas conclusões.

<a id="navegação-lateral-na-0390"></a>

## Navegação lateral na 0.40.0

A barra lateral reúne ferramentas em cinco grupos estáveis. As listas de conteúdo ficam em um **Índice** separado, ao lado do editor: percorrer uma lista extensa não aumenta a navegação global.

| Grupo | Conteúdo |
| --- | --- |
| **01 Projeto** | Visão geral e dados gerais do relatório. |
| **02 Conteúdo** | **Achados** abre o quadro; **Seções do relatório** e **Lista de achados** abrem o índice correspondente. |
| **03 Evidências e escopo** | Evidências, caixa de capturas, ativos e cobertura. |
| **04 Análise e acompanhamento** | Causas raiz, tarefas de correção, correções e retestes, alterações desde a entrega, matriz de retestes e versões. |
| **05 Entrega** | Revisão de entrega, backup do projeto e **Ferramentas**. |

Nas telas do relatório, de seções, de achados e do quadro, use **Índice** para abrir o painel e **Fechar índice** para recolhê-lo. As abas **Seções** e **Achados** mudam a lista sem trocar o item aberto. Pesquise por ID ou título e filtre achados por **Severidade** ou **Tipo**. A lista mantém a ordem do projeto e mostra até 50 registros por página. Pesquisar, filtrar ou mudar de página não reordena nem edita o relatório.

Se um filtro excluir a seleção atual, o painel informa isso e oferece **Mostrar seleção**. O item aberto permanece no editor até que você escolha outro. Cada lista tem sua própria rolagem no painel; ela já não fica aninhada em uma lista da barra global.

Para mudar a ordem das seções, ative **Ordenar seções**, use **Mover** na linha correspondente e escolha a posição de destino. É possível desfazer essa alteração; **Concluir ordenação** retorna à navegação normal. As linhas normais não permitem arrastar. Para mover achados, abra o quadro **Achados**, escolha a ordem **Manual** e use a ação **Mover**. Esses movimentos alteram a ordem do projeto; os filtros do índice não a alteram.

No desktop, **Largura do índice** ajusta o painel de 220 a 420 pixels, em passos de 20. Use as setas do teclado para ajustar, **Home** para o mínimo e **End** para o máximo. Abertura, largura, aba, pesquisas, filtros e página ficam salvos neste navegador, separados por espaço de trabalho e projeto; não são gravados como conteúdo do relatório. Em telas menores, a largura se adapta automaticamente. Se o índice deixar pouco espaço para a prévia, feche-o ou use **Mostrar prévia** para recuperar esse espaço.

**Entrega → Ferramentas** reúne **Biblioteca de modelos de relatório**, **Backup do espaço de trabalho**, **Dados privados armazenados**, **Verificar instalação**, **Atualizar report-gen** e, no desktop, **Evidências e decisões**. No celular, esta última permanece em **Mais**; **Tutorial visual** também fica em **Mais**. O backup do projeto continua separado do backup integral.

No celular, **Navegação** abre a barra global. O índice tem seu próprio botão; selecionar um item fecha o painel e leva o foco ao conteúdo. **Escape** fecha o painel aberto e devolve o foco ao botão. Um diálogo sobreposto mantém seu próprio controle de foco. Rótulos e controles estão disponíveis em espanhol, inglês e português do Brasil, nos temas claro e escuro; mudar o idioma da interface não traduz o conteúdo redigido.

## Modelos e idiomas

A biblioteca recomenda **Sóbrio** como ponto de partida geral. Compare capa, resumo e conteúdo técnico da mesma amostra. Existem seis modelos gerais, 26 perfis de certificação e prática, quatro estruturas empresariais e modelos pessoais. Filtre por finalidade ou fornecedor, busque pelo nome e compare as variantes **Marca** e **Sóbria**.

**Revisão de controles** inclui composição editorial e oito seções sobre desenho e operação dos controles, amostragem, exceções e retestes. Abrir a biblioteca de um projeto especializado mantém esse contexto; navegar pela galeria não altera o projeto. Aplicar uma aparência preserva seções, achados e evidências. Criar um projeto incorpora a estrutura inicial. Alterar o preset não substitui a aparência escolhida.

Os perfis fornecidos têm títulos, instruções e amostras em espanhol, inglês e português. Modelos pessoais podem conter os idiomas que você efetivamente redigiu: traduções são opcionais e o texto original é preservado quando uma versão não existe. Nada é traduzido automaticamente. Perfis de certificação são apoios independentes; um seletor em português não altera a exigência de relatório em inglês de determinados exames. Confira as instruções atuais do fornecedor.

O Word usa Calibri; PDF e HTML usam Carlito como fonte compatível. Comandos mantêm fonte monoespaçada. As miniaturas são páginas de exportações reais; duas categorias podem apontar para a mesma página quando resumo e conteúdo técnico cabem juntos.

## Organizar vários projetos

Em **Visão geral → Seus projetos**, busque título, cliente ou identificador; a busca aceita texto sem acentos. Filtre ativos, arquivados, todos ou projetos com retestes pendentes. Ordene por modificação, cliente, prazo mais próximo ou quantidade de retestes. Cada página apresenta oito projetos.

A data planejada de entrega é independente da data do relatório. O próximo prazo considera a entrega e os prazos dos achados, excluindo correções verificadas e riscos aceitos; atrasos continuam visíveis. Retestes pendentes contam achados com correção informada, não qualquer atualização recebida por CSV.

Arquivar preserva o conteúdo e permite abrir, editar ou reativar o projeto. Não exclui arquivos nem torna o projeto somente leitura. Datas e estado de arquivamento acompanham backups e histórico, mas não a publicação do relatório.

## Editar achados em lote

Abra **Achados → Edição em lote** e selecione os registros. Busca e páginas de 50 itens preservam seleções de outras páginas; o contador inclui todos os selecionados. Uma operação aceita até 500 achados.

1. Ative os campos a alterar: responsável, prazo de correção ou grupo de causa raiz. Um valor vazio remove essa atribuição; campos não ativados permanecem iguais.
2. Compare os valores anteriores e propostos. As alterações pendentes do relatório são salvas primeiro, inclusive antes da comparação de itens ocultos pela busca.
3. Revise, confirme e salve as alterações. O conjunto é salvo em uma operação com revisão recuperável em **Versões**. Uma alteração simultânea do projeto exige nova comparação.

A operação não muda estado, verificação técnica, evidências ou retestes. Uma falha de salvamento preserva a seleção e a proposta na aba para nova tentativa; não há garantia de sobrevivência ao recarregamento. Descartar uma proposta pendente exige confirmação.

O controle **Mover** permite reordenar pelo teclado. Filtros, vistas salvas, posição de leitura e atividade recente são separados por projeto e espaço de trabalho. Preferências antigas sem identidade de origem não são adotadas automaticamente. Um filtro cujo valor foi removido aparece como indisponível; limpar os filtros exibe novamente todos os achados.

## Diagnósticos compartilháveis

Abra **Entrega → Ferramentas → Verificar instalação**. A verificação gera arquivos PDF e DOCX sintéticos temporários e testa gravação no diretório de dados, sem exportar projetos reais. Um mecanismo indisponível aparece separadamente como falha.

Na área de diagnóstico compartilhável, revise o JSON, confirme a leitura dos campos e baixe o arquivo revisado. Ele contém versão do report-gen, sistema operacional genérico, versão do Python e estados de exportação sintética e gravação. Exclui projetos, clientes, usuários, caminhos, hostname, variáveis de ambiente e detalhes de exceções. Nada é enviado automaticamente. Alterar a prévia invalida o download; execute o diagnóstico novamente.

O teste DOCX cria e relê o documento. Não comprova paginação nem abertura no Microsoft Word nativo.

## Verificações e limites da entrega

**Ver verificações** apresenta revisão salva, SHA-256, tamanho e controles de cada arquivo. Todos os formatos exigem revisão visual. As mensagens completas ficam no editor; manifestos compartilháveis mantêm categorias e contagens dos avisos sem copiar caminhos ou valores privados dos diagnósticos. Isso não censura conteúdo que você escolheu incluir.

Anexos ficam excluídos até serem revisados e selecionados individualmente. Somente a entrega combinada os inclui. São copiados sem alteração, censura ou remoção de metadados; envie cópias já revisadas. Anexos obrigatórios bloqueiam a entrega até estarem revisados, incluídos e íntegros. Confirmar avisos não ignora esse requisito. Backups com anexos exigem 0.21.0 ou superior; registros com `required`, mesmo falso, exigem 0.21.1 ou superior.

O scanner de anexos lê o primeiro MiB de texto UTF-8, conta metadados de imagens e inspeciona PDFs com escopo limitado. [Consulte o percurso e os limites](#revisar-erros-e-documentos-na-0380). Não faz OCR de anexos, não os autoriza nem modifica. O OCR de imagens publicadas é outra ação, opcional e explícita, no inspetor. Os resultados apresentam escopo e limitações sem reproduzir valores sensíveis.

As verificações estruturadas comparam texto, código literal, metadados, tabelas nativas, links e posição de evidências no achado. Normalizam somente finais de linha do código. Destinos internos ausentes bloqueiam a publicação. A visibilidade estática do HTML não comprova geometria, sobreposição, CSS condicional ou estados dinâmicos.

No PDF, são verificados texto, células, itens de lista, imagens e destinos do sumário. Presença global de texto não comprova posição ou associação de cada célula. Com seções canônicas, os textos de cada achado também devem ocorrer entre os destinos que delimitam sua região; cópias no sumário não substituem texto ausente ali. Isso não verifica ordem visual nem associação individual das imagens. Documentos não canônicos mantêm a verificação global.

Linhas lógicas de código quebradas visualmente ficam na mesma página. Uma linha maior que a área imprimível é rejeitada, preservando o arquivo anterior. Espaços literais, associação de blocos e composição visual do PDF precisam de revisão humana. Ocorrências físicas independentes são reservadas para linhas de código e, em cada categoria, títulos, células, itens e parágrafos. Se a ambiguidade exceder o orçamento de verificação, o processo informa que não conseguiu concluir; não inventa perda de conteúdo.

Tabelas dentro de um achado devem caber em uma página com seu título. Divida ou reduza a tabela, ou mova o registro extenso para uma seção narrativa ou apêndice, onde pode continuar entre páginas. O prazo padrão de PDF é de 300 segundos. `REPORT_GEN_PDF_TIMEOUT` aceita inteiros de 30 a 600, definidos antes de abrir o aplicativo. Valor inválido impede iniciar o mecanismo; um timeout preserva a saída anterior e remove intermediários. A fila conserva cancelamento e prazo externo de 1.800 segundos. O orçamento não aumenta sozinho depois de uma falha.

PDF e HTML portátil ajustam URLs literais à largura disponível sem alterar texto ou destino. Literais ASCII longos possuem regras próprias de quebra, sem inserir caracteres invisíveis. No DOCX, o LibreOffice pode antecipar a quebra de algumas URLs sem a extensão opcional descrita abaixo. Preserve valores literais que sejam evidência ou comandos; rótulos descritivos são uma escolha de redação.

O PDF padrão com WeasyPrint detecta caracteres sem glifo nas fontes disponíveis e interrompe antes de substituir a saída anterior. Instale uma fonte que contenha o código indicado, como `U+1F3E6`, ou revise o texto. Texto extraível não comprova renderização correta do símbolo. Esse controle não certifica as fontes ou a composição do mecanismo Chromium opcional.

Em páginas com mapas de fontes especiais ou escrita da direita para a esquerda, um hífen ASCII no fim da linha só é recuperado se os códigos, mapas e um segundo leitor concordarem caractere a caractere. Hífen opcional, mapa não suportado ou leitura divergente podem continuar ambíguos. Nesse caso, a entrega para sem substituir o arquivo anterior; ajuste a quebra ou revise outro formato.

Inteiros do projeto devem ficar entre −9.007.199.254.740.991 e 9.007.199.254.740.991 para preservar o valor no navegador. Use texto entre aspas em YAML/JSON para identificadores maiores. Valores fora desse intervalo são rejeitados com o caminho do campo. Listas numeradas aceitam contadores de 0 a 2.147.483.647; ultrapassar o limite preserva qualquer saída anterior.

Em listas Markdown, use quatro espaços por nível para texto de continuação e blocos cercados de código, independentemente dos dígitos do marcador. Oito espaços no primeiro nível representam código indentado. Blocos cercados preservam tabulações, espaços e linhas vazias; código indentado segue a normalização do Markdown.

Listas do Word que começam acima de 65.535 usam campos `SEQ` para evitar truncamento observado no LibreOfficeDev 26.8. As demais mantêm numeração automática. Para ampliar uma lista baseada em campos, edite no report-gen e exporte novamente. No Word, copie um item posterior ao primeiro, conservando o campo, e atualize com **Ctrl+A → F9**. O primeiro campo define o início; Enter sozinho não adiciona o campo. A verificação de ordinais e instruções não substitui a revisão visual.

O sumário DOCX é construído na exportação, com links internos e campos `PAGEREF` independentes. O LibreOffice calcula números de página durante a diagramação; após editar, atualize com **Ctrl+A → F9**. Os números seguem a paginação do editor, não a do PDF. Adicionar, remover, renomear ou reordenar capítulos exige nova exportação do report-gen: a lista de entradas não é reconstruída por um campo TOC. Há largura reservada para que o número não fique isolado abaixo do título. Revise o resultado em cada editor utilizado; Word e LibreOffice podem paginar de forma diferente.

O Markdown inclui o gráfico de severidade como PNG, texto alternativo com contagens e legenda de escopo. A verificação compara os bytes da imagem, o texto e sua posição em relação ao resumo, separadamente das evidências.

## Extensão opcional do LibreOffice

O ambiente verificado é a distribuição oficial **LibreOffice 26.2.6.3 para Linux x86-64**, com seu provedor Python UNO. A aceitação instala a OXT pelo carregador real em um perfil temporário e verifica abertura, alterações de largura, salvamento e reabertura. Não promete quebras idênticas em outros editores nem substitui a revisão do seu documento.

A exportação DOCX marca literais elegíveis com o identificador não linguístico privado `zxx-ZZ-x-rgwrap`. Isso altera metadados de idioma dos fragmentos, não a prosa, os caracteres, o estilo ou os destinos. A marcação pode abranger texto, tabelas, cabeçalhos e rodapés; campos e resultados são preservados. Exportar e abrir o DOCX não exige instalar a extensão.

A regra cobre URLs HTTP/HTTPS/FTP/FTPS inteiramente ASCII com pelo menos 32 caracteres e identificadores ASCII imprimíveis, sem espaços, com pelo menos 24 caracteres e algum dígito, sublinhado, barra ou dois-pontos. Exclui palavras compostas somente de letras e URLs não ASCII. Não insere caracteres invisíveis, hífens ou quebras manuais. Ao acrescentar prosa depois de um literal no Writer, mantenha o idioma da prosa ao redor.

O provedor UNO deve pertencer à mesma instalação do LibreOffice. A `.venv` do report-gen não o substitui. O ambiente aceito usa os pacotes oficiais 26.2.6.3, incluindo `libobasis26.2-pyuno` e `libobasis26.2-python-script-provider`. Não misture componentes Python de distribuições diferentes. A instalação da extensão falhou nos pacotes **LibreOffice 24.2.7.2 do Ubuntu**, mesmo com os provedores instalados; esse caminho não está aceito para a extensão.

Crie a OXT sem instalá-la:

```bash
python integrations/libreoffice/build_oxt.py --output report-gen-libreoffice-0.40.0.oxt
```

1. No LibreOffice escolhido, abra **Ferramentas → Extensões → Adicionar**; algumas versões usam **Gerenciador de extensões**.
2. Selecione a OXT e instale para seu usuário.
3. Feche todas as janelas dessa instalação, reabra o aplicativo e abra uma cópia do DOCX recém-exportado.
4. Revise URLs, listas e tabelas depois de abrir, editar e salvar. Para remover, desative ou exclua a extensão pelo mesmo gerenciador e reinicie.

Sem a extensão, o documento conserva texto e edição, mas pode manter quebras antecipadas. Documentos antigos precisam ser exportados novamente para receber as marcações. A melhoria depende do mecanismo e da extensão; não é uma correção portátil contida somente no DOCX. Microsoft Word nativo e a extensão no LibreOffice de Windows ou macOS continuam sem aceitação equivalente.

A OXT não altera exportações PDF, HTML ou Markdown do report-gen. Não impede toda normalização na conversão LibreOffice → PDF: um destino com `%2D` pode virar `-` na anotação do PDF, embora o literal visível e o destino DOCX sejam preservados. A OXT é criada separadamente e não é um quarto ativo da Release; o atualizador não a instala.

## Recuperação e privacidade

O editor funciona em um processo local em `127.0.0.1`; não é um serviço multiusuário. O espaço de trabalho externo contém `projects/` e `library/`, com originais, histórico e anexos dentro de cada projeto. Sem seleção externa, o lançador mantém `webapp/projects/` e `webapp/library/`; não procura nem move dados sozinho.

**Backup do espaço de trabalho** contém projetos salvos, originais e bibliotecas. Trate-o como informação privada. Rascunhos pendentes ficam em IndexedDB por 30 dias, separados por identidade do espaço de trabalho, perfil do navegador, host e porta. A interface só informa recuperação disponível depois que a gravação termina. O aplicativo não criptografa esses rascunhos.

Um registro separado protege capturas e formulários de evidências e decisões pendentes, com recuperação explícita: não anexa evidências nem aprova publicação automaticamente. Limites: 16 MiB por imagem, 1 MiB por formulário, 64 MiB no total e 30 dias. Falhas de armazenamento são indicadas como trabalho somente na aba. Após recuperar, a autorização de publicação deve ser dada novamente. Essa proteção não abrange todo diálogo auxiliar.

Rascunhos e formulários pendentes ficam fora dos backups e do JSON de emergência; incorpore e salve o trabalho antes de mudar a instalação ou a origem do navegador. Navegação privada, limpeza de armazenamento ou troca de perfil/porta podem tornar as cópias inacessíveis. Use **Mais → Baixar rascunho privado** como cópia de emergência. A recuperação exige o projeto correto e resolução explícita de conflitos.

A identidade permanece estável enquanto o diretório externo não mudar. Mover dados ou restaurar um backup em outro espaço cria um novo escopo; nomes iguais não autorizam adotar rascunhos. Se a aba detectar mudança de espaço no servidor, bloqueia as requisições e permite baixar o rascunho antes de recarregar.

Cópias antigas sem identidade são mantidas em **Cópias legadas sem origem atribuída**, sem adoção nem exclusão automática. Reconheça a origem incerta, revise e baixe a cópia privada. Capturas pendentes oferecem também a imagem original. Importar um rascunho com identidade ausente ou diferente exige confirmação antes da comparação. A exclusão dessas cópias é explícita.

**Dados privados armazenados** inventaria arquivos atuais, originais, histórico e anexos removidos. A limpeza exige seleção das categorias e identificador exato do projeto. Dados atuais são preservados; limpar o histórico cria um novo ponto de recuperação. Rascunhos têm controles separados. Backups externos e downloads não podem ser excluídos por esse painel.

A censura de texto afeta a cópia de publicação; a censura de imagem cria uma cópia com pixels alterados e preserva o original privado. Metadados das imagens são removidos das exportações. Padrões de detecção não identificam todos os segredos: revise manualmente. O HTML portátil contém o relatório inteiro; filtros e vista executiva não são controle de acesso. Comparações internas podem conter imagens privadas e não são entregas ao cliente.

A fila encerra os processos de cada trabalho antes de limpar arquivos. Windows usa um job de processo privado. Linux e macOS mantêm o grupo do trabalho por meio de um supervisor; a limpeza abrange descendentes que permaneçam nesse grupo, não programas que criem deliberadamente outra sessão.

## Atualizações guiadas

Abra **Entrega → Ferramentas → Atualizar report-gen**. Não há consultas de rede em segundo plano nem atualizações automáticas.

1. Autorize consultar e baixar do GitHub e verifique a versão oficial. Somente `IphobiusS/report-gen` é consultado; relatórios, caminhos locais e credenciais não são enviados.
2. Revise versão, tamanho, SHA-256 e Release. Confirme separadamente a preparação do pacote e de um backup privado sem criptografia. Alterações pendentes no projeto aberto são salvas primeiro.
3. Baixe as instruções privadas. Elas contêm destinos do aplicativo e backup, horário da captura, hash e comandos para continuar ou retornar à instalação anterior.
4. Salve ou baixe rascunhos de outras abas, feche-as e pare o servidor com `Ctrl+C`. Não edite entre o backup e a atualização. Execute as linhas uma por vez e pare se houver falha. Instalar as dependências da nova pasta exige Internet.
5. Confira projetos, imagens, histórico e exportações antes de desativar a instalação anterior; mantenha o backup.

A preparação verifica tag, commit, os três ativos oficiais (ZIP, JSON e SHA-256), o hash do ZIP e cada arquivo do manifesto. Rejeita caminhos e tipos de arquivo não suportados. Isso verifica integridade em relação à origem HTTPS oficial, não uma assinatura independente do repositório. Limites: 128 MiB comprimidos, 256 MiB extraídos e 4.000 arquivos.

Os arquivos ficam em `~/report-gen-updates/update-*/`: `application/`, `workspace-backup.zip` e `receipt.json`. Cada preparação captura os dados salvos e valida uma restauração temporária. Uma captura idêntica pode reutilizar a preparação verificada; dados alterados criam outra, preservando o backup anterior. Esses arquivos são privados e o ZIP não é criptografado. Rascunhos do navegador ficam excluídos.

A preparação não executa o código baixado nem substitui o aplicativo em execução. Use uma única instalação por vez no mesmo espaço de trabalho. Se já tiver editado na versão nova, mantenha ambas as pastas e restaure o backup em um espaço vazio para retornar, sem sobrescrever trabalho.

## Migrar uma versão anterior

Se os dados já estiverem fora do aplicativo, pare o editor, extraia a versão nova em outra pasta e execute nela:

```bash
python3 scripts/install.py --desktop --workspace /caminho/dados-existentes --lang pt
```

Isso prepara a nova `.venv` e atualiza o atalho para reutilizar os dados, sem importar ou usar `--upgrade-from`. Não execute dois processos sobre o mesmo espaço.

Para separar os dados ainda guardados na instalação antiga, pare ambos os editores e execute na pasta nova:

```bash
python3 start.py --ready --workspace /caminho/novos-dados --upgrade-from /caminho/report-gen-anterior --lang pt
```

O destino deve estar vazio e fora das instalações. Se você atualizou o código na pasta que contém os dados antigos, use `--upgrade-from .` para transferi-los dali. Sem `--workspace`, permanece a migração entre duas instalações distintas. Não mescle nem exclua diretórios manualmente.

O lançador cria um backup da origem, valida uma restauração temporária e transfere os dados. Exibe resultado, caminho do ZIP e SHA-256, verifica os mecanismos e abre o editor. Sem `--ready`, com dependências preparadas, para após o diagnóstico. O backup privado fica em `~/report-gen-backups/upgrade-*/workspace.zip`, com `result.json`, fora das instalações e do destino externo.

Caminhos sobrepostos, links simbólicos, estados de recuperação pendentes e destinos ocupados são rejeitados. Corrija a causa e use um destino vazio; não apague dados para forçar a migração. A origem permanece intacta. São preservados projetos, evidências, histórico e bibliotecas; `.venv`, entregas e rascunhos de navegador não são copiados. Baixe os rascunhos antes de mudar a origem do navegador.

Também é possível restaurar um backup integral anterior em uma instalação vazia. O exportador 0.21.2 podia omitir a única revisão anterior em `engagement.yaml.bak`, sem snapshots. Preserve a pasta original e use a migração 0.30.0 ou posterior para incluir esse estado legado. Um ZIP antigo que já omitiu a cópia não pode reconstruí-la.

Os identificadores são preservados. Desde 0.21.2, `finding_sequence` impede reutilizar IDs removidos. Referências já desviadas por alterações antigas não podem ser corrigidas automaticamente sem conhecer a intenção original.

## Importar resultados de scanners

O fluxo aceita CSV, Burp, Nuclei JSONL e Nmap XML. Revise e selecione antes de aplicar. Resultados do Nuclei continuam sem verificação técnica; importar não confirma um achado. O Nmap adiciona ativos, serviços e cobertura pendente, não achados simplesmente por haver portas abertas.

As importações preservam origem, evitam duplicatas e verificam a revisão atual. Não executam comandos importados nem contatam alvos. Limites: 4 MiB, 500 linhas ou hosts e 10.000 portas. O Nmap omite scripts NSE, sistema operacional e traceroute; uma varredura sem término bem-sucedido registrado é marcada como parcial.

## OCR opcional de capturas

Solicite OCR de uma imagem publicada específica no inspetor. É necessário Tesseract local com dados `eng`; não há download automático do mecanismo nem serviço externo de imagens. Limites: imagem estática de 12 MiB e 12 megapixels.

O resultado apresenta categorias e regiões de possíveis dados sensíveis, sem exibir nem guardar os valores reconhecidos. Ausência de alerta não comprova segurança. Revise a imagem e crie explicitamente uma cópia censurada quando necessário. O original permanece intacto. Mecanismo ausente, erros e limites são informados. A interface em português não muda o idioma dos dados OCR instalados.

## Backups periódicos opcionais

Em **Backup do espaço de trabalho → Backups periódicos opcionais**, informe o caminho absoluto de uma pasta existente fora do aplicativo e do espaço de trabalho. Escolha frequência de hora, dia ou semana e retenção de 1 a 90 cópias. Revise o destino, reconheça que são cópias privadas sem criptografia e salve a programação. Ela começa desativada. Desativá-la não remove as cópias existentes.

A programação funciona somente enquanto o servidor local permanece aberto. Fechar a aba não para o servidor; encerrar o processo, sim. Ao reiniciar, uma cópia atrasada pode ser feita, sem repetir cada intervalo perdido. Há verificação na abertura e a cada minuto; falhas aguardam ao menos cinco minutos. Nenhuma tarefa do sistema operacional é instalada e nada é enviado pela rede.

Cada cópia inclui projetos salvos, originais, anexos, versões e bibliotecas. A captura usa o bloqueio de edição para não registrar uma operação pela metade. Rascunhos e formulários pendentes ficam excluídos. Criar e verificar uma cópia imediatamente salva primeiro o projeto aberto; execuções programadas usam apenas o que já está em disco. Senhas não são guardadas.

O aplicativo cria a subpasta `report-gen-backups-<identificador>`. Antes de registrar a cópia e remover antigas, restaura o ZIP temporariamente, valida conteúdo e bytes. A retenção afeta somente arquivos registrados e íntegros daquela série. Arquivos alheios, cópias modificadas e destinos anteriores são preservados. Mudar o destino inicia outra série.

Avisos identificam retenção pendente por permissão ou arquivo alterado. Uma cópia que mudou durante a remoção pode permanecer em `.retention-*` quando retornar ao nome original sobrescreveria outro arquivo; revise antes de limpar manualmente. Esse controle não isola arquivos de um processo malicioso com acesso à mesma conta do sistema.

O painel mostra última cópia e restauração temporária bem-sucedidas, caminho privado e SHA-256. Atualize o estado e verifique a última cópia quando necessário. Uma data antiga não comprova o sucesso da última tentativa. Resolva falta de espaço, disco desconectado ou permissões e repita a verificação.

A configuração pertence ao espaço atual e fica fora de relatórios e backups; programe novamente após mover ou restaurar dados. Para recuperar, restaure o ZIP em uma instalação vazia. A verificação temporária não substitui uma cópia em outro dispositivo.

## Backups privados criptografados

Instale a dependência opcional no ambiente do projeto:

```bash
.venv/bin/python -m pip install -e '.[privacy]' -c requirements-audited.txt
```

Em **Backup do espaço de trabalho**, informe e confirme uma senha de 12 a 256 caracteres e baixe o backup criptografado. O `.rgbackup` contém todo o espaço privado, não uma entrega ao cliente. AES-256-GCM autentica o arquivo; scrypt deriva a chave com parâmetros fixos. Guarde a senha separadamente: o report-gen não a recupera.

A criptografia cobre esse arquivo baixado, não projetos em disco nem rascunhos. O ZIP sem criptografia continua disponível, identificado como tal. Restaure com a senha em uma instalação vazia. A autenticação precede validação e ativação; senha errada, arquivo modificado ou destino ocupado não autorizam restauração parcial ou mescla.

## Causas raiz e tarefas de correção

Em **Análise e acompanhamento → Causas raiz**, crie um grupo com nome, causa e ação compartilhada. Vincule os achados; cada um mantém identidade, severidade, evidências, responsável e retestes. Remover um grupo desvincula membros após confirmação, sem excluir achados. Cada achado também pode ter critérios verificáveis de encerramento.

Uma ação específica do achado tem precedência sobre a ação compartilhada. A seção de causas raiz fica desativada por padrão; ative-a explicitamente e revise o resultado. Entregas parciais conservam somente grupos com achados incluídos. Públicos executivo e público não recebem automaticamente esse conteúdo privado.

Em **Tarefas de correção**, escolha os campos a compartilhar. Referências permanentes mantêm a correspondência com os achados. Campos redigidos podem conter dados do cliente e exigem confirmação de revisão. Salve, gere a prévia e baixe CSV ou cartões HTML em ZIP. Alterar campos ou projeto invalida a prévia e exige nova revisão. Nenhuma tarefa é enviada a um serviço externo.

Células CSV que poderiam ser fórmulas são neutralizadas. Cartões mostram texto sem executar HTML. Dados ausentes ficam vazios. Exportar uma tarefa ou escrever critérios não comprova que a correção foi concluída.

## Receber atualizações dos responsáveis

Em **Tarefas de correção → Receber atualizações dos responsáveis**, emita um modelo CSV de retorno. Selecione achados com responsável, revise os dados e confirme a retenção. Emitir salva uma atribuição no projeto e no histórico; não é somente baixar um arquivo. São mantidos até 20 lotes ou 4 MiB; novos lotes expiram os mais antigos. Backups e reinícios preservam os lotes vigentes.

Forneça `remediation-return.csv` e solicite alterações apenas em `owner`, `due_date` e `reported_remediation`. Preserve referências, cabeçalhos e apóstrofos iniciais dos campos de texto, inclusive `project_slug`; pertencem ao formato reversível que neutraliza fórmulas. O responsável não pode ficar vazio. Datas usam `YYYY-MM-DD`; data vazia propõe limpar o prazo. Salve CSV UTF-8 separado por vírgulas, até 2 MiB e 500 linhas. É possível devolver parte das linhas, mas não misturar lotes. O CSV informativo de tarefas não é um modelo de retorno.

Envie o arquivo e compare o retorno. São exibidos valores atuais e propostos, além do valor emitido se houver alteração desde então. Nada é aceito por padrão. Selecione cada mudança, confirme a revisão e salve. Alterações simultâneas exigem nova comparação. Falha temporária de salvamento preserva o arquivo carregado e as escolhas na aba. Depois do sucesso, a prévia do relatório deixa de considerar atual a revisão anterior.

A comunicação fica separada como correção informada pelo retorno, sem verificação. Importar nunca altera estado, verificação técnica, retestes, descrição ou evidências. Registre as verificações reais em **Correções e retestes**. O modelo identifica projeto e lote, mas não autentica o remetente; confira a origem antes de aceitar.

## Entregas por responsável e registro local

Na emissão do modelo, selecione os achados e os campos dos cartões. Reconheça dados privados e retenção. A prévia da entrega por responsável mostra cartões e os campos sempre incluídos no CSV: `owner`, `due_date` e `reported_remediation`, inclusive a última comunicação existente.

Emitir cartões e CSV por responsável cria `remediation-delivery.zip` e salva o lote. Cada pasta `owner-001/`, `owner-002/` etc. contém índice HTML, cartões e CSV de retorno. O manifesto registra campos, responsáveis, revisão e hashes; `INSTRUCTIONS.txt` explica a separação. Imagens e anexos não são adicionados. O ZIP inteiro inclui todos os responsáveis selecionados: revise e separe as pastas adequadas antes de compartilhar. Nada é enviado automaticamente e o ZIP não impõe controle de acesso.

O registro local diferencia emissão, recebimento registrado, alterações aceitas e revogação, com horários, revisão e hashes. Comparar CSV é somente leitura. Após revisar, registre recebimento sem aplicar ou salve as alterações selecionadas; nenhuma ação autentica o remetente. Revogar impede novos retornos desse lote sem excluir achados nem registros.

Limites: 20 lotes ou 4 MiB no total e 16 eventos por lote; o registro informa quantos eventos anteriores foram omitidos. Lotes acompanham backup e histórico e ficam fora dos relatórios. Restaurar uma revisão antiga também restaura o estado dos lotes e revogações. O registro editável não comprova recebimento pelo destinatário nem correção verificada.

## Terminal e desenvolvimento

Desenvolvimento e testes de interface exigem Node.js 22 ou superior e um ambiente Python preparado. Execute na raiz do projeto:

```bash
.venv/bin/python export.py /caminho/dados/projects/meu-projeto/engagement.yaml -f html -o relatorio.html --error-language pt
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci
.venv/bin/python -m pytest
npm test
export RG_PYTHON="$PWD/.venv/bin/python"
npm run test:workspace
npx playwright install chromium
export REPORT_GEN_CHROMIUM="$(node -p "require('playwright').chromium.executablePath()")"
.venv/bin/python -m pytest tests/test_portable_report_browser.py
node tests/test_visual_tutorial_0340.cjs --output out/tutorial
```

Os demais formatos são `pdf`, `docx` e `md` (ZIP com imagens). Instalações legadas usam `webapp/projects/`. Clientes de API selecionam mensagens de erro com `X-UI-Language: es`, `en` ou `pt`; `pt-BR` é aceito. Sem cabeçalho ou com valor não suportado, permanece o padrão histórico espanhol. Diagnósticos de bibliotecas e ferramentas externas são preservados literalmente. Isso não altera o idioma do relatório nem conteúdo redigido.

Resumos automáticos descrevem os achados e classificações registrados, sem afirmar que todos foram confirmados. Registros de máquinas e inventário de ativos não comprovam avaliação. Consulte cobertura, limitações e estado de verificação. Texto explicitamente redigido é preservado e precisa de revisão.

O repositório contém código, testes, demonstrações, modelos e documentação relevante de uso. Logos pertencem aos respectivos titulares e não implicam afiliação.

## Releases e aceitação externa

A [Release](https://github.com/IphobiusS/report-gen/releases/latest) fornece ZIP de código, arquivo SHA-256 e manifesto JSON. A publicação automática exige sete workflows no mesmo commit: **tests**, **Browser acceptance**, **Windows compatibility**, **macOS compatibility**, **Additional renderer acceptance**, **Reproducible source package** e **R16 trilingual acceptance**. O publicador reconstrói a partir do Git e verifica os três ativos antes de publicar. Automação aprovada não substitui revisão de documentos nem sessões humanas.

`python scripts/prepare-external-acceptance.py --output out/external-acceptance` prepara seis DOCX sintéticos e um CSV vazio para cinco participantes e três tarefas. O manifesto registra Word nativo e sessões humanas como `not_run`. O fluxo manual de Word exige Windows com Word de desktop instalado. Consulte `CONTRIBUTING.md` para o protocolo; preparar material não comprova que a observação ocorreu.

O kit contém `word-review.csv` e `INSTRUCTIONS.txt`. Depois das verificações reais, `python scripts/prepare-external-acceptance.py --summarize out/external-acceptance` valida hashes e registros sem alterá-los. Automação nativa, revisão visual e sessões humanas mantêm estados separados; preencher registros não comprova usabilidade geral.

## Importar SARIF e comparar páginas PDF

Em **Importar resultados**, escolha **SARIF 2.1.0** e um arquivo `.sarif` ou `.json` UTF-8 (até 4 MiB, 50 execuções e 500 resultados). Confira a prévia antes de importar a seleção. Resultados com supressão aceita, pendente ou sem estado, ausentes ou sem falha aparecem excluídos; uma supressão rejeitada não exclui o resultado. Duplicatas já importadas não são incorporadas novamente. São preservados origem, localização, nível do analisador e hash do arquivo. Localizações, esquemas e fragmentos externos nunca são baixados; o arquivo deve ser independente.

São aceitas regras do analisador principal (`driver`) e de `tool.extensions`, localizações físicas e nomes lógicos incluídos diretamente. As referências de extensões são resolvidas por índice ou GUID coerentes; o nome apenas confirma a seleção. Cada execução aceita até 100 extensões e 10.000 regras agregadas. Os catálogos permanecem separados. Sem GUID, a identidade da extensão usa o hash do componente completo: mudanças de versão ou metadados podem gerar uma nova observação para evitar unir componentes diferentes. As impressões digitais anteriores do driver são preservadas. Artefatos aninhados por `parentIndex` e localizações lógicas indexadas são rejeitados.

As observações entram com severidade informativa, sem CVSS inferido e pendentes de revisão. Confira significado e evidências antes de classificá-las. Marcar o conteúdo importado como revisado não confirma tecnicamente um achado.

No histórico, **Comparar PDFs** aceita um arquivo anterior e outro posterior. O resultado mostra páginas lado a lado, diferenças de pixels destacadas, mudanças de tamanho e páginas adicionadas ou removidas. O pareamento padrão usa a posição. O pareamento manual permite relacionar cada página anterior a uma posterior ou indicar que não existe equivalente; páginas posteriores não atribuídas são mostradas como adicionadas. O editor apresenta a cobertura e bloqueia referências repetidas. Cada página dos dois documentos deve aparecer exatamente uma vez, até 160 pares. Alterar arquivos invalida o mapa; alterar o mapa invalida o resultado anterior. Os hashes verificam se os PDFs comparados correspondem aos inspecionados.

O resultado identifica o modo, a ordem de cada par e os números originais das duas páginas. O alinhamento usa o canto superior esquerdo e escala comum. Igualdade visual não comprova igualdade de texto, links, anexos ou metadados. Inspeção de páginas e comparação usam processos isolados com os mesmos limites; a inspeção devolve apenas geometria e hashes.

O HTML baixado contém imagens dos documentos e seus hashes. Revise antes de compartilhar, pois os PDFs podem conter informações privadas. Os PDFs temporários são excluídos após o processamento. Limites: 16 MiB e 80 páginas por PDF, 64 milhões de pixels comparados no total, 32 MiB de saída e 45 segundos por operação. PDFs criptografados ou acima desses limites são rejeitados explicitamente.

**Registro opcional de revisão:** após comparar, informe autor (1–120 caracteres), decisão e nota de até 4000 caracteres. A nota é obrigatória ao registrar problemas. Salvar cria um anexo JSON privado com hashes dos originais e do HTML, correspondências, contagens e sua declaração de revisão. O projeto só muda quando você salva explicitamente; o anexo fica excluído da entrega por padrão e pendente de revisão como anexo. Os registros compartilham a cota existente de 100 anexos e 64 MiB por projeto.

O recibo temporário pertence à sessão, expira após 30 minutos e mantém até oito comparações por sessão, dentro de uma cota global de 64. Uma nova comparação substitui o recibo mais antigo dessa sessão quando o limite de oito é atingido. A expiração impede o uso do recibo; seus metadados em memória são removidos na próxima operação do armazenamento temporário. Fechar o resultado ou mudar arquivos ou correspondências também descarta o recibo temporário sem excluir os registros salvos.

Os registros salvos permanecem no projeto, nas revisões e nos backups, sem expiração nem exclusão automática. Baixe o JSON para conservar o registro e o HTML separadamente para conservar as imagens. PDFs, HTML, imagens e nomes dos arquivos originais não são copiados automaticamente; o texto informado em autor e nota é salvo. A autoria é autodeclarada, inclusive nos registros importados: o JSON não é uma assinatura e não comprova autenticidade, equivalência semântica nem validação do Microsoft Word. Gerencie também as cópias históricas e os backups ao remover um registro definitivamente.

A proteção de memória depende do sistema: Linux limita o espaço virtual a 768 MiB e Windows limita a memória comprometida do processo. No macOS, o crescimento virtual é limitado a 768 MiB acima dos mapas iniciais, e um supervisor encerra o processo se uma amostra de memória residente ou de pegada física exceder 768 MiB. O intervalo-alvo é 50 ms; pode haver excesso entre amostras, portanto não é um teto físico instantâneo.

## Revisar erros e documentos na 0.38.0

### Localizar a origem de um erro

Em **Importar resultados**, a localização aparece abaixo do erro ou da linha correspondente. CSV identifica o registro e, quando disponíveis, as linhas físicas inicial/final e a coluna mapeada; um registro pode ocupar várias linhas. Burp mostra a entrada e a localização XML; Nuclei, o registro, linha e campo; Nmap, o host ou a porta. SARIF identifica a execução e o resultado com índices a partir de zero, como no arquivo. Uma linha JSON só aparece quando vem do analisador de sintaxe.

Em **Exportações e downloads**, uma exportação com falha pode mostrar o identificador do achado e o campo afetado. Nas tabelas redigidas, os números de tabela, linha e célula começam em um, incluindo o cabeçalho como linha. O índice de evidência começa em zero. Nenhuma célula é inventada quando várias tabelas têm cabeçalhos ou dimensões ambíguos; uma falha global pode indicar apenas operação e formato. Corrija a origem, salve e gere novamente. Esses detalhes ficam na interface e no estado privado da tarefa, fora dos manifestos e entregas.

### Ver o DOCX com LibreOffice

1. Instale o **LibreOffice Writer** no computador se estiver indisponível. O report-gen o detecta localmente; não o baixa nem instala. Reabra o editor após a instalação.
2. Gere uma exportação com **Word** e aguarde a conclusão. Em **Exportações e downloads**, escolha **Visualização DOCX com LibreOffice** e depois **Gerar visualização nativa**.
3. Examine o PDF derivado, especialmente sumário, tabelas, URLs, legendas e quebras de página. Baixe o PDF e seu recibo se necessário; o recibo identifica mecanismo, versão, SHA-256 do DOCX, revisão e hash do PDF.

A conversão usa o DOCX já gerado, inclusive quando está dentro de uma entrega combinada; não reconstrói o documento a partir do projeto atual nem altera a origem. Uma vista anterior continua vinculada à revisão original. Essa operação opcional usa processo e perfil temporário separados: até 16 MiB de entrada, 32 MiB de PDF, 500 páginas e 180 segundos. Só há uma conversão simultânea. Ausência do mecanismo, falhas e limites são informados sem atribuir uma revisão concluída.

A vista e o recibo são privados e expiram após 15 minutos; o servidor limpa o material expirado durante operações ou ao encerrar. Fechar o diálogo cancela a operação ativa e solicita a remoção dos temporários. Os resultados não são salvos automaticamente no projeto. Downloads mantidos continuam privados e devem ser gerenciados por você. **Essa vista comprova apenas o resultado do LibreOffice para aqueles bytes, não equivalência nem aceitação do Microsoft Word.** A revisão nativa no Word permanece independente.

Com Windows e Microsoft Word de desktop instalado e licenciado, você pode vincular essa verificação ao mesmo DOCX: mantenha somente esse documento em `word-input` e execute `powershell -NoProfile -File .\scripts\verify-microsoft-word.ps1 -InputDirectory .\word-input -OutputDirectory .\word-output -ExpectedSourceReceipt .\docx-libreoffice-preview.json`. Use uma pasta de saída vazia. O recibo baixado verifica o hash e mantém a revisão de origem antes de abrir o Word; o script trabalha numa cópia, atualiza campos, exporta um PDF e registra versão, métricas e hashes. Examine esse PDF depois: possuir o comando ou recibo do LibreOffice não comprova que o Word foi executado.

### Inspecionar um anexo PDF

Em **Inventário de anexos → Verificar possíveis segredos**, revise as categorias e localizações detectadas. Os resultados PDF mostram páginas, objetos e caracteres examinados. A inspeção abrange texto extraível, metadados Info/XMP e cadeias de texto nas estruturas atuais, incluindo links, anotações, formulários e JavaScript como texto estático. Detecta a presença de ações, imagens e arquivos incorporados sem executar ações, visitar links ou abrir esses arquivos.

Os resultados nunca reproduzem valores sensíveis e ficam vinculados ao hash e à revisão inspecionados. A análise é temporária e fica fora das entregas e de seus manifestos. O estado “inspecionado” indica que aquele escopo limitado terminou, não que o arquivo seja seguro. O escopo sempre é parcial e exige revisão manual: não há OCR nem inspeção exaustiva de binários incorporados ou do histórico de revisões incrementais. PDFs criptografados, mesmo com senha vazia, não são inspecionados. Erros, limites e partes omitidas são informados explicitamente.

Os limites incluem 16 MiB por PDF, 200 páginas, 8000 objetos, 2.097.152 caracteres e 20 segundos, além de limites de profundidade e fluxos de texto. **A análise não censura, modifica nem autoriza o anexo.** Revise a cópia que será compartilhada e marque expressamente sua revisão e inclusão. Alertas orientam a revisão; anexos obrigatórios continuam bloqueando entregas incompletas.
