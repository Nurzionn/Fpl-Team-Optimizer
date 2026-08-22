"""
FPL Optimizer — busca dados da Fantasy Premier League, seleciona a equipa
ótima dentro do orçamento/regras, e usa a API do Claude para gerar
uma explicação em linguagem natural.

Dependências: requests, pulp, anthropic
    pip install requests pulp anthropic
"""

import os
import json
import requests
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, LpBinary, PULP_CBC_CMD
import anthropic

FPL_BASE = "https://fantasy.premierleague.com/api"
BUDGET = 1000  # FPL representa preços em décimos (100.0M = 1000)
SQUAD_SIZE = 15
POS_LIMITS = {1: 2, 2: 5, 3: 5, 4: 3}  # 1=GK, 2=DEF, 3=MID, 4=FWD
MAX_PER_CLUB = 3


def fetch_players():
    """Busca dados atuais de todos os jogadores da FPL."""
    resp = requests.get(f"{FPL_BASE}/bootstrap-static/", timeout=15)
    resp.raise_for_status()
    data = resp.json()

    teams = {t["id"]: t["name"] for t in data["teams"]}
    short_names = {t["id"]: t["short_name"] for t in data["teams"]}
    players = []
    for p in data["elements"]:
        players.append({
            "id": p["id"],
            "name": f"{p['first_name']} {p['second_name']}",
            "web_name": p["web_name"],
            "team": teams[p["team"]],
            "team_short": short_names[p["team"]],
            "team_id": p["team"],
            "position": p["element_type"],  # 1 GK, 2 DEF, 3 MID, 4 FWD
            "price": p["now_cost"],  # em décimos de milhão
            "total_points": p["total_points"],
            "form": float(p["form"]) if p["form"] else 0.0,
            "points_per_game": float(p["points_per_game"]) if p["points_per_game"] else 0.0,
            "minutes": p["minutes"],
            "status": p["status"],  # 'a' = disponível, 'i' = lesionado, etc.
            "chance_of_playing": p.get("chance_of_playing_next_round"),
            "xgi": float(p.get("expected_goal_involvements") or 0),
            "xgc": float(p.get("expected_goals_conceded") or 0),
            "expected_goals": float(p.get("expected_goals") or 0),
            "expected_assists": float(p.get("expected_assists") or 0),
            "bps": p.get("bps", 0),
            "bonus": p.get("bonus", 0),
            "starts": p.get("starts", 0),
            "news": p.get("news", ""),
        })
    return players


GOALS_PTS = {1: 6, 2: 6, 3: 5, 4: 4}  # pontos por golo, por posição
CLEAN_SHEET_PTS = {1: 4, 2: 4, 3: 1, 4: 0}  # pontos por jogo sem sofrer, por posição


def score_player(p, fdr=3.0, dgw_factor=1.0, w_form=0.35, w_ppg=0.25, w_xpts=0.30, w_bps=0.10):
    """
    Pontos esperados combinando forma, pontos/jogo, uma métrica subjacente
    (xG/xA/xGC convertidos em pontos FPL reais por posição) e tendência de
    bonus points (bps/90). Ajustado por dificuldade de fixtures, jogos
    duplos/em branco, fiabilidade de minutos e disponibilidade.
    """
    games = max(p.get("minutes", 0) / 90, 1)

    goals_pts = GOALS_PTS[p["position"]]
    cs_pts = CLEAN_SHEET_PTS[p["position"]]

    xg90 = p.get("expected_goals", 0.0) / games
    xa90 = p.get("expected_assists", 0.0) / games
    xgc90 = p.get("xgc", 0.0) / games

    attack_pts90 = xg90 * goals_pts + xa90 * 3
    clean_sheet_prob = max(0.0, 1 - xgc90 / 1.3) ** 2
    xpts90 = attack_pts90 + clean_sheet_prob * cs_pts

    bps90 = p.get("bps", 0) / games
    bps_score = min(bps90 / 30, 1.5)  # normaliza (top performers ~30-40 bps/jogo)

    base = w_form * p["form"] + w_ppg * p["points_per_game"] + w_xpts * xpts90 + w_bps * bps_score

    # fiabilidade: penaliza jogadores frequentemente suplentes/substituídos cedo
    starts = p.get("starts", 0)
    if starts > 0:
        reliability = min(1.0, (p.get("minutes", 0) / starts) / 70)
    else:
        reliability = 1.0
    base *= reliability

    base *= 1.0 + (3.0 - fdr) * 0.05  # ±10% across FDR range 1–5
    base *= dgw_factor  # boost em jogo duplo, penalização em jornada em branco

    if p["chance_of_playing"] is not None and p["chance_of_playing"] < 75:
        base *= p["chance_of_playing"] / 100
    if p["status"] not in ("a", "d"):
        base = 0

    p["xpts90"] = round(xpts90, 2)
    p["reliability"] = round(reliability, 2)
    return base


def optimize_squad(players, budget=BUDGET, fdr_map=None, dgw_map=None):
    """Resolve o problema de seleção de equipa via programação linear inteira."""
    fdr_map = fdr_map or {}
    dgw_map = dgw_map or {}
    for p in players:
        p["score"] = score_player(
            p, fdr=fdr_map.get(p["team_id"], 3.0), dgw_factor=dgw_map.get(p["team_id"], 1.0)
        )

    prob = LpProblem("FPL_Squad", LpMaximize)
    x = {p["id"]: LpVariable(f"x_{p['id']}", cat=LpBinary) for p in players}

    # Objetivo: maximizar score total
    prob += lpSum(x[p["id"]] * p["score"] for p in players)

    # Restrição de orçamento
    prob += lpSum(x[p["id"]] * p["price"] for p in players) <= budget

    # Tamanho do plantel
    prob += lpSum(x[p["id"]] for p in players) == SQUAD_SIZE

    # Limites por posição
    for pos, limit in POS_LIMITS.items():
        prob += lpSum(x[p["id"]] for p in players if p["position"] == pos) == limit

    # Máximo por clube
    club_ids = set(p["team_id"] for p in players)
    for club in club_ids:
        prob += lpSum(x[p["id"]] for p in players if p["team_id"] == club) <= MAX_PER_CLUB

    prob.solve(PULP_CBC_CMD(msg=0))

    selected = [p for p in players if x[p["id"]].value() == 1]
    return sorted(selected, key=lambda p: (p["position"], -p["score"]))


def _compact_fixtures(fixtures):
    if not fixtures:
        return ""
    return "|".join(
        f"{f['opponent']}({'C' if f['is_home'] else 'F'},{f['difficulty']})" for f in fixtures
    )


def _compact_squad(squad):
    """Representação compacta (CSV-like), ordenada por score, para minimizar tokens de input."""
    header = "nome,clube,pos,preco,forma,ppj,xpts90,bps90,proximos4"
    rows = []
    for p in sorted(squad, key=lambda p: -p.get("score", 0)):
        games = max(p.get("minutes", 0) / 90, 1)
        bps90 = round(p.get("bps", 0) / games, 1)
        row = (
            f"{p['web_name']},{p.get('team_short', p['team'])},{p['position']},{p['price']/10},{p['form']},"
            f"{p['points_per_game']},{p.get('xpts90', 0)},{bps90},{_compact_fixtures(p.get('fixtures'))}"
        )
        tags = []
        if p.get("gw_note"):
            tags.append(p["gw_note"])
        if p.get("news"):
            tags.append(f"⚠{p['news'][:40]}")
        if tags:
            row += "," + ";".join(tags)
        rows.append(row)
    return header + "\n" + "\n".join(rows)


def _top_captain_candidates(squad, n=3):
    """Pré-calcula os melhores candidatos a capitão (por score), evitando que o Claude tenha de comparar 15 linhas."""
    eligible = [p for p in squad if p.get("gw_note") != "BGW"]
    ranked = sorted(eligible, key=lambda p: -p.get("score", 0))
    return ", ".join(f"{p['web_name']}(score:{p.get('score', 0):.1f})" for p in ranked[:n])


def _compact_transfers(transfers):
    if not transfers:
        return None
    rows = [
        f"{t['out']['web_name']}->{t['in']['web_name']},"
        f"custo:{t['cost_diff']:.1f},ganho_liq:{t['net_gain']:.1f},"
        f"{'livre' if t['uses_free_transfer'] else 'paga(-4)'}"
        for t in transfers
    ]
    return "\n".join(rows)


SYSTEM_PROMPT = (
    "Analista de Fantasy Premier League. Respostas em português, "
    "diretas, sem preâmbulo, sem repetir os dados em tabela. "
    "Pos: 1=GR,2=DEF,3=MED,4=AVA. "
    "xpts90=pontos esperados/90min (modelo próprio via xG/xA/xGC); "
    "bps90=bonus points system por 90min (indicador de probabilidade de bónus). "
    "⚠=alerta lesão/rotação. DGW=jogo duplo esta jornada; BGW=sem jogo esta jornada. "
    "proximos4=próximos 4 jogos, formato ADV(C/F,dificuldade); C=casa,F=fora. "
    "Escala de dificuldade: 1-2=fácil, 3=médio, 4-5=difícil. NÃO confundir a direção da escala. "
    "Usa apenas os números fornecidos nos dados; não estimes ou inventes valores fora da tabela."
)


def analyze_with_claude(squad, transfers=None, client=None):
    """
    Chamada única à API que cobre equipa + transfers (quando existirem),
    para poupar overhead de tokens fixos face a duas chamadas separadas.
    Formato de dados compacto (CSV) em vez de frases longas.
    """
    if client is None:
        client = anthropic.Anthropic()

    squad_csv = _compact_squad(squad)
    transfers_csv = _compact_transfers(transfers) if transfers else None
    captain_candidates = _top_captain_candidates(squad)

    prompt = f"Equipa (15 jog., ordenada por score):\n{squad_csv}\n\n"
    prompt += (
        "1) Em até 80 palavras: 2-3 melhores escolhas e 1 risco a vigiar.\n"
        f"2) Escolhe o capitão apenas entre estes candidatos pré-calculados: {captain_candidates}. "
        "Não sugiras nenhum nome fora desta lista.\n"
    )

    if transfers_csv:
        prompt += f"\nTransfers propostos:\n{transfers_csv}\n"
        prompt += "3) Em até 60 palavras: vale a pena fazer? qual primeiro?\n"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=350,  # suficiente para ~140 palavras + margem, evita desperdício
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def fetch_current_gameweek():
    """Descobre qual é a jornada atual/próxima."""
    resp = requests.get(f"{FPL_BASE}/bootstrap-static/", timeout=15)
    resp.raise_for_status()
    events = resp.json()["events"]
    for e in events:
        if e["is_next"]:
            return e["id"]
    for e in events:
        if e["is_current"]:
            return e["id"]
    return events[-1]["id"]


def fetch_fixture_difficulty(current_gw, next_n_gws=3):
    """Returns avg fixture difficulty rating (1–5) per team_id for the next N gameweeks."""
    resp = requests.get(f"{FPL_BASE}/fixtures/", timeout=15)
    resp.raise_for_status()
    fixtures = resp.json()

    upcoming = [
        f for f in fixtures
        if f.get("event") and current_gw <= f["event"] < current_gw + next_n_gws
    ]
    fdr_sum, fdr_count = {}, {}
    for fix in upcoming:
        for team_key, diff_key in (("team_h", "team_h_difficulty"), ("team_a", "team_a_difficulty")):
            tid = fix[team_key]
            fdr = fix[diff_key]
            fdr_sum[tid] = fdr_sum.get(tid, 0) + fdr
            fdr_count[tid] = fdr_count.get(tid, 0) + 1

    return {tid: fdr_sum[tid] / fdr_count[tid] for tid in fdr_sum}


def fetch_next_fixtures(current_gw, next_n=4):
    """
    Devolve, por team_id, a lista dos próximos N jogos:
    [{"opponent": "ARS", "is_home": bool, "difficulty": 1-5, "gw": int}, ...]
    """
    teams_resp = requests.get(f"{FPL_BASE}/bootstrap-static/", timeout=15)
    teams_resp.raise_for_status()
    short_names = {t["id"]: t["short_name"] for t in teams_resp.json()["teams"]}

    fixtures_resp = requests.get(f"{FPL_BASE}/fixtures/", timeout=15)
    fixtures_resp.raise_for_status()
    fixtures = [f for f in fixtures_resp.json() if f.get("event") and f["event"] >= current_gw]
    fixtures.sort(key=lambda f: f["event"])

    result = {}
    for fix in fixtures:
        for team_key, opp_key, diff_key in (
            ("team_h", "team_a", "team_h_difficulty"),
            ("team_a", "team_h", "team_a_difficulty"),
        ):
            tid = fix[team_key]
            entries = result.setdefault(tid, [])
            if len(entries) >= next_n:
                continue
            entries.append({
                "opponent": short_names[fix[opp_key]],
                "is_home": team_key == "team_h",
                "difficulty": fix[diff_key],
                "gw": fix["event"],
            })
    return result


def compute_gw_fixture_counts(team_fixtures, current_gw):
    """Conta jogos de cada equipa na jornada atual (0=jornada em branco, 2+=jogo duplo)."""
    return {
        tid: sum(1 for f in fixtures if f["gw"] == current_gw)
        for tid, fixtures in team_fixtures.items()
    }


def fetch_manager_squad(manager_id, gameweek=None):
    """
    Busca a equipa atual de um manager (o teu 'team ID' da FPL).
    Encontra-se na URL da app: fantasy.premierleague.com/entry/<ID>/...
    """
    if gameweek is None:
        gameweek = fetch_current_gameweek() - 1  # última jornada já jogada
        if gameweek < 1:
            gameweek = 1

    resp = requests.get(
        f"{FPL_BASE}/entry/{manager_id}/event/{gameweek}/picks/", timeout=15
    )
    resp.raise_for_status()
    picks = resp.json()["picks"]
    return {p["element"]: p for p in picks}  # id -> pick info


def suggest_transfers(current_squad_ids, players, max_transfers=2, free_transfers=1, fdr_map=None, dgw_map=None):
    """
    Compara a equipa atual com a ótima e sugere as trocas de maior impacto,
    respeitando o nº de transfers livres (cada transfer extra custa -4 pts).
    """
    players_by_id = {p["id"]: p for p in players}
    fdr_map = fdr_map or {}
    dgw_map = dgw_map or {}
    for p in players:
        p["score"] = score_player(
            p, fdr=fdr_map.get(p["team_id"], 3.0), dgw_factor=dgw_map.get(p["team_id"], 1.0)
        )

    current = [players_by_id[pid] for pid in current_squad_ids if pid in players_by_id]
    current_ids = set(current_squad_ids)

    # Para cada jogador atual, encontra o melhor substituto na mesma posição/orçamento
    candidates = []
    for out_p in current:
        budget_available = out_p["price"]  # preço de venda (aprox.; FPL tem regras de venda a considerar)
        same_pos = [
            p for p in players
            if p["position"] == out_p["position"]
            and p["id"] not in current_ids
            and p["price"] <= budget_available + 999  # ajusta consoante banco disponível
        ]
        if not same_pos:
            continue
        best_in = max(same_pos, key=lambda p: p["score"])
        gain = best_in["score"] - out_p["score"]
        if gain > 0:
            candidates.append({
                "out": out_p, "in": best_in, "gain": gain,
                "cost_diff": (best_in["price"] - out_p["price"]) / 10,
            })

    candidates.sort(key=lambda c: -c["gain"])
    top = candidates[:max_transfers]

    for i, c in enumerate(top):
        penalty = 0 if i < free_transfers else 4
        c["net_gain"] = c["gain"] - penalty
        c["uses_free_transfer"] = i < free_transfers

    return top


def load_history(path="history.json"):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def save_history_entry(gameweek, squad, cost, score, path="history.json"):
    history = load_history(path)
    entry = {
        "gameweek": gameweek,
        "cost": cost,
        "score": score,
        "squad_ids": [p["id"] for p in squad],
        "squad_names": [p["web_name"] for p in squad],
    }
    # substitui entrada existente da mesma jornada, se houver (evita duplicados em re-runs)
    history = [h for h in history if h["gameweek"] != gameweek]
    history.append(entry)
    history.sort(key=lambda h: h["gameweek"])
    with open(path, "w") as f:
        json.dump(history, f, indent=2)
    return history


if __name__ == "__main__":
    print("A buscar dados da FPL...")
    players = fetch_players()
    gw = fetch_current_gameweek()

    print("A buscar dificuldade de fixtures...")
    fdr_map = fetch_fixture_difficulty(gw)
    team_fixtures = fetch_next_fixtures(gw, next_n=4)
    fixture_counts = compute_gw_fixture_counts(team_fixtures, gw)
    dgw_map = {tid: (0.4 if c == 0 else (1.5 if c >= 2 else 1.0)) for tid, c in fixture_counts.items()}

    print("A otimizar equipa...")
    squad = optimize_squad(players, fdr_map=fdr_map, dgw_map=dgw_map)
    for p in squad:
        p["fixtures"] = team_fixtures.get(p["team_id"], [])
        c = fixture_counts.get(p["team_id"], 1)
        p["gw_note"] = "DGW" if c >= 2 else ("BGW" if c == 0 else "")

    total_cost = sum(p["price"] for p in squad) / 10
    total_score = sum(p["score"] for p in squad)
    print(f"\nEquipa selecionada (custo: €{total_cost}M, score: {total_score:.1f}):")
    for p in squad:
        print(f"  [{p['position']}] {p['web_name']} ({p['team']}) - €{p['price']/10}M")

    output = {"squad": squad, "cost": total_cost, "score": total_score, "gameweek": gw}

    # --- Comparação com equipa atual (opcional: define FPL_MANAGER_ID) ---
    transfers = None
    manager_id = os.environ.get("FPL_MANAGER_ID")
    if manager_id:
        try:
            print(f"\nA buscar equipa atual do manager {manager_id}...")
            current_picks = fetch_manager_squad(int(manager_id))

            players_by_id = {p["id"]: p for p in players}
            current_squad = []
            for pid, pick in current_picks.items():
                if pid not in players_by_id:
                    continue
                pl = dict(players_by_id[pid])
                pl["fixtures"] = team_fixtures.get(pl["team_id"], [])
                c = fixture_counts.get(pl["team_id"], 1)
                pl["gw_note"] = "DGW" if c >= 2 else ("BGW" if c == 0 else "")
                pl["is_captain"] = pick.get("is_captain", False)
                pl["is_vice_captain"] = pick.get("is_vice_captain", False)
                current_squad.append(pl)
            current_squad.sort(key=lambda p: (p["position"], -p["score"]))
            output["current_squad"] = current_squad
            output["current_squad_cost"] = round(sum(p["price"] for p in current_squad) / 10, 1)
            output["current_squad_score"] = round(sum(p["score"] for p in current_squad), 2)

            transfers = suggest_transfers(list(current_picks.keys()), players, fdr_map=fdr_map, dgw_map=dgw_map)
            output["suggested_transfers"] = [
                {
                    "out": t["out"]["web_name"], "in": t["in"]["web_name"],
                    "cost_diff": t["cost_diff"], "net_gain": round(t["net_gain"], 2),
                    "uses_free_transfer": t["uses_free_transfer"],
                }
                for t in transfers
            ]
        except Exception as e:
            print(f"Erro ao buscar equipa do manager: {e}")
    else:
        print("\n(Define FPL_MANAGER_ID no ambiente para ativar sugestão de transfers)")

    # --- Uma única chamada à API cobre equipa + transfers (poupa tokens fixos) ---
    print("\nA gerar análise com Claude (1 chamada)...")
    try:
        analysis = analyze_with_claude(squad, transfers=transfers)
        print("\n" + "=" * 50)
        print(analysis)
        output["analysis"] = analysis
    except Exception as e:
        print(f"Erro ao chamar a API do Claude: {e}")
        print("Verifica se ANTHROPIC_API_KEY está definida no ambiente.")

    # --- Histórico ---
    save_history_entry(gw, squad, total_cost, total_score)
    print(f"\nHistórico atualizado (jornada {gw}) em history.json")

    with open("latest_squad.json", "w") as f:
        json.dump(output, f, indent=2)
