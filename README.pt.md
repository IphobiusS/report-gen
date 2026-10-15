<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen com Prometeo e Evaristo" width="300">
</p>

# report-gen 0.36.0

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

## Novidades da 0.36.0

**SARIF 2.1.0:** em **Importar resultados**, confira a origem e selecione o que deseja incorporar. Os resultados permanecem como observações informativas não verificadas; o nível do analisador não é convertido em CVSS.

**Comparar PDFs:** selecione dois arquivos no histórico para ver as páginas e as diferenças destacadas. Baixe a comparação como HTML independente. As páginas são pareadas por posição; mudanças visuais não comprovam mudanças de significado.

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
