"""Eleições ES 2026 — painel de avaliação de candidatos.

Roda com:  .venv/bin/streamlit run app.py

Os dados vêm de data/candidatos.json, gerado por preparar_dados.py a partir da pesquisa
em ~/pesquisa. Este app só apresenta — nenhum número é calculado aqui.
"""
import json
import os
from collections import Counter
from html import escape as esc

import altair as alt
import pandas as pd
import streamlit as st

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = json.load(open(f'{AQUI}/data/candidatos.json', encoding='utf-8'))
RESSALVAS = json.load(open(f'{AQUI}/data/ressalvas.json', encoding='utf-8'))
MAT = json.load(open(f'{AQUI}/data/materias.json', encoding='utf-8'))
MAT_CAND = MAT['candidatos']
MAT_VOT = MAT['votacoes']
TODOS = json.load(open(f'{AQUI}/data/candidatos-todos.json', encoding='utf-8'))
# as fotos ficam em ./static/ e sao servidas pelo Streamlit em /app/static/...
# (server.enableStaticServing = true no .streamlit/config.toml)
URL_FOTOS = 'app/static/fotos'

st.set_page_config(page_title='Eleições ES 2026', page_icon='🗳️', layout='wide')

# ─── estado ───
if 'filtros' not in st.session_state:
    st.session_state.filtros = {}

df = pd.DataFrame(DADOS)
# Colunas que guardam lista/dict (emendas_destinos, emendas_planos) viram coluna 'object'
# com NaN misturado, e o pyarrow nao converte: "Expected bytes, got a 'float' object".
# O Streamlit se recupera sozinho, mas loga erro a cada rerun — entao normalizo aqui.
for _col in ('emendas_destinos', 'emendas_planos'):
    if _col in df.columns:
        df[_col] = df[_col].apply(
            lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else '')
df['subst_pct'] = (df['subst'] / df['pl'] * 100).where(df['pl'] > 0)
df['conversao_pct'] = (df['leis'] / df['pl'] * 100).where(df['pl'] > 0)
df['rotulo'] = df['nome'].str.title()

PARTIDOS = sorted({p for p in df['partido'].dropna() if p})
CARGOS = sorted({c for c in df['cargo26'].dropna() if c})


def faixa(g):
    if pd.isna(g):
        return 'sem dado'
    if g >= 85:
        return 'Alinhado ao governo (≥85%)'
    if g >= 75:
        return 'Majoritariamente governo (75–85%)'
    if g >= 40:
        return 'Dividido (40–75%)'
    return 'Oposição (<40%)'


df['faixa_gov'] = df['gov'].apply(faixa)

# ─── sidebar: filtros ───
st.sidebar.title('Filtros')
casas = st.sidebar.multiselect('Casa', ['Estadual', 'Federal'], default=['Estadual', 'Federal'])
partidos = st.sidebar.multiselect('Partido', PARTIDOS, default=[])
cargos = st.sidebar.multiselect('Candidatura 2026', CARGOS, default=[])
min_gov = st.sidebar.slider('Alinhamento mínimo ao governo (%)', 0, 100, 0, 5,
                            help='Votações com posição declarada em que acompanhou o governo.')
so_com_voto = st.sidebar.checkbox('Só quem tem dado de voto', value=False)

st.sidebar.divider()
st.sidebar.caption('Os números vêm da pesquisa em `~/pesquisa`. '
                   'Leia a aba **Método** antes de concluir qualquer coisa.')

# ─── aplica filtros ───
f = df[df['casa'].isin(casas)]
if partidos:
    f = f[f['partido'].isin(partidos)]
if cargos:
    f = f[f['cargo26'].isin(cargos)]
f = f[(f['gov'].isna()) | (f['gov'] >= min_gov)]
if so_com_voto:
    f = f[f['gov'].notna()]

# ─── cabecalho ───
st.title('Eleições ES 2026')
st.caption('Quem já ocupa cargo e está na disputa — deputados estaduais (ALES), '
           'deputados federais (Câmara) e quem concorre a outro cargo.')
st.caption(f'{len(f)} de {len(df)} candidatos segundo os filtros · '
           f'{int(f["casa"].eq("Estadual").sum())} estaduais e '
           f'{int(f["casa"].eq("Federal").sum())} federais · eleição em 04/10/2026')

med = f['gov'].mean()
producao = f'{int(f["pl"].fillna(0).sum()):,}'.replace(',', '.')   # 3.486, so' no valor
# KPIs em HTML+CSS, nao st.metric: no celular o st.columns empilha e 4 metricas
# gastam meia tela antes de qualquer conteudo. Aqui vira 2x2 no celular e 1x4 no desktop.
st.markdown(f"""
<style>
.kpis {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 6px 0 2px; }}
@media (min-width: 700px) {{ .kpis {{ grid-template-columns: repeat(4, 1fr); gap: 16px; }} }}
.kpi {{ background: #f7f8fa; border: 1px solid #e6e8ec; border-radius: 8px; padding: 9px 11px; }}
.kpi .lbl {{ font-size: 0.72rem; color: #6b7280; line-height: 1.25; }}
.kpi .val {{ font-size: 1.5rem; font-weight: 650; line-height: 1.25; }}
@media (max-width: 699px) {{ .kpi .val {{ font-size: 1.25rem; }} }}
</style>
<div class="kpis">
  <div class="kpi"><div class="lbl">Candidatos</div><div class="val">{len(f)}</div></div>
  <div class="kpi"><div class="lbl">Com dado de voto</div>
       <div class="val">{int(f['gov'].notna().sum())}</div></div>
  <div class="kpi"><div class="lbl">Alinhamento médio</div>
       <div class="val">{f'{med:.1f}%' if pd.notna(med) else '—'}</div></div>
  <div class="kpi"><div class="lbl">Produção total</div>
       <div class="val">{producao}</div></div>
</div>
""", unsafe_allow_html=True)

st.divider()

aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs(
    ['📍 Posição', '🔎 Ficha', '📜 Matérias', '🖼️ Candidatos', '💰 Emendas', '⚠️ Método'])

# ═══════════════════ 1. POSICIONAMENTO ═══════════════════
with aba1:
    st.subheader('Eixo governo × produção')
    st.caption('Cada ponto é um candidato. O eixo X diz **onde** ele se posiciona; o Y, **o que ele produz**. '
               'Tamanho = volume de projetos. Passe o mouse para ver quem é.')

    base = f[f['gov'].notna() & f['subst_pct'].notna()].copy()
    if base.empty:
        st.info('Nenhum candidato com dado suficiente para o gráfico.')
    else:
        pontos = alt.Chart(base).mark_circle(opacity=0.75, stroke='white', strokeWidth=1).encode(
            x=alt.X('gov:Q', title='Alinhamento ao governo (%)', scale=alt.Scale(domain=[0, 100])),
            y=alt.Y('subst_pct:Q', title='Produção substantiva (%)', scale=alt.Scale(domain=[0, 105])),
            size=alt.Size('pl:Q', title='Projetos', scale=alt.Scale(range=[60, 900])),
            color=alt.Color('casa:N', title='Casa',
                            scale=alt.Scale(domain=['Estadual', 'Federal'],
                                            range=['#4C78A8', '#E45756'])),
            tooltip=[alt.Tooltip('rotulo:N', title='Candidato'),
                     alt.Tooltip('partido:N', title='Partido'),
                     alt.Tooltip('cargo26:N', title='Candidatura'),
                     alt.Tooltip('gov:Q', title='Alinhamento governo', format='.1f'),
                     alt.Tooltip('subst_pct:Q', title='Substantiva %', format='.1f'),
                     alt.Tooltip('pl:Q', title='Projetos'),
                     alt.Tooltip('leis:Q', title='Leis')],
        )
        linha = alt.Chart(pd.DataFrame({'x': [50]})).mark_rule(
            strokeDash=[4, 4], color='#999').encode(x='x:Q')
        st.altair_chart((pontos + linha).properties(height=460), width='stretch')

        st.caption('A linha tracejada em 50% separa governo de oposição. '
                   'No estadual o alinhamento é medido por **voto em veto** (proxy); '
                   'no federal, pela **orientação oficial do Governo**.')

    st.subheader('A tabela')
    st.caption('Clique nos cabeçalhos para ordenar.')

    tab = f[['rotulo', 'casa', 'partido', 'cargo26', 'gov', 'posicionamento',
             'pl', 'subst_pct', 'leis', 'conversao_pct', 'fefc', 'patrimonio']].copy()
    tab.columns = ['Candidato', 'Casa', 'Partido', 'Candidatura 2026', 'Alinh. governo %',
                   'Posicionamento %', 'Projetos', 'Substantiva %', 'Leis', 'Conversão %',
                   'FEFC (R$)', 'Patrimônio (R$)']
    st.dataframe(
        tab, width='stretch', hide_index=True, height=460,
        column_config={
            'Alinh. governo %': st.column_config.ProgressColumn(
                format='%.1f%%', min_value=0, max_value=100),
            'Posicionamento %': st.column_config.NumberColumn(format='%.1f%%'),
            'Substantiva %': st.column_config.NumberColumn(format='%.1f%%'),
            'Conversão %': st.column_config.NumberColumn(format='%.1f%%'),
            'FEFC (R$)': st.column_config.NumberColumn(format='R$ %.2f'),
            'Patrimônio (R$)': st.column_config.NumberColumn(format='R$ %.2f'),
        })

    st.warning('**Conversão em lei engana nas duas casas.** No estadual ela mede posição na '
               'coalizão (governo ~42% contra oposição ~20%) — o Coronel Weliton converte 18,2% '
               'nomeando prédios. No federal ela não discrimina: governo 1,1% e oposição 1,4%. '
               'Não ordene por essa coluna.')

# ═══════════════════ 2. FICHA ═══════════════════
with aba2:
    nomes = sorted(f['nome'].dropna().unique()) if not f.empty else sorted(df['nome'].unique())
    if not nomes:
        st.info('Nenhum candidato com os filtros atuais.')
    else:
        escolha = st.selectbox('Candidato', nomes, index=0, key='ficha_escolha')
        r = df[df['nome'] == escolha].iloc[0]

        st.subheader(f'{r["nome"].title()}')
        st.markdown(f'**{r["partido"] or "—"}** · candidato a **{r["cargo26"] or "—"}** em 2026 · '
                    f'{"Deputado Estadual em exercício (ALES)" if r["casa"] == "Estadual" else "Deputado Federal · Espírito Santo"}')

        if r.get('cobertura_incompleta'):
            st.warning('**Cobertura incompleta.** Há produção medida, mas **nenhum voto nominal** '
                       'deste parlamentar entrou na extração. As dimensões 1, 2 e 4 saem sem dado. '
                       'Não leia a ausência como oposição — é ausência na fonte.')

        k1, k2, k3, k4 = st.columns(4)
        k1.metric('Eixo governo', f'{r["gov"]:.1f}%' if pd.notna(r['gov']) else '—',
                  help='Votações com posição declarada em que acompanhou o governo.')
        k2.metric('Posicionamento',
                  f'{r["posicionamento"]:.1f}%' if pd.notna(r['posicionamento']) else '—',
                  help='Fatia das votações em que registrou voto, em vez de abster-se ou ausentar-se.')
        k3.metric('Produção substantiva',
                  f'{r["subst_pct"]:.0f}%' if pd.notna(r['subst_pct']) else '—',
                  help='Proporção da produção que propõe política pública, em vez de homenagem.')
        k4.metric('Leis', f'{int(r["leis"])}' if pd.notna(r['leis']) else '—',
                  help='Propostas que viraram norma. Cuidado: mede coalizão, não qualidade.')

        st.divider()
        e1, e2 = st.columns(2)
        with e1:
            st.markdown('#### Onde se posiciona')
            g = r['gov']
            if pd.isna(g):
                st.write('Sem dado de posicionamento suficiente.')
            elif g >= 85:
                st.write(f'Alinhado ao governo em **{g:.1f}%** das votações com posição declarada. '
                         f'Vota consistentemente com o bloco do governador.')
            elif g >= 75:
                st.write(f'Majoritariamente com o governo (**{g:.1f}%**), mas com divergência '
                         f'relevante ({100-g:.1f}% contra). Não é voto de cabresto.')
            elif g >= 40:
                st.write(f'**{g:.1f}%** de alinhamento — perto da metade. Perfil dividido, sem '
                         f'alinhamento claro com governo ou oposição.')
            else:
                st.write(f'**Oposição**: alinha com o governo em apenas **{g:.1f}%** das votações. '
                         f'{100-g:.1f}% contra.')

            p = r['posicionamento']
            if pd.notna(p):
                if p < 30:
                    st.error(f'**Atenção:** posicionou-se em apenas {p:.1f}% das '
                             f'{int(r["vot_total"])} votações. A ausência de voto não é oposição '
                             f'— é ausência de posição.')
                else:
                    st.write(f'Posicionou-se em **{p:.1f}%** das {int(r["vot_total"])} votações nominais.')

        with e2:
            st.markdown('#### O que produz')
            if pd.notna(r['subst_pct']):
                st.write(f'**{r["subst_pct"]:.0f}%** da produção é substantiva — '
                         f'{int(r["subst"])} de {int(r["pl"])} propostas.')
                if r['subst_pct'] < 40:
                    st.warning('Produção majoritariamente **simbólica** — nomeação de próprio, '
                               'utilidade pública, homenagem. Passa fácil e não muda política pública.')
            if pd.notna(r['leis']):
                st.write(f'**{int(r["leis"])} viraram lei** em {int(r["pl"])} propostas '
                         f'({r["conversao_pct"]:.1f}%).')

        st.divider()
        d1, d2 = st.columns(2)
        d1.metric('Fundo eleitoral (FEFC)', f'R$ {r["fefc"]:,.2f}'.replace(',', '.')
                  if pd.notna(r['fefc']) else '—')
        d2.metric('Patrimônio declarado', f'R$ {r["patrimonio"]:,.2f}'.replace(',', '.')
                  if pd.notna(r['patrimonio']) else '—')

        if pd.notna(r.get('emendas_valor')) and r['emendas_valor']:
            st.divider()
            st.markdown('#### O que entrega')
            st.write(f'**{int(r["emendas_n"])} emendas** de transferência especial ("emenda pix"), '
                     f'**R$ {r["emendas_valor"]:,.2f}**'.replace(',', '.') +
                     ' em planos de ação.')
            # emendas_destinos virou string JSON na normalizacao do df (ver topo do arquivo)
            dest = pd.DataFrame(json.loads(r['emendas_destinos'] or '[]'),
                                columns=['Destino', 'Valor (R$)'])
            dest['Destino'] = dest['Destino'].str.title()
            st.dataframe(dest, width='stretch', hide_index=True,
                         column_config={'Valor (R$)': st.column_config.NumberColumn(format='R$ %.2f')})
            st.caption('Cobre só transferências especiais. Não inclui RP6, RP7 nem RP8.')

# ═══════════════════ 3. MATÉRIAS E VOTOS ═══════════════════
with aba3:
    st.subheader('O que o candidato propôs — e o que virou lei')
    st.caption('Propostas de autoria própria na legislatura 20 (2023–2026), classificadas pelo '
               'objetivo declarado na ementa. Fonte: API de dados abertos da ALES.')

    est = sorted(MAT_CAND.keys())
    if not est:
        st.info('Sem dados de matérias.')
    else:
        # mantém a escolha da aba Ficha, se houver
        padrao = 0
        if 'ficha_escolha' in st.session_state:
            try:
                padrao = est.index(st.session_state['ficha_escolha'].upper())
            except ValueError:
                padrao = 0
        sel = st.selectbox('Candidato', est, index=padrao,
                           format_func=lambda k: MAT_CAND[k]['nome'].title(), key='mat_sel')
        c = MAT_CAND[sel]
        fun = c['funil']
        simb = sum(c['temas'].get('simbólica', {}).values())
        subst = sum(c['temas'].get('substantiva', {}).values())
        indef = sum(c['temas'].get('indefinida', {}).values())
        total = fun['protocoladas'] or 1

        # ── indicadores macro ──
        # KPIs em HTML: 5 metricas em st.columns viram 5 linhas empilhadas no celular.
        # Aqui: 2 por linha no celular, 5 no desktop.
        st.markdown(f"""
<style>
.kpis-mat {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 9px; margin: 4px 0 2px; }}
@media (min-width: 760px) {{ .kpis-mat {{ grid-template-columns: repeat(5, 1fr); gap: 14px; }} }}
.kpis-mat .kpi {{ background: #f7f8fa; border: 1px solid #e6e8ec; border-radius: 8px; padding: 9px 11px; }}
.kpis-mat .lbl {{ font-size: 0.7rem; color: #6b7280; line-height: 1.25; min-height: 2.1em; }}
.kpis-mat .val {{ font-size: 1.35rem; font-weight: 650; line-height: 1.2; }}
.kpis-mat .sub {{ font-size: 0.68rem; color: #6b7280; }}
</style>
<div class="kpis-mat">
  <div class="kpi"><div class="lbl">Propostas</div><div class="val">{fun['protocoladas']}</div>
       <div class="sub">PL + PLC</div></div>
  <div class="kpi"><div class="lbl">Viraram lei</div><div class="val">{fun['virou_lei']}</div>
       <div class="sub">{fun['virou_lei']/total*100:.1f}% do total</div></div>
  <div class="kpi"><div class="lbl">Substantivas</div><div class="val">{subst/total*100:.0f}%</div>
       <div class="sub">{subst} propostas</div></div>
  <div class="kpi"><div class="lbl">Simbólicas</div><div class="val">{simb/total*100:.0f}%</div>
       <div class="sub">{simb} propostas</div></div>
  <div class="kpi"><div class="lbl">Com votação nominal</div><div class="val">{fun['com_votacao']}</div>
       <div class="sub">{fun['com_votacao']/total*100:.1f}% do total</div></div>
</div>
""", unsafe_allow_html=True)

        # ── funil ──
        st.markdown('#### O funil da proposta')
        etapas = pd.DataFrame([
            {'etapa': 'Protocoladas', 'n': fun['protocoladas']},
            {'etapa': 'Ainda tramitando', 'n': fun['tramitando']},
            {'etapa': 'Viraram lei', 'n': fun['virou_lei']},
            {'etapa': 'Morreram (arquivadas sem lei)', 'n': fun['morreu']},
        ])
        st.altair_chart(
            alt.Chart(etapas).mark_bar().encode(
                x=alt.X('n:Q', title='propostas'),
                y=alt.Y('etapa:N', sort=None, title=None),
                color=alt.Color('etapa:N', legend=None,
                                scale=alt.Scale(domain=['Protocoladas', 'Ainda tramitando',
                                                        'Viraram lei', 'Morreram (arquivadas sem lei)'],
                                                range=['#4C78A8', '#B0B0B0', '#54A24B', '#E45756'])),
                tooltip=['etapa', alt.Tooltip('n:Q', title='propostas')],
            ).properties(height=170), width='stretch')
        st.caption('Cuidado: **arquivado não é fracasso** — é o último passo de um projeto que '
                   'virou lei. Por isso "virou lei" e "morreu" são contados pela tramitação '
                   '(fase "Norma Sancionada"), não pela situação do registro.')

        # ── temas ──
        st.markdown('#### Decomposto por tema')
        t1, t2 = st.columns(2)
        with t1:
            st.markdown('**Substantivas** — propõem política pública')
            d = pd.DataFrame(list(c['temas'].get('substantiva', {}).items()),
                             columns=['tema', 'n'])
            if d.empty:
                st.caption('nenhuma')
            else:
                st.dataframe(d.sort_values('n', ascending=False), hide_index=True,
                             width='stretch', height=210)
        with t2:
            st.markdown('**Simbólicas** — homenagem, nomeação, utilidade pública')
            d = pd.DataFrame(list(c['temas'].get('simbólica', {}).items()),
                             columns=['tema', 'n'])
            if d.empty:
                st.caption('nenhuma')
            else:
                st.dataframe(d.sort_values('n', ascending=False), hide_index=True,
                             width='stretch', height=210)
        if indef:
            st.caption(f'{indef} propostas sem marcador classificável.')

        st.divider()

        # ── 3 colunas: foto | propostas | votos ──
        col_foto, col_prop, col_voto = st.columns([1, 2, 2])

        with col_foto:
            if c.get('foto'):
                try:
                    st.image(c['foto'], width='stretch')
                except Exception:
                    st.caption('foto indisponível')
            else:
                st.caption('sem foto')
            st.markdown(f"**{c['nome'].title()}**")
            st.caption(f"{c['partido']} · {c['cargo26']}")
            st.caption('foto: ALES (link direto, não baixada)')

        with col_prop:
            st.markdown('**Propostas**')
            fc1, fc2 = st.columns(2)
            cats = fc1.multiselect('Categoria', ['substantiva', 'simbólica', 'indefinida'],
                                   default=['substantiva', 'simbólica'], key='mat_cat')
            so_leis = fc2.checkbox('Só as que viraram lei', key='mat_leis')
            so_vot = fc2.checkbox('Só as com votação', key='mat_vot')

            props = c['propostas']
            props = [p for p in props
                     if p['categoria'] in cats
                     and (not so_leis or p['virou_lei'])
                     and (not so_vot or p['votacao'])]
            st.caption(f'{len(props)} de {fun["protocoladas"]} propostas')

            if not props:
                st.info('Nenhuma proposta com esses filtros.')
                escolhida = None
            else:
                tab = pd.DataFrame([{
                    'Proposta': f"{p['sigla']} {p['numero']}/{p['ano']}",
                    'Tema': p['tema'],
                    'Título': p['ementa'],
                    'Situação': p['situacao'],
                    'Lei': 'sim' if p['virou_lei'] else '',
                    'Votada': 'sim' if p['votacao'] else '',
                } for p in props])
                ev = st.dataframe(
                    tab, hide_index=True, width='stretch', height=420,
                    on_select='rerun', selection_mode='single-row',
                    column_config={'Título': st.column_config.TextColumn(width='large')})
                linha = ev.selection.rows if ev and ev.selection else []
                escolhida = props[linha[0]] if linha else None
                if not linha:
                    st.caption('Clique numa linha para ver a votação à direita.')

        with col_voto:
            st.markdown('**Como votaram**')
            chave = None
            if escolhida is not None:
                chave = f"{escolhida['sigla']} {escolhida['numero']}/{escolhida['ano']}"
            elif props:
                # sem selecao: mostra a votacao mais recente deste candidato
                for p in props:
                    k = f"{p['sigla']} {p['numero']}/{p['ano']}"
                    if k in MAT_VOT:
                        chave, escolhida = k, p
                        break

            if not chave or chave not in MAT_VOT:
                st.info('Esta proposta não tem votação nominal registrada.')
                st.caption('A maioria das proposições nunca vai a voto nominal — morre em '
                           'comissão ou é arquivada. Das '
                           f'{fun["protocoladas"]} deste candidato, '
                           f'**{fun["com_votacao"]}** têm votação.')
            else:
                v = MAT_VOT[chave]
                pl = v['placar']
                tt = sum(pl.values()) or 1
                st.caption(f'{chave} · boletim {v["boletim"]} · {v.get("data")}')
                k1, k2, k3 = st.columns(3)
                k1.metric('Sim', pl.get('Sim', 0))
                k2.metric('Não', pl.get('Não', 0))
                k3.metric('Sem posição',
                          pl.get('Não votou', 0) + pl.get('Abstenção', 0) + pl.get('Ausente', 0))
                dv = pd.DataFrame(sorted(v['votos'].items(), key=lambda x: x[0]),
                                  columns=['Deputado', 'Voto'])
                st.dataframe(dv, hide_index=True, width='stretch', height=300)
                st.caption('Todos os deputados que estavam na casa, não só este candidato. '
                           '"Não votou" / "Abstenção" / "Ausente" são situações distintas.')

        st.divider()
        st.caption('**Ressalvas desta seção:** a classificação de tema é regex sobre a ementa — '
                   'lê o objetivo **declarado**, não o conteúdo nem a constitucionalidade. '
                   'A votação só existe para as propostas que foram a plenário. '
                   '105 dos 458 boletins não são legíveis por `pdftotext` (fonte sem mapa '
                   'Unicode), então a cobertura de votação é parcial.')

# ═══════════════════ 4. TODOS OS CANDIDATOS ═══════════════════
with aba4:
    st.subheader('Todos os candidatos — dep. estadual, dep. federal e senador pelo ES')
    st.caption('Os 558 candidatos registrados no TSE para os três cargos, em ordem alfabética '
               'dentro de cada cargo. Foto, nome de urna, partido e número. '
               'Fonte: TSE (DivulgaCandContas).')

    if not TODOS:
        st.info('Sem dados de candidatos.')
    else:
        PART_TODOS = sorted({c['partido'] for c in TODOS if c['partido']})
        CARGO_TODOS = ['Dep. Estadual', 'Dep. Federal', 'Senador']

        g1, g2 = st.columns(2)
        f_part = g1.multiselect('Partido', PART_TODOS, default=[], key='todos_part')
        f_busca = g2.text_input('Buscar por nome', key='todos_busca',
                                placeholder='parte do nome')
        g3, g4 = st.columns(2)
        f_cargo = g3.multiselect('Cargo', CARGO_TODOS, default=CARGO_TODOS, key='todos_cargo')
        f_pag = g4.selectbox('Por página', [60, 120, 240, 558], index=0, key='todos_pag')

        sel = [c for c in TODOS
               if c['cargo'] in f_cargo
               and (not f_part or c['partido'] in f_part)
               and (not f_busca.strip()
                    or f_busca.strip().lower() in c['nome_urna'].lower()
                    or f_busca.strip().lower() in c['nome'].lower())]

        # partidos do resultado, para mostrar a distribuição de relance
        dist = Counter(c['partido'] for c in sel)
        st.caption(f'**{len(sel)}** candidatos · **{len(dist)}** partidos · '
                   f'mostrando os primeiros {min(f_pag, len(sel))}')

        if not sel:
            st.info('Nenhum candidato com esses filtros.')
        else:
            pagina = sel[:f_pag]

            # Grade em HTML+CSS, nao st.columns: o st.columns NAO reflui, e no celular
            # cada coluna vira uma linha inteira (foto gigante, uma por linha).
            # 'auto-fill' + 'minmax' deixa o navegador decidir quantas colunas cabem:
            # ~3 no celular, ~7 no tablet, ~11 no desktop.
            st.markdown("""
<style>
.grade-cand {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 12px 10px;
  margin-top: 4px;
}
@media (min-width: 640px)  { .grade-cand { grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); } }
@media (min-width: 1200px) { .grade-cand { grid-template-columns: repeat(auto-fill, minmax(124px, 1fr)); } }
.card-cand { display: flex; flex-direction: column; }
.card-cand img {
  width: 100%;
  aspect-ratio: 161 / 225;
  object-fit: cover;
  border-radius: 6px;
  background: #f0f2f6;
  display: block;
}
.card-cand .nome {
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.2;
  margin-top: 5px;
  /* nome de urna pode ser longo: corta em 2 linhas em vez de estourar a celula */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-cand .meta {
  font-size: 0.68rem;
  color: #6b7280;
  line-height: 1.25;
  margin-top: 2px;
}
@media (max-width: 639px) {
  /* no celular economiza espaco vertical: so' a linha essencial */
  .card-cand .cargo { display: none; }
}
</style>
""", unsafe_allow_html=True)

            cards = []
            for c in pagina:
                foto = (f'<img src="{URL_FOTOS}/{esc(c["foto"])}" alt="{esc(c["nome_urna"])}" '
                        f'loading="lazy" decoding="async">') if c['foto'] else \
                       '<div style="aspect-ratio:161/225;background:#f0f2f6;border-radius:6px"></div>'
                marca = ' 📋' if c['tem_ficha'] else ''
                cards.append(
                    f'<div class="card-cand">'
                    f'{foto}'
                    f'<div class="nome">{esc(c["nome_urna"])}{marca}</div>'
                    f'<div class="meta">{esc(c["partido"])} · nº {esc(str(c["numero"]))}'
                    f'<span class="cargo"> · {esc(c["cargo"])}</span></div>'
                    f'</div>')
            st.markdown(f'<div class="grade-cand">{"".join(cards)}</div>',
                        unsafe_allow_html=True)

            if len(sel) > f_pag:
                st.caption(f'... e mais {len(sel) - f_pag}. Aumente "Por página" para ver todos.')

        st.divider()
        st.caption('📋 = tem ficha analisada nas outras abas (é quem já ocupa cargo).')
        with st.expander('De onde vêm as fotos, e por que não são link direto'):
            st.markdown(
                'O CSV de candidaturas do TSE **não tem campo de foto** — são 50 colunas e nenhuma '
                'de imagem. O `fotoUrl` vem do endpoint do DivulgaCandContas:\n\n'
                '```\n/divulga/rest/v1/candidatura/buscar/{ano}/{UF}/{eleicao}/candidato/{sq}\n```\n\n'
                'O caminho foi descoberto lendo os chunks JS do próprio app do TSE, porque a '
                'documentação não publica esse endpoint.\n\n'
                '**Por que as fotos estão no pacote em vez de linkadas:** o TSE serve as imagens '
                'com proteção de WAF (Akamai) que devolve **403 para requisição de navegador** — '
                'testei em quatro contextos, inclusive carregando do próprio domínio do TSE. '
                'O download funciona (exige header `Accept-Language: pt-BR`), o hotlink não. '
                'Então as 558 fotos foram baixadas (161×225, ~5,7 KB cada, 3 MB no total) e são '
                'servidas localmente.\n\n'
                'A URL original de cada uma continua guardada em `foto_url` no JSON, para '
                'auditoria e para o caso de o TSE liberar o hotlink depois.'
            )

# ═══════════════════ 5. EMENDAS ═══════════════════
with aba5:
    st.subheader('Emendas de transferência especial — bancada federal do ES')
    fed = df[(df['casa'] == 'Federal') & df['emendas_valor'].notna()].copy()
    if fed.empty:
        st.info('Nenhum candidato federal nos filtros atuais.')
    else:
        tot = fed['emendas_valor'].sum()
        ntot = int(fed['emendas_n'].sum())
        m1, m2, m3 = st.columns(3)
        m1.metric('Total', f'R$ {tot:,.0f}'.replace(',', '.'))
        m2.metric('Deputados', len(fed))
        m3.metric('Planos de ação', ntot)
        st.caption('Uma emenda se desdobra em vários planos de ação — um por município beneficiado. '
                   'Contar emendas e contar repasses dá números bem diferentes.')

        por = fed[['rotulo', 'partido', 'emendas_n', 'emendas_valor', 'gov']].copy()
        por['media'] = por['emendas_valor'] / por['emendas_n']
        por = por.sort_values('emendas_valor', ascending=False)
        por.columns = ['Deputado', 'Partido', 'Emendas', 'Total (R$)', 'Alinh. governo %', 'Média (R$)']
        st.dataframe(por, width='stretch', hide_index=True,
                     column_config={
                         'Total (R$)': st.column_config.NumberColumn(format='R$ %.2f'),
                         'Média (R$)': st.column_config.NumberColumn(format='R$ %.2f'),
                         'Alinh. governo %': st.column_config.NumberColumn(format='%.1f%%')})

        st.subheader('Para onde vai')
        todos = []
        for _, r in fed.iterrows():
            # emendas_destinos virou string JSON na normalizacao do df (ver topo do arquivo)
            for d, v in json.loads(r['emendas_destinos'] or '[]'):
                todos.append({'Destino': str(d).title(), 'Deputado': r['rotulo'], 'Valor (R$)': v})
        if todos:
            dt = pd.DataFrame(todos)
            agrup = (dt.groupby('Destino', as_index=False)['Valor (R$)'].sum()
                     .sort_values('Valor (R$)', ascending=False).head(15))
            st.altair_chart(
                alt.Chart(agrup).mark_bar().encode(
                    x=alt.X('Valor (R$):Q', title='R$'),
                    y=alt.Y('Destino:N', sort='-x', title=None),
                    tooltip=['Destino', alt.Tooltip('Valor (R$):Q', format=',.0f')],
                ).properties(height=420), width='stretch')
            st.caption('15 maiores destinos somados. Municípios aparecem como recebedores '
                       'individuais; o Estado do ES aparece agregado.')

# ═══════════════════ 6. MÉTODO ═══════════════════
with aba6:
    st.subheader('Por que estas quatro dimensões — e por que as óbvias ficaram de fora')
    st.markdown(
        'A pesquisa mediu muito mais que isto. Estas quatro sobreviveram porque **discriminam** '
        'entre candidatos sem enganar. As que todo mundo usa foram testadas e reprovadas.'
    )

    st.markdown('#### As quatro que importam')
    st.markdown(
        '1. **Eixo governo** — responde a pergunta que um voto responde: de quem você quer que '
        'controle a agenda. É o mais difícil de fraudar.\n'
        '2. **Posicionamento** — se o candidato vota. Ausência de voto não é oposição, é ausência '
        'de posição. Funciona independente de ideologia.\n'
        '3. **Produção substantiva** — o que o mandato faz o dia inteiro, entre propor política '
        'pública e distribuir homenagem.\n'
        '4. **Conversão em lei** — com ressalvas pesadas nas duas casas. Está aqui para você ver '
        'o número, não para ordenar por ele.'
    )

    st.markdown('#### As três armadilhas')
    st.error(
        '**1. "Quem mais aprova lei" mede coalizão.** No estadual, governo converte ~42% e '
        'oposição ~20%. O Coronel Weliton converte 18,2% com 48% de produção simbólica: nomear '
        'prédio é o que a oposição consegue aprovar. Um ranking por leis aprovadas premia quem '
        'nomeia prédio e pune quem propõe política pública.\n\n'
        '**2. "Alinhamento" por maioria de bancada mede coesão partidária, não posição.** '
        'O Gilvan da Federal dá 91,2% por esse método e 25,1% na orientação oficial do Governo — '
        '66 pontos de diferença. Este app usa o método oficial.\n\n'
        '**3. Volume de projeto mede esforço de sinalização.** O Evair tem 214 projetos (9º maior '
        'da Câmara) e 2 leis. Volume diz que a pessoa trabalha; não diz que entrega.'
    )

    st.markdown('#### Ressalvas — estaduais')
    for r in RESSALVAS['estadual']:
        st.markdown(f'- {r}')

    st.markdown('#### Ressalvas — federais')
    for r in RESSALVAS['federal']:
        st.markdown(f'- {r}')

    st.markdown('#### O que esta base não responde')
    st.info(
        '- **Honestidade** — não há processo, condenação nem licitação aqui.\n'
        '- **Competência** — só atividade. Um péssimo legislador prolífico parece ótimo.\n'
        '- **Conteúdo das propostas** — classificação por regex sobre a ementa (objetivo '
        'declarado), não leitura dos projetos.\n'
        '- **Se a posição é boa** — o eixo governo é o dado mais informativo do conjunto e é '
        '100% neutro: diz onde a pessoa está, não se o lugar presta.'
    )

    st.divider()
    with st.expander('Fontes dos dados'):
        st.markdown(
            '- **ALES** — API de dados abertos (produção, legislatura 20) e boletins de votação '
            'nominal em PDF (269 de 458 extraídos).\n'
            '- **Câmara dos Deputados** — `votacoesVotos`, `votacoesOrientacoes` (orientação '
            'oficial, bancada `Governo`), `proposicoes` e `proposicoesAutores`, 2023–2026.\n'
            '- **TSE** — candidaturas, bens e prestação de contas (parcial, 22/09/2026).\n'
            '- **TransfereGov** — transferências especiais (emendas pix).\n\n'
            'Preparado por `preparar_dados.py` a partir dos artefatos da pesquisa.'
        )
