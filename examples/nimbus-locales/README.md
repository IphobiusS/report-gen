# Nimbus: ES / EN / pt-BR

## Español

«Probar Nimbus» crea una copia independiente en el idioma actual de la interfaz:
español, inglés o portugués de Brasil. El idioma del informe queda guardado en esa
copia. Cambiar después la interfaz no traduce ni modifica informes existentes.

Nimbus es un escenario ficticio. Sus imágenes son diagramas sintéticos; no son
capturas de pruebas ejecutadas. Las ediciones inglesa y portuguesa son ediciones
editoriales localizadas, no traducciones literales. Conservan los 12 hallazgos,
60 pasos, 8 activos, 18 evidencias, 22 filas de cobertura y 6 retests, junto con
IDs, relaciones, estados, fechas, puntuaciones, vectores y referencias del
original español. Las fechas y menciones de report-gen 0.14.0 describen la
preparación original del ejemplo. Los identificadores técnicos se mantienen
literales, aunque contengan palabras españolas.

## English

“Try Nimbus” creates an independent copy in the current interface language:
Spanish, English or Brazilian Portuguese. The report language is saved in that
copy. Changing the interface later does not translate or modify existing reports.

Nimbus is fictional. Its images are synthetic diagrams, not screenshots of
executed tests. The English and Portuguese versions are localized editorial
editions, not literal translations. They retain all 12 findings, 60 steps,
8 assets, 18 evidence records, 22 coverage rows and 6 retests, with the Spanish
original's IDs, relationships, states, dates, scores, vectors and references.
Dates and references to report-gen 0.14.0 describe the original preparation.
Technical identifiers remain literal, including identifiers containing Spanish
words.

## Português (Brasil)

“Experimentar Nimbus” cria uma cópia independente no idioma atual da interface:
espanhol, inglês ou português do Brasil. O idioma do relatório fica salvo nessa
cópia. Mudar a interface depois não traduz nem modifica relatórios existentes.

Nimbus é um cenário fictício. Suas imagens são diagramas sintéticos, não capturas
de testes executados. As versões inglesa e portuguesa são edições editoriais
localizadas, não traduções literais. Elas preservam os 12 achados, 60 passos,
8 ativos, 18 registros de evidência, 22 linhas de cobertura e 6 retestes, com IDs,
relações, estados, datas, pontuações, vetores e referências do original espanhol.
As datas e referências ao report-gen 0.14.0 descrevem a preparação original.
Os identificadores técnicos permanecem literais, inclusive quando contêm
palavras em espanhol.

## Rebuild / Reconstrucción / Reconstrução

The locale JSON and bilingual diagram definitions are the editable sources.
The builder works offline and leaves the original Spanish ZIP unchanged. The
localized packages contain their current document, all 19 localized diagrams
and a SHA-256 manifest; they do not import the Spanish edition's historical
snapshots.

```sh
python scripts/build-nimbus-translations.py
python scripts/build-nimbus-translations.py --check
python -m pytest tests/test_nimbus_languages_0350.py
```

The tests cover language aliases and invalid input, independent copies,
structural invariants, literal URLs, archive integrity, reproducible packaging,
and complete English/Portuguese PDF, DOCX, Markdown and HTML exports. Native
office applications require separate renderer acceptance; a development build
of LibreOffice is a diagnostic environment, not stable-renderer acceptance.
