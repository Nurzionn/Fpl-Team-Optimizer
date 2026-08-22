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

st.title("⚽ FPL Optimizer")
st.caption("Equipa ótima gerada automaticamente com base em forma, pontos/jogo e disponibilidade")

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
    df = pd.DataFrame(pos_players)[
        ["web_name", "team", "price", "form", "points_per_game", "total_points"]
    ]
    df.columns = ["Jogador", "Clube", "Preço (€M)", "Forma", "Pts/Jogo", "Pontos Totais"]
    df["Preço (€M)"] = df["Preço (€M)"] / 10
    st.dataframe(df, hide_index=True, use_container_width=True)

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
        st.line_chart(df_h.set_index("Jornada")["Score"])
        st.dataframe(df_h, hide_index=True, use_container_width=True)
    else:
        st.caption("Ainda sem histórico registado.")
except FileNotFoundError:
    st.caption("Ainda sem `history.json`. É criado automaticamente após a primeira execução do otimizador.")

st.divider()
if st.button("🔄 Atualizar equipa (correr otimizador)"):
    st.warning(
        "Este botão não corre o otimizador diretamente no Streamlit Cloud gratuito "
        "(não tem acesso a segredos/execução longa por defeito). "
        "Usa o GitHub Actions para atualizar `latest_squad.json`, "
        "e este dashboard reflete automaticamente a próxima leitura do repo."
    )
