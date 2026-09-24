#!/usr/bin/env python3
"""Gera uma ficha .md por candidato (estaduais + federais) a partir dos JSONs da pesquisa.

Fontes (todas geradas nesta pesquisa):
  estadual : ales-votos/perfil_final.json      (voto/participacao/governo/producao)
             eleicoes-2026/RELATORIO-candidaturas-2026.md  (FEFC, patrimonio)
  federal  : federais-es/eixo_governo.json     (eixo governo oficial)
             federais-es/perfil_fed.json       (producao substantiva)
             federais-es/data_emendas.json     (transferencias especiais)
             federais-es/RELATORIO-perfil-politico.md (conversao em lei, cargo 2026)
"""
import argparse
import json
import re
import os
import unicodedata
from collections import defaultdict

ap = argparse.ArgumentParser(description='Gera uma ficha .md por candidato.')
ap.add_argument('--pesquisa', default=os.path.expanduser('~/pesquisa'),
                help='raiz dos artefatos da pesquisa (default: ~/pesquisa)')
ap.add_argument('--saida', default=None,
                help='diretorio de saida (default: <pesquisa>/fichas)')
A = ap.parse_args()
R = A.pesquisa
SAIDA = A.saida or f'{R}/fichas'
os.makedirs(SAIDA, exist_ok=True)


def norm(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', str(s or ''))
                  .encode('ascii', 'ignore').decode().upper().strip())


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', norm(s).lower()).strip('-')


def br(v, dec=0):
    if v is None:
        return '—'
    return f'{v:,.{dec}f}'.replace(',', '@').replace('.', ',').replace('@', '.')


def dinheiro(v):
    return '—' if v is None else 'R$ ' + br(v, 2)


def pct(v, dec=1):
    return '—' if v is None else br(v, dec) + '%'


# ═══════════════════════════ fontes ═══════════════════════════
perfil = json.load(open(f'{R}/ales-votos/perfil_final.json', encoding='utf-8'))
EST = {norm(p['nome']): p for p in perfil}
FED_EIXO = json.load(open(f'{R}/federais-es/eixo_governo.json', encoding='utf-8'))
FED_PERFIL = json.load(open(f'{R}/federais-es/perfil_fed.json', encoding='utf-8'))
FED_EMENDAS = json.load(open(f'{R}/federais-es/data_emendas.json', encoding='utf-8'))
FED = {v['nome']: v for v in FED_PERFIL.values()}

# FEFC + patrimonio (tabela: | NOME | PARTIDO | CARGO | FEFC | PATRIMONIO | ratio |)
def reais(t):
    t = str(t).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(t)
    except ValueError:
        return None

CAND = {}
for l in open(f'{R}/eleicoes-2026/RELATORIO-candidaturas-2026.md', encoding='utf-8'):
    if not l.startswith('|') or l.startswith('| ---') or 'Deputado | Partido' in l:
        continue
    c = [x.strip() for x in l.strip('|\n').split('|')]
    if len(c) < 5:
        continue
    CAND[norm(c[0])] = {'nome': c[0], 'partido': c[1], 'cargo26': c[2],
                        'fefc': reais(c[3]), 'patrimonio': reais(c[4])}

# conversao em lei + cargo no federal (secao 2: 7 colunas; secao 4: 6 colunas)
FED_LEI, CARGO_FED = {}, {}
for l in open(f'{R}/federais-es/RELATORIO-perfil-politico.md', encoding='utf-8'):
    if not l.startswith('|') or '---' in l:
        continue
    c = [x.strip().strip('*').strip() for x in l.strip('|\n').split('|')]
    if c and c[0] in ('Deputado', ''):
        continue
    nome = re.sub(r'\s+', ' ', c[0])
    # secao 2: | Deputado | partido | cargo | votacoes | alinhado | contra | % |
    if len(c) == 7 and c[2] and not c[2].replace('.', '').replace(',', '').isdigit():
        CARGO_FED[nome] = c[2]
    # secao 4: | Deputado | % gov | PL+PLP | % subst | leis | conversao |
    if len(c) == 6:
        try:
            FED_LEI[nome] = {'pl': int(re.sub(r'\D', '', c[2])),
                             'leis': int(re.sub(r'\D', '', c[4]))}
        except (ValueError, IndexError):
            pass

# ═══════════════════════════ helpers de leitura ═══════════════════════════
def faixa_gov(g):
    if g is None:
        return 'sem dado'
    if g >= 85:
        return 'alinhado ao governo'
    if g >= 75:
        return 'majoritariamente governo'
    if g >= 40:
        return 'dividido / indefinido'
    return 'oposição'


def leitura_gov(g, casa):
    ax = 'voto em veto' if casa == 'estadual' else 'orientação oficial do Governo'
    if g is None:
        return f'Sem dado de posicionamento suficiente para medir alinhamento ({ax}).'
    if g >= 85:
        return (f'Alinhado ao governo em **{pct(g)}** das votações com posição declarada '
                f'({ax}). Vota consistentemente com o bloco do governador.')
    if g >= 75:
        return (f'Majoritariamente com o governo (**{pct(g)}**), mas com divergência relevante '
                f'({pct(100 - g)} contra). Não é voto de cabresto.')
    if g >= 40:
        return (f'**{pct(g)}** de alinhamento — perto da metade. Perfil dividido, sem '
                f'alinhamento claro com governo ou oposição.')
    return (f'**Oposição**: alinha com o governo em apenas {pct(g)} das votações ({ax}). '
            f'{pct(100 - g)} contra.')


def faixa_participacao(p):
    if p is None:
        return 'sem dado'
    if p >= 90:
        return 'altíssima'
    if p >= 75:
        return 'alta'
    if p >= 60:
        return 'média'
    if p >= 30:
        return 'baixa'
    return 'praticamente ausente'


def leitura_participacao(p, vot_total):
    if p is None or vot_total is None:
        return 'Sem base de votações suficiente.'
    if p >= 90:
        return (f'Participa de {pct(p)} das {br(vot_total)} votações nominais — '
                f'presença e voto consistentes.')
    if p >= 60:
        return f'Posicionou-se em {pct(p)} das {br(vot_total)} votações nominais.'
    if p >= 30:
        return (f'**Baixa participação**: {pct(p)} das {br(vot_total)} votações. '
                f'Ficou sem posição registrada na maioria delas.')
    return (f'**Atenção**: posicionou-se em apenas {pct(p)} das {br(vot_total)} votações. '
            f'A ausência de voto não é oposição — é ausência de posição. '
            f'Avaliar por outras dimensões.')


def leitura_producao(subst, simb, pl, casa):
    if not pl:
        return 'Sem produção medida.'
    s = (subst / pl * 100) if pl else 0
    if s >= 85:
        t = ('Produção majoritariamente **substantiva** — programa, direito, obrigação '
             'estatal, regulação.')
    elif s >= 60:
        t = 'Produção **predominantemente substantiva**, com parte simbólica.'
    elif s >= 40:
        t = ('Produção **dividida**: metade substantiva, metade simbólica '
             '(nomeação de próprio público, utilidade pública, homenagem).')
    else:
        t = ('Produção **majoritariamente simbólica** — nomeação de prédio, declaração de '
             'utilidade pública, homenagem. Isso passa fácil e não muda política pública.')
    return f'{t} ({pct(s)} do volume declarado)'


def converte(leis, pl, casa):
    if not pl or leis is None:
        return ''
    c = leis / pl * 100
    if casa == 'estadual':
        if c >= 40:
            nota = 'Conversão alta — mas leia a ressalva: no estado, isso mede posição na coalizão.'
        elif c >= 20:
            nota = 'Conversão mediana. Ressalva: no estado, mede posição na coalizão, não mérito.'
        else:
            nota = ('Conversão baixa. Ressalva: no estado quem propõe matéria substantiva fora '
                    'do governo quase não aprova.')
    else:
        nota = ('Ressalva: no federal a conversão **não discrimina** — governo e oposição ficam '
                'ambos perto de 1%. Não use como critério aqui.')
    return f'{leis} viraram lei em {br(pl)} propostas ({pct(c)}). {nota}'


# ═══════════════════════════ estadual ═══════════════════════════
# A lista de CANDIDATOS dirige quem ganha ficha; perfil_final.json so' preenche o que existe.
# Assim um candidato sem dado de voto (BRUNO LAMAS: 4 PLs, zero votos nominais) nao desaparece.
ALVOS = {k: p for k, p in EST.items() if p.get('cargo26') != 'NAO CONCORRE'}
for k, c in CAND.items():
    if k not in ALVOS and k != 'DEPUTADO':
        ALVOS[k] = {'nome': c['nome'], 'partido': c.get('partido'), 'cargo26': c.get('cargo26'),
                    'pl': None, 'lei': None, 'subst': None, 'simb': None,
                    'vot_total': None, 'particip': None, 'gov': None}

# Producao de quem tem PL mas nao entrou no cruzamento (sem voto nominal):
# recupera do taxonomia_final.json via parlamentares.json.
TAX = json.load(open(f'{R}/ales-votos/taxonomia_final.json', encoding='utf-8'))
ALES_P = json.load(open(f'{R}/ales/data/parlamentares.json', encoding='utf-8'))
ID2NOME = {str(a['autorID']): a.get('parlamentarNome', '') for a in ALES_P}
for aid, t in TAX.items():
    k = norm(ID2NOME.get(aid, ''))
    if k in ALVOS and not ALVOS[k].get('pl'):
        ALVOS[k]['pl'] = t.get('t')
        ALVOS[k]['subst'] = t.get('substantiva')
        ALVOS[k]['simb'] = t.get('simbolica')
        ALVOS[k]['_so_producao'] = True

gerados = []
for k, p in sorted(ALVOS.items(), key=lambda x: x[1]['nome']):
    cargo = p.get('cargo26') or ''
    c = CAND.get(k, {})
    nome = p['nome'].title()
    L = []
    L.append(f'# {nome}\n')
    L.append(f'**{p.get("partido", "—")}** · candidato a **{cargo}** em 2026 · '
             f'Deputado Estadual em exercício (ALES)\n')
    if c.get('fefc') is not None or c.get('patrimonio') is not None:
        L.append(f'- Fundo eleitoral (FEFC): **{dinheiro(c.get("fefc"))}**')
        L.append(f'- Patrimônio declarado: **{dinheiro(c.get("patrimonio"))}**')
        if c.get('fefc') and c.get('patrimonio'):
            L.append(f'- FEFC / patrimônio: {br(c["fefc"]/c["patrimonio"], 2)}×')
        L.append('')

    gov = p.get('gov')
    gov = float(gov) if gov not in (None, '') else None
    part = float(p['particip']) if p.get('particip') else None
    pl = int(p['pl']) if p.get('pl') else None
    lei = int(p['lei']) if p.get('lei') else None
    subst = int(p['subst']) if p.get('subst') else None
    simb = int(p['simb']) if p.get('simb') else None
    vt = int(p['vot_total']) if p.get('vot_total') else None

    L.append('## As quatro dimensões\n')
    L.append(f'| Dimensão | Valor | Leitura |')
    L.append(f'| --- | --- | --- |')
    L.append(f'| 1. Eixo governo | **{pct(gov)}** | {faixa_gov(gov)} |')
    L.append(f'| 2. Posicionamento | {pct(part)} | {faixa_participacao(part)} |')
    L.append(f'| 3. Produção substantiva | '
             f'{pct(subst/pl*100) if pl else "—"} | '
             f'{br(subst)} de {br(pl)} propostas |')
    L.append(f'| 4. Conversão em lei | {br(lei)} leis | '
             f'{pct(lei/pl*100) if (pl and lei is not None) else "—"} de {br(pl)} |')
    L.append('')

    if p.get('_so_producao'):
        L.append('> **Cobertura incompleta.** Há produção legislativa medida, mas **nenhum voto '
                 'nominal** deste parlamentar entrou na extração — nem presença, nem '
                 'posicionamento. As dimensões 1, 2 e 4 saem sem dado; a 3 (produção) é válida. '
                 'Não leia a ausência como oposição ou afastamento: é ausência na fonte.\n')

    L.append('## Leitura\n')
    L.append(f'**Onde se posiciona.** {leitura_gov(gov, "estadual")}\n')
    L.append(f'**Se se posiciona.** {leitura_participacao(part, vt)}\n')
    L.append(f'**O que produz.** {leitura_producao(subst or 0, simb or 0, pl, "estadual")}\n')
    if lei is not None:
        L.append(f'**O que converte.** {converte(lei, pl, "estadual")}\n')

    L.append('---\n')
    L.append('*Fontes: API de dados abertos da ALES (produção, legislatura 20) · boletins de '
             'votação nominal (269 de 458 votações extraídas) · TSE (FEFC e patrimônio, '
             'prestação de contas parcial de 22/09/2026).*')
    L.append('')
    L.append('*Ressalvas: alinhamento medido por voto em veto (proxy — a ALES não publica '
             'orientação de bancada) · 189 boletins fora, 36% dos vetos · conversão em lei mede '
             'posição na coalizão, não qualidade.*')

    fn = f'{SAIDA}/estadual-{slug(p["nome"])}.md'
    open(fn, 'w', encoding='utf-8').write('\n'.join(L))
    gerados.append(('estadual', p['nome'], cargo, gov, part))

# ═══════════════════════════ federal ═══════════════════════════
# FED_EIXO vem indexado por ID de deputado; re-indexa por nome para casar com perfil_fed.
EIXO_NOME = {v[0]: v for v in FED_EIXO.values()}

for idd, v in sorted(FED.items(), key=lambda x: x[1]['nome']):
    nome = v['nome']
    eixo = EIXO_NOME.get(nome)
    gov = float(eixo[4]) if eixo else None
    vt = int(eixo[1]) if eixo else None
    cnt = v.get('contagem') or {}
    total = cnt.get('total') or 0
    subst = cnt.get('substantiva') or 0
    simb = cnt.get('simbolica') or 0
    lei = FED_LEI.get(nome, {})
    cargo = CARGO_FED.get(nome, '—')

    prog = FED_EMENDAS.get(nome) or []
    n_em = len(prog)
    valor = sum(float(x.get('valor_investimento_plano_acao') or 0) +
                float(x.get('valor_custeio_plano_acao') or 0) for x in prog)
    destinos = defaultdict(float)
    for x in prog:
        destinos[str(x.get('nome_beneficiario_plano_acao') or '?').title()] += (
            float(x.get('valor_investimento_plano_acao') or 0) +
            float(x.get('valor_custeio_plano_acao') or 0))
    top = sorted(destinos.items(), key=lambda x: -x[1])[:5]

    L = []
    L.append(f'# {nome}\n')
    L.append(f'**Deputado Federal · Espírito Santo** · candidato a **{cargo}** em 2026\n')
    L.append('## As quatro dimensões\n')
    L.append('| Dimensão | Valor | Leitura |')
    L.append('| --- | --- | --- |')
    L.append(f'| 1. Eixo governo | **{pct(gov)}** | {faixa_gov(gov)} |')
    L.append(f'| 2. Posicionamento | — | {br(vt)} votações com orientação do Governo |')
    L.append(f'| 3. Produção substantiva | {pct(subst/total*100) if total else "—"} | '
             f'{br(subst)} de {br(total)} propostas |')
    if lei:
        L.append(f'| 4. Conversão em lei | {br(lei.get("leis"))} leis | '
                 f'{pct(lei["leis"]/lei["pl"]*100) if lei.get("pl") else "—"} '
                 f'de {br(lei.get("pl"))} |')
    L.append('')

    L.append('## Leitura\n')
    L.append(f'**Onde se posiciona.** {leitura_gov(gov, "federal")}\n')
    L.append(f'**O que produz.** {leitura_producao(subst, simb, total, "federal")}\n')
    if lei:
        L.append(f'**O que converte.** {converte(lei.get("leis"), lei.get("pl"), "federal")}\n')
    if n_em:
        L.append(f'**O que entrega.** {n_em} emendas de transferência especial '
                 f'("emenda pix"), **{dinheiro(valor)}** em {br(n_em)} planos de ação.\n')
        if top:
            L.append('Principais destinos:')
            for d, val in top:
                L.append(f'- {d} — {dinheiro(val)}')
            L.append('')
        L.append('*Ressalva: cobre só transferências especiais. Não inclui RP6, RP7 nem RP8 — '
                 'o total de emendas do deputado é maior.*\n')

    L.append('---\n')
    L.append('*Fontes: Câmara dos Deputados — `votacoesVotos` (voto de cada deputado), '
             '`votacoesOrientacoes` (orientação oficial, bancada `Governo`), `proposicoes` e '
             '`proposicoesAutores` (2023–2026) · TransfereGov (transferências especiais).*')
    L.append('')
    L.append('*Ressalvas: alinhamento usa a orientação OFICIAL do Governo em 1.133 votações — ' \
             'não a maioria de bancada (mede coesão partidária, não posição) · produção '
             'classificada por regex sobre a ementa (objetivo declarado) · conversão em lei tem '
             'viés temporal (2026 incompleto) e não discrimina posição no federal — o baseline '
             'nacional é 1,57%, a bancada está em 1,3%.*')

    fn = f'{SAIDA}/federal-{slug(nome)}.md'
    open(fn, 'w', encoding='utf-8').write('\n'.join(L))
    gerados.append(('federal', nome, cargo, gov, None))

# ═══════════════════════════ indice ═══════════════════════════
L = ['# Fichas por candidato — ES 2026\n',
     f'Gerado por `gera_fichas.py` em {__import__("datetime").date.today().isoformat()}.',
     f'{sum(1 for g in gerados if g[0]=="estadual")} estaduais + '
     f'{sum(1 for g in gerados if g[0]=="federal")} federais.\n',
     '## Estaduais (ALES)\n',
     '| Candidato | Cargo 2026 | Eixo governo | Posicionamento | Ficha |',
     '| --- | --- | --- | --- | --- |']
for casa, nome, cargo, gov, part in sorted([g for g in gerados if g[0] == 'estadual'],
                                           key=lambda x: -(x[3] or 0)):
    L.append(f'| {nome} | {cargo} | {pct(gov)} | {pct(part)} | '
             f'[abrir](estadual-{slug(nome)}.md) |')
L += ['\n## Federais (Câmara)\n',
      '| Candidato | Cargo 2026 | Eixo governo | Ficha |',
      '| --- | --- | --- | --- |']
for casa, nome, cargo, gov, part in sorted([g for g in gerados if g[0] == 'federal'],
                                           key=lambda x: -(x[3] or 0)):
    L.append(f'| {nome} | {cargo} | {pct(gov)} | [abrir](federal-{slug(nome)}.md) |')
open(f'{SAIDA}/INDICE.md', 'w', encoding='utf-8').write('\n'.join(L))

print(f'fichas geradas: {len(gerados)}')
print(f'  estaduais: {sum(1 for g in gerados if g[0]=="estadual")}')
print(f'  federais : {sum(1 for g in gerados if g[0]=="federal")}')
sem_dado = [p['nome'] for p in ALVOS.values() if p.get('_so_producao')]
if sem_dado:
    print(f'\nCom ficha mas SEM dado de voto (cobertura incompleta, declarada na ficha):')
    for n in sem_dado:
        print(f'   {n}')
