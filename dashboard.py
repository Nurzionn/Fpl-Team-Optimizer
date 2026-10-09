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

st.set_page_config(page_title="FPL Optimizer", page_icon="⚽", layout="wide")

POS_NAMES = {1: "🧤 Guarda-Redes", 2: "🛡️ Defesas", 3: "🎯 Médios", 4: "⚡ Avançados"}
POS_ORDER = [1, 2, 3, 4]
BADGE_URL = "https://resources.premierleague.com/premierleague/badges/50/t{code}.png"
PLAYER_PHOTO_URL = "https://resources.premierleague.com/premierleague/photos/players/110x140/p{code}.png"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --fpl-green: #1e8e3e;
    --fpl-green-light: #3ec86a;
    --fpl-blue: #4a9eff;
    --fpl-surface: rgba(120,120,120,0.08);
    --fpl-border: rgba(120,120,120,0.22);
}

html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
div.block-container { max-width: 1180px; padding-top: 1.5rem; padding-bottom: 3rem; }

/* --- Hero header --- */
.fpl-hero { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; background: linear-gradient(120deg, #0f3d20, #1e8e3e 65%, #2ea84a); border-radius: 16px; padding: 22px 28px; margin-bottom: 1.5rem; box-shadow: 0 10px 24px -12px rgba(15,61,32,0.55); }
.fpl-hero-title { color: white; font-size: 1.65rem; font-weight: 800; margin: 0; letter-spacing: -0.02em; }
.fpl-hero-subtitle { color: rgba(255,255,255,0.85); font-size: 0.85rem; margin-top: 4px; }
.fpl-hero-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.fpl-hero-chip { background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.3); color: white; font-size: 12px; font-weight: 600; padding: 5px 12px; border-radius: 999px; backdrop-filter: blur(4px); }

/* --- Section headings --- */
.section-heading { display: flex; align-items: center; gap: 8px; font-size: 1.05rem; font-weight: 700; margin: 1.6rem 0 0.75rem 0; padding-bottom: 6px; border-bottom: 2px solid var(--fpl-border); }
.pos-heading { color: #2e7d32; margin: 0.4rem 0 0.6rem 0; font-size: 1.05rem; font-weight: 700; }

/* --- Stat cards --- */
.stat-card { background: var(--fpl-surface); border: 1px solid var(--fpl-border); border-radius: 12px; padding: 14px 16px; display: flex; flex-direction: column; gap: 2px; transition: transform 0.15s ease, box-shadow 0.15s ease; }
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 8px 18px -10px rgba(0,0,0,0.35); }
.stat-card-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.65; }
.stat-card-value { font-size: 1.45rem; font-weight: 800; }
.stat-card-icon { font-size: 1.1rem; }

/* --- Tables --- */
.fpl-table { width: auto; min-width: 100%; table-layout: auto !important; border-collapse: collapse; margin-bottom: 1.25rem; font-size: 14px; border-radius: 10px; overflow: hidden; }
.fpl-table th { text-align: left; padding: 8px 10px; background: var(--fpl-surface); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; opacity: 0.7; white-space: nowrap; border-bottom: 1px solid var(--fpl-border); }
.fpl-table td { padding: 8px 10px; border-bottom: 1px solid var(--fpl-border); vertical-align: middle; white-space: nowrap !important; }
.fpl-table tbody tr:nth-child(even) { background: rgba(120,120,120,0.05); }
.fpl-table tbody tr:hover { background: rgba(62,200,106,0.10); }
.fpl-table td.col-wrap { white-space: normal !important; max-width: 130px; word-break: break-word; }
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
.team-badge { width: 16px; height: 16px; object-fit: contain; vertical-align: middle; margin-right: 5px; }
.player-photo { width: 24px; height: 24px; object-fit: cover; object-position: top; border-radius: 50%; vertical-align: middle; margin-right: 6px; background: rgba(120,120,120,0.15); }
.pitch-photo { width: 44px; height: 44px; object-fit: cover; object-position: top; border-radius: 50%; border: 2px solid rgba(255,255,255,0.85); box-shadow: 0 1px 3px rgba(0,0,0,0.5); background: #e8e8e8; }
.pitch-field { background: repeating-linear-gradient(180deg, #1e6b30, #1e6b30 36px, #26802f 36px, #26802f 72px); border: 3px solid rgba(255,255,255,0.85); border-radius: 14px; padding: 34px 8px 22px 8px; position: relative; margin-bottom: 0.75rem; overflow: hidden; transform: perspective(900px) rotateX(10deg); transform-origin: bottom center; box-shadow: 0 24px 30px -14px rgba(0,0,0,0.55); }
.pitch-goal { position: absolute; top: -4px; left: 50%; transform: translateX(-50%); width: 64px; height: 8px; border: 3px solid rgba(255,255,255,0.95); border-top: none; background: rgba(255,255,255,0.15); z-index: 1; }
.pitch-goal-area { position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 150px; height: 46px; border: 2px solid rgba(255,255,255,0.7); border-top: none; z-index: 1; }
.pitch-penalty-area { position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 270px; height: 96px; border: 2px solid rgba(255,255,255,0.7); border-top: none; z-index: 1; }
.pitch-penalty-arc { position: absolute; top: 96px; left: 50%; transform: translateX(-50%); width: 96px; height: 46px; border: 2px solid rgba(255,255,255,0.7); border-top: none; border-radius: 0 0 50% 50%; z-index: 1; }
.pitch-halfway { position: absolute; left: 6%; right: 6%; bottom: 18px; height: 2px; background: rgba(255,255,255,0.6); z-index: 1; }
.pitch-circle-half { position: absolute; bottom: 18px; left: 50%; transform: translateX(-50%); width: 110px; height: 55px; border: 2px solid rgba(255,255,255,0.6); border-bottom: none; border-radius: 50% 50% 0 0; z-index: 1; }
.pitch-row { display: flex; justify-content: center; flex-wrap: wrap; gap: 10px; margin: 12px 0; position: relative; z-index: 2; }
.pitch-player { display: flex; flex-direction: column; align-items: center; width: 84px; }
.pitch-avatar-wrap { position: relative; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; }
.pitch-badge { width: 30px; height: 30px; object-fit: contain; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.7)); }
.pitch-team-badge { position: absolute; bottom: -2px; right: -4px; width: 18px; height: 18px; object-fit: contain; background: white; border-radius: 50%; border: 1.5px solid rgba(255,255,255,0.9); box-shadow: 0 1px 3px rgba(0,0,0,0.5); padding: 1px; }
.pitch-name { background: rgba(0,0,0,0.6); color: white; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-top: 3px; white-space: nowrap; max-width: 84px; overflow: hidden; text-overflow: ellipsis; }
.pitch-sub { color: #eafff0; font-size: 10px; margin-top: 2px; text-shadow: 0 1px 2px rgba(0,0,0,0.6); }
.bench-strip { background: rgba(120,120,120,0.12); border: 1px solid rgba(120,120,120,0.3); border-radius: 10px; padding: 10px 8px 6px 8px; margin-bottom: 1rem; }
.bench-label { font-size: 11px; font-weight: 700; opacity: 0.7; text-transform: uppercase; margin-bottom: 4px; }

/* --- Transfer cards --- */
.transfer-card { display: flex; align-items: center; gap: 10px; background: var(--fpl-surface); border: 1px solid var(--fpl-border); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; flex-wrap: wrap; }
.transfer-arrow { opacity: 0.5; font-weight: 700; }
.transfer-out { font-weight: 600; }
.transfer-in { font-weight: 700; color: var(--fpl-green-light); }
.transfer-pill { margin-left: auto; font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 999px; }
.transfer-pill-gain { background: rgba(62,200,106,0.18); color: #1e8e3e; }
.transfer-pill-free { background: rgba(74,158,255,0.18); color: #2176d6; font-weight: 600; }
.transfer-pill-cost { background: rgba(224,102,58,0.18); color: #c0532a; font-weight: 600; }

/* --- Tabs --- */
button[data-baseweb="tab"] { font-weight: 600; }

/* --- History --- */
.trend-up { color: #1e8e3e; font-weight: 700; }
.trend-down { color: #c0392b; font-weight: 700; }
.trend-flat { opacity: 0.45; }

/* --- Sidebar --- */
.sidebar-legend-item { font-size: 13px; margin-bottom: 4px; }
</style>
""", unsafe_allow_html=True)


def stat_card(label, value, icon=""):
    return (
        '<div class="stat-card">'
        f'<div class="stat-card-label">{icon} {label}</div>'
        f'<div class="stat-card-value">{value}</div>'
        "</div>"
    )


def section_heading(icon, text):
    st.markdown(f'<div class="section-heading">{icon} {text}</div>', unsafe_allow_html=True)



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


def team_badge_html(p, css_class="team-badge"):
    code = p.get("team_code")
    if not code:
        return ""
    return f'<img class="{css_class}" src="{BADGE_URL.format(code=code)}">'


def player_photo_html(p, css_class="player-photo"):
    code = p.get("code")
    if not code:
        return ""
    return f'<img class="{css_class}" src="{PLAYER_PHOTO_URL.format(code=code)}" loading="lazy">'


def render_squad_tables(squad):
    """Constrói e apresenta uma tabela HTML por posição, com barras e badges de dificuldade."""
    for pos in POS_ORDER:
        pos_players = [p for p in squad if p["position"] == pos]
        if not pos_players:
            continue
        st.markdown(f'<div class="pos-heading">{POS_NAMES[pos]}</div>', unsafe_allow_html=True)

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
            if p.get("nailedness", 1.0) < 0.5:
                name += " 🪑"
            if p.get("news"):
                name += " ⚠️"

            rows_html.append(
                "<tr>"
                f"<td>{player_photo_html(p)}{name}</td>"
                f"<td class=\"col-wrap\">{team_badge_html(p)}{p.get('team_short', p['team'])}</td>"
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


def render_history_table(history):
    """Tabela de histórico com indicador de variação de score face à jornada anterior."""
    rows = sorted(history, key=lambda h: h["gameweek"])
    rows_html = []
    prev_score = None
    for h in rows:
        score = h["score"]
        if prev_score is None:
            trend_html = '<span class="trend-flat">—</span>'
        else:
            delta = score - prev_score
            if abs(delta) < 0.05:
                trend_html = '<span class="trend-flat">— 0.0</span>'
            else:
                css_class = "trend-up" if delta > 0 else "trend-down"
                arrow = "▲" if delta > 0 else "▼"
                trend_html = f'<span class="{css_class}">{arrow} {abs(delta):.1f}</span>'
        prev_score = score
        rows_html.append(
            "<tr>"
            f"<td><span class=\"fpl-chip\">GW {h['gameweek']}</span></td>"
            f"<td>€{h['cost']}M</td>"
            f"<td>{score:.1f}</td>"
            f"<td>{trend_html}</td>"
            "</tr>"
        )
    table_html = (
        '<table class="fpl-table"><thead><tr>'
        "<th>Jornada</th><th>Custo</th><th>Score</th><th>Variação</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table>"
    )
    st.markdown(f'<div style="overflow-x:auto">{table_html}</div>', unsafe_allow_html=True)


def render_pitch(squad, formation_label):
    """Mostra o plantel como um campo de futebol: 11 titulares na formação escolhida + banco de 4."""
    starters = [p for p in squad if p.get("is_starting")]
    bench = [p for p in squad if not p.get("is_starting")]
    if not starters:
        return

    def by_pos(pos, players):
        return sorted((p for p in players if p["position"] == pos), key=lambda p: -p.get("score", 0))

    def card(p):
        tag = " (C)" if p.get("is_captain") else (" (V)" if p.get("is_vice_captain") else "")
        player_photo = player_photo_html(p, "pitch-photo")
        if player_photo:
            # foto real + brasão do clube sobreposto no canto
            avatar = player_photo + team_badge_html(p, "pitch-team-badge")
        else:
            avatar = team_badge_html(p, "pitch-badge")
        return (
            '<div class="pitch-player">'
            f'<div class="pitch-avatar-wrap">{avatar}</div>'
            f'<div class="pitch-name">{p["web_name"]}{tag}</div>'
            f'<div class="pitch-sub">{p.get("team_short", "")} · €{p["price"]/10:.1f}M</div>'
            "</div>"
        )

    lines = [by_pos(1, starters), by_pos(2, starters), by_pos(3, starters), by_pos(4, starters)]
    rows_html = "".join(
        f'<div class="pitch-row">{"".join(card(p) for p in line)}</div>' for line in lines if line
    )
    markings_html = (
        '<div class="pitch-goal"></div>'
        '<div class="pitch-goal-area"></div>'
        '<div class="pitch-penalty-area"></div>'
        '<div class="pitch-penalty-arc"></div>'
        '<div class="pitch-circle-half"></div>'
        '<div class="pitch-halfway"></div>'
    )
    st.markdown(
        f'<div class="pitch-field">{markings_html}{rows_html}</div>',
        unsafe_allow_html=True,
    )
    if formation_label:
        st.caption(f"Formação: {formation_label}")

    if bench:
        bench.sort(key=lambda p: (p["position"] != 1, -p.get("score", 0)))
        bench_html = "".join(card(p) for p in bench)
        st.markdown(
            f'<div class="bench-strip"><div class="bench-label">Banco</div>'
            f'<div class="pitch-row">{bench_html}</div></div>',
            unsafe_allow_html=True,
        )


try:
    with open("latest_squad.json") as f:
        data = json.load(f)
except FileNotFoundError:
    st.error(
        "Ainda não existe `latest_squad.json`. Corre primeiro o `fpl_optimizer.py` "
        "(localmente ou via GitHub Actions) para gerar os dados."
    )
    st.stop()

st.markdown(
    '<div class="fpl-hero">'
    '<div><div class="fpl-hero-title">⚽ FPL Optimizer</div>'
    '<div class="fpl-hero-subtitle">Equipa ótima gerada automaticamente com base em forma, pontos/jogo, xG/xA e dificuldade de fixtures</div></div>'
    '<div class="fpl-hero-chips">'
    f'<span class="fpl-hero-chip">📅 Jornada {data.get("gameweek", "?")}</span>'
    f'<span class="fpl-hero-chip">🧩 {data.get("formation", "-")}</span>'
    "</div></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### ⚽ FPL Optimizer")
    st.caption("Seleção ótima de equipa via otimização linear + análise com IA.")
    st.markdown("**Legenda**")
    st.markdown(
        '<div class="sidebar-legend-item">✅ Selecionado para a equipa ótima</div>'
        '<div class="sidebar-legend-item">🪑 Risco de rotação</div>'
        '<div class="sidebar-legend-item">⚠️ Lesão / dúvida</div>'
        '<div class="sidebar-legend-item">★ Capitão · (V) Vice-capitão</div>'
        '<div class="sidebar-legend-item"><span class="gw-tag gw-dgw">DGW</span> Jornada dupla</div>'
        '<div class="sidebar-legend-item"><span class="gw-tag gw-bgw">BGW</span> Jornada em branco</div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("🔄 Atualizado automaticamente via GitHub Actions.")

squad = data["squad"]

tab_optimal, tab_current = st.tabs(["🏆 Equipa Ótima", "👤 Minha Equipa"])

with tab_optimal:
    c1, c2, c3 = st.columns(3)
    c1.markdown(stat_card("Custo total", f"€{data['cost']}M", "💰"), unsafe_allow_html=True)
    c2.markdown(stat_card("Orçamento restante", f"€{100 - data['cost']:.1f}M", "🏦"), unsafe_allow_html=True)
    c3.markdown(stat_card("Score total", f"{data['score']:.1f}", "📊"), unsafe_allow_html=True)

    render_pitch(squad, data.get("formation", ""))

    section_heading("🏅", "Top jogadores por posição")
    st.caption("Top 10 por posição segundo o modelo de score. ✅ = selecionado para a equipa ótima dentro do orçamento.")
    top_players = [p for group in data.get("top_players", {}).values() for p in group]
    render_squad_tables(top_players)

    section_heading("📋", "Análise")
    if "analysis" in data:
        st.write(data["analysis"])
    else:
        st.info(
            "Sem análise guardada. Para incluir a explicação do Claude aqui, "
            "adiciona o texto ao dicionário guardado em `latest_squad.json` "
            "(campo `analysis`) no fpl_optimizer.py."
        )

    section_heading("🔄", "Transfers sugeridos")
    if "suggested_transfers" in data and data["suggested_transfers"]:
        for t in data["suggested_transfers"]:
            pill = (
                '<span class="transfer-pill transfer-pill-free">Transfer livre</span>'
                if t["uses_free_transfer"]
                else '<span class="transfer-pill transfer-pill-cost">Extra (-4 pts)</span>'
            )
            st.markdown(
                '<div class="transfer-card">'
                f'<span class="transfer-out">{t["out"]}</span>'
                '<span class="transfer-arrow">→</span>'
                f'<span class="transfer-in">{t["in"]}</span>'
                f'<span class="fpl-chip">€{t["cost_diff"]:+.1f}M</span>'
                f'<span class="transfer-pill transfer-pill-gain">Ganho líquido: +{t["net_gain"]:.1f} pts</span>'
                f"{pill}"
                "</div>",
                unsafe_allow_html=True,
            )
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
        c1, c2 = st.columns(2)
        c1.markdown(stat_card("Custo da equipa atual", f"€{data.get('current_squad_cost', 0)}M", "💰"), unsafe_allow_html=True)
        c2.markdown(stat_card("Score da equipa atual", f"{data.get('current_squad_score', 0):.1f}", "📊"), unsafe_allow_html=True)

        render_pitch(current_squad, data.get("current_formation", ""))
        render_squad_tables(current_squad)
    else:
        st.info(
            "Sem dados da tua equipa atual — define `FPL_MANAGER_ID` no ambiente "
            "ao correr o `fpl_optimizer.py` (o ID está na URL da tua conta FPL: "
            "fantasy.premierleague.com/entry/<ID>/...)."
        )

section_heading("📈", "Histórico de jornadas")
try:
    with open("history.json") as f:
        history = json.load(f)
    if history:
        df_h = pd.DataFrame(history)[["gameweek", "cost", "score"]]
        df_h.columns = ["Jornada", "Custo (€M)", "Score"]
        c1, c2 = st.columns(2)
        with c1, st.container(border=True):
            st.markdown("**📊 Score por jornada**")
            st.line_chart(df_h.set_index("Jornada")["Score"], color="#1e8e3e")
        with c2, st.container(border=True):
            st.markdown("**💰 Custo (€M) por jornada**")
            st.line_chart(df_h.set_index("Jornada")["Custo (€M)"], color="#4a9eff")
        render_history_table(history)
    else:
        st.caption("Ainda sem histórico registado.")
except FileNotFoundError:
    st.caption("Ainda sem `history.json`. É criado automaticamente após a primeira execução do otimizador.")
