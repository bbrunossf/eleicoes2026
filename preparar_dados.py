#!/usr/bin/env python3
"""Prepara os dados da pesquisa para o app.

Le os artefatos de ~/pesquisa e emite JSON limpo em data/, para o repo ser auto-contido
e o app nao depender do layout interno da pesquisa.

Uso:  python3 preparar_dados.py [--pesquisa /caminho/para/pesquisa]
"""
import argparse
import json
import os
import re
import unicodedata

ap = argparse.ArgumentParser()
ap.add_argument('--pesquisa', default=os.path.expanduser('~/pesquisa'))
ap.add_argument('--saida', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'))
A = ap.parse_args()
P, OUT = A.pesquisa, A.saida
os.makedirs(OUT, exist_ok=True)


def norm(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', str(s or ''))
                  .encode('ascii', 'ignore').decode().upper().strip())


def reais(t):
    t = str(t).replace('R$', '').strip()
    if t in ('—', '', '-', 'None'):
        return None
    t = t.replace('.', '').replace(',', '.')
    try:
        return float(t)
    except ValueError:
        return None


def num(t):
    t = re.sub(r'\D', '', str(t or ''))
    return int(t) if t else None


# Rótulos de cargo vêm de duas fontes com grafias diferentes (relatório federal usa
# "Dep. Estadual", o do TSE usa "Deputado Estadual"). Sem normalizar, o filtro da UI
# mostra duas opções para a mesma coisa.
CARGO_NORM = {
    'Deputado Estadual': 'Dep. Estadual',
    'Deputado Federal': 'Dep. Federal',
    'Deputada Estadual': 'Dep. Estadual',
    'Deputada Federal': 'Dep. Federal',
}


def cargo(t):
    t = re.sub(r'\s+', ' ', str(t or '')).strip()
    return CARGO_NORM.get(t, t) or None


# ─── candidatura: FEFC + patrimonio (tabela do relatorio de candidaturas) ───
CAND = {}
arq = f'{P}/eleicoes-2026/RELATORIO-candidaturas-2026.md'
for l in open(arq, encoding='utf-8'):
    if not l.startswith('|') or '---' in l:
        continue
    c = [x.strip() for x in l.strip('|\n').split('|')]
    if len(c) < 5 or c[0] in ('Deputado', 'Deputado | Partido'):
        continue
    CAND[norm(c[0])] = {'nome': c[0], 'partido': c[1], 'cargo26': cargo(c[2]),
                        'fefc': reais(c[3]), 'patrimonio': reais(c[4])}

# ─── estaduais: perfil de voto e producao ───
perfil = json.load(open(f'{P}/ales-votos/perfil_final.json', encoding='utf-8'))
EST = {}
for p in perfil:
    k = norm(p['nome'])
    if p.get('cargo26') == 'NAO CONCORRE':
        continue
    c = CAND.get(k, {})
    gov = float(p['gov']) if p.get('gov') not in (None, '') else None
    part = float(p['particip']) if p.get('particip') not in (None, '') else None
    EST[k] = {
        'nome': p['nome'], 'partido': p.get('partido'), 'casa': 'Estadual',
        'cargo26': cargo(p.get('cargo26')), 'gov': gov, 'posicionamento': part,
        'pl': int(p['pl']) if p.get('pl') else None,
        'leis': int(p['lei']) if p.get('lei') else None,
        'subst': int(p['subst']) if p.get('subst') else None,
        'simb': int(p['simb']) if p.get('simb') else None,
        'vot_total': int(p['vot_total']) if p.get('vot_total') else None,
        'fefc': c.get('fefc'), 'patrimonio': c.get('patrimonio'),
        'emendas_n': None, 'emendas_valor': None,
    }

# estadual presente na lista de candidatos mas ausente do cruzamento (sem voto nominal):
TAX = json.load(open(f'{P}/ales-votos/taxonomia_final.json', encoding='utf-8'))
ID2NOME = {str(a['autorID']): a.get('parlamentarNome', '')
           for a in json.load(open(f'{P}/ales/data/parlamentares.json', encoding='utf-8'))}
for aid, t in TAX.items():
    k = norm(ID2NOME.get(aid, ''))
    if k in CAND and k not in EST:
        c = CAND[k]
        EST[k] = {'nome': c['nome'], 'partido': c['partido'], 'casa': 'Estadual',
                  'cargo26': cargo(c.get('cargo26')), 'gov': None, 'posicionamento': None,
                  'pl': t.get('t'), 'leis': None, 'subst': t.get('substantiva'),
                  'simb': t.get('simbolica'), 'vot_total': None,
                  'fefc': c.get('fefc'), 'patrimonio': c.get('patrimonio'),
                  'emendas_n': None, 'emendas_valor': None, 'cobertura_incompleta': True}

# ─── federais ───
EIXO = json.load(open(f'{P}/federais-es/eixo_governo.json', encoding='utf-8'))
PFED = json.load(open(f'{P}/federais-es/perfil_fed.json', encoding='utf-8'))
EMEN = json.load(open(f'{P}/federais-es/data_emendas.json', encoding='utf-8'))
EIXO_NOME = {v[0]: v for v in EIXO.values()}

CARGO, LEI = {}, {}
for l in open(f'{P}/federais-es/RELATORIO-perfil-politico.md', encoding='utf-8'):
    if not l.startswith('|') or '---' in l:
        continue
    c = [x.strip().strip('*').strip() for x in l.strip('|\n').split('|')]
    if not c or c[0] in ('Deputado', ''):
        continue
    n = re.sub(r'\s+', ' ', c[0])
    if len(c) == 7 and c[2] and not c[2].replace('.', '').replace(',', '').isdigit():
        CARGO[n] = c[2]
    if len(c) == 6:
        pl, lei = num(c[2]), num(c[4])
        if pl is not None:
            LEI[n] = {'pl': pl, 'leis': lei}

FED = []
for idd, v in PFED.items():
    nome = v['nome']
    e = EIXO_NOME.get(nome)
    cnt = (v.get('contagem') or {})
    prog = EMEN.get(nome) or []
    valor = sum(float(x.get('valor_investimento_plano_acao') or 0) +
                float(x.get('valor_custeio_plano_acao') or 0) for x in prog)
    dest = {}
    for x in prog:
        d = str(x.get('nome_beneficiario_plano_acao') or '?')
        dest[d] = dest.get(d, 0) + (float(x.get('valor_investimento_plano_acao') or 0) +
                                    float(x.get('valor_custeio_plano_acao') or 0))
    c = CAND.get(norm(nome), {})
    FED.append({
        'nome': nome, 'partido': c.get('partido'), 'casa': 'Federal',
        'cargo26': cargo(CARGO.get(nome) or c.get('cargo26')),
        'gov': float(e[4]) if e else None,
        'posicionamento': None,
        'vot_total': int(e[1]) if e else None,
        'pl': cnt.get('total'), 'leis': (LEI.get(nome) or {}).get('leis'),
        'subst': cnt.get('substantiva'), 'simb': cnt.get('simbolica'),
        'fefc': c.get('fefc'), 'patrimonio': c.get('patrimonio'),
        'emendas_n': len(prog) or None,
        'emendas_valor': valor or None,
        'emendas_destinos': sorted(dest.items(), key=lambda x: -x[1])[:10],
        'emendas_planos': [{
            'ano': x.get('ano_plano_acao'),
            'numero': x.get('numero_emenda_parlamentar_plano_acao'),
            'destino': x.get('nome_beneficiario_plano_acao'),
            'uf': x.get('uf_beneficiario_plano_acao'),
            'investimento': float(x.get('valor_investimento_plano_acao') or 0),
            'custeio': float(x.get('valor_custeio_plano_acao') or 0),
            'situacao': x.get('situacao_plano_acao'),
            'area': x.get('codigo_descricao_areas_politicas_publicas_plano_acao'),
            'funcao': x.get('descricao_funcao_plano_acao'),
        } for x in prog],
    })

# ─── ressalvas, para a UI nunca mostrar numero sem contexto ───
RESSALVAS = {
    'estadual': [
        "Alinhamento medido por **voto em veto** — a ALES não publica orientação de bancada, "
        "então `Sim` em veto = manter o veto do governador. É proxy, não voto declarado.",
        "**189 dos 458 boletins de votação nominal ficaram fora** (36% dos vetos), por PDFs com "
        "fonte sem mapa Unicode. A cobertura é de 269 votações.",
        "**Conversão em lei mede posição na coalizão, não qualidade.** Governo converte ~42%, "
        "oposição ~20% — quem propõe matéria substantiva fora do governo quase não aprova.",
        "FEFC e patrimônio vêm de **prestação de contas parcial** do TSE (22/09/2026).",
    ],
    'federal': [
        "Alinhamento usa a **orientação oficial do Governo** (1.133 votações) — não a maioria de "
        "bancada, que mede coesão partidária e erra em até 66 pontos.",
        "**Conversão em lei não discrimina posição no federal**: governo 1,1% e oposição 1,4%. "
        "Não usar como critério.",
        "Emendas cobrem **só transferências especiais** (\"emenda pix\"). Não inclui RP6, RP7 nem "
        "RP8 — o total de cada deputado é maior.",
        "Produção classificada por **regex sobre a ementa** — lê o objetivo declarado, não o "
        "conteúdo nem a constitucionalidade.",
        "2026 é parcial em produção, votação e candidatura.",
    ],
}

TODOS = sorted(list(EST.values()) + FED, key=lambda x: (x['casa'], x['nome']))
json.dump(TODOS, open(f'{OUT}/candidatos.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
json.dump(RESSALVAS, open(f'{OUT}/ressalvas.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f'candidatos: {len(TODOS)}  (estaduais {len(EST)} | federais {len(FED)})')
print(f'  gravado em {OUT}/candidatos.json  '
      f'({os.path.getsize(f"{OUT}/candidatos.json")/1024:.0f} KB)')
print()
for c in TODOS:
    g = f"{c['gov']:.1f}%" if c['gov'] is not None else "—"
    print(f"  [{c['casa'][:3]}] {c['nome'][:30]:<31} {str(c['cargo26'])[:14]:<15} "
          f"gov={g:>6}  PL={c['pl'] or 0:>4}")
