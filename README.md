# Eleições ES 2026 — painel de avaliação de candidatos

Painel Streamlit para comparar os candidatos do Espírito Santo que **já ocupam cargo** —
33 deputados estaduais (ALES) e 10 federais (Câmara) — em quatro dimensões que a pesquisa
mostrou serem as únicas que discriminam sem enganar.

## Rodar

```bash
cd eleicoes-es-2026

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/streamlit run app.py
```

Abre em `http://localhost:8501`. Para ver da rede local (celular, outro computador), o
`.streamlit/config.toml` já vem com `address = "0.0.0.0"` — acesse por `http://<ip-da-maquina>:8501`.

> **Não exponha esta porta na internet.** O Streamlit não é feito para isso.

Testado em Python 3.11 com Streamlit 1.64, pandas 3.0 e altair 6.3. As versões maiores do
pandas (3.x) e numpy (2.x) funcionam — as transformações foram verificadas nelas.

## As quatro dimensões

| # | Dimensão | O que mede |
|---|---|---|
| 1 | **Eixo governo** | Votações com posição declarada em que acompanhou o governo |
| 2 | **Posicionamento** | Fatia das votações em que **registrou voto**, em vez de abster-se ou ausentar-se |
| 3 | **Produção substantiva** | Quanto da produção propõe política pública, em vez de homenagem |
| 4 | **Conversão em lei** | Propostas que viraram norma — **com ressalvas pesadas** |

## As quatro que ficaram de fora, e por quê

A pesquisa mediu muito mais que isto. Estas foram testadas e reprovadas:

**"Quem mais aprova lei" mede coalizão, não qualidade.** No estadual o governo converte ~42%
e a oposição ~20%. O Coronel Weliton converte 18,2% com 48% de produção **simbólica** —
nomear prédio é o que a oposição consegue aprovar. Um ranking por leis aprovadas premia quem
nomeia prédio e pune quem propõe política pública. No federal a conversão simplesmente **não
discrimina**: governo 1,1%, oposição 1,4%.

**"Alinhamento" por maioria de bancada mede coesão partidária, não posição política.** O
Gilvan da Federal dá 91,2% por esse método e **25,1%** na orientação oficial do Governo —
66 pontos de diferença. Este painel usa o método oficial.

**Volume de projeto mede esforço de sinalização.** O Evair tem 214 projetos (9º maior da
Câmara inteira) e 2 leis. Volume diz que a pessoa trabalha; não diz que entrega.

**Presença no plenário não é posicionamento.** O Marcelo Santos tem 242 votações, 188
abstenções e 49 ausências: posicionou-se em 5. Não é oposição, é ausência de posição.

## O que os dados NÃO respondem

- **Honestidade** — não há processo, condenação nem licitação aqui
- **Competência** — só atividade medida. Um péssimo legislador prolífico parece ótimo
- **Conteúdo das propostas** — classificação por regex sobre a ementa (objetivo declarado)
- **Se a posição é boa** — o eixo governo é 100% neutro: diz onde a pessoa está, não se o lugar presta

A aba **Método** do app repete tudo isso, e cada tela carrega a ressalva que lhe cabe. É
proposital: ficha sem ressalva vira ficha enganosa.

## Estrutura

```
app.py                  painel Streamlit, 5 abas (só apresenta — não calcula nada)
preparar_dados.py       gera data/candidatos.json e data/ressalvas.json
preparar_materias.py    gera data/materias.json (propostas, temas, funil, votações)
gera_fichas.py          gera as fichas .md por candidato
data/candidatos.json    43 candidatos, as 4 dimensões (286 KB)
data/materias.json      33 candidatos estaduais: propostas, temas, funil, 239 votações (1,2 MB)
data/ressalvas.json     texto das ressalvas, exibido na UI
.streamlit/config.toml  porta, CORS e tema
fichas/                 uma ficha .md por candidato, em texto (43 arquivos)
```

### Abas

1. **Onde se posicionam** — dispersão eixo governo × produção substantiva, com a tabela completa
2. **Ficha** — as quatro dimensões de um candidato
3. **Matérias e votos** — o que ele propôs, por tema, o funil até virar lei, e como a casa votou
4. **Emendas** — transferências especiais da bancada federal, com destinos
5. **Método** — as métricas que foram testadas e reprovadas, e as ressalvas de cada casa

## A aba Matérias e votos

Uma ficha por candidato com foto (link direto da ALES, não baixada), indicadores macro,
decomposição por tema, funil da proposta e — em três colunas — o que ele propôs, com número
e título, e o placar da votação correspondente.

**O funil é medido pela tramitação, não pela situação do registro.** "Arquivado" não é
fracasso: é o último passo de um projeto que virou lei. Por isso "virou lei" é contado pela
fase *Norma Sancionada* na `Tramitacoes`.

### Duas ressalvas que essa aba carrega

**Só 3,5% das propostas têm votação nominal.** Das 2.790 propostas dos candidatos, 98 foram a
voto nominal — a maioria morre em comissão ou é arquivada sem nunca ser votada. É por isso que
a terceira coluna quase sempre diz "sem votação": não é falha de coleta, é a realidade do
processo legislativo.

**Tema é classificado por regex sobre a ementa.** Lê o objetivo *declarado*, não o conteúdo nem
a constitucionalidade.

### Atribuição de autoria: `_autorID_consultado`, não `nomeRazao`

O `nomeRazao` que a API da ALES devolve no campo do autor **diverge** do nome do parlamentar em
três casos reais:

```
"ENGENHERIO JOSE ESMERALDO"   →  ALES: ENGENHEIRO JOSÉ ESMERALDO   (typo da própria API)
"FABIO DUARTE DE ALMEIDA"     →  ALES: FABIO DUARTE                (nome civil)
"JULIO CEZAR MENDEL"          →  ALES: JULIO DA FETAES             (nome de urna diferente)
```

Ligar por nome zerava a produção desses três. O `preparar_materias.py` liga por `autorID`.

E entre os **dois campos de autor** disponíveis, a escolha foi medida: `_autorID_consultado`
reproduz os números que o app já mostra (16 de 16 conferidos), `AutorRequerenteDados.autorId`
reproduz 1 de 16. Usar o segundo faria o app mostrar 335 num lugar e 326 em outro para o mesmo
deputado.


## Procedência dos dados

| Fonte | O que veio |
|---|---|
| ALES — API de dados abertos | Produção legislativa, legislatura 20 |
| ALES — boletins RVP (PDF) | Votação nominal: **269 de 458** extraídos |
| Câmara — `votacoesVotos` | Voto de cada deputado, 2023–2026 |
| Câmara — `votacoesOrientacoes` | **Orientação oficial** das bancadas, incl. `Governo` |
| Câmara — `proposicoes` / `proposicoesAutores` | Produção e autoria |
| TSE | Candidaturas, bens, fundo eleitoral (contas **parciais**, 22/09/2026) |
| TransfereGov | Transferências especiais ("emendas pix") — R$ 416 mi |

## Ressalvas que mudam a leitura

1. **Alinhamento estadual é proxy** — a ALES não publica orientação de bancada, então é
   medido por voto em veto. O federal usa a orientação oficial, que é dado duro.
2. **189 dos 458 boletins estaduais ficaram fora** (36% dos vetos), por PDFs sem mapa Unicode.
3. **FEFC e patrimônio** vêm de prestação de contas parcial do TSE.
4. **Emendas cobrem só transferências especiais** — não inclui RP6/RP7/RP8, então o total
   real de cada deputado é maior.
5. **2026 é parcial** em produção, votação e candidatura.
6. **Bruno Lamas tem produção medida e zero voto nominal** extraído. As dimensões 1, 2 e 4
   saem sem dado, e a ficha dele avisa. Ausência na fonte ≠ ausência de posição.

## Reproduzir os dados

`data/` já está no pacote, então **o app roda sem nada mais**. Para regerar:

```bash
python3 preparar_dados.py --pesquisa /caminho/para/pesquisa
```

O `preparar_dados.py` lê os artefatos brutos da pesquisa (não incluídos aqui — são 1,4 GB).
Ele existe para documentar de onde cada número veio e tornar o pacote auditável.
