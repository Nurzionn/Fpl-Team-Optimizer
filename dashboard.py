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
FDR_EMOJI = {1: "🟢", 2: "🟢", 3: "🟡", 4: "🔴", 5: "🔴"}


def format_fixtures(fixtures):
    if not fixtures:
        return "-"
    return " ".join(
        f"{FDR_EMOJI.get(f['difficulty'], '⚪')}{f['opponent']}({'C' if f['is_home'] else 'F'})"
        for f in fixtures
    )

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
col1, col2, col3 = st.columns(3)
col1.metric("Custo total", f"€{data['cost']}M")
col2.metric("Orçamento restante", f"€{100 - data['cost']:.1f}M")
col3.metric("Score total", f"{data['score']:.1f}")

st.divider()

for pos in POS_ORDER:
    pos_players = [p for p in squad if p["position"] == pos]
    if not pos_players:
        continue
    st.subheader(POS_NAMES[pos])
    xg_col = "xGI/90" if pos in (3, 4) else "xGC/90"
    rows = []
    for p in pos_players:
        games = max(p.get("minutes", 0) / 90, 1)
        if pos in (3, 4):
            xg90 = round(p.get("xgi", 0.0) / games, 2)
        else:
            xg90 = round(p.get("xgc", 0.0) / games, 2)
        name = f"⚠️ {p['web_name']}" if p.get("news") else p["web_name"]
        rows.append({
            "Jogador": name,
            "Clube": p["team"],
            "Preço (€M)": p["price"] / 10,
            "Forma": float(p["form"]),
            "Pts/Jogo": float(p["points_per_game"]),
            xg_col: xg90,
            "Score": round(p.get("score", 0.0), 2),
            "Próx. 4 jogos": format_fixtures(p.get("fixtures")),
        })
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Forma": st.column_config.ProgressColumn("Forma", min_value=0, max_value=10, format="%.1f"),
            "Pts/Jogo": st.column_config.ProgressColumn("Pts/Jogo", min_value=0, max_value=12, format="%.1f"),
        },
    )

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
