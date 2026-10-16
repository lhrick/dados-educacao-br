# Programas federais de educação por município — 2025

> Gerado por `src/metrics/programas.py` a partir das tabelas do pipeline. Não editar à mão: rode `.venv/bin/python -m src.metrics.programas`.

Arquivo de dados: `data/processed/educacao_municipios_2025.csv` (uma linha por município) e `educacao_municipios_2025_dicionario.csv` (descrição de cada coluna, com fonte e tipo).

## Resumo — Brasil

| Programa | Como chega | Valor no ano | Alunos afetados por corte | Por aluno | Por escola |
|---|---|---:|---:|---|---|
| Pé-de-Meia | conta do estudante | R$ 10,53 bi | 4.084.491 | R$ 2.624,00 (mediana municipal) | não disponível |
| PNLD — Programa Nacional do Livro e do Material Didático | livros entregues na escola | R$ 1,69 bi | 33.653.979 | R$ 49,64 (mediana municipal, estimativa) | não disponível |
| Fundeb | conta do Fundeb da rede | R$ 337,02 bi | 32.292.911 | R$ 9.281,94 (mediana, rede municipal) | R$ 1.581.532,49 (mediana municipal da média por escola municipal) |
| Escola em Tempo Integral (fomento) | repasse à rede | R$ 3,05 bi | 667.619 | R$ 6.158,69 por matrícula (mediana das redes) | R$ 41.974,09 (mediana municipal da média por escola com tempo integral) |

**Nunca somar os alunos afetados entre programas** — o mesmo estudante pode estar em vários. Total de alunos distintos nas redes públicas (Censo 2024): **37.571.090**.

**Por escola:** nenhuma das fontes publica valores por escola (Pé-de-Meia só tem município; PNLD só UF; Fundeb e ETI são pagos à rede de ensino). Para Fundeb e ETI há uma **média por escola** (valor da rede municipal ÷ escolas da rede) — é uma média, não o que cada escola recebe.

**Risco de corte:** cada programa tem sua coluna `afetados_*` (número de alunos/matrículas por cidade). Frases prontas: `txt_afetados_pe_de_meia`, `txt_afetados_fundeb`, `txt_afetados_eti` (só valores publicados/calculados — não há frase de PNLD, que é estimativa).

**Tipos de número** (coluna `tipo` do dicionário): `publicado` = valor oficial; `calculado` = regra determinística sobre valores oficiais; `estimativa` = rateio/aproximação nossa — não apresentar como número oficial.

## Pé-de-Meia

- **O que é:** Incentivo financeiro-educacional, na modalidade poupança, para estudantes do ensino médio público de famílias inscritas no CadÚnico.
- **Como chega ao município:** Direto na conta do estudante (não passa pela prefeitura nem pela secretaria estadual). Parcelas: Matrícula R$ 200 por ano; Frequência R$ 200 por mês (R$ 225 na maior parte das parcelas de EJA); Conclusão R$ 1.000 por ano concluído, depositada em poupança; Enem R$ 200.
- **Valor por aluno:** vl_por_aluno_pe_de_meia = valor pago no ano letivo ÷ beneficiários. R$ 2.624,00 (mediana municipal).
- **Valor por escola:** Não disponível: a fonte (CGU) identifica só o município do estudante, não a escola.
- **Alunos afetados por corte:** afetados_pe_de_meia = beneficiários do ano letivo (uma parcela de Matrícula por estudante). Brasil: 4.084.491 estudantes em 5.561 municípios.
- **Risco de corte/interrupção:** Programa federal criado por lei; o pagamento depende de dotação orçamentária anual. Interrupção afeta diretamente a renda dos estudantes beneficiários.
- **Natureza dos números:** Calculado a partir de pagamentos publicados (valores líquidos de estornos).
- **Limitações:** Beneficiários = parcelas de Matrícula (a fonte não permite identificar estudantes menores de idade). 'Conclusão' é poupança, não dinheiro sacável no ano. 8.573 estornos de Conclusão no ano, já descontados. Razão beneficiários/matrículas > 1 em alguns municípios: conferir antes de publicar.
- **Base legal:** Lei nº 14.818/2024; Decreto nº 11.901/2024.
- **Fonte dos dados:** CGU — Portal da Transparência, arquivos mensais do Pé-de-Meia.
- **Colunas no CSV:** qtd_beneficiarios_pe_de_meia, afetados_pe_de_meia, vl_pago_pe_de_meia, vl_por_aluno_pe_de_meia, vl_conclusao_pe_de_meia, razao_pe_de_meia_censo, flag_pe_de_meia_acima_censo, txt_pe_de_meia, txt_afetados_pe_de_meia
- **Valor total no Brasil (2025):** R$ 10,53 bi

## PNLD — Programa Nacional do Livro e do Material Didático

- **O que é:** Compra centralizada de livros didáticos e literários para alunos e professores das escolas públicas da educação básica.
- **Como chega ao município:** Em livros, não em dinheiro: o FNDE compra das editoras e entrega direto nas escolas. O valor é o custo de aquisição.
- **Valor por aluno:** vl_pnld_por_aluno_est = valor estimado ÷ alunos atendidos. R$ 49,64 (mediana municipal, estimativa).
- **Valor por escola:** Não disponível em base pública: o FNDE publica só por UF; a consulta por escola é individual (pedido via LAI pendente).
- **Alunos afetados por corte:** afetados_pnld = alunos atendidos (um objeto por etapa, mesma regra do total publicado pelo FNDE). Brasil: 33.653.979 alunos.
- **Risco de corte/interrupção:** Interrupção da compra deixa as escolas sem material didático no ciclo seguinte; o efeito aparece no início do ano letivo.
- **Natureza dos números:** ESTIMATIVA no nível municipal: total da UF rateado pelas matrículas públicas da etapa no Censo.
- **Limitações:** Rateio supõe adesão de todas as redes públicas da UF; em MT (anos finais e ensino médio) e PB (ensino médio) a cobertura é baixa — flag_pnld_cobertura_baixa_uf. Não gerar texto de PNLD por município.
- **Base legal:** Decreto nº 9.099/2017.
- **Fonte dos dados:** FNDE — PNLD, Dados estatísticos por UF (PNLD 2025).
- **Colunas no CSV:** afetados_pnld, vl_pnld_total_est, vl_pnld_por_aluno_est, flag_pnld_cobertura_baixa_uf
- **Valor total no Brasil (2025):** R$ 1,69 bi

## Fundeb

- **O que é:** Fundo constitucional e permanente que redistribui impostos de estados e municípios dentro de cada UF, por matrícula, com complementação da União (VAAF, VAAT e VAAR).
- **Como chega ao município:** Repasse automático à conta do Fundeb de cada rede (prefeitura e governo estadual), em parcelas ao longo do ano. A contribuição vem de FPM, FPE, ICMS, IPVA, ITCMD, ITR e IPI-Exportação; a União complementa as redes abaixo dos valores mínimos (VAAF, VAAT) e por resultados (VAAR).
- **Valor por aluno:** vl_fundeb_por_aluno_rede_municipal = receita do ano ÷ matrículas da rede no Censo (sem ponderação). R$ 9.281,94 (mediana, rede municipal).
- **Valor por escola:** Não há valor por escola publicado (o dinheiro vai para a rede). Calculamos a MÉDIA: vl_fundeb_media_por_escola_rede_municipal = Fundeb da rede municipal ÷ escolas municipais com matrícula. R$ 1.581.532,49 (mediana municipal da média por escola municipal).
- **Alunos afetados por corte:** afetados_fundeb_complementacao = matrículas das redes que recebem complementação da União. Brasil: 32.292.911 matrículas.
- **Risco de corte/interrupção:** Não há 'corte total' (EC 108/2020). O risco é a complementação da União (R$ 54,36 bi em 2025) — perda_fundeb_sem_uniao — e a perda de VAAT/VAAR por inabilitação (dados não enviados ao SIOPE/SICONFI) ou condicionalidades. 3.946 redes municipais receberam VAAR em 2025 (risco_perda_vaar).
- **Natureza dos números:** Rede municipal: repasses efetivos publicados. Rede estadual por município: ESTIMATIVA (rateio pelas matrículas estaduais).
- **Limitações:** Base de caixa (janeiro inclui a última parcela do ano anterior). Valor por aluno usa matrículas sem ponderação. O fomento ETI (FTI) é excluído do total para não ser somado duas vezes.
- **Base legal:** Constituição, art. 212-A (EC 108/2020); Lei nº 14.113/2020.
- **Fonte dos dados:** Tesouro Nacional — API de Transferências Constitucionais (repasses 2025).
- **Colunas no CSV:** vl_fundeb_rede_municipal, vl_fundeb_uniao_rede_municipal, pct_uniao_rede_municipal, vl_fundeb_por_aluno_rede_municipal, vl_fundeb_rede_estadual_est, vl_fundeb_uniao_rede_estadual_est, afetados_fundeb_complementacao, perda_fundeb_sem_uniao, risco_perda_vaar, recebe_vaaf/vaat/vaar_rede_municipal, qtd_escolas_rede_municipal, vl_fundeb_media_por_escola_rede_municipal, txt_fundeb_uniao, txt_afetados_fundeb
- **Valor total no Brasil (2025):** R$ 337,02 bi

## Escola em Tempo Integral (fomento)

- **O que é:** Fomento federal por matrícula em tempo integral criada pelas redes (diferença entre os Censos de 2022 e 2024).
- **Como chega ao município:** Repasse do FNDE à rede de ensino (prefeitura ou governo estadual) em 4 parcelas (out/2025 a jan/2026). Desde a EC 135/2024 o recurso sai da complementação da União ao Fundeb.
- **Valor por aluno:** Valor por matrícula variável por rede (critérios da Portaria MEC 1.495/2023). R$ 6.158,69 por matrícula (mediana das redes).
- **Valor por escola:** Não há valor por escola publicado (o fomento vai para a rede). Calculamos a MÉDIA: vl_eti_media_por_escola_rede_municipal = fomento da rede municipal ÷ escolas municipais com matrícula em tempo integral (vazio onde o Censo 2024 não tem escola integral, 30 municípios). R$ 41.974,09 (mediana municipal da média por escola com tempo integral).
- **Alunos afetados por corte:** afetados_eti = matrículas em tempo integral fomentadas (rede municipal publicada + rede estadual rateada). Brasil: 667.619 matrículas.
- **Risco de corte/interrupção:** Sem o fomento, as redes custeiam com recursos próprios as matrículas integrais já criadas. A partir de 2026 a criação de matrículas integrais passa a ser obrigação de aplicação do próprio Fundeb (Resolução CIF nº 23/2026).
- **Natureza dos números:** Rede municipal: publicado (anexos das portarias). Rede estadual por município: ESTIMATIVA.
- **Limitações:** Não somar com o Fundeb do mesmo ano: é parte da complementação da União (no Tesouro aparece como FTI). Redes sem política de tempo integral registrada tiveram desconto de 45%.
- **Base legal:** Lei nº 14.640/2023; EC 135/2024; Portarias MEC nº 586, 605 e 823/2025.
- **Fonte dos dados:** DOU — Portaria MEC 605/2025 (matrículas) e 823/2025 (valores vigentes).
- **Colunas no CSV:** afetados_eti, qtd_matriculas_eti_rede_municipal, vl_fomento_eti_rede_municipal, vl_fomento_eti_rede_estadual_est, registrou_politica_eti_rede_municipal, qtd_escolas_eti_rede_municipal, vl_eti_media_por_escola_rede_municipal, txt_eti, txt_afetados_eti
- **Valor total no Brasil (2025):** R$ 3,05 bi
