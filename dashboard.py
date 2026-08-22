"""
Dashboard FPL — mostra a equipa otimizada gerada pelo fpl_optimizer.py

Correr localmente:
    pip install streamlit pandas
    streamlit run dashboard.py

Deploy grátis:
    https://share.streamlit.io -> liga ao teu repo GitHub -> aponta para este ficheiro
"""

import json
import streamlit as st
import pandas as pd

st.set_page_config(page_title="FPL Optimizer", page_icon="⚽", layout="centered")

POS_NAMES = {1: "Guarda-Redes", 2: "Defesas", 3: "Médios", 4: "Avançados"}
POS_ORDER = [1, 2, 3, 4]

st.markdown("""
<style>
.fpl-table { width: 100%; border-collapse: collapse; margin-bottom: 1.25rem; font-size: 14px; }
.fpl-table th { text-align: left; padding: 6px 8px; border-bottom: 2px solid rgba(120,120,120,0.4); font-size: 12px; opacity: 0.75; }
.fpl-table td { padding: 6px 8px; border-bottom: 1px solid rgba(120,120,120,0.2); vertical-align: middle; white-space: nowrap; }
.fpl-bar-wrap { background: rgba(120,120,120,0.25); border-radius: 4px; height: 12px; width: 80px; display: inline-block; vertical-align: middle; overflow: hidden; }
.fpl-bar { height: 100%; border-radius: 4px; }
.fpl-chip { display: inline-flex; align-items: center; gap: 5px; background: rgba(120,120,120,0.12); border: 1px solid rgba(120,120,120,0.3); border-radius: 6px; padding: 2px 6px 2px 2px; margin: 2px 4px 2px 0; font-size: 12px; white-space: nowrap; }
.fdr-sq { display: inline-block; min-width: 18px; height: 18px; line-height: 18px; text-align: center; border-radius: 4px; color: white; font-weight: 700; font-size: 11px; }
.fdr-1 { background: #0b8a3d; }
.fdr-2 { background: #3ec86a; color: #0a2e15; }
.fdr-3 { background: #e0c518; color: #3a2f00; }
.fdr-4 { background: #e0663a; }
.fdr-5 { background: #c0392b; }
.captain-badge { color: #e0c518; font-weight: 700; }
.vice-badge { opacity: 0.7; font-size: 11px; }
.gw-tag { display: inline-block; border-radius: 4px; padding: 1px 6px; margin-right: 4px; font-size: 11px; font-weight: 700; color: white; }
.gw-dgw { background: #0b8a3d; }
.gw-bgw { background: #c0392b; }
</style>
""", unsafe_allow_html=True)


def bar_html(value, max_value, color):
    pct = max(0, min(100, value / max_value * 100)) if max_value else 0
    return (
        f'<div class="fpl-bar-wrap"><div class="fpl-bar" '
        f'style="width:{pct:.0f}%;background:{color};"></div></div> {value:.1f}'
    )


def fixture_chip(f):
    diff = f["difficulty"]
    loc = "C" if f["is_home"] else "F"
    return f'<span class="fpl-chip"><span class="fdr-sq fdr-{diff}">{diff}</span>{f["opponent"]} ({loc})</span>'


def fixtures_row_html(fixtures, gw_note):
    tag = ""
    if gw_note == "DGW":
        tag = '<span class="gw-tag gw-dgw">DGW</span>'
    elif gw_note == "BGW":
        tag = '<span class="gw-tag gw-bgw">BGW</span>'
    if not fixtures:
        return tag + "-" if tag else "-"
    return tag + "".join(fixture_chip(f) for f in fixtures)


def render_squad_tables(squad):
    """Constrói e apresenta uma tabela HTML por posição, com barras e badges de dificuldade."""
    for pos in POS_ORDER:
        pos_players = [p for p in squad if p["position"] == pos]
        if not pos_players:
            continue
        st.subheader(POS_NAMES[pos])

        rows_html = []
        for p in pos_players:
            games = max(p.get("minutes", 0) / 90, 1)
            bps90 = round(p.get("bps", 0) / games, 1)

            name = p["web_name"]
            if p.get("is_captain"):
                name = f'<span class="captain-badge">★ {name}</span>'
            elif p.get("is_vice_captain"):
                name = f'{name} <span class="vice-badge">(V)</span>'
            if p.get("is_selected"):
                name = f"✅ {name}"
            if p.get("news"):
                name += " ⚠️"

            rows_html.append(
                "<tr>"
                f"<td>{name}</td>"
                f"<td>{p['team']}</td>"
                f"<td>€{p['price']/10:.1f}M</td>"
                f"<td>{bar_html(float(p['form']), 10, '#3ec86a')}</td>"
                f"<td>{bar_html(float(p['points_per_game']), 12, '#4a9eff')}</td>"
                f"<td>{p.get('xpts90', 0.0)}</td>"
                f"<td>{bps90}</td>"
                f"<td>{round(p.get('score', 0.0), 2)}</td>"
                f"<td>{fixtures_row_html(p.get('fixtures'), p.get('gw_note'))}</td>"
                "</tr>"
            )

        table_html = (
            '<table class="fpl-table"><thead><tr>'
            "<th>Jogador</th><th>Clube</th><th>Preço</th><th>Forma</th>"
            "<th>Pts/Jogo</th><th>Pts Esp/90</th><th>BPS/90</th><th>Score</th><th>Próx. 4 jogos</th>"
            "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table>"
        )
        st.markdown(f'<div style="overflow-x:auto">{table_html}</div>', unsafe_allow_html=True)


st.title("⚽ FPL Optimizer")
st.caption("Equipa ótima gerada automaticamente com base em forma, pontos/jogo, xG/xA e dificuldade de fixtures")

try:
    with open("latest_squad.json") as f:
        data = json.load(f)
except FileNotFoundError:
    st.error(
        "Ainda não existe `latest_squad.json`. Corre primeiro o `fpl_optimizer.py` "
        "(localmente ou via GitHub Actions) para gerar os dados."
    )
    st.stop()

squad = data["squad"]

tab_optimal, tab_current = st.tabs(["🏆 Equipa Ótima", "👤 Minha Equipa"])

with tab_optimal:
    col1, col2, col3 = st.columns(3)
    col1.metric("Custo total", f"€{data['cost']}M")
    col2.metric("Orçamento restante", f"€{100 - data['cost']:.1f}M")
    col3.metric("Score total", f"{data['score']:.1f}")

    st.divider()

    st.caption("Top 10 por posição segundo o modelo de score. ✅ = selecionado para a equipa ótima dentro do orçamento.")
    top_players = [p for group in data.get("top_players", {}).values() for p in group]
    render_squad_tables(top_players)

    st.divider()

    if "analysis" in data:
        st.subheader("📋 Análise")
        st.write(data["analysis"])
    else:
        st.info(
            "Sem análise guardada. Para incluir a explicação do Claude aqui, "
            "adiciona o texto ao dicionário guardado em `latest_squad.json` "
            "(campo `analysis`) no fpl_optimizer.py."
        )

    st.divider()

    if "suggested_transfers" in data and data["suggested_transfers"]:
        st.subheader("🔄 Transfers sugeridos")
        df_t = pd.DataFrame(data["suggested_transfers"])
        df_t.columns = ["Sai", "Entra", "Diferença custo (€M)", "Ganho líquido (pts)", "Usa transfer livre"]
        st.dataframe(df_t, hide_index=True, use_container_width=True)
    elif "suggested_transfers" in data:
        st.info("Nenhuma troca vantajosa encontrada esta jornada.")
    else:
        st.caption(
            "Sem sugestão de transfers — define `FPL_MANAGER_ID` no ambiente "
            "ao correr o `fpl_optimizer.py` para comparar com a tua equipa atual."
        )

with tab_current:
    current_squad = data.get("current_squad")
    if current_squad:
        col1, col2 = st.columns(2)
        col1.metric("Custo da equipa atual", f"€{data.get('current_squad_cost', 0)}M")
        col2.metric("Score da equipa atual", f"{data.get('current_squad_score', 0):.1f}")

        st.divider()
        render_squad_tables(current_squad)
    else:
        st.info(
            "Sem dados da tua equipa atual — define `FPL_MANAGER_ID` no ambiente "
            "ao correr o `fpl_optimizer.py` (o ID está na URL da tua conta FPL: "
            "fantasy.premierleague.com/entry/<ID>/...)."
        )

st.divider()

st.subheader("📈 Histórico de jornadas")
try:
    with open("history.json") as f:
        history = json.load(f)
    if history:
        df_h = pd.DataFrame(history)[["gameweek", "cost", "score"]]
        df_h.columns = ["Jornada", "Custo (€M)", "Score"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Score por jornada**")
            st.line_chart(df_h.set_index("Jornada")["Score"])
        with c2:
            st.markdown("**Custo (€M) por jornada**")
            st.line_chart(df_h.set_index("Jornada")["Custo (€M)"])
        st.dataframe(df_h, hide_index=True, use_container_width=True)
    else:
        st.caption("Ainda sem histórico registado.")
except FileNotFoundError:
    st.caption("Ainda sem `history.json`. É criado automaticamente após a primeira execução do otimizador.")

st.caption("🔄 Equipa atualizada automaticamente todas as sextas via GitHub Actions.")
