# Fontes — schema real confirmado

Registro do que foi verificado em cada fonte (data da verificação entre parênteses).

## Conexão TLS com servidores gov.br (2026-10-15)

`servicodados.ibge.gov.br` e `download.inep.gov.br` não enviam o certificado
intermediário, e a verificação TLS falha (`unable to get local issuer certificate`).
Em vez de desligar a verificação, os intermediários oficiais ficam em `certs/`
e `src/manifest.ca_bundle()` os junta ao bundle do `certifi`:

| Arquivo | Emissor | Origem (campo AIA do certificado) |
|---|---|---|
| `certs/sectigo_dv_r36.pem` | Sectigo Public Server Authentication Root R46 | http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt |
| `certs/rnp_icpedu_gr46_ov_2025.pem` | GlobalSign Root R46 | http://secure.globalsign.com/cacert/rnpicpedugr46ovtlsca2025.crt |

O servidor do INEP também derruba conexões de forma intermitente
(`Connection reset by peer`); `baixar()` tenta de novo com backoff.

## IBGE — localidades/municipios (2026-10-15)

- URL: `https://servicodados.ibge.gov.br/api/v1/localidades/municipios`
- Retorna **5.571** municípios, não 5.570. O extra é **Boa Esperança do Norte (MT, 5101837)**,
  que vem com `microrregiao: null`; a UF tem de ser lida de
  `regiao-imediata.regiao-intermediaria.UF`.
- O Censo Escolar 2024 ainda tem 5.570 municípios (sem o 5101837): esse município
  vai aparecer com matrícula nula nos joins até o Censo que o incluir.
- `cod_ibge_6` = 6 primeiros dígitos; único entre os 5.571 (checado).

## INEP — Censo Escolar, microdados (2026-10-15)

- URL: `https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{ano}.zip`
- Ano mais recente nesse padrão: **2024** (2025 e 2026 retornam 404). O zip foi
  republicado em 08/07/2026, com pasta `microdados_censo_escolar_2024_defeso/`.
- Arquivo: `dados/microdados_ed_basica_2024.csv` — `sep=';'`, `encoding='latin-1'`,
  426 colunas, 215.545 linhas (uma por escola). O zip traz o MD5 publicado em
  `dados/md5_microdados_ed_basica_2024.txt`, conferido na ingestão.
- Dicionário: `Anexos/ANEXO I - Dicionário de Dados/dicionário_dados_educação_básica.xlsx`,
  aba `microdados_unidade_coleta`.
- Colunas confirmadas: `NU_ANO_CENSO`, `SG_UF`, `CO_MUNICIPIO` (7 díg.), `CO_ENTIDADE` (8 díg., único),
  `NO_ENTIDADE`, `TP_DEPENDENCIA` (1 federal, 2 estadual, 3 municipal, 4 privada),
  `TP_SITUACAO_FUNCIONAMENTO` (1 em atividade, 2 paralisada, 3 extinta no ano, 4 extinta antes).
- Matrículas: `QT_MAT_BAS`, `QT_MAT_INF[_CRE|_PRE]`, `QT_MAT_FUND[_AI|_AF]`,
  `QT_MAT_MED[_PROP|_CT|_NM]`, `QT_MAT_PROF`, `QT_MAT_EJA[_FUND|_MED]`, `QT_MAT_ESP`;
  tempo integral: `QT_MAT_INF_INT`, `QT_MAT_INF_CRE_INT`, `QT_MAT_INF_PRE_INT`,
  `QT_MAT_FUND_INT`, `QT_MAT_FUND_AI_INT`, `QT_MAT_FUND_AF_INT`, `QT_MAT_MED_INT`.
- `QT_MAT_BAS` não inclui turmas exclusivas de atividade complementar nem de AEE.
- Tempo integral = ≥ 35 h semanais somando escolarização + atividade complementar + AEE
  + itinerário formativo (nota do dicionário).
- Escolas paralisadas/extintas têm todas as `QT_MAT_*` nulas. 1.779 escolas **em atividade**
  também vêm nulas (sem turma de escolarização); a ingestão trata como 0.

### Totais 2024 (escolas em atividade)

| Rede | Escolas | `QT_MAT_BAS` | `QT_MAT_MED` |
|---|---:|---:|---:|
| Estadual | 29.558 | 14.052.850 | 6.475.182 |
| Federal | 708 | 383.522 | 243.625 |
| Municipal | 107.581 | 23.134.718 | 41.041 |
| Privada | 43.218 | 9.517.832 | 1.030.548 |
| **Total** | **181.065** | **47.088.922** | **7.790.396** |

Rede pública (federal + estadual + municipal): 37.571.090 matrículas na educação básica.

## CGU — Pé-de-Meia (2026-10-15)

- A **API** do Portal da Transparência (`/v3/api-docs?group=api-de-dados`, 109 paths)
  **não tem endpoint do Pé-de-Meia** (só Bolsa Família, BPC, Seguro Defeso, Garantia-Safra,
  PETI, auxílios). A chave da API não é usada para esta fonte.
- O site `portaldatransparencia.gov.br/download-de-dados` tem verificação humana (AWS WAF).
  Os arquivos em si saem de outro host, sem verificação:
  `https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/pe-de-meia/{AAAAMM}_PeDeMeia.zip`
  (mês inexistente → HTTP 403).
- Meses publicados em 2026-10-15: 202403–202606, **sem 202407 e 202601**. 202501 é bem menor
  que os demais (12 MB vs ~90 MB).
- Zip com um CSV `{AAAAMM}_PeDeMeia.csv`: `sep=';'`, `encoding='latin-1'`, campos entre aspas,
  CRLF, ~3,7 mi linhas/mês. Valor com vírgula decimal (`200,00`).
- Colunas: `MÊS FOLHA`, `MÊS REFERÊNCIA`, `UF`, `CÓDIGO MUNICÍPIO SIAFI`, `NOME MUNICÍPIO`,
  `NIS BENEFICIÁRIO`, `CPF BENEFICIÁRIO`, `NOME BENEFICIÁRIO`, `NIS RESPONSÁVEL`,
  `CPF RESPONSÁVEL`, `NOME RESPONSÁVEL`, `CÓDIGO TIPO INCENTIVO`, `TIPO INCENTIVO`,
  `PERÍODO INCENTIVO`, `CÓDIGO ETAPA ENSINO`, `ETAPA ENSINO`, `DATA DO PAGAMENTO`, `VALOR PARCELA`.
- **Não tem escola** (só município) → Pé-de-Meia não sai por `co_entidade`.
- **Município vem em código SIAFI (4 dígitos), não IBGE.** Mapeamento: UF + nome normalizado
  contra `ref_municipios` (5.530/5.561 casam); os 31 com grafia antiga/diferente estão em
  `src/ingest/siafi_ibge_correcoes.csv` (nome IBGE atual → código resolvido pela ref IBGE).
- **Uma linha = uma parcela**, não um estudante. Em 202506: tipos `Frequência` (cód. 02) e
  `Matrícula` (cód. 01); `PERÍODO INCENTIVO` = mês da frequência (`Abril 2025`) ou `Ano letivo 2025`.
  Valores: R$ 200 e R$ 225 (R$ 225 quase todo em EJA).
- **82% das linhas são de menores**: nome mascarado (`*** ... ***`), NIS/CPF do estudante vazios,
  só NIS/CPF do responsável. Não dá para deduplicar estudantes por identificador (irmãos com
  o mesmo responsável colapsam). A ingestão nem lê essas colunas.

### Pé-de-Meia — como contar beneficiários (análise de 2026-10-15, folhas 202403–202606)

`PERÍODO INCENTIVO` traz o mês da frequência (`Março 2025`, `Julho/Agosto 2024`) ou
`Ano letivo AAAA` (Matrícula, Conclusão, Enem). Todas as parcelas de matrícula valem R$ 200.

| Ano letivo | Matrícula | Maior mês de frequência | Razão |
|---|---:|---:|---:|
| 2024 | 4.070.595 | Jun/2024: 3.454.537 | 1,18 |
| 2025 | 4.084.491 | Fev/2025: 3.634.148 | 1,12 |
| 2026 (parcial) | 3.972.198 | Fev/2026: 3.501.052 | 1,13 |

Por grupo de etapa (razão matrícula / maior mês, 2024–2026): Regular 1,12–1,13; Técnico 1,05–1,11; EJA 1,25–1,50.

- Matrícula ≥ maior mês de frequência em todas as etapas e anos: consistente com
  "uma parcela de matrícula por estudante/ano" e com perda de frequência ao longo do ano.
- EJA: razão 1,25–1,50. **Não** é matrícula semestral: em 2025, a matrícula EJA foi paga
  quase toda em mar–abr (≤ ~26 mil parcelas no 2º semestre, ~0,6% do total). Em 2024 a EJA
  entrou no 2º semestre (143 mil parcelas na folha 202409). A diferença vem da evasão,
  que derruba a frequência.
- A matrícula de um ano letivo continua sendo paga em folhas posteriores (2024 pago até 202505):
  sempre somar **todas** as folhas.
- Frequência 2025: 9 períodos (Fev–Out), batendo com o calendário oficial de 9 parcelas.

**vs Censo 2024** (EM público = `qt_mat_med` + `qt_mat_eja_med`, redes federal/estadual/municipal):
- Nacional: 4.070.595 / 7.614.082 = **0,535**. Mediana municipal 0,61.
- Razão > 1 em 12 municípios (máx. Natalândia/MG 2,39; demais ≤ 1,21, maioria BA/PB).
  O achado do TCU (56 municípios ≥ 1,5, concentrados no TO) não se reproduz com esta métrica.
- Os 8 municípios sem beneficiário são exatamente os 8 sem EM público no Censo (+ Boa Esperança
  do Norte, ausente do Censo 2024) → valida o mapeamento SIAFI→IBGE.

**Decisão proposta:** `qtd_beneficiarios_pe_de_meia` = parcelas de `Matrícula` do `Ano letivo`
de referência (todas as folhas). `vl_pago_pe_de_meia` = soma de todas as parcelas cujo período
é desse ano letivo (matrícula + frequência + conclusão + Enem).

**Adotado (2026-10-15):** critério acima, `ano_ref = 2025`, implementado em
`src/transform/pe_de_meia.py` → `data/interim/pe_de_meia_municipio_2025.parquet`.
Resultado (folhas até 202606): 4.084.491 beneficiários; R$ 10.527.544.100,00
(frequência 6,22 bi; conclusão 3,38 bi; matrícula 0,82 bi; Enem 0,11 bi);
R$ 2.624 por aluno (mediana municipal). Razão > 1 vs Censo 2024 em 44 municípios —
anos diferentes (beneficiários 2025 × matrículas 2024); revalidar quando sair o Censo 2025.
Obs.: "Conclusão" é depósito na poupança do estudante (saque só ao concluir o EM).

## FNDE — Fundeb 2026, estimativas por ente (2026-10-15)

- **Ato vigente: Portaria Interministerial MEC/MF nº 6, de 29/04/2026** (em vigor 01/05/2026),
  que substituiu os Anexos I a VII da Portaria nº 14/2025 (revisão quadrimestral: reestimativa
  de receitas + revisão de matrículas conveniadas; acerto retroativo pago em maio/2026).
  - VAAF-MIN: R$ 5.954,14 (era R$ 5.962,79 na Portaria 14) · VAAT-MIN: R$ 10.193,74 (era R$ 10.194,38).
- A Portaria em si só existe em PDF no FNDE (página de legislação; URL do arquivo termina em
  `/@@download/file` — sem isso vem a página HTML). Os **anexos saem em CSV/xlsx/pdf** em
  `.../financiamento/fundeb/2026-1/publicacoes-2026/2-publicacao/` (pasta criada em 11/05/2026;
  a 1ª publicação, da Portaria 14, fica um nível acima).
- CSV: `latin-1`, `;`, linhas de título antes do cabeçalho, cabeçalho com quebra de linha
  dentro de aspas, números pt-BR com espaços (`' 18.707.652,69 '`), zero como `' -   '`,
  percentual como `53,50%`. Linha TOTAL ora na 1ª, ora na 3ª coluna; o Anexo VI não tem TOTAL.
- Ente: governo estadual = código de 2 dígitos (UF); município = 7 dígitos. DF só como estado (53).
  Fora do Fundeb na ref IBGE: Brasília (5300108) e Fernando de Noronha (2605459, distrito estadual).
  Boa Esperança do Norte (5101837) **está** no Fundeb 2026.

| Anexo | Conteúdo | Uso |
|---|---|---|
| 1 | Receita total por ente: contribuição, compl. VAAF/VAAT/VAAR, total União, total | **base** |
| 2 | Cronograma mensal VAAF | conferência (ver abaixo) |
| 3 | VAAT antes/depois da complementação, % educação infantil | VAAT por ente |
| 4 | Indicador de educação infantil | — |
| 5 | Cronograma mensal VAAT | bate centavo a centavo com Anexo 1 |
| 6 | Redes beneficiadas VAAR + coeficiente | flag VAAR (coef. somam 1) |
| 7 | Cronograma mensal VAAR | — |

Totais (Anexo I, conferidos com a linha TOTAL): contribuição R$ 301,249 bi; VAAF 30,125;
VAAT 31,631; VAAR 7,531; União 69,287; **total R$ 370,537 bi**.
Recebem: VAAF 1.766 entes (1.757 municípios + AL, AM, BA, CE, MA, PA, PB, PE, PI);
VAAT 2.546; VAAR 3.034.

- **Anexo II ≠ Anexo I por ente** (até ±2,4%), com totais por UF idênticos: o cronograma reflete
  jan–abr pagos pelos coeficientes da Portaria 14 + acerto em maio. Usar o **Anexo I** como
  estimativa anual. O RJ recebia VAAF pela Portaria 14 (83 entes → os 1.849 citados antes) e
  saiu na revisão; no cronograma sobram resíduos de centavos.
- 23 municípios sem VAAT calculado no Anexo III (ex.: Cabo Frio, Cubatão, Ourinhos, Guaratuba).
  Hipótese: inabilitados ao VAAT (falta de dados SIOPE/SICONFI) — ⚠️ VERIFICAR contra a lista
  de inabilitados publicada pelo FNDE em `fundeb/2026-1/`.

### Fundeb — matrículas ponderadas por ente (pendência) e metodologia municipal (2026-10-15)

- **Não há arquivo público com matrículas ponderadas por ente para 2026.** A "Tabela de
  Transparência do Fundeb" (matrículas consideradas por rede) foi criada pela Portaria MEC
  nº 714, de 14/09/2026 (DOU 17/09/2026); a versão final sai até 31/01 do ano seguinte às
  estimativas → esperar até ~31/01/2027. Verificados e descartados:
  - texto da Portaria 6/2026 (não traz matrículas por ente);
  - `fundeb/consultas/anexo-nt-conjunta-no-6-2026.xlsx` = regras de filtragem (categorias), sem contagens;
  - `fundeb/2026-1/Fatoresdeponderaodetalhadosporsegmentodeensino.csv` = ~320 fatores por
    segmento (etapa × integral × campo/indígena/quilombola × especial × conveniada) — recalcular
    pelos microdados não reproduziria a filtragem oficial.
- **Provisório (decisão do usuário, 2026-10-15):** `vl_fundeb_por_aluno_* = receita da rede ÷
  qt_mat_bas da rede no Censo 2024` (sem ponderação, sem conveniadas, Censo um ano anterior ao
  usado pelo FNDE). Mediana municipal R$ 10.179; extremos R$ 4.533 (Caiçara/RS) a R$ 29.774
  (Quijingue/BA). Substituir quando sair a Tabela de Transparência.
- **Rede estadual por município = ESTIMATIVA (decisão do usuário):** receita do governo
  estadual × (matrículas da rede estadual no município ÷ matrículas da rede estadual na UF),
  Censo 2024. Colunas com sufixo `_est`; o rateio devolve exatamente o total de cada UF.
  DF: todo o ente 53 cai em Brasília (5300108). Fernando de Noronha recebe só rateio estadual.

### Fundeb — entes sem VAAT calculado (2026-10-15)

- 23 municípios + o governo de MG estão no Fundeb 2026 sem VAAT no Anexo III.
- Cruzamento com a **lista preliminar** de inabilitados ao VAAT 2026 (FNDE, situação em 19/05/2025,
  928 entes; `data/raw/fnde/fundeb_2026/lista_preliminar_inabilitados_vaat_2026_19mai2025.pdf`):
  **22 dos 23 municípios estão nela**; o 23º é Boa Esperança do Norte (município novo, sem dados de 2024).
  Dos 923 municípios da lista preliminar, 901 regularizaram até a data-base (31/08/2025) e têm VAAT.
  Pendências típicas: não transmitiu dados de 2024 ao SIOPE (art. 38 da Lei 14.113) e/ou não enviou
  a MSC de encerramento ao SICONFI (art. 163-A da CF).
- Imprensa noticiou MG inabilitado (O Fator), consistente com o governo de MG sem VAAT.
- **Lista definitiva não localizada** no site do FNDE → colunas `sem_vaat_calculado_*` descrevem
  "provável inabilitação". Não afirmar inabilitação em texto publicado sem a lista definitiva.

## FNDE — PNLD (2026-10-15)

- Página "Dados Estatísticos" do PNLD (`.../programas-do-livro/pnld/dados-estatisticos`) traz links
  no corpo do texto (não na lista de itens do Plone). Arquivos relevantes:
  - `dados-estatisticos-1/2025/DadosestatisticosporUF_2024_2025.xlsx` — aba "ANUÁRIO ABRELIVROS":
    **por UF**, PNLD 2025, por etapa (Ed. Infantil literário/didático, Anos Iniciais, Anos Finais,
    Ensino Médio): QTDE ESCOLA, QTDE ALUNO, QTDE EXEMPLARES, VALOR TOTAL. Aba "Planilha1":
    exemplares por objeto/ciclo (aquisição 2025 para uso em 2026 etc.).
  - `CONSOLIDADOPNLDDE2025PARA2026EDITORAS_*.xlsx`, `DISTRIBUIOPNLDANO2023...xlsx` — por editora/título
    (tiragem e valor), sem recorte geográfico.
- **Não há base pública por município nem por escola.** A distribuição por escola existe no FNDE
  (consulta individual por código INEP), sem download em lote localizado. dados.gov.br sem conjunto útil.

### PNLD 2025 — aba "ANUÁRIO ABRELIVROS" e rateio municipal (2026-10-15)

- Layout: título dos blocos mesclados na linha 7, campos na linha 8, UFs a partir da linha 9,
  linha "TOTAL BRASIL". Blocos: EI literário (B:F), EI didático (G:J), AI didático obj. 1 (K:N),
  AI práticas obj. 2 (O:R), AF (S:V), AF Braille (W:Z), EM (AA:AF; valor = impresso obj. 2 +
  digital obj. 4), TOTAL (AG:AJ). A soma das UFs bate com TOTAL BRASIL em todas as colunas.
- Exemplares descartados: EI literário tem duas colunas "QTDE EXEMPLARES" diferentes (razão
  ~1,29) sem distinção; AI práticas traz exemplares com casas decimais.
- **TOTAL / QTDE ALUNO = EI literário + AI obj. 1 + AF + EM, exatamente, nas 27 UFs** — o FNDE
  conta um objeto por etapa. `afetados_pnld` usa a mesma regra (33.653.999 alunos no Brasil).
- Totais 2025: R$ 1.693.150.523,55 (AI didático R$ 790 mi; AI práticas 244; AF 238; EM 224;
  EI literário 123; EI didático 53; AF Braille 21).
- Cobertura (alunos PNLD ÷ matrículas públicas Censo 2024), Brasil: EI lit. 1,045 (inclui
  conveniadas), AI 0,94, AF 1,00, EM 0,87. **MT: AF 0,16 e EM 0,06** (rede estadual não adere
  nessas etapas); PB: EM 0,68. Rateio dentro dessas UFs superestima municípios com muita
  matrícula estadual → `flag_pnld_cobertura_baixa_uf`.

## MEC/FNDE — Fomento à criação de matrículas em tempo integral (ETI), ciclo 2025 (2026-10-15)

- **Natureza do recurso:** com a EC 135/2024, o fomento ETI passou a sair da complementação da União
  ao Fundeb. Portaria MEC nº 586/2025: R$ 3.053.316.945,67 em 2025, deduzidos de VAAF
  (R$ 1.568.227.270,69), VAAT (R$ 917.940.505,62) e VAAR (R$ 567.149.169,36). **Não somar com o Fundeb 2025.**
- **Normas:** Portaria MEC 605/2025 (diretrizes + anexo por rede: matrículas, valor, política registrada);
  669/2025 (cronograma em 4 parcelas: 42,5% out, 21,25% nov, 21,25% dez/2025, 15% jan/2026);
  **823/2025 (DOU 16/12/2025) substituiu o Anexo II** — dez e jan retificados, jan = remanescente.
- Metodologia (605, art. 2º e 6º): matrículas criadas = tempo integral Censo 2024 − Censo 2022;
  valor por matrícula variável por ente (critérios da Portaria 1.495/2023), limitado às matrículas
  declaradas no Simec em 2025; dedução de 45,42765597604% para redes sem política registrada.
- **Fonte de leitura: HTML do DOU** (tabelas limpas), não o PDF do FNDE (layout de 3 colunas):
  `in.gov.br/web/dou/-/portaria-mec-n-605-de-29-de-agosto-de-2025-652034216` e
  `.../portaria-mec-n-823-de-12-de-dezembro-de-2025-675518888`. URLs achadas pela busca do DOU
  (`in.gov.br/consulta/-/buscar/dou`, JSON em `BuscaDouPortlet_params`). O in.gov.br derruba conexões
  com o User-Agent padrão do requests → `src/manifest.HEADERS`.
- 605: 4.910 redes (27 estaduais + 4.883 municipais), 776 com "-" (sem fomento); 404 não registraram
  política. 823 lista só as 4.134 redes com valor. Total por rede idêntico nas duas.
- Totais: R$ 3.053.316.945,67 (= Portaria 586); 667.619 matrículas (estaduais 261.219; municipais 406.400).
  R$/matrícula: mediana 6.158,70; mín. 846,61; máx. 12.858,51.
- O site do MEC (`gov.br/mec/.../escola-em-tempo-integral`) respondeu 429 e depois verificação humana:
  não foi usado.

## Tesouro Nacional — Fundeb 2025, repasses efetivos (2026-10-15)

Decisão do usuário: alinhar o Fundeb em 2025 (mesmo ano de Pé-de-Meia, PNLD e ETI).

- Fontes oficiais avaliadas para 2025:
  - Portaria Interministerial MEC/MF nº 13, de 29/12/2025 (3ª atualização quadrimestral do Fundeb 2025;
    VAAF-MIN R$ 5.669,79; VAAT-MIN R$ 8.020,77; DOU Extra-C 30/12/2025) — anexos têm VAAT/VAAR por ente,
    mas **não a receita total por ente**.
  - Portaria Interministerial MEC/MF nº 5, de 29/04/2026 (ajuste anual 2025) — VAAT e VAAR devidos por ente;
    VAAF só por UF; sem receita total por ente.
  - **Escolhida: API de Transferências Constitucionais do Tesouro** — repasses efetivos por ente, mês e
    componente. `https://apiapex.tesouro.gov.br/aria/v1/transferencias_constitucionais/custom`:
    `/estados`, `/municipios?p_uf=`, `/por_estado_municipio` (paginado; campos UF, ANO, MES, TRANSFERENCIA,
    codigo_siafi, CO_IBGE, MUNICIPIO, VALOR), `/por_estados` (governos estaduais; não paginado).
    Parâmetros `p_estado` (código do Tesouro, não IBGE), `p_ano`, `p_transferencia=10:14`
    (10 FUNDEB, 14 AJUSTE FUNDEB), `p_sn_detalhar=sim`, `page`, `pageSize` (5000 aceito).
    Caminhos confirmados no código do pacote R `tesouror` 0.3.1 (CRAN).
  - **Pegadinha:** o campo `next` vem preenchido até na última página → parar quando a página vier com
    menos linhas que `pageSize`. DF (estado 7) volta `[]` no endpoint municipal.
- Componentes: contribuição (FPM, FPE, ICMS, IPVA, ITCMD, ITR, IPI-EXP), COUN VAAF/VAAT/VAAR,
  `FUNDEB - FUNDEB - FTI` (fomento tempo integral) e `AJUSTE FUNDEB - *`.
- Totais 2025 (caixa): contribuição R$ 282,66 bi (mun 173,60; est 109,06); complementação R$ 54,36 bi
  (VAAF 25,17; VAAT 24,14; VAAR 5,06); FTI R$ 2,595 bi; ajustes R$ 2,77 bi.
- **FTI = ETI:** soma das parcelas out–dez/2025 da Portaria 823 (85% de R$ 3,053 bi) = R$ 2,595 bi, e
  bate centavo a centavo município a município (teste `test_fti_igual_eti_out_a_dez`).
- Base de caixa: jan/2025 inclui a 13ª parcela da complementação de 2024 → as flags `recebe_*` refletem
  quem recebeu no ano (ex.: 3.946 municípios com VAAR, mais que o ciclo 2025 isolado).
- Sem repasse municipal em 2025: Brasília (DF é ente estadual), Fernando de Noronha, Boa Esperança do Norte
  (entra no Fundeb em 2026).
