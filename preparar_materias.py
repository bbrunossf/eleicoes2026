#!/usr/bin/env python3
"""Gera data/materias.json — propostas por candidato, temas, funil e votacoes.

Uso:  python3 preparar_materias.py [--pesquisa ~/pesquisa] [--saida data]

Junta:
  ales/data/proposicoes_legislativas.jsonl   propostas (ementa, autor, tramitacao)
  ales/data/parlamentares.json               foto do parlamentar (URL, nao baixada)
  ales-votos/rvps_completo.json + raw/*.pdf  boletins -> quem votou o que
  data/candidatos.json                       quem e' candidato (gerado por preparar_dados.py)
"""
import argparse
import json
import os
import re
import subprocess
from collections import Counter, defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--pesquisa', default=os.path.expanduser('~/pesquisa'))
ap.add_argument('--saida', default=f'{AQUI}/data')
ap.add_argument('--ementa-max', type=int, default=320,
                help='trunca a ementa neste tamanho (a UI mostra titulo, nao o texto todo)')
A = ap.parse_args()
P, OUT, MAXE = A.pesquisa, A.saida, A.ementa_max
RAW = f'{P}/ales-votos/raw'
os.makedirs(OUT, exist_ok=True)


# ═══════════ classificador de objetivo (mesmas regras da pesquisa) ═══════════
def limpa(e):
    u = ' '.join(str(e).split()).upper()
    u = re.sub(r'^(PROJETO\s+DE\s+LEI|PROJETO\s+LEI)\s*(COMPLEMENTAR)?\s*(N[ºO°\.\s\d/]*)?\s*', '', u)
    u = re.sub(r'^(,|\s)+', '', u)
    u = re.sub(r'^,?\s*(DE\s+AUTORIA\s+)?(DO|DA|DOS|DAS)\s+DEPUTAD(O|A)\s+[A-ZÀ-Ú][A-ZÀ-Ú\s\.]{2,40}?\s+QUE\s+', '', u)
    u = re.sub(r'^,?\s*O\s+DEPUTAD(O|A)\s+[A-ZÀ-Ú][A-ZÀ-Ú\s\.]{2,40}?\s+', '', u)
    u = re.sub(r'^,?\s*DE\s+AUTORIA\s+(DO|DA)\s+DEPUTAD(O|A)\s+[A-ZÀ-Ú][A-ZÀ-Ú\s\.]{2,40}?\s+', '', u)
    u = re.sub(r'^\s*[“"]+', '', u)
    return u.strip()


SIMB = [
    (r'UTILIDADE\s+P[ÚU]BLICA', 'utilidade pública'),
    (r'ACRESCENTA\s+(ITEM|AO\s+ANEXO|O\s+ITEM)|ACRESCENTA.{0,50}ANEXO|ALTERA\s+O\s+ITEM\s+\d', 'denominação (anexo)'),
    (r'DENOMINA|PASS[AE]\s+A\s+DENOMINAR|D[ÁA]\s+O\s+NOME\s+DE|DENOMINAR', 'denominação'),
    (r'DIA\s+(ESTADUAL|NACIONAL|DO|DA|MUNICIPAL)|INSTITUI.{0,40}(DIA|SEMANA|M[ÊE]S)\s+(ESTADUAL|NACIONAL)', 'data comemorativa'),
    (r'PATRIM[ÔO]NIO\s+CULTURAL|RECONHECE.{0,60}(FESTA|PATRIM[ÔO]NIO|MANIFESTA[ÇC][ÃA]O|CULTURAL|ROTA)|FICA\s+RECONHECID|RECONHECE\s+O\s+CIRCUITO|DECLARA.{0,30}PATRIM[ÔO]NIO', 'patrimônio / festa'),
    (r'T[ÍI]TULO\s+DE|MEDALHA|HOMENAGEM|CONGRATULA[ÇC][ÃA]O|MO[ÇC][ÃA]O\s+DE\s+APLAUSO|SESS[ÃA]O\s+SOLENE', 'homenagem'),
    (r'CALEND[ÁA]RIO\s+OFICIAL', 'calendário'),
]
SUBS = [
    (r'PRO[ÍI]BE|PROIBI[ÇC][ÃA]O|PROIBID|VEDA|VEDA[ÇC][ÃA]O|COMBATE|PREVINE|PUNI[ÇC][ÃA]O|SAN[ÇC][ÃA]O\s+A', 'proibição / vedação'),
    (r'ASSEGURA|GARANTE|GARANTIA|DIREITO\s+D[AE]|DIGNIDADE', 'direito / garantia'),
    (r'OBRIGA|FICA\s+O\s+(PODER|ESTADO|GOVERNO|MUNIC[ÍI]PIO)|OBRIGATORIEDADE|DEVER\s+D[AE]|TORNA\s+OBRIGAT', 'obrigação estatal'),
    (r'ISEN[ÇC][ÃA]O|ISENTA|BENEF[ÍI]CIO|DESCONTO|SUBVEN|AUX[ÍI]LIO|BOLSA|GRATUIDADE|COTA|SUBS[ÍI]DIO|INCENTIVO', 'benefício / incentivo'),
    (r'INSTITUI.{0,30}(PROGRAMA|POL[ÍI]TICA|PLANO|SISTEMA|CAMPANHA|PROTOCOLO|PASSAPORTE|ROTA|CIRCUITO)|CRIA.{0,30}(PROGRAMA|POL[ÍI]TICA|PLANO|SISTEMA|CAMPANHA|PROJETO|CADASTRO|CENTRO|N[ÚU]CLEO|FUNDO|ROTA|CIRCUITO|BANCO)|DISP[ÕO]E\s+SOBRE\s+O\s+“?PROGRAMA', 'programa / política pública'),
    (r'DIRETRIZES|ESTABELECE\s+NORMAS|DISP[ÕO]E\s+SOBRE\s+NORMAS|NORMAS\s+(GERAIS|PARA)|REGULAMENTA|DISP[ÕO]E\s+SOBRE\s+OS?\s+PROCEDIMENTOS|DISP[ÕO]E\s+SOBRE\s+A\s+(UTILIZA[ÇC][ÃA]O|GEST[ÃA]O|COMERCIALIZA|REGULAMENTA)', 'regulamentação'),
    (r'ALTERA\s+(A\s+LEI|O\s+ART|A\s+REDA[ÇC][ÃA]O|O\s+DECRETO|O\s+ANEXO)|ACRESCENTA\s+(O\s+ART|PAR[ÁA]GRAFO|INCISO|AL[ÍI]NEA|ITEM)|REVOGA|D[ÁA]\s+NOVA\s+REDA[ÇC][ÃA]O|CONSOLIDA|^ACRESCENTA.{0,40}(ART|LEI|DECRETO)', 'altera norma'),
    (r'TRIBUT|IMPOSTO|ICMS|AL[ÍI]QUOTA|ARRECADA|FISCAL|OR[ÇC]AMENT|CR[ÉE]DITO\s+P[ÚU]BLICO|REN[ÚU]NCIA\s+DE\s+RECEITA', 'tributo / fiscal'),
    (r'POLIC|SEGURAN[ÇC]A\s+P[ÚU]BLICA|MILITAR|BOMBEIR|PENA|CRIME|PRIS[ÃA]O|DROGA|ARMA', 'segurança pública'),
    (r'SA[ÚU]DE|SUS|HOSPITAL|MEDIC|SANIT|VACIN|DOEN[ÇC]A|ENFERMAGEM|ODONTO|PSICOL', 'saúde'),
    (r'EDUCA|ESCOLA|ENSINO|UNIVERSID|PROFESSOR|ALUNO|CAPACITA|CRECHE|FACULDADE', 'educação'),
    (r'AMBIENT|CLIMA|DESMAT|FLOREST|[ÁA]GUA|RES[ÍI]DUO|SANEA|ENERGIA|SOLAR|FOTOVOLTAIC|E[ÓO]LICA', 'meio ambiente / energia'),
    (r'SERVIDOR|VENCIMENTO|SUBS[ÍI]DIO|CARGO|CONCURSO|EST[ÁA]GIO|QUADRO\s+DE\s+PESSOAL|APOSENTAD|PREVID', 'servidor público'),
    (r'TRANSPORTE|RODOVI|MOBILIDADE|TR[ÂA]NSITO|ESTRADA|ASFALT|FERROVI|PORTU[ÁA]RIO|SANEAR?MENTO\s+B[ÁA]SICO|HABITA', 'infraestrutura / transporte'),
    (r'AGRICULT|AGROPECU|PRODUTOR\s+RURAL|PESCA|CAF[ÉE]|LEITE|AGROIND', 'agricultura'),
    (r'EMPRESA|IND[ÚU]STRIA|COM[ÉE]RCIO|TURISMO|COOPERATIV|MICROEMPRESA|EMPREENDEDOR|ECON[ÔO]MICO|MERCADO', 'economia produtiva'),
    (r'MULHER|CRIAN[ÇC]A|ADOLESC|IDOSO|IND[ÍI]GENA|QUILOMBOLA|RACIAL|DEFICI[ÊE]NCIA|AUTIS|LGBT|FAM[ÍI]LIA|FEMINIC[ÍI]DIO|M[ÃA]E\s+SOLO', 'direitos de grupos'),
    (r'CULTUR|ARTIST|M[ÚU]SICA|TEATRO|ESPORTE|DESPORTO|LAZER', 'cultura / esporte'),
]


def classifica(e):
    u = limpa(e)
    for rx, nome in SIMB:
        if re.search(rx, u):
            return 'simbólica', nome
    for rx, nome in SUBS:
        if re.search(rx, u):
            return 'substantiva', nome
    if re.match(r'^(DISP[ÕO]E|ESTABELECE|TRATA|DEFINE|AUTORIZA|CRIA|INSTITUI)', u):
        return 'substantiva', 'genérico'
    return 'indefinida', 'sem marcador'


NORMA = re.compile(r'Norma Sancionada|Norma Promulgada', re.I)


# ═══════════ 1. candidatos e foto ═══════════
cands = json.load(open(f'{OUT}/candidatos.json', encoding='utf-8'))
EST = {c['nome'].upper(): c for c in cands if c['casa'] == 'Estadual'}
FOTOS = {}
for a in json.load(open(f'{P}/ales/data/parlamentares.json', encoding='utf-8')):
    FOTOS[a['parlamentarNome'].upper()] = a.get('parlamentarFoto')
print(f'candidatos estaduais: {len(EST)} | com foto: {sum(1 for f in FOTOS.values() if f)}')

# ═══════════ 2. propostas ═══════════
# Liga por AUTORID, nao por nome. O nomeRazao da API diverge do parlamentarNome em 3 casos
# reais: "ENGENHERIO JOSE ESMERALDO" (typo), "FABIO DUARTE DE ALMEIDA" (nome civil) e
# "JULIO CEZAR MENDEL" (nome de urna diferente). Por nome, esses 3 ficavam com producao ZERO.
#
# Qual campo de autor? Medido: `_autorID_consultado` reproduz os numeros do perfil_final.json
# que o app ja mostra (16 de 16 conferidos); `AutorRequerenteDados.autorId` reproduz 1 de 16.
# Como o resto do app usa o primeiro criterio, esta secao usa o MESMO — senao o app
# mostraria 335 num lugar e 326 em outro para o mesmo deputado.
NOME_POR_ID = {str(a['autorID']): a['parlamentarNome'] for a in
               json.load(open(f'{P}/ales/data/parlamentares.json', encoding='utf-8'))}

props = defaultdict(list)
sem_id = 0
for ln in open(f'{P}/ales/data/proposicoes_legislativas.jsonl', encoding='utf-8'):
    x = json.loads(ln)
    if str(x.get('ano')) not in ('2023', '2024', '2025', '2026'):
        continue
    if x['sigla'] not in ('PL', 'PLC'):
        continue
    aid = str(x.get('_autorID_consultado')
              or (x.get('AutorRequerenteDados') or {}).get('autorId') or '')
    nome_ales = NOME_POR_ID.get(aid)
    if not nome_ales or nome_ales.upper() not in EST:
        sem_id += 1
        continue
    tram = x.get('Tramitacoes') or []
    ementa = ' '.join(str(x.get('assunto') or '').split())
    props[nome_ales.upper()].append({
        'sigla': x['sigla'], 'numero': int(x['numero']), 'ano': int(x['ano']),
        'ementa': ementa[:MAXE], 'situacao': x.get('situacao'),
        'virou_lei': bool(NORMA.search(' | '.join(str(t.get('fase', '')) for t in tram))),
        'tramitacao': len(tram),
    })
print(f'propostas: {sum(len(v) for v in props.values())} | descartadas (autor fora): {sem_id}')
faltando = [n for n in EST if n not in props]
print(f'candidatos sem propostas: {faltando or "nenhum"}')

# ═══════════ 3. votacoes dos boletins ═══════════
SIGLA = {'PROJETO DE LEI COMPLEMENTAR': 'PLC', 'PROJETO DE LEI': 'PL'}
RX_PROP = re.compile(r'(PROJETO DE LEI COMPLEMENTAR|PROJETO DE LEI)\s*n[º°]?\s*(\d+)\s*/?\s*(\d{4})', re.I)
RX_VOTO = re.compile(
    r'^\s*(?P<nome>[A-ZÀ-Ú][A-ZÀ-Ú\.\s]{3,40}?)\s*\((?P<part>[A-ZÀ-Ú/]{2,12})\)\s+'
    r'(?P<voto>Sim|Não votou|Não|Abstenção|Ausente)(?:\s+\d{2}:\d{2}:\d{2})?\s*$')

VOTACOES = {}
ilegiveis = 0
for r in json.load(open(f'{P}/ales-votos/rvps_completo.json', encoding='utf-8')):
    f = f"{RAW}/rvp_{r['id']}.pdf"
    if not os.path.exists(f):
        continue
    txt = subprocess.run(['pdftotext', '-layout', f, '-'],
                         capture_output=True, text=True).stdout
    m = RX_PROP.search(txt)
    if not m:
        continue
    votos = {}
    for l in txt.splitlines():
        mv = RX_VOTO.match(l)
        if mv:
            votos[mv.group('nome').strip()] = mv.group('voto')
    if len(votos) < 10:
        ilegiveis += 1
        continue
    chave = f'{SIGLA[m.group(1).upper().strip()]} {int(m.group(2))}/{int(m.group(3))}'
    VOTACOES[chave] = {'boletim': r['id'], 'data': r.get('data'),
                       'placar': dict(Counter(votos.values())), 'votos': votos}
print(f'votacoes com placar: {len(VOTACOES)} | boletins ilegiveis/descartados: {ilegiveis}')

# ═══════════ 4. monta ═══════════
saida = {'candidatos': {}, 'votacoes': VOTACOES}
for nome in EST:                       # TODOS os candidatos, mesmo sem proposta
    lista = props.get(nome, [])
    temas = defaultdict(lambda: defaultdict(int))
    leis = 0
    for p in lista:
        tipo, sub = classifica(p['ementa'])
        temas[tipo][sub] += 1
        if p['virou_lei']:
            leis += 1
    for p in lista:
        tipo, sub = classifica(p['ementa'])
        p['categoria'] = tipo
        p['tema'] = sub
        p['votacao'] = f"{p['sigla']} {p['numero']}/{p['ano']}" in VOTACOES
    mortas = sum(1 for p in lista if not p['virou_lei'] and p['situacao'] == 'Arquivado')
    saida['candidatos'][nome] = {
        'nome': EST[nome]['nome'],
        'partido': EST[nome].get('partido'),
        'cargo26': EST[nome].get('cargo26'),
        'foto': FOTOS.get(nome),
        'temas': {k: dict(sorted(v.items(), key=lambda x: -x[1])) for k, v in temas.items()},
        'funil': {
            'protocoladas': len(lista),
            'virou_lei': leis,
            'morreu': mortas,
            'tramitando': len(lista) - leis - mortas,
            'com_votacao': sum(1 for p in lista if p['votacao']),
        },
        'propostas': sorted(lista, key=lambda p: (-p['ano'], -p['numero'])),
    }

json.dump(saida, open(f'{OUT}/materias.json', 'w', encoding='utf-8'),
          ensure_ascii=False, separators=(',', ':'))
tam = os.path.getsize(f'{OUT}/materias.json')
print(f'\ngravado {OUT}/materias.json — {tam/1024:.0f} KB')
print(f'  candidatos: {len(saida["candidatos"])} | votacoes: {len(VOTACOES)}')

print('\n=== amostra ===')
for n in ('CORONEL WELITON', 'DENNINHO SILVA'):
    c = saida['candidatos'].get(n)
    if not c:
        continue
    f_ = c['funil']
    print(f"\n{c['nome']} ({c['partido']}) — {c['cargo26']}")
    print(f"  funil: protocoladas {f_['protocoladas']} | virou lei {f_['virou_lei']} "
          f"| morreu {f_['morreu']} | tramitando {f_['tramitando']} | com votacao {f_['com_votacao']}")
    print(f"  temas: simbólica {sum(c['temas'].get('simbólica', {}).values())} "
          f"| substantiva {sum(c['temas'].get('substantiva', {}).values())}")
    print(f"  top subtemas: {list(c['temas'].get('simbólica', {}).items())[:3]} + "
          f"{list(c['temas'].get('substantiva', {}).items())[:3]}")
