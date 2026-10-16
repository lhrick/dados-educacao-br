# Decisões, trade-offs e fontes — pipeline de educação por município

Registro do que foi usado para construir `data/processed/educacao_municipios_2025.csv`, por que cada
escolha foi feita, o que se perdeu em cada uma e o que ficou pendente. Trabalho feito em 2026-10-15.

Documentos complementares:
- [`docs/fontes.md`](fontes.md) — schema real de cada fonte, URLs, layouts e totais conferidos (nível técnico).
- [`docs/programas.md`](programas.md) — explicação dos programas para o time de redação (gerado pelo pipeline).
- `data/processed/*_dicionario.csv` — descrição, unidade, tipo e fonte de cada coluna.
- `data/processed/educacao_municipios_2025_validacao.md` — checklist de validação da última execução.

---

## 1. Objetivo e entrega

Uma linha por município com, para cada programa federal de educação: quanto chega à cidade (total, por
aluno e, onde possível, por escola), quantos alunos seriam afetados por corte e frases prontas para
redação/motion. Os números serão publicados, então **rastreabilidade da fonte é obrigatória**.

| Arquivo | Conteúdo |
|---|---|
| `data/processed/educacao_municipios_2025.csv` (+ `.parquet`) | 5.571 municípios × 50 colunas, UTF-8 com BOM, `;`, decimal `,` |
| `educacao_municipios_2025_dicionario.csv` | descrição, unidade, tipo e fonte de cada coluna (gerado dos dicionários parciais) |
| `programas_explicacao_2025.csv` | uma linha por programa: como chega, por aluno, por escola, risco de corte, limitações |
| `educacao_municipios_2025_validacao.md` | checklist do CLAUDE.md |
| `<programa>_municipio_<ano>.csv` | tabelas por programa, com todas as colunas intermediárias |

Como rodar: `.venv/bin/python -m src.pipeline` (≈1 min com os brutos presentes; `--de <etapa>` para retomar).

---

## 2. Princípios adotados

1. **Publicado × calculado × estimativa.** Toda coluna tem um `tipo` no dicionário:
   `chave`, `referencia`, `publicado` (valor oficial), `calculado` (regra determinística sobre valores
   oficiais) ou `estimativa` (rateio/aproximação nossa). Estimativas **nunca** geram texto pronto e têm
   sufixo `_est` quando possível. No consolidado: 9 das 50 colunas são estimativa.
2. **Nunca somar alunos entre programas.** Uma coluna `afetados_*` por programa; o único total de alunos
   distintos é `qtd_alunos_rede_publica` (Censo). Há teste que impede uma coluna de soma.
3. **Conferir antes de confiar.** Cada fonte tem checagem contra um total oficial ou contra outra fonte
   independente (seção 7). Onde não há referência, o relatório de validação diz "SEM REFERÊNCIA" em vez de "OK".
4. **Brutos imutáveis + manifest.** `data/raw/` nunca é editado; cada download entra em
   `data/raw/_manifest.csv` com URL, data, SHA-256 e ano. 74 arquivos registrados.
5. **Sem dados pessoais derivados.** O Pé-de-Meia traz CPF/NIS/nome; a leitura usa só colunas não pessoais
   (`usecols`), então esses campos nunca entram em memória nem em `interim/`/`processed/`. O checklist
   varre os arquivos atrás de colunas pessoais e de valores com padrão de CPF.
6. **Dicionário junto com o código.** Cada módulo que grava uma tabela declara seu `DICIONARIO`; a gravação
   falha se tabela e dicionário divergirem. O dicionário consolidado é montado dos parciais, nunca à mão.
7. **Não contornar bloqueios.** Captchas (CGU, MEC) não foram burlados: usamos download manual pelo usuário
   ou fontes oficiais alternativas com o mesmo conteúdo (DOU, FNDE, Tesouro).

---

## 3. Stack e estrutura

- Python 3.12, **pandas** + pyarrow (decisão do usuário: pandas em vez de polars), requests, openpyxl.
- `src/ingest/` (um módulo por fonte) → `data/interim/*.parquet`; `src/transform/` (tabelas municipais e
  consolidação); `src/metrics/` (textos e explicação dos programas); `src/validate/checklist.py`.
- `src/manifest.py`: download com retry, User-Agent de navegador, bundle de certificados e registro no manifest.
- `src/dicionario.py`: formato `Col(descricao, unidade, tipo, fonte)` e validação.
- 60 testes (`tests/`): invariantes, reconciliações com fontes, sincronia tabela × dicionário, formatação de texto.

**Pandas vs. PySpark** (pergunta do usuário): mantido pandas. O volume (~86 mi de parcelas do Pé-de-Meia
em 26 arquivos) cabe numa máquina se cada mês for agregado antes do próximo. Otimização adotada: leitor CSV
do pyarrow (multithread) + 4 meses em paralelo → de 2min51s para 44s, saída idêntica.

---

## 4. Fontes usadas (resumo)

| Tema | Fonte | Granularidade | Ano |
|---|---|---|---|
| Municípios | API de localidades do IBGE | município (5.571) | baixado em 2026-10-15 |
| Matrículas/escolas | INEP — microdados do Censo Escolar | escola | 2024 (mais recente publicado) |
| Pé-de-Meia | CGU — arquivos mensais `AAAAMM_PeDeMeia.zip` | parcela × município (código SIAFI) | folhas 03/2024–06/2026; ano letivo 2025 |
| PNLD | FNDE — "Dados estatísticos por UF 2024/2025" | UF × etapa | PNLD 2025 |
| ETI | DOU — Portaria MEC 605/2025 (matrículas) e 823/2025 (valores vigentes) | rede de ensino | ciclo 2025 |
| Fundeb (consolidado) | Tesouro — API de Transferências Constitucionais | ente × mês × componente | repasses 2025 |
| Fundeb (projeção) | FNDE — anexos da Portaria Interministerial nº 6/2026 | ente | estimativa 2026 |

Detalhes de URL, layout e armadilhas de cada uma em [`fontes.md`](fontes.md).

---

## 5. Decisões

Legenda: **U** = decisão do usuário; **T** = decisão técnica tomada durante a implementação (registrada aqui
para revisão).

### 5.1 Gerais

| # | Decisão | Alternativas | Motivo | Quem |
|---|---|---|---|---|
| G1 | pandas, não polars nem PySpark | polars (sugerido no CLAUDE.md); PySpark | preferência do time; volume cabe numa máquina | U |
| G2 | Cluster A (711 cidades) desconsiderado | filtro na saída | fora do escopo | U |
| G3 | **Ano de referência único: 2025** | manter anos mistos (Fundeb 2026) | comparabilidade entre programas no mesmo CSV | U |
| G4 | Censo 2024 como base de matrículas | — | é o último publicado (2025 retorna 404) | T |
| G5 | 5.571 municípios, não 5.570 | fixar 5.570 | API do IBGE já inclui Boa Esperança do Norte (MT) | T |
| G6 | Dicionário por tabela + consolidado gerado | um dicionário escrito no fim | decisões documentadas enquanto o contexto existe; não diverge | U |
| G7 | Rede estadual por município por **rateio** de matrículas | só rede municipal | mostrar o que chega às escolas estaduais da cidade, marcado como estimativa | U |
| G8 | Textos só de valores publicados/calculados | textos também de estimativas | números serão publicados | T |

### 5.2 Pé-de-Meia

| # | Decisão | Alternativas | Motivo | Quem |
|---|---|---|---|---|
| P1 | Download em lote da CGU, não a API | API do Portal da Transparência | a API (109 endpoints) **não tem** Pé-de-Meia | T |
| P2 | Arquivos baixados manualmente pelo usuário | contornar captcha | servidor passou a exigir captcha (AWS WAF) após as sondagens | U |
| P3 | **Beneficiários = parcelas de Matrícula do ano letivo** | deduplicar por CPF/NIS; frequência de um mês | 82% das linhas são de menores sem NIS/CPF próprio — deduplicar juntaria irmãos; cada estudante recebe 1 matrícula por ano | U (proposta T) |
| P4 | Valor = soma de todas as parcelas do ano letivo, de todas as folhas | só folhas do ano civil | há pagamento retroativo (matrícula 2024 paga até 05/2025) | U |
| P5 | Ano letivo 2025 | 2024; 2026 | último ano completo (9 parcelas de frequência fev–out + conclusão + Enem) | U |
| P6 | SIAFI → IBGE por UF + nome normalizado + 31 correções versionadas | tabela SIAFI×IBGE do Tesouro | Tesouro recusou conexões; correções guardam o **nome** IBGE, o código vem da ref oficial | T |
| P7 | Estornos contados à parte (`qtd_estornos`), valores líquidos | ignorar | 48.730 estornos de Conclusão (R$ −1.000); pipeline falha se surgir estorno de Matrícula | T |

### 5.3 PNLD

| # | Decisão | Alternativas | Motivo | Quem |
|---|---|---|---|---|
| L1 | **Rateio dos totais da UF** pelas matrículas públicas da etapa | LAI ao FNDE; os dois | não há base pública por município/escola | U (opção "a") |
| L2 | Usar alunos e valor; descartar exemplares | usar exemplares | colunas de exemplares ambíguas (duplicada em EI literário; decimais em AI práticas) | T |
| L3 | Alunos afetados = 1 objeto por etapa (EI literário + AI didático + AF + EM) | somar todos os objetos | igual, UF a UF, ao TOTAL de alunos publicado pelo FNDE | T |
| L4 | Sinalizar UFs com cobertura < 0,7 | excluir UFs | MT (AF 0,16; EM 0,06) e PB (EM 0,68): rede estadual não adere | T |

### 5.4 Fundeb

| # | Decisão | Alternativas | Motivo | Quem |
|---|---|---|---|---|
| F1 | Estimativa 2026: Portaria nº 6/2026, não nº 14/2025 | Portaria 14/2025 (citada no CLAUDE.md) | a nº 6 substituiu os anexos (revisão quadrimestral) | T |
| F2 | Valor por aluno provisório = receita ÷ matrículas do Censo, sem ponderação | VAAT oficial; arquivo de matrículas ponderadas | VAAT inclui outras receitas e falta em 23 entes; a Tabela de Transparência (ponderadas) só sai até 31/01/2027 | U (opção "a" até achar "c") |
| F3 | **Consolidado usa repasses efetivos 2025 (Tesouro)** | Portaria 13/2025 (3ª revisão das estimativas); Portaria 5/2026 (ajuste anual) | nenhuma das portarias de 2025 traz receita total por ente; o ano já fechou | T (após U escolher 2025) |
| F4 | Base de caixa (ano do repasse) | competência | é o que a fonte publica | T |
| F5 | FTI e ajustes de anos anteriores fora da receita | somar tudo | FTI = fomento ETI (já em outra coluna); ajustes não são do ano | T |
| F6 | Sem cenário de "corte total"; risco = complementação da União e VAAR/VAAT | modelar corte total | Fundeb é constitucional e permanente (EC 108/2020) | CLAUDE.md |
| F7 | Inabilitação ao VAAT descrita como "provável" | afirmar inabilitação | só existe a lista **preliminar** (22 de 23 casos batem); definitiva não localizada | T |
| F8 | Tabela 2026 mantida como projeção, fora do consolidado | apagar | útil para comparação; ano diferente | T |

### 5.5 Escola em Tempo Integral

| # | Decisão | Alternativas | Motivo | Quem |
|---|---|---|---|---|
| E1 | Fonte = HTML do DOU (Portarias 605 e 823/2025) | PDF do FNDE; site do MEC | tabelas limpas; MEC respondeu 429 e depois captcha | T |
| E2 | Valores vigentes da Portaria 823/2025 | 669/2025 | a 823 retificou o cronograma (dez/jan) | T |
| E3 | ETI **não** é somado ao Fundeb do mesmo ano | somar | desde a EC 135/2024 sai da complementação da União (Portaria 586/2025) | T |
| E4 | Texto do ETI: "matrículas criadas", "da União" | "para criar", "governo federal" | o fomento remunera matrículas já criadas (Censo 2024 − 2022) | T |

### 5.6 Saída para redação

| # | Decisão | Alternativas | Motivo | Quem |
|---|---|---|---|---|
| R1 | CSV em UTF-8 **com BOM**, `;`, decimal `,` | UTF-8 sem BOM | Excel abre acentos corretamente | T |
| R2 | Média por escola para Fundeb e ETI (rede municipal) | sem valor por escola | nenhuma fonte publica por escola; média com aviso explícito | U |
| R3 | ETI: média ÷ escolas **com tempo integral** | ÷ todas as escolas | fomento é só para matrículas integrais | T |
| R4 | Textos de risco (`txt_afetados_*`) para Pé-de-Meia, Fundeb, ETI | incluir PNLD | PNLD é estimativa | U (escopo) / T (PNLD fora) |
| R5 | Valores em texto com escala (MIL/MILHÕES/BILHÕES, 1 casa) | valor exato | padrão do CLAUDE.md ("R$ {x} MILHÕES") | T |

### 5.7 Visualização (2026-10-16)

| # | Decisão | Alternativas | Motivo | Quem |
|---|---|---|---|---|
| V1 | Só páginas HTML interativas (`docs/explorador/`) | gráficos estáticos matplotlib (PNG/SVG); Plotly; Folium; Streamlit; Datawrapper | exploração por município (busca + ficha); estáticos foram feitos e descartados | U |
| V2 | Template genérico + config JSON por programa | uma página escrita para cada programa | reaproveitar em outro projeto (ex.: Saúde, mesma chave `cod_ibge_7`); metadados vêm do dicionário | U |
| V3 | HTML único, sem build e sem biblioteca externa; mapa em SVG projetado no Python | D3/Leaflet via CDN | abre offline e por cópia de arquivo; nada a fixar de versão | T |
| V4 | Malha IBGE v3 (qualidade mínima), SIRGAS 2000 Polyconic, `shapely.coverage_simplify` (tolerância 4000) | simplificação polígono a polígono | a simplificação isolada abria frestas entre vizinhos; divisas estaduais = união dos municípios simplificados | T |
| V5 | Páginas para Pé-de-Meia, Fundeb e ETI; **PNLD fora** | página municipal do PNLD | PNLD municipal é 100% rateio (correlação 0,998 com alunos); passaria precisão que não existe | U |
| V6 | Uso interno do time; sem seção de gráficos de conferência | dispersão Pé-de-Meia × Censo e histograma do Fundeb por aluno | limitações ficam em "Observações" no rodapé e em avisos na ficha | U |
| V7 | Colunas `estimativa` com selo em resumo, mapa, ficha e gráficos; `*` na tabela | esconder estimativas | rede estadual e Fundeb por aluno são úteis, mas não podem parecer oficiais | T |
| V8 | ETI: vazio = "fora do anexo da Portaria 605"; zero = "no anexo, sem matrícula fomentada" | "sem dado" para ambos | são situações diferentes da rede | T |
| V9 | Comparação UF/Brasil por razão das somas (ex.: % União = Σ União ÷ Σ receita); média por escola do ETI por mediana | média simples dos municípios | razão das somas é o valor do estado; na ETI a soma de escolas inclui municípios sem fomento e subestimava a média | T |
| V10 | HTMLs gerados versionados no repositório (~6 MB) | só o código | o time abre sem rodar o pipeline | U |

Números citados nas notas das configs (ex.: "44 municípios", faixas do Fundeb por aluno) são de 2025 e
precisam ser revistos quando a tabela for regerada.

---

## 6. Trade-offs e limitações (o que ler antes de publicar)

**Pé-de-Meia**
- Beneficiários é uma *proxy* (parcelas de Matrícula). Validação: nenhum município tem frequência em 2025
  sem matrícula em 2025; o total (4.084.491) não foi conferido contra um número oficial do MEC.
- 44 municípios têm mais beneficiários (2025) que matrículas de EM público (Censo 2024) — maior razão:
  Natalândia/MG 2,58. Anos diferentes; revalidar com o Censo 2025. O achado do TCU (56 municípios, TO) não
  se reproduz com esta métrica.
- "Conclusão" (R$ 3,38 bi) é depósito em poupança, não renda sacável no ano.
- Sem recorte por escola.

**PNLD**
- Todo valor municipal é estimativa (rateio da UF). Em MT e PB o rateio superestima municípios com muita
  matrícula estadual. Não publicar valores municipais de MT. Dado real só via LAI.

**Fundeb**
- Base de caixa: jan/2025 inclui a 13ª parcela da complementação de 2024; a de 2025 entra em jan/2026.
  Flags `recebe_*` refletem quem recebeu no ano (ex.: 3.946 municípios com VAAR).
- Valor por aluno usa matrículas sem ponderação e sem conveniadas — difere do critério do FNDE; extremos
  podem ser distorcidos.
- Rede estadual por município é rateio (estimativa).
- Média por escola é média da rede, não o valor que a escola recebe.

**ETI**
- Rede estadual por município é rateio. 30 municípios receberam fomento sem escola municipal integral no
  Censo 2024 (média por escola vazia).
- Valor por matrícula é variável por rede (R$ 847 a R$ 12.859); redes sem política registrada tiveram
  desconto de 45,43%.

**Gerais**
- Boa Esperança do Norte (MT) não está no Censo 2024 nem recebeu Fundeb municipal em 2025.
- Brasília aparece sem "rede municipal": o DF é ente estadual no Fundeb e no ETI.

---

## 7. Validações cruzadas

| Checagem | Resultado |
|---|---|
| Censo 2024: matrículas da educação básica | 47.088.922 (escolas em atividade); MD5 do INEP conferido no zip |
| Pé-de-Meia: municípios sem beneficiário × sem EM público | os 8 sem EM público são exatamente os sem beneficiário (+ Vespasiano Corrêa/RS: zero real, nenhuma parcela em 2025) — valida SIAFI→IBGE |
| PNLD: soma das UFs × TOTAL BRASIL | igual em todas as colunas; TOTAL de alunos = 1 objeto por etapa nas 27 UFs |
| Fundeb 2026: anexos × linhas TOTAL | Anexo I bate; cronograma VAAT bate centavo a centavo; coeficientes VAAR somam 1 |
| ETI: soma das redes × Portaria 586/2025 | R$ 3.053.316.945,67 = R$ 3.053.316.945,67 |
| **Fundeb (Tesouro, FTI) × ETI (DOU, parcelas out–dez)** | igual centavo a centavo em todos os 4.107 municípios — duas fontes independentes |
| Rateios (Fundeb est., PNLD, ETI est.) | somam exatamente o total de cada UF |
| Dados pessoais em interim/processed | nenhuma coluna ou valor com padrão de CPF |
| Manifest | 74 arquivos, hashes conferem |

---

## 8. Problemas técnicos encontrados (e como foram resolvidos)

| Problema | Solução |
|---|---|
| `servicodados.ibge.gov.br` e `download.inep.gov.br` não enviam certificado intermediário | intermediários oficiais em `certs/` somados ao bundle do certifi — verificação TLS mantida |
| Conexões derrubadas (INEP, FNDE, DOU) | retry com backoff, inclusive para download interrompido no meio |
| `in.gov.br` recusa o User-Agent padrão do Python | User-Agent de navegador identificando o pipeline |
| CGU e MEC com captcha | não contornado: download manual (CGU) e fontes alternativas oficiais (DOU/FNDE) |
| `pd.read_csv(engine="pyarrow", dtype=str)` perdia zero à esquerda do SIAFI (`0377`→`377`) | leitor do pyarrow com tipos string declarados + checagem de 4 dígitos |
| Conferência de totais do Fundeb "passava" sem conferir (rótulo TOTAL em outra coluna; Anexo VI sem TOTAL) | conferência agora falha se não achar o total; Anexo VI validado pela soma dos coeficientes |
| API do Tesouro devolve `next` até na última página (loop infinito) | parar quando a página vem incompleta + trava de 500 páginas |
| Formatação "R$ 999.999" virava "R$ 1000 MIL" | sobe de escala no arredondamento; teste |
| Estornos (parcelas negativas) contados como parcelas | contagem separada (`qtd_estornos`) |

Correções de afirmações feitas durante o trabalho (registradas para transparência):
- "TOTAL de alunos do PNLD é dupla contagem" — **errado**; é exatamente a regra de 1 objeto por etapa.
- Primeira comparação "idêntico" após a otimização do Pé-de-Meia comparou o arquivo antigo com ele mesmo
  (a nova versão tinha falhado); detectado pela data do arquivo e corrigido.

---

## 9. Números de referência (2025)

| Programa | Valor | Alunos afetados por corte | Por aluno (mediana) | Por escola (mediana da média) |
|---|---:|---:|---:|---:|
| Pé-de-Meia | R$ 10,53 bi | 4.084.491 | R$ 2.624 | — |
| PNLD (estimativa municipal) | R$ 1,69 bi | 33.653.979 | R$ 49,64 | — |
| Fundeb (receita; União R$ 54,4 bi) | R$ 337,0 bi | 32.292.911 | R$ 9.282 (rede municipal) | R$ 1,58 mi |
| Tempo Integral (fomento) | R$ 3,05 bi | 667.619 | R$ 6.159 por matrícula | R$ 42 mil |
| Alunos distintos nas redes públicas (Censo 2024) | | **37.571.090** | | |

Os números exatos e atualizados ficam em `docs/programas.md` e no relatório de validação, gerados pelo pipeline.

---

## 10. Pendências

- [ ] **PNLD por escola/município** — pedido via LAI ao FNDE (hoje: rateio da UF).
- [ ] **Matrículas ponderadas por ente** — Tabela de Transparência do Fundeb (Portaria MEC 714/2026), prevista
  até 31/01/2027; substituiria o valor por aluno provisório.
- [ ] **Lista definitiva de inabilitados ao VAAT** — hoje só a preliminar (19/05/2025).
- [ ] **Censo Escolar 2025** — quando publicado, revalidar razão Pé-de-Meia/matrículas e rateios.
- [ ] **Total oficial do Pé-de-Meia 2025** para conferência nacional.
- [ ] **ETI 2026** — confirmar se haverá fomento separado (Resolução CIF 23/2026) ou só obrigação no Fundeb.
- [ ] 30 municípios com fomento ETI sem escola municipal integral no Censo 2024 — conferir caso a caso.
- [ ] Frente de Saúde (pausada; ver CLAUDE.md).
