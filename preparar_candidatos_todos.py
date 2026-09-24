#!/usr/bin/env python3
"""Gera data/candidatos-todos.json — os 558 candidatos a dep. estadual, dep. federal
e senador pelo ES, com foto, partido, numero e cargo.

Uso:  python3 preparar_candidatos_todos.py [--pesquisa ~/pesquisa] [--saida data]

Fonte: TSE. O CSV de candidaturas NAO tem foto — o `fotoUrl` vem do endpoint do
DivulgaCandContas, cujo caminho foi descoberto lendo os chunks do proprio app:

  /divulga/rest/v1/candidatura/buscar/{ano}/{sgUe}/{eleicao}/candidato/{sq}

O WAF (Akamai) exige header de navegador: sem `Accept-Language: pt-BR` devolve 403.
"""
import argparse
import csv
import io
import json
import os
import unicodedata
import zipfile
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--pesquisa', default=os.path.expanduser('~/pesquisa'))
ap.add_argument('--saida', default=f'{AQUI}/data')
A = ap.parse_args()
P, OUT = A.pesquisa, A.saida
os.makedirs(OUT, exist_ok=True)

CARGO = {'5': 'Senador', '6': 'Dep. Federal', '7': 'Dep. Estadual'}
ALVO = set(CARGO)


def norm(s):
    return ' '.join(unicodedata.normalize('NFKD', str(s or ''))
                    .encode('ascii', 'ignore').decode().upper().split())


# ── as fotos coletadas (com o fotoUrl oficial de cada uma) ──
fonte = json.load(open(f'{P}/eleicoes-2026/candidatos-fotos.json', encoding='utf-8'))
POR_SQ = {str(x['sq']): x for x in fonte}
print(f'fotos coletadas: {len(POR_SQ)}')

# ── quem eu ja analisei (para marcar e linkar com a ficha) ──
ja = set()
try:
    for c in json.load(open(f'{OUT}/candidatos.json', encoding='utf-8')):
        ja.add(norm(c['nome']))
except FileNotFoundError:
    pass
print(f'ja analisados (tem ficha): {len(ja)}')

# ── as 558 candidaturas do CSV oficial ──
with zipfile.ZipFile(f'{P}/eleicoes-2026/raw/consulta_cand_2026.zip') as z:
    nome = next(x for x in z.namelist() if x.endswith('_ES.csv'))
    with z.open(nome) as fh:
        r = csv.DictReader(io.TextIOWrapper(fh, encoding='latin-1', newline=''), delimiter=';')
        linhas = [x for x in r if x['CD_CARGO'] in ALVO]

DIRF = f'{OUT}/fotos'
saida = []
for x in linhas:
    sq = x['SQ_CANDIDATO']
    f = POR_SQ.get(sq, {})
    arquivo = f'{sq}.jpg'
    tem = os.path.exists(f'{DIRF}/{arquivo}')
    saida.append({
        'sq': sq,
        'nome_urna': x['NM_URNA_CANDIDATO'],
        'nome': x['NM_CANDIDATO'],
        'partido': x['SG_PARTIDO'],
        'numero': x['NR_CANDIDATO'],
        'cargo': CARGO[x['CD_CARGO']],
        'foto': arquivo if tem else None,
        'foto_url': f.get('foto_url'),
        'ocupacao': x.get('DS_OCUPACAO'),
        'situacao': x.get('DS_SITUACAO_CANDIDATURA'),
        'genero': x.get('DS_GENERO'),
        'tem_ficha': norm(x['NM_URNA_CANDIDATO']) in ja or norm(x['NM_CANDIDATO']) in ja,
    })

saida.sort(key=lambda c: (c['cargo'], c['nome_urna']))
json.dump(saida, open(f'{OUT}/candidatos-todos.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f'\ncandidatos: {len(saida)}')
print('  por cargo ....', dict(Counter(c['cargo'] for c in saida)))
print('  com foto .....', sum(1 for c in saida if c['foto']))
print('  com ficha ....', sum(1 for c in saida if c['tem_ficha']))
part = Counter(c['partido'] for c in saida)
print(f'  partidos ..... {len(part)}')
print(f'\ngravado {OUT}/candidatos-todos.json ({os.path.getsize(f"{OUT}/candidatos-todos.json")/1024:.0f} KB)')
