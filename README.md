# dados-educacao-br

Pipeline que reúne dados oficiais do governo federal e monta **uma linha por município brasileiro (5.571)** com quanto cada programa federal de educação entrega à cidade, quantos alunos seriam afetados por corte e frases prontas para a redação.

Ano de referência atual: **2025**. Matrículas e escolas vêm do Censo Escolar 2024, o mais recente publicado.

| Programa | Como chega ao município | Valor no ano (Brasil) | Alunos afetados por corte |
|---|---|---:|---:|
| Pé-de-Meia | direto na conta do estudante | R$ 10,53 bi | 4.084.491 |
| PNLD (livro didático) | livros entregues na escola | R$ 1,69 bi | 33.653.979 |
| Fundeb | conta do Fundeb da rede de ensino | R$ 337,02 bi | 32.292.911 |
| Escola em Tempo Integral (fomento) | repasse à rede de ensino | R$ 3,05 bi | 667.619 |

> **Nunca some os alunos afetados de programas diferentes.** O mesmo estudante pode estar em vários deles. O total de alunos distintos nas redes públicas é **37.571.090** (Censo 2024).

## Explorar os dados

| Página | O que mostra | Baixar |
|---|---|---|
| Pé-de-Meia | beneficiários, valor pago e alcance sobre as matrículas do ensino médio | [pe_de_meia.html](docs/explorador/pe_de_meia.html) |
| Fundeb | receita da rede municipal e parte que vem da União | [fundeb.html](docs/explorador/fundeb.html) |
| Escola em Tempo Integral | fomento federal e matrículas em tempo integral fomentadas | [eti.html](docs/explorador/eti.html) |

Para abrir uma página:
1. Clique no link da página.
2. No GitHub, clique em **Download raw file** (ícone de download, ao lado de "Raw").
3. Abra o arquivo baixado no navegador.

A página funciona offline e permite buscar o município, ver o mapa e a ficha com frases prontas e baixar a tabela em CSV. É para uso interno do time: leia os avisos da ficha e as observações no rodapé antes de publicar um número. Detalhes em [Explorador interativo](#4-explorador-interativo).

---

## Arquivos de saída

Os arquivos ficam em `data/processed/`. Os CSVs usam UTF-8, separador `;` e decimal `,`, e abrem direto no Excel ou no Google Sheets em pt-BR.

| Arquivo | Conteúdo | Versionado |
|---|---|---|
| `educacao_municipios_2025.csv` | tabela final, uma linha por município (chave `cod_ibge_7`) | sim |
| `educacao_municipios_2025_dicionario.csv` | descrição, unidade, tipo e fonte de cada coluna | sim |
| `programas_explicacao_2025.csv` | o que é cada programa, como chega, limitações, base legal e fonte | sim |
| `programas_explicacao_2025_dicionario.csv` | dicionário do arquivo acima | sim |
| `educacao_municipios_2025.parquet` | mesma tabela final, em parquet | não (gerado) |
| `educacao_municipios_2025_validacao.md` | resultado das checagens automáticas | não (gerado) |
| `<programa>_municipio_<ano>.csv` | tabelas parciais por programa, cada uma com seu dicionário | não (gerado) |

### Como ler os números

A coluna `tipo` do dicionário indica a natureza de cada valor:

- `publicado`: valor oficial, como saiu da fonte.
- `calculado`: regra fixa aplicada sobre valores oficiais, por exemplo valor por aluno.
- `estimativa`: rateio ou aproximação feita por nós. **Não apresente como número oficial.** As colunas desse tipo terminam em `_est`.

As colunas `txt_*` trazem frases prontas, como "1.234 estudantes recebem o Pé-de-Meia em …". Elas só usam números publicados ou calculados. Municípios com valor zero ficam com o texto vazio.

### Limitações principais (leia antes de publicar)

- **Pé-de-Meia:** o número de beneficiários é aproximado pelas parcelas de matrícula, porque a fonte não permite identificar cada estudante. Não há recorte por escola. Em 44 municípios há mais beneficiários (2025) do que matrículas no ensino médio público (Censo 2024); a diferença de ano é parte da explicação.
- **PNLD:** o FNDE publica só totais por UF, então **todo valor municipal é estimativa**, feita por rateio das matrículas. Não publique valores municipais de MT.
- **Fundeb:** os valores são repasses efetivos de 2025 em base de caixa (Tesouro Nacional). O valor por aluno usa matrículas sem ponderação, o que difere do critério do FNDE. A rede estadual por município é estimativa.
- **Escola em Tempo Integral:** o valor por matrícula varia por rede. A rede estadual por município é estimativa.
- **Médias por escola** dividem o valor da rede pelo número de escolas. Não correspondem ao que cada escola recebe.
- Boa Esperança do Norte (MT) foi criado depois do Censo 2024 e aparece sem matrículas. Brasília não tem "rede municipal", porque o DF é ente estadual.

A lista completa está em [`docs/decisoes.md`](docs/decisoes.md#6-trade-offs-e-limitações-o-que-ler-antes-de-publicar).

---

## Como rodar

### Requisitos

- Python 3.12
- cerca de 2,5 GB livres em disco para os dados brutos

### Instalação

```bash
git clone https://github.com/lhrick/dados-educacao-br.git
cd dados-educacao-br
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 1. Baixar o Pé-de-Meia à mão

Este é o único passo manual. O servidor da CGU pode exigir captcha, por isso os zips mensais são baixados no navegador:

1. Abra os links em [`links_pe_de_meia.txt`](links_pe_de_meia.txt).
2. Salve cada `AAAAMM_PeDeMeia.zip`, **sem renomear**, em `data/raw/cgu/pe_de_meia/`.

Todas as outras fontes (IBGE, INEP, FNDE, DOU e Tesouro) são baixadas automaticamente.

### 2. Rodar o pipeline

```bash
.venv/bin/python -m src.pipeline
```

O pipeline faz download, transformação, consolidação e validação. Com os brutos já baixados, roda em cerca de 1 minuto. A primeira execução demora mais, porque precisa baixar os dados brutos (cerca de 180 MB, sem contar o Pé-de-Meia).

Para recomeçar a partir de uma etapa, sem refazer as anteriores:

```bash
.venv/bin/python -m src.pipeline --de consolidar
```

As etapas, na ordem, são: `ibge`, `censo`, `pe_de_meia`, `pe_de_meia_mun`, `pnld`, `pnld_mun`, `eti`, `eti_mun`, `fundeb_repasses`, `fundeb_mun`, `fundeb_2026_projecao`, `fundeb_2026_projecao_mun`, `consolidar`, `programas`, `validar`.

O comando termina com código 1 se alguma checagem de validação tiver status `FALHA`. Itens marcados como `ATENÇÃO` não interrompem o pipeline, mas devem ser conferidos em `data/processed/educacao_municipios_2025_validacao.md`.

### 3. Testes

```bash
.venv/bin/python -m pytest
```

Entre outras coisas, os testes conferem se cada tabela gravada bate com o seu dicionário de dados.

### 4. Explorador interativo

```bash
.venv/bin/python -m src.viz.explorador            # todos os programas
.venv/bin/python -m src.viz.explorador fundeb     # só um
```

Gera uma página HTML por programa em `docs/explorador/`, a partir da tabela final. Basta abrir o arquivo no navegador: ele funciona offline, sem servidor e sem biblioteca externa.

| Página | Conteúdo |
|---|---|
| `pe_de_meia.html` | beneficiários, valor pago e alcance sobre as matrículas do ensino médio público |
| `fundeb.html` | receita da rede municipal e parte que vem da União (VAAF, VAAT, VAAR) |
| `eti.html` | fomento à Escola em Tempo Integral e matrículas fomentadas |

Cada página tem:
- busca por município e filtro por estado;
- mapa com zoom;
- ficha do município, com comparação com o estado e o Brasil, avisos e frases prontas para copiar;
- gráficos por estado;
- tabela ordenável com exportação para CSV.

Valores do tipo `estimativa` aparecem com selo. O link `pagina.html#<cod_ibge_7>` abre direto a ficha de um município.

As páginas são para uso interno do time. O PNLD não tem página, porque todo valor municipal dele é estimativa (rateio dos totais da UF).

**Como funciona:** o template `src/viz/templates/explorador.html` é genérico e não conhece nenhum programa. Cada página é definida por um JSON em `src/viz/configs/`, que diz:
- quais colunas mostrar, com rótulo, formato e forma de agregar por estado;
- as faixas do mapa;
- os alertas, as frases e as notas.

Descrição, unidade, tipo e fonte de cada coluna vêm do dicionário de dados. Para um programa novo, ou outro projeto com tabela por `cod_ibge_7` e dicionário no mesmo formato, basta escrever uma config.

Os números citados nas notas e observações das configs (por exemplo, "44 municípios") são de 2025. Revise esses textos quando a tabela for gerada com dados novos.

### Chave da API do Portal da Transparência (opcional)

O pipeline atual **não precisa** dela. O módulo `src/ingest/portal_transparencia.py` serve para consultas avulsas e lê a chave de um arquivo `.env` na raiz:

```
PORTAL_TRANSPARENCIA_API_KEY=sua_chave
```

O `.env` está no `.gitignore` e nunca deve ser commitado.

### Certificados TLS

Alguns servidores gov.br (IBGE, INEP) não enviam o certificado intermediário. Em vez de desligar a verificação TLS, o pipeline completa a cadeia com os certificados oficiais em `certs/`. Os detalhes estão em [`docs/fontes.md`](docs/fontes.md#conexão-tls-com-servidores-govbr-2026-10-15).

---

## Fontes

| Dado | Fonte |
|---|---|
| Municípios | API de localidades do IBGE |
| Matrículas e escolas | Censo Escolar 2024, microdados do INEP |
| Pé-de-Meia | Portal da Transparência (CGU), arquivos mensais |
| PNLD | FNDE, dados estatísticos por UF |
| Fundeb 2025 | Tesouro Nacional, API de Transferências Constitucionais |
| Fundeb 2026 (projeção) | Portaria Interministerial MEC/MF nº 6/2026 |
| Escola em Tempo Integral | Portarias MEC 586, 605 e 823/2025 (DOU) |

A **proveniência** de cada arquivo baixado (URL, data, hash SHA-256 e ano de referência) fica registrada em [`data/raw/_manifest.csv`](data/raw/_manifest.csv). Os dados brutos (`data/raw/`) e intermediários (`data/interim/`) não são versionados; o pipeline os recria.

**Dados pessoais:** a base do Pé-de-Meia é individual. O pipeline lê só colunas não pessoais e agrega por município logo na leitura. Nenhum CPF, NIS ou nome é gravado, e a validação confere isso.

---

## Estrutura

```
src/
  ingest/      um módulo por fonte (download + leitura)
  transform/   agregação por município e cálculos por aluno
  metrics/     textos prontos e tabela explicativa dos programas
  validate/    checklist de validação
  viz/         explorador interativo (explorador.py, templates/, configs/)
  pipeline.py  orquestra tudo
  dicionario.py, manifest.py
docs/
  explorador/   páginas HTML interativas (geradas)
  programas.md  explicação dos programas para a redação
  fontes.md     schema real de cada fonte, como foi verificado
  decisoes.md   decisões, trade-offs, limitações e pendências
tests/
data/
  raw/ interim/ processed/
```

## Pendências conhecidas

- PNLD por escola ou município: só disponível via pedido de LAI ao FNDE.
- Matrículas ponderadas do Fundeb por ente, previstas pelo FNDE até 31/01/2027.
- Censo Escolar 2025: quando sair, revalidar os rateios e a relação Pé-de-Meia/matrículas.
- Total oficial do Pé-de-Meia 2025, para conferência do total nacional.

A lista completa está em [`docs/decisoes.md`](docs/decisoes.md#10-pendências).
