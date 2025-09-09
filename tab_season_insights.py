# keep these imports at top of file
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit.components.v1 import html as st_html

def show_season_insights(st, go, teams_df, matchups_df, players_df, draft_roster_df=None):
    has_draft = draft_roster_df is not None

    # -----------------------------
    # Normalize columns
    # -----------------------------
    teams = teams_df.copy()
    matchups = matchups_df.copy()
    players = players_df.copy()
    for df in (teams, matchups, players):
        df.columns = df.columns.str.strip().str.lower()

    def _pick(df, options):
        return next((c for c in options if c in df.columns), None)

    # Require team_key
    if "team_key" not in teams.columns:
        st.error("Season Insights: teams_df is missing 'team_key'.")
        return

    # Column picks (teams table)
    year_col   = _pick(teams, ["year", "season"])
    owner_col  = _pick(teams, ["owner_name", "owner", "manager"])
    team_col   = _pick(teams, ["team_name", "team"])

    wins_col   = _pick(teams, ["wins", "regular_season_wins", "reg_wins"])
    losses_col = _pick(teams, ["losses", "regular_season_losses", "reg_losses"])
    pf_col     = _pick(teams, ["points_for_total", "points_for", "regular_season_points_for", "pf_total", "total_pf"])
    pa_col     = _pick(teams, ["points_against_total", "points_against", "regular_season_points_against", "pa_total", "total_pa"])

    waiver_col   = _pick(teams, ["number_of_waiver_moves", "waiver_moves"])
    trades_col   = _pick(teams, ["number_of_trades", "trades"])
    faab_used_col = "faab_balance_used" if "faab_balance_used" in teams.columns else None

    # -----------------------------
    # Repair wins/losses/pf/pa from matchups if needed (regular season only)
    # -----------------------------
    need_from_m = (wins_col is None) or (losses_col is None) or (pf_col is None) or (pa_col is None)
    if need_from_m:
        need = {"team_key", "week", "points_for", "points_against"}
        if not need.issubset(matchups.columns):
            missing = ", ".join(sorted(need - set(matchups.columns)))
            st.error(f"Season Insights: teams_df is missing W/L/PF/PA and matchups_df lacks columns to compute them ({missing}).")
            return

        m = matchups.copy()
        if "year" not in m.columns:
            if "year" not in teams.columns:
                st.error("Season Insights: no 'year' column in teams_df or matchups_df; cannot group by season.")
                return
            t_year = teams[["team_key", "year"]].dropna().drop_duplicates()
            m = m.merge(t_year, on="team_key", how="left", validate="m:1")

        if "is_playoffs" in m.columns:
            m["is_playoffs"] = pd.to_numeric(m["is_playoffs"], errors="coerce").fillna(0).astype(int)
            m = m[m["is_playoffs"] == 0]

        m["points_for"] = pd.to_numeric(m["points_for"], errors="coerce").fillna(0.0)
        m["points_against"] = pd.to_numeric(m["points_against"], errors="coerce").fillna(0.0)

        if "week_result" in m.columns:
            res = m["week_result"].astype(str).str.strip().str.lower()
            win_mask  = res.eq("win")
            loss_mask = res.eq("loss")
        else:
            win_mask  = m["points_for"] > m["points_against"]
            loss_mask = m["points_for"] < m["points_against"]

        m["win"]  = win_mask.astype(int)
        m["loss"] = loss_mask.astype(int)

        agg = (m.groupby(["team_key", "year"], dropna=False)
                 .agg(wins=("win", "sum"),
                      losses=("loss", "sum"),
                      points_for_total=("points_for", "sum"),
                      points_against_total=("points_against", "sum"))
                 .reset_index())

        teams["team_key"] = teams["team_key"].astype(str)
        agg["team_key"]   = agg["team_key"].astype(str)

        if year_col is None:
            year_col = "year"
            if "year" not in teams.columns:
                st.error("Season Insights: 'year' not in teams_df; needed to merge season aggregates.")
                return

        teams = teams.merge(agg, on=["team_key", "year"], how="left", suffixes=("", "_calc"))

        if wins_col   is None: wins_col   = "wins_calc"
        if losses_col is None: losses_col = "losses_calc"
        if pf_col     is None: pf_col     = "points_for_total_calc"
        if pa_col     is None: pa_col     = "points_against_total_calc"

        for base, calc in [("wins", "wins_calc"), ("losses","losses_calc"),
                           ("points_for_total", "points_for_total_calc"),
                           ("points_against_total","points_against_total_calc")]:
            if base in teams.columns and calc in teams.columns:
                teams[base] = teams[base].fillna(teams[calc])

        for colname in [wins_col, losses_col, pf_col, pa_col]:
            if colname not in teams.columns:
                st.error(f"Season Insights: failed to compute missing column '{colname}'.")
                return

    # Confirm owner/year
    if year_col is None or year_col not in teams.columns:
        st.error("Season Insights: Could not resolve a 'year' column in teams_df.")
        return
    if owner_col is None or owner_col not in teams.columns:
        st.error("Season Insights: Could not resolve an 'owner_name' column in teams_df.")
        return

    # Coerce numerics (safe)
    for c in [year_col, wins_col, losses_col, pf_col, pa_col, waiver_col, trades_col, faab_used_col]:
        if c and c in teams.columns:
            teams[c] = pd.to_numeric(teams[c], errors="coerce")

    # -----------------------------
    # Year slicer (default latest)
    # -----------------------------
    years = sorted(teams[year_col].dropna().astype(int).unique())
    if not years:
        st.info("No seasons available.")
        return

    selected_year = st.selectbox("Season:", options=years, index=len(years)-1, key="season_insights_year")
    season = teams[teams[year_col] == selected_year].copy()
    if season.empty:
        st.info("No data for the selected season.")
        return

    # =============== Season Result ===============
    is_finished_col = next((c for c in ["is_finished", "finished", "season_finished"] if c in teams.columns), None)
    league_res_col  = next((c for c in ["league_result", "league_result_final", "final_result"] if c in teams.columns), None)
    owner_disp_col  = owner_col

    _season_raw = teams[teams[year_col] == selected_year].copy()

    def _norm_res(s: str) -> str:
        t = (s or "").strip().lower()
        return t.replace("runner up", "runner-up").replace("runnerup", "runner-up")

    def _owner_for(result_key: str) -> str:
        if league_res_col is None or owner_disp_col is None or _season_raw.empty:
            return "-"
        cand = _season_raw[_season_raw[league_res_col].astype(str).map(_norm_res) == result_key]
        if cand.empty:
            return "-"
        name = cand.iloc[0][owner_disp_col]
        return str(name).strip() if pd.notna(name) and str(name).strip() else "-"

    # Decide if season is finished (robust to 1/0, True/False, yes/no, etc.)
    show_season_result = False
    if is_finished_col and is_finished_col in _season_raw.columns:
        try:
            s = _season_raw[is_finished_col].astype(str).str.strip().str.lower()
            truthy = s.isin({"1","true","yes","y","finished","final","complete","completed","done"})
            numeric_one = pd.to_numeric(s, errors="coerce").fillna(0).astype(int).eq(1)
            show_season_result = bool((truthy | numeric_one).any())
        except Exception:
            show_season_result = False

    if show_season_result:
        winner    = _owner_for("winner")
        runner_up = _owner_for("runner-up")
        loser     = _owner_for("loser")

        html = f"""
        <style>
          .season-result-cards {{
            display:grid;
            grid-template-columns: repeat(3, minmax(0,1fr));
            column-gap:15px;
            row-gap:10px;
            margin:6px 0;
          }}
          .sr-card {{
            background:transparent;
            border:none;
            border-radius:10px;
            padding:10px 12px;
            min-width:0;
            display:flex;
            flex-direction:column;
          }}
          .sr-label-row {{
            display:flex;
            align-items:center;
            justify-content:center;
            margin-bottom:4px;
            border-bottom:none;
            padding-bottom:0;
          }}
          .sr-emoji {{ font-size:28px; line-height:1; }}
          .sr-value {{
            color:#fff; font-size:25px; font-weight:800; line-height:1.3;
            white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:center;
          }}
          @media (max-width:480px){{
            .sr-emoji{{font-size:25px;}}
            .sr-value{{font-size:23px;}}
          }}
        </style>
        <div class="season-result-cards">
          <div class="sr-card">
            <div class="sr-label-row"><div class="sr-emoji" title="Winner">🏆</div></div>
            <div class="sr-value">{winner}</div>
          </div>
          <div class="sr-card">
            <div class="sr-label-row"><div class="sr-emoji" title="Runner-up">🥈</div></div>
            <div class="sr-value">{runner_up}</div>
          </div>
          <div class="sr-card">
            <div class="sr-label-row"><div class="sr-emoji" title="Loser">🗑️</div></div>
            <div class="sr-value">{loser}</div>
          </div>
        </div>
        """
        st_html(html, height=90)

    # -----------------------------
    # Season Standings table
    # -----------------------------
    w = season[wins_col].fillna(0).astype(int)
    l = season[losses_col].fillna(0).astype(int)
    season["Record"] = w.astype(str) + "-" + l.astype(str)

    season["Points For"]     = pd.to_numeric(season[pf_col], errors="coerce").fillna(0).astype(int)
    season["Points Against"] = pd.to_numeric(season[pa_col], errors="coerce").fillna(0).astype(int) if pa_col else 0
    season["Waiver Moves"]   = pd.to_numeric(season[waiver_col], errors="coerce").fillna(0).astype(int) if waiver_col else 0
    season["Trades"]         = pd.to_numeric(season[trades_col], errors="coerce").fillna(0).astype(int) if trades_col else 0

    if faab_used_col:
        faab_clean = season[faab_used_col].astype(str).str.replace(r"[^0-9\.\-]", "", regex=True)
        season["FAAB Balance"] = pd.to_numeric(faab_clean, errors="coerce").round(0).fillna(0).astype(int)
    else:
        season["FAAB Balance"] = 0

    # # High/Low Scores (regular season only)
    need_flags = {"team_key","week","high_score_flag","low_score_flag"}
    if not need_flags.issubset(matchups.columns):
        season["_high_scores"] = 0
        season["_low_scores"]  = 0
    else:
        m2 = matchups.copy()
        if "year" not in m2.columns:
            ty = teams[["team_key", year_col]].dropna().drop_duplicates().rename(columns={year_col: "year"})
            m2 = m2.merge(ty, on="team_key", how="left", validate="m:1")
        m2 = m2[m2["year"] == selected_year].copy()
        if "is_playoffs" in m2.columns:
            m2["is_playoffs"] = pd.to_numeric(m2["is_playoffs"], errors="coerce").fillna(0).astype(int)
            m2 = m2[m2["is_playoffs"] == 0]
        m2["team_key"] = m2["team_key"].astype(str)
        m2["high_score_flag"] = pd.to_numeric(m2["high_score_flag"], errors="coerce").fillna(0).astype(int)
        m2["low_score_flag"]  = pd.to_numeric(m2["low_score_flag"],  errors="coerce").fillna(0).astype(int)
        counts = (
            m2.groupby("team_key", dropna=False)[["high_score_flag","low_score_flag"]]
              .sum().reset_index()
              .rename(columns={"high_score_flag": "_high_scores", "low_score_flag": "_low_scores"})
        )
        season["team_key"] = season["team_key"].astype(str)
        season = season.merge(counts, on="team_key", how="left")
        season["_high_scores"] = season["_high_scores"].fillna(0).astype(int)
        season["_low_scores"]  = season["_low_scores"].fillna(0).astype(int)

    season = season.sort_values(by=[wins_col, pf_col], ascending=[False, False]).reset_index(drop=True)
    season["Rank"] = range(1, len(season) + 1)

    if team_col is None:
        season["_team_display"] = "-"
    else:
        season["_team_display"] = season[team_col].astype(str).replace({"": "-"}).fillna("-")

    season = season.rename(columns={
        owner_col: "Owner",
        "_team_display": "Team",
        "_high_scores": "# High Scores",
        "_low_scores":  "# Low Scores"
    })

    final_df = season[[
        "Owner", "Rank", "Record",
        "Points For", "Points Against",
        "# High Scores", "# Low Scores",
        "Waiver Moves", "Trades", "FAAB Balance"
    ]].copy()

    st.markdown(
        '<div style="font-size:20px;font-weight:600;margin-top:0px; margin-bottom:2px;">Season Standings</div>',
        unsafe_allow_html=True
    )
    n_rows = len(final_df)
    fit_height = min(1200, 40 + n_rows*34 + 10)
    st.dataframe(
        final_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rank": st.column_config.NumberColumn("Rank", format="%d"),
            "Owner": st.column_config.TextColumn("Owner", pinned="left"),
            "Record": st.column_config.TextColumn("Record"),
            "Points For": st.column_config.NumberColumn("Points For", format="%d"),
            "Points Against": st.column_config.NumberColumn("Points Against", format="%d"),
            "# High Scores": st.column_config.NumberColumn("# High Scores", format="%d"),
            "# Low Scores":  st.column_config.NumberColumn("# Low Scores",  format="%d"),
            "Waiver Moves": st.column_config.NumberColumn("Waiver Moves", format="%d"),
            "Trades": st.column_config.NumberColumn("Trades", format="%d"),
            "FAAB Balance": st.column_config.NumberColumn("FAAB Balance Used", format="%d"),
        },
        height=fit_height,
    )

    # Owner -> overall Rank (for labels/sorting)
    owner_rank_map = dict(zip(final_df["Owner"], final_df["Rank"]))

    # -----------------------------
    # Started Position Group Ranks — Heatmap (1 = best)
    # -----------------------------
    st.markdown(
        '<div style="font-size:20px;font-weight:600;margin:10px 0 2px;">Started Position Ranks by Total Points</div>',
        unsafe_allow_html=True
    )

    if "team_key" not in teams.columns or "team_key" not in matchups.columns:
        st.info("Missing 'team_key' in teams or matchups; cannot compute position ranks.")
        return

    _teams_key_year = teams[["team_key", year_col]].dropna().drop_duplicates().rename(columns={year_col: "year"})

    _m = matchups.merge(_teams_key_year, on="team_key", how="left", validate="m:1")
    _m = _m[_m["year"] == selected_year].copy()
    if "is_playoffs" in _m.columns:
        _m["is_playoffs"] = pd.to_numeric(_m["is_playoffs"], errors="coerce").fillna(0).astype(int)
        _m = _m[_m["is_playoffs"] == 0]
    if "week" not in _m.columns:
        st.info("Missing 'week' in matchups; cannot compute position ranks.")
        return
    _m["week"] = pd.to_numeric(_m["week"], errors="coerce")

    owner_map = (
        teams[teams[year_col] == selected_year][["team_key", owner_col]]
        .dropna(subset=["team_key"]).drop_duplicates().assign(team_key=lambda d: d["team_key"].astype(str))
        .rename(columns={owner_col: "owner_name"})
    )

    if "team_key" not in players.columns or "week" not in players.columns:
        st.info("Missing 'team_key' or 'week' in players; cannot compute position ranks.")
        return

    _t_y = teams[teams[year_col] == selected_year].drop_duplicates(subset=["team_key"])[["team_key", year_col]].rename(columns={year_col: "year"})
    _p = players.merge(_t_y, on="team_key", how="left", validate="m:1")
    _p = _p[_p["year"].notna()].copy()
    _p["year"] = _p["year"].astype(int)
    _pm = _p.merge(_m[["team_key", "week", "year"]], on=["team_key", "week", "year"], how="inner")

    if not {"selected_position", "player_week_points", "team_key", "week"}.issubset(_pm.columns):
        st.info("Missing required columns to compute position ranks.")
        return

    def _is_started(slot):
        s = str(slot).strip().upper() if slot is not None else ""
        return s not in ("BN", "IR")

    _pm = _pm[_pm["selected_position"].apply(_is_started)].copy()
    _pm["player_week_points"] = pd.to_numeric(_pm["player_week_points"], errors="coerce").fillna(0.0)
    _pm["team_key"] = _pm["team_key"].astype(str)

    BASE = {"QB", "RB", "WR", "TE", "K", "DEF"}
    def _map_slot(s: str) -> str:
        s = (s or "").strip().upper()
        if s == "DST": return "DEF"
        return s if s in BASE else "FLEX"
    _pm["pos"] = _pm["selected_position"].map(_map_slot)

    # Avg within TEAM × WEEK × POS (two RBs started → avg their points)
    twpos = (
        _pm.groupby(["team_key", "week", "pos"], as_index=False)["player_week_points"]
           .mean()
           .rename(columns={"player_week_points": "weekly_avg"})
    )
    if twpos.empty:
        st.info("No starter data found to compute position ranks.")
        return

    twpos = twpos.merge(owner_map, on="team_key", how="left")

    owner_pos = (
        twpos.groupby(["owner_name", "pos"], dropna=False)["weekly_avg"]
             .mean()
             .reset_index()
             .rename(columns={"weekly_avg": "owner_pos_avg"})
    )

    owner_pos["rank_in_pos"] = (
        owner_pos.groupby("pos")["owner_pos_avg"]
                 .rank(method="dense", ascending=False)
                 .astype(int)
    )

    desired_order = ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF"]
    heat_rank = owner_pos.pivot(index="owner_name", columns="pos", values="rank_in_pos")
    heat_rank = heat_rank[[c for c in desired_order if c in heat_rank.columns]]

    owners_sorted_rank = sorted(
        heat_rank.index.tolist(),
        key=lambda o: owner_rank_map.get(o, 1e9)
    )
    heat_rank = heat_rank.reindex(owners_sorted_rank)
    y_labels_rank = [f"#{owner_rank_map.get(o, '-') } {o}" for o in heat_rank.index]

    fig_rank = px.imshow(
        heat_rank,
        text_auto=True,
        aspect="auto",
        color_continuous_scale=["#2ca02c", "#ffffbf", "#d7191c"],  # green → yellow → red
        labels=dict(color="Rank (1=best)"),
        height=420
    )
    fig_rank.update_layout(
        margin=dict(l=8, r=0, t=4, b=8),
        coloraxis_colorbar=dict(title="Rank"),
    )
    fig_rank.update_xaxes(side="top", tickangle=0, title=None)
    fig_rank.update_yaxes(title=None, ticktext=y_labels_rank, tickvals=list(range(len(y_labels_rank))))
    st.plotly_chart(fig_rank, use_container_width=True, config={"displayModeBar": False})

    # -----------------------------
    # Leave-One-Out positional diffs helper
    # -----------------------------
    def _compute_positional_diffs_LOO(teams, matchups, players, selected_year, year_col, owner_col):
        mk = matchups.copy()
        if "year" not in mk.columns:
            ty = teams[["team_key", year_col]].dropna().drop_duplicates().rename(columns={year_col: "year"})
            mk = mk.merge(ty, on="team_key", how="left", validate="m:1")

        mk = mk[["team_key","week","year","is_playoffs"]].copy()
        mk["team_key"] = mk["team_key"].astype(str)
        mk["year"]     = pd.to_numeric(mk["year"], errors="coerce")
        mk = mk[mk["year"] == selected_year]
        if "is_playoffs" in mk.columns:
            mk["is_playoffs"] = pd.to_numeric(mk["is_playoffs"], errors="coerce").fillna(0).astype(int)
            mk = mk[mk["is_playoffs"] == 0]

        pp = players.copy()
        pp["team_key"] = pp["team_key"].astype(str)
        pp = pp.merge(mk, on=["team_key","week"], how="inner")

        pp = pp[~pp["selected_position"].astype(str).str.upper().isin(["BN","IR"])].copy()
        pp["player_week_points"] = pd.to_numeric(pp["player_week_points"], errors="coerce").fillna(0.0)

        def _map_slot2(s: str) -> str:
            s = (s or "").strip().upper()
            if s == "DST": return "DEF"
            return s if s in {"QB","RB","WR","TE","K","DEF"} else "FLEX"
        pp["pos"] = pp["selected_position"].map(_map_slot2)

        twpos_avg = (
            pp.groupby(["team_key","week","pos"], as_index=False)["player_week_points"]
              .mean()
              .rename(columns={"player_week_points":"weekly_avg"})
        )

        owner_map_df = (
            teams[teams[year_col] == selected_year][["team_key", owner_col]]
            .dropna(subset=["team_key"]).drop_duplicates()
            .rename(columns={owner_col: "owner_name"})
        )
        owner_map_df["team_key"] = owner_map_df["team_key"].astype(str)
        twpos_avg = twpos_avg.merge(owner_map_df, on="team_key", how="left")

        if twpos_avg.empty or twpos_avg["owner_name"].isna().all():
            return None

        base = twpos_avg.copy()
        grp = base.groupby(["week","pos"])["weekly_avg"]
        base["sum_all"] = grp.transform("sum")
        base["cnt_all"] = grp.transform("count")
        den = (base["cnt_all"] - 1).replace(0, np.nan)
        base["loo_avg"] = np.where(
            base["cnt_all"] > 1,
            (base["sum_all"] - base["weekly_avg"]) / den,
            base["weekly_avg"]
        )
        base["diff"] = base["weekly_avg"] - base["loo_avg"]

        owner_pos_diff = (
            base.groupby(["owner_name","pos"], dropna=False)["diff"]
                .mean()
                .reset_index()
        )

        BASE_POS = ["QB","RB","WR","TE","FLEX","K","DEF"]
        heat_diff = owner_pos_diff.pivot(index="owner_name", columns="pos", values="diff").fillna(0.0)
        cols_present = [c for c in BASE_POS if c in heat_diff.columns]
        heat_diff = heat_diff[cols_present]
        return heat_diff

    heat_diff = _compute_positional_diffs_LOO(teams, matchups, players, selected_year, year_col, owner_col)

    # ============================================
    # Owner Tabs (positions on y-axis) — uses LOO diffs
    # ============================================
    st.markdown(
        '<div style="font-size:20px;font-weight:600;margin:10px 0 4px;">Positional Scoring vs League</div>',
        unsafe_allow_html=True
    )

    if heat_diff is None or heat_diff.empty:
        st.info("No data available to build owner tabs for positional scoring.")
    else:
        owners_sorted = sorted(heat_diff.index.tolist(), key=lambda o: owner_rank_map.get(o, 10**9))
        POS_ORDER = ["DEF","K","FLEX","TE","WR","RB","QB"]
        positions = [p for p in POS_ORDER if p in heat_diff.columns]

        def _rank_label(owner: str) -> str:
            r = owner_rank_map.get(owner, None)
            try:
                return f"#{int(r)} {owner}" if r is not None and pd.notna(r) else owner
            except Exception:
                return owner

        POS_COLOR = {
            "QB":"#d62728","RB":"#2ca02c","WR":"#1f77b4","TE":"#ff7f0e",
            "FLEX":"#7f7f7f","K":"#9467bd","DEF":"#8c564b"
        }

        tabs = st.tabs([_rank_label(o) for o in owners_sorted])

        global_max_abs = float(np.nanmax(np.abs(heat_diff[positions].values))) if positions else 0.0
        global_xr = (-global_max_abs * 1.15, global_max_abs * 1.15) if global_max_abs > 0 else (-1, 1)

        for owner, tab in zip(owners_sorted, tabs):
            with tab:
                s = heat_diff.loc[owner, positions].astype(float).fillna(0.0)

                # ---- FIXED Y-AXIS ORDER (top→bottom) ----
                FIXED_POS_ORDER = ["QB","RB","WR","TE","FLEX","K","DEF"]
                y_lbls = [p for p in FIXED_POS_ORDER if p in s.index]  # keep order, drop missing
                x_vals = s.reindex(y_lbls).round(3).tolist()
                colors = [POS_COLOR.get(p, "#999") for p in y_lbls]

                fig_owner = go.Figure(go.Bar(
                    y=y_lbls,
                    x=x_vals,
                    orientation="h",
                    marker=dict(color=colors),
                    hovertemplate="<b>%{y}</b><br>%{x:.2f} pts vs league<extra></extra>"
                ))

                fig_owner.update_layout(
                    height=max(320, 30*len(y_lbls) + 80),
                    margin=dict(l=8, r=12, t=6, b=8),
                    xaxis=dict(
                        title=dict(text="Avg Weekly Points Per Starter vs League Avg", standoff=10),
                        range=list(global_xr),
                        zeroline=True, zerolinecolor="#AAAAAA", zerolinewidth=1,
                        gridcolor="#3F3F3F", gridwidth=1, fixedrange=True
                    ),
                    # lock the y axis to our fixed order
                    yaxis=dict(
                        title=None,
                        categoryorder="array",
                        categoryarray=y_lbls,
                        fixedrange=True
                    ),
                    showlegend=False
                )

                fig_owner.add_shape(
                    type="line", x0=0, x1=0, y0=-0.5, y1=len(y_lbls)-0.5,
                    line=dict(color="#AAAAAA", width=1)
                )

                st.plotly_chart(fig_owner, use_container_width=True, config={"displayModeBar": False})

    # =============================
    # Consistency vs Output — Avg Weekly Points (x) vs Std Dev (y)
    # =============================

    def _pick(df, options):
        return next((c for c in options if c in df.columns), None)

    need_match = {"team_key","week","points_for"}
    if not need_match.issubset(matchups.columns):
        st.info(f"Cannot build consistency scatter — missing columns: {', '.join(sorted(need_match - set(matchups.columns)))}")
    else:
        # Start from matchups; make sure year exists
        m = matchups.copy()
        if "year" not in m.columns:
            ty = (teams[["team_key", year_col]]
                  .dropna().drop_duplicates()
                  .rename(columns={year_col: "year"}))
            m = m.merge(ty, on="team_key", how="left", validate="m:1")

        # Season + regular season only
        m = m[m["year"] == selected_year].copy()
        if "is_playoffs" in m.columns:
            m["is_playoffs"] = pd.to_numeric(m["is_playoffs"], errors="coerce").fillna(0).astype(int)
            m = m[m["is_playoffs"] == 0]

        # Coerce numerics
        m["points_for"] = pd.to_numeric(m["points_for"], errors="coerce").fillna(0.0)
        m["week"] = pd.to_numeric(m["week"], errors="coerce").astype("Int64")
        m["team_key"] = m["team_key"].astype(str)

        # Owner for this season
        owner_map = (
            teams[teams[year_col] == selected_year][["team_key", owner_col]]
            .dropna(subset=["team_key"]).drop_duplicates()
            .rename(columns={owner_col: "owner_name"})
        )
        owner_map["team_key"] = owner_map["team_key"].astype(str)
        m = m.merge(owner_map, on="team_key", how="left")

        # Aggregate weekly points per owner (sum in case a manager had multiple team_keys in a season)
        weekly_owner = (
            m.groupby(["owner_name","week"], dropna=False)["points_for"]
             .sum()
             .reset_index()
             .dropna(subset=["owner_name","week"])
        )

        if weekly_owner.empty:
            st.info("No weekly scoring data found for this season.")
        else:
            # Stats per owner
            stats = (weekly_owner
                     .groupby("owner_name", dropna=False)["points_for"]
                     .agg(mean="mean", std="std", median="median", n="count", min="min", max="max")
                     .reset_index())

            # If an owner only has 1 recorded week, std is NaN; set to 0 for plotting & flag it
            stats["std"] = stats["std"].fillna(0.0)

            # Label: "#rank Owner" if rank map exists
            def _rank_label(owner):
                if "owner_rank_map" in locals() and isinstance(owner_rank_map, dict):
                    r = owner_rank_map.get(owner, None)
                    try:
                        return f"#{int(r)} {owner}" if r is not None and pd.notna(r) else owner
                    except Exception:
                        return owner
                return owner

            stats["label"] = stats["owner_name"].astype(str).apply(_rank_label)

            # Medians for guides
            x_med = float(stats["mean"].median())
            y_med = float(stats["std"].median())

            # Sort by x desc (stronger teams first) just for legend/text ordering; scatter doesn’t need explicit order
            stats = stats.sort_values("mean", ascending=False)

            # Build scatter
            fig_scatter = go.Figure()

            fig_scatter.add_trace(go.Scatter(
                x=stats["mean"],
                y=stats["std"],
                mode="markers+text",
                text=stats["label"],
                textposition="top center",
                textfont=dict(size=10),
                marker=dict(
                    size=np.clip(8 + (stats["n"] - stats["n"].min()) * 1.2, 8, 18),  # size by weeks recorded (subtle)
                    color="#E0E0E0",
                    line=dict(color="#4A4A4A", width=1.2)
                ),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Avg: %{x:.1f} pts/wk<br>"
                    "Std Dev: %{y:.1f}<br>"
                    f"League Medians → Avg: {x_med:.1f}, Std: {y_med:.1f}<br>"
                    "Weeks: %{customdata[0]}<br>"
                    "Median: %{customdata[1]:.1f}<br>"
                    "Min / Max: %{customdata[2]:.1f} / %{customdata[3]:.1f}"
                    "<extra></extra>"
                ),
                customdata=np.stack([stats["n"], stats["median"], stats["min"], stats["max"]], axis=1)
            ))

            # Median guide lines
            fig_scatter.add_shape(
                type="line", x0=x_med, x1=x_med, y0=0, y1=max(1.0, stats["std"].max()*1.05),
                line=dict(color="#666", width=1, dash="dash")
            )
            fig_scatter.add_shape(
                type="line", x0=max(0.0, stats["mean"].min()*0.95), x1=max(1.0, stats["mean"].max()*1.05),
                y0=y_med, y1=y_med, line=dict(color="#666", width=1, dash="dash")
            )

            # Axis ranges with a little padding
            x_min = max(0.0, float(stats["mean"].min()) * 0.95)
            x_max = float(stats["mean"].max()) * 1.05
            y_min = -0.05
            y_max = float(stats["std"].max()) * 1.15 + 0.1

            fig_scatter.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(
                    title=dict(text="Average Weekly Points", standoff=10),
                    range=[x_min, x_max],
                    gridcolor="#3F3F3F", gridwidth=1, zeroline=False, fixedrange=True
                ),
                yaxis=dict(
                    title=dict(text="Week-to-Week Consistency (Std Dev)", standoff=10),
                    range=[y_min, y_max],
                    gridcolor="#3F3F3F", gridwidth=1, zeroline=False, fixedrange=True
                ),
                showlegend=False
            )

            # After fig_scatter.update_layout(...)
            # Add quadrant labels as annotations

            fig_scatter.add_annotation(
                x=x_min + (x_med - x_min) / 2,
                y=y_med / 2 - 0.02,
                text="Bad & Consistent",
                showarrow=False,
                font=dict(size=11, color="#AAAAAA"),
                align="center"
            )

            fig_scatter.add_annotation(
                x=x_max - (x_max - x_med) / 2,
                y=y_med / 2 - 0.02,
                text="Elite & Consistent",
                showarrow=False,
                font=dict(size=11, color="#AAAAAA"),
                align="center"
            )

            fig_scatter.add_annotation(
                x=x_min + (x_med - x_min) / 2,
                y=y_max - (y_max - y_med) / 2,
                text="Bad & Volatile",
                showarrow=False,
                font=dict(size=11, color="#AAAAAA"),
                align="center"
            )

            fig_scatter.add_annotation(
                x=x_max - (x_max - x_med) / 2,
                y=y_max - (y_max - y_med) / 2,
                text="Elite & Volatile",
                showarrow=False,
                font=dict(size=11, color="#AAAAAA"),
                align="center"
            )

            st.markdown(
                '<div style="font-size:20px;font-weight:600;margin:10px 0 4px;">Team Scoring: Consistency vs Output</div>',
                unsafe_allow_html=True
            )
            # Optional callout if some owners have very few weeks
            few = stats[stats["n"] < 5]
            if not few.empty:
                st.caption("Note: Volatility may be unstable or zero early in the season")
            st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})



    # ============================================
    # 100% Horizontal Stacked Bar:
    # % of Team Scoring from Drafted vs Non-Drafted Starters (Regular Season)
    # ============================================

    # ---- helpers ----
    def _pick(df, options):
        return next((c for c in options if c in df.columns), None)

    # required cols
    need_players = {"team_key","week","player_week_points","selected_position","player_key"}
    need_match   = {"team_key","week"}
    if not need_players.issubset(players.columns) or not need_match.issubset(matchups.columns):
        missing = sorted((need_players - set(players.columns)) | (need_match - set(matchups.columns)))
        st.info(f"Cannot compute drafted vs non-drafted breakdown — missing: {', '.join(missing)}")
    else:
        # --- Build schedule (year & is_playoffs) onto players
        mk = matchups.copy()
        if "year" not in mk.columns:
            ty = teams[["team_key", year_col]].dropna().drop_duplicates().rename(columns={year_col: "year"})
            mk = mk.merge(ty, on="team_key", how="left", validate="m:1")

        mk = mk[["team_key","week","year","is_playoffs"]].copy()
        mk["team_key"] = mk["team_key"].astype(str)

        pp = players.copy()
        pp["team_key"] = pp["team_key"].astype(str)
        pp = pp.merge(mk, on=["team_key","week"], how="left")

        # season + regular season + starters only
        pp = pp[pp["year"] == selected_year].copy()
        pp["is_playoffs"] = pd.to_numeric(pp["is_playoffs"], errors="coerce").fillna(0).astype(int)
        pp = pp[pp["is_playoffs"] == 0]
        pp = pp[~pp["selected_position"].astype(str).str.upper().isin(["BN","IR"])]
        pp["player_week_points"] = pd.to_numeric(pp["player_week_points"], errors="coerce").fillna(0.0)

        # --- Owner map for this season
        owner_map_df = (
            teams[teams[year_col] == selected_year][["team_key", owner_col]]
            .dropna(subset=["team_key"]).drop_duplicates()
            .rename(columns={owner_col: "owner_name"})
        )
        owner_map_df["team_key"] = owner_map_df["team_key"].astype(str)
        pp = pp.merge(owner_map_df, on="team_key", how="left")

        # --- Drafted set per team for this season
        d = draft_roster_df.copy()
        d.columns = d.columns.str.strip().str.lower()
        pp.columns = pp.columns.str.strip().str.lower()

        dkey = _pick(d, ["player_key","player_id"])
        if dkey is None:
            st.info("draft_roster_df needs a player_key/player_id column to determine drafted players.")
        else:
            # filter draft list for this season if it has a year column
            if "year" in d.columns:
                d_season = d[d["year"] == selected_year].copy()
            else:
                d_season = d.copy()

            # normalize types for join/membership tests
            d_season["team_key"]  = d_season["team_key"].astype(str)
            d_season[dkey]        = d_season[dkey].astype(str)
            pp["player_key"]      = pp["player_key"].astype(str)

            # Build a (team_key -> set(player_key)) map of drafted players
            drafted_map = (
                d_season.groupby("team_key")[dkey]
                        .apply(lambda s: set(s.dropna().astype(str).unique()))
                        .to_dict()
            )

            # Flag drafted vs non-drafted at time of scoring
            def _is_drafted(row):
                t = row["team_key"]
                pid = row["player_key"]
                drafted_set = drafted_map.get(t, set())
                return pid in drafted_set

            pp["drafted_flag"] = pp.apply(_is_drafted, axis=1)

            # --- Aggregate scoring by owner × drafted_flag
            owner_flag_totals = (
                pp.groupby(["owner_name","drafted_flag"], dropna=False)["player_week_points"]
                  .sum()
                  .reset_index()
                  .rename(columns={"player_week_points":"pts"})
            )

            if owner_flag_totals.empty:
                st.info("No starter scoring rows found to compute drafted vs non-drafted breakdown.")
            else:
                # pivot to wide: columns = Drafted / Non-Drafted
                owner_wide = owner_flag_totals.pivot(index="owner_name", columns="drafted_flag", values="pts").fillna(0.0)
                # columns True/False -> friendly names
                owner_wide = owner_wide.rename(columns={True: "Drafted", False: "Non-Drafted"})
                if "Drafted" not in owner_wide.columns:     owner_wide["Drafted"] = 0.0
                if "Non-Drafted" not in owner_wide.columns: owner_wide["Non-Drafted"] = 0.0

                # totals & percentages (avoid divide by zero)
                totals = owner_wide.sum(axis=1)
                totals = totals.replace({0.0: 1e-9})
                pct = owner_wide.div(totals, axis=0) * 100.0

                # ----- Sort owners by Drafted% (desc) -----
                owners = pct.sort_values("Drafted", ascending=True).index.tolist()

                # Label "#rank Owner" if rank map exists; else just owner name
                def _rank_label(owner):
                    r = owner_rank_map.get(owner, None) if "owner_rank_map" in locals() else None
                    try:
                        return f"#{int(r)} {owner}" if r is not None and pd.notna(r) else owner
                    except Exception:
                        return owner

                y_labels = [_rank_label(o) for o in owners]

                # ----- Monochrome palette (stylish grays) -----
                COLOR_DRAFTED     = "#3A3A3A"  # dark gray
                COLOR_NON_DRAFTED = "#BFBFBF"  # light gray
                LINE_BORDER       = "#E0E0E0"

                fig100 = go.Figure()

                fig100.add_trace(go.Bar(
                    y=y_labels,
                    x=pct.loc[owners, "Drafted"].tolist(),
                    name="Drafted",
                    orientation="h",
                    marker=dict(color=COLOR_DRAFTED, line=dict(color=LINE_BORDER, width=1.2)),
                    hovertemplate="<b>%{y}</b><br>Drafted: %{x:.1f}%<extra></extra>",
                ))

                fig100.add_trace(go.Bar(
                    y=y_labels,
                    x=pct.loc[owners, "Non-Drafted"].tolist(),
                    name="Non-Drafted",
                    orientation="h",
                    marker=dict(color=COLOR_NON_DRAFTED, line=dict(color=LINE_BORDER, width=1.2)),
                    hovertemplate="<b>%{y}</b><br>Non-Drafted: %{x:.1f}%<extra></extra>",
                ))

                fig100.update_layout(
                    barmode="stack",
                    height=max(320, 28*len(y_labels) + 80),
                    margin=dict(l=8, r=12, t=6, b=8),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom", y=1.02,
                        xanchor="center", x=0.5
                    ),
                    xaxis=dict(
                        title=dict(text="% of Team Points (Regular Season Starters)", standoff=10),
                        range=[0, 105],
                        ticksuffix="%",
                        fixedrange=True,
                        gridcolor="#3F3F3F",
                        gridwidth=1
                    ),
                    yaxis=dict(
                        title=None,
                        categoryorder="array",
                        categoryarray=y_labels,
                        fixedrange=True
                    ),
                )

                st.markdown(
                    '<div style="font-size:20px;font-weight:600;margin:10px 0 4px;">Drafted vs Non-Drafted: % Team Scoring</div>',
                    unsafe_allow_html=True
                )
                st.plotly_chart(fig100, use_container_width=True, config={"displayModeBar": False})
    
    # =============================
    # Top 10 Players per Position (starters-only, regular season) — Tabs
    # =============================

    st.markdown(
        '<div style="font-size:20px;font-weight:600;margin:10px 0 2px;">Top Players</div>',
        unsafe_allow_html=True
    )

    need_cols_players = {"team_key","week","player_week_points","selected_position","player_position"}
    if not need_cols_players.issubset(players.columns):
        missing = ", ".join(sorted(need_cols_players - set(players.columns)))
        st.info(f"Players table missing columns: {missing}. Cannot compute top players.")
    else:
        # Stamp YEAR onto matchups via teams; filter selected year + regular season
        _teams_key_year = teams[["team_key", year_col]].dropna().drop_duplicates().rename(columns={year_col: "year"})
        _m = matchups.merge(_teams_key_year, on="team_key", how="left", validate="m:1")
        _m = _m[_m["year"] == selected_year].copy()
        if "is_playoffs" in _m.columns:
            _m["is_playoffs"] = pd.to_numeric(_m["is_playoffs"], errors="coerce").fillna(0).astype(int)
            _m = _m[_m["is_playoffs"] == 0]
        if "week" not in _m.columns:
            st.info("Missing 'week' in matchups; cannot compute top players.")
        else:
            _m["week"] = pd.to_numeric(_m["week"], errors="coerce").astype("Int64")

            # Map team_key -> owner for selected year
            _owner_map = (
                teams[teams[year_col] == selected_year][["team_key", owner_col]]
                .dropna(subset=["team_key"]).drop_duplicates()
                .rename(columns={owner_col: "owner_name"})
            )
            _owner_map["team_key"] = _owner_map["team_key"].astype(str)

            # Join players to scheduled weeks for this season
            _t_y = teams[teams[year_col] == selected_year].drop_duplicates(subset=["team_key"])[["team_key", year_col]].rename(columns={year_col: "year"})
            _p = players.merge(_t_y, on="team_key", how="left", validate="m:1")
            _p = _p[_p["year"].notna()].copy()
            _p["year"] = _p["year"].astype(int)

            _pm = _p.merge(_m[["team_key","week","year"]], on=["team_key","week","year"], how="inner")

            # Starters only (exclude BN/IR), numeric points
            def _is_started(slot):
                s = str(slot).strip().upper() if slot is not None else ""
                return s not in ("BN","IR")
            _pm = _pm[_pm["selected_position"].apply(_is_started)].copy()

            _pm["player_week_points"] = pd.to_numeric(_pm["player_week_points"], errors="coerce").fillna(0.0)
            _pm["team_key"] = _pm["team_key"].astype(str)

            # Normalize player_position groups (DST -> DEF)
            def _norm_pos(p):
                s = str(p).strip().upper() if p is not None else ""
                return "DEF" if s == "DST" else s
            _pm["player_position_norm"] = _pm["player_position"].map(_norm_pos)

            # Attach owner name
            _pm = _pm.merge(_owner_map, on="team_key", how="left")

            # Choose a name column for players
            player_name_col = next((c for c in ["player_name","name","full_name","player_full_name","player_key"] if c in _pm.columns), None)
            if player_name_col is None:
                st.info("No player name/key column found; cannot compute top players.")
            else:
                _pm["player_name_display"] = _pm[player_name_col].astype(str)

                # --------- Build "drafted" set for Non-Drafted tab ---------
                undrafted_pm = None
                if draft_roster_df is None:
                    undrafted_reason = "No draft roster available for this league/season."
                else:
                    d = draft_roster_df.copy()
                    d.columns = d.columns.str.strip().str.lower()
                    dkey = "player_key" if "player_key" in d.columns else ("player_id" if "player_id" in d.columns else None)
                    if dkey is None:
                        undrafted_reason = "draft_roster_df is missing player_key/player_id."
                    else:
                        # Restrict to selected season if year present
                        if "year" in d.columns:
                            d = d[d["year"] == selected_year].copy()
                        drafted_ids = set(d[dkey].astype(str).dropna().unique())
                        if "player_key" not in _pm.columns:
                            undrafted_reason = "players_df is missing player_key; cannot identify undrafted players."
                        else:
                            _pm["player_key"] = _pm["player_key"].astype(str)
                            undrafted_pm = _pm[~_pm["player_key"].isin(drafted_ids)].copy()
                            undrafted_reason = None

                # --------- Aggregate per-position (existing tabs) ----------
                POS_ORDER = ["QB","RB","WR","TE","K","DEF"]
                agg = (
                    _pm.groupby(["player_position_norm","player_name_display","owner_name"], dropna=False)["player_week_points"]
                       .sum()
                       .reset_index()
                       .rename(columns={"player_week_points": "total_points"})
                )
                agg = agg[agg["player_position_norm"].isin(POS_ORDER)]
                if agg.empty:
                    st.info("No started-player scoring found for top-player computation.")
                else:
                    tabs = st.tabs(POS_ORDER + ["Non-Drafted"])

                    # Position tabs
                    for pos, tab in zip(POS_ORDER, tabs[:-1]):
                        with tab:
                            pos_tbl = agg[agg["player_position_norm"] == pos].copy()
                            if pos_tbl.empty:
                                st.info(f"No data for {pos}.")
                                continue

                            # Sort desc by total points and compute dense rank starting at 1
                            pos_tbl = pos_tbl.sort_values("total_points", ascending=False).reset_index(drop=True)
                            pos_tbl["Rank"] = pos_tbl["total_points"].rank(method="dense", ascending=False).astype(int)

                            # Final display: Rank, Player, Owner, Total Points Scored (top 10)
                            view = pos_tbl[["Rank","player_name_display","owner_name","total_points"]].copy()
                            view.rename(columns={
                                "player_name_display": "Player",
                                "owner_name": "Owner",
                                "total_points": "Total Points"
                            }, inplace=True)
                            view = view.sort_values(["Rank","Total Points"], ascending=[True, False]).head(10).reset_index(drop=True)

                            # Fit height for 10 rows
                            n_rows = len(view)
                            fit_height = min(600, 40 + n_rows*34 + 16)

                            st.dataframe(
                                view,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Rank": st.column_config.NumberColumn("Rank", format="%d", pinned="left"),
                                    "Player": st.column_config.TextColumn("Player"),
                                    "Owner": st.column_config.TextColumn("Owner"),
                                    "Total Points": st.column_config.NumberColumn("Total Points", format="%d"),
                                },
                                height=fit_height,
                            )

                    # Non-Drafted tab (all positions; players whose player_key NOT in draft_roster_df)
                    with tabs[-1]:
                        if undrafted_pm is None:
                            st.info(f"Cannot compute Non-Drafted tab: {undrafted_reason}")
                        else:
                            if undrafted_pm.empty:
                                st.info("No qualifying undrafted starters found for the selected season.")
                            else:
                                # Aggregate across ALL positions
                                und = (
                                    undrafted_pm.groupby(["player_name_display","owner_name"], dropna=False)["player_week_points"]
                                                .sum()
                                                .reset_index()
                                                .rename(columns={"player_week_points": "total_points"})
                                )
                                if und.empty:
                                    st.info("No qualifying undrafted starters found for the selected season.")
                                else:
                                    und = und.sort_values("total_points", ascending=False).reset_index(drop=True)
                                    und["Rank"] = und["total_points"].rank(method="dense", ascending=False).astype(int)

                                    view = und[["Rank","player_name_display","owner_name","total_points"]].copy()
                                    view.rename(columns={
                                        "player_name_display": "Player",
                                        "owner_name": "Current Owner",
                                        "total_points": "Total Points"
                                    }, inplace=True)
                                    view = view.sort_values(["Rank","Total Points"], ascending=[True, False]).head(10).reset_index(drop=True)

                                    n_rows = len(view)
                                    fit_height = min(600, 40 + n_rows*34 + 16)

                                    st.dataframe(
                                        view,
                                        use_container_width=True,
                                        hide_index=True,
                                        column_config={
                                            "Rank": st.column_config.NumberColumn("Rank", format="%d", pinned="left"),
                                            "Player": st.column_config.TextColumn("Player"),
                                            "Owner": st.column_config.TextColumn("Owner"),
                                            "Total Points": st.column_config.NumberColumn("Total Points", format="%d"),
                                        },
                                        height=fit_height,
                                    )
    
    # =============================
    # Top Performances — Tabs: Started Players, Benched Players, Teams
    # =============================

    st.markdown(
        '<div style="font-size:20px;font-weight:600;margin:10px 0 2px;">Top Performances</div>',
        unsafe_allow_html=True
    )

    TOP_N = 10  # change this if you want more/less rows

    tabs = st.tabs(["Started Players", "Benched Players", "Teams"])

    # ---------- Helpers ----------
    def _pick(df, options):
        return next((c for c in options if c in df.columns), None)

    def _fit_height(n_rows, row_px=34, header_px=40, padding_px=16, max_px=1200):
        return min(max_px, header_px + n_rows * row_px + padding_px)

    # Map team_key -> owner for selected year
    _owner_map = (
        teams[teams[year_col] == selected_year][["team_key", owner_col]]
        .dropna(subset=["team_key"]).drop_duplicates()
        .rename(columns={owner_col: "owner_name"})
    )
    _owner_map["team_key"] = _owner_map["team_key"].astype(str)

    # Common base join (players + schedule for selected season, regular season only)
    def _base_player_weeks(players_df, matchups_df):
        mk = matchups_df.copy()
        if "year" not in mk.columns:
            ty = teams[["team_key", year_col]].dropna().drop_duplicates().rename(columns={year_col: "year"})
            mk = mk.merge(ty, on="team_key", how="left", validate="m:1")
        mk = mk[["team_key","week","year","is_playoffs"]].copy()
        mk["team_key"] = mk["team_key"].astype(str)

        pp = players_df.copy()
        pp["team_key"] = pp["team_key"].astype(str)
        pp = pp.merge(mk, on=["team_key","week"], how="left")

        # Filter selected season, regular season only
        pp = pp[pp["year"] == selected_year].copy()
        pp["is_playoffs"] = pd.to_numeric(pp["is_playoffs"], errors="coerce").fillna(0).astype(int)
        pp = pp[pp["is_playoffs"] == 0]

        # Points + owner
        pp["player_week_points"] = pd.to_numeric(pp["player_week_points"], errors="coerce").fillna(0.0)
        pp = pp.merge(_owner_map, on="team_key", how="left")
        return pp

    # ---------- Tab 1: Started Players (top individual weekly performances) ----------
    with tabs[0]:
        need_cols_players = {"team_key","week","player_week_points","selected_position"}
        if not need_cols_players.issubset(players.columns):
            missing = ", ".join(sorted(need_cols_players - set(players.columns)))
            st.info(f"Players table missing columns: {missing}. Cannot compute player weekly performances.")
        else:
            pp = _base_player_weeks(players, matchups)
            # Starters only (exclude BN/IR)
            pp = pp[~pp["selected_position"].astype(str).str.upper().isin(["BN","IR"])]

            # Choose a player-name column
            pname = _pick(pp, ["player_name","name","full_name","player_full_name","player_key"])
            if pname is None:
                st.info("No player name/key column found in players.")
            else:
                pp["_player_week"] = pp[pname].astype(str).fillna("-") + " (Wk " + pp["week"].astype("Int64").astype(str) + ")"
                pos_tbl = (
                    pp[["_player_week","owner_name","player_week_points","week"]]
                    .sort_values("player_week_points", ascending=False)
                    .head(TOP_N)
                    .copy()
                )
                if pos_tbl.empty:
                    st.info("No player-week performances found.")
                else:
                    pos_tbl["Rank"] = pos_tbl["player_week_points"].rank(method="dense", ascending=False).astype(int)
                    view = pos_tbl[["Rank","_player_week","owner_name","player_week_points"]].copy()
                    view = view.sort_values(["Rank","player_week_points"], ascending=[True, False]).reset_index(drop=True)
                    view.rename(columns={
                        "_player_week": "Player (Week)",
                        "owner_name": "Owner",
                        "player_week_points": "Points"
                    }, inplace=True)

                    st.dataframe(
                        view,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Rank": st.column_config.NumberColumn("Rank", format="%d", pinned="left"),
                            "Player (Week)": st.column_config.TextColumn("Player (Week)"),
                            "Current Owner": st.column_config.TextColumn("Current Owner"),
                            "Points": st.column_config.NumberColumn("Points", format="%d"),
                        },
                        height=_fit_height(len(view)),
                    )

    # ---------- Tab 2: Benched Players (selected_position == "BN") ----------
    with tabs[1]:
        need_cols_players = {"team_key","week","player_week_points","selected_position"}
        if not need_cols_players.issubset(players.columns):
            missing = ", ".join(sorted(need_cols_players - set(players.columns)))
            st.info(f"Players table missing columns: {missing}. Cannot compute benched performances.")
        else:
            pp = _base_player_weeks(players, matchups)
            # Benched only
            pp = pp[pp["selected_position"].astype(str).str.upper().eq("BN")]

            pname = _pick(pp, ["player_name","name","full_name","player_full_name","player_key"])
            if pname is None:
                st.info("No player name/key column found in players.")
            else:
                pp["_player_week"] = pp[pname].astype(str).fillna("-") + " (Wk " + pp["week"].astype("Int64").astype(str) + ")"
                pos_tbl = (
                    pp[["_player_week","owner_name","player_week_points","week"]]
                    .sort_values("player_week_points", ascending=False)
                    .head(TOP_N)
                    .copy()
                )
                if pos_tbl.empty:
                    st.info("No benched player-week performances found.")
                else:
                    pos_tbl["Rank"] = pos_tbl["player_week_points"].rank(method="dense", ascending=False).astype(int)
                    view = pos_tbl[["Rank","_player_week","owner_name","player_week_points"]].copy()
                    view = view.sort_values(["Rank","player_week_points"], ascending=[True, False]).reset_index(drop=True)
                    view.rename(columns={
                        "_player_week": "Player (Week)",
                        "owner_name": "Owner",
                        "player_week_points": "Points"
                    }, inplace=True)

                    st.dataframe(
                        view,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Rank": st.column_config.NumberColumn("Rank", format="%d", pinned="left"),
                            "Player (Week)": st.column_config.TextColumn("Player (Week)"),
                            "Current Owner": st.column_config.TextColumn("Current Owner"),
                            "Points": st.column_config.NumberColumn("Points", format="%d"),
                        },
                        height=_fit_height(len(view)),
                    )

    # ---------- Tab 3: Teams (top team weekly performances) ----------
    with tabs[2]:
        need_cols_matchups = {"team_key","week","points_for"}
        if not need_cols_matchups.issubset(matchups.columns):
            missing = ", ".join(sorted(need_cols_matchups - set(matchups.columns)))
            st.info(f"Matchups table missing columns: {missing}. Cannot compute team weekly performances.")
        else:
            m2 = matchups.copy()

            # Ensure year on matchups
            if "year" not in m2.columns:
                ty = teams[["team_key", year_col]].dropna().drop_duplicates().rename(columns={year_col: "year"})
                m2 = m2.merge(ty, on="team_key", how="left", validate="m:1")

            # Filter season + regular season
            m2 = m2[m2["year"] == selected_year].copy()
            if "is_playoffs" in m2.columns:
                m2["is_playoffs"] = pd.to_numeric(m2["is_playoffs"], errors="coerce").fillna(0).astype(int)
                m2 = m2[m2["is_playoffs"] == 0]

            # Coerce numerics
            m2["points_for"] = pd.to_numeric(m2["points_for"], errors="coerce").fillna(0.0)
            m2["team_key"] = m2["team_key"].astype(str)

            # Attach owner
            m2 = m2.merge(_owner_map, on="team_key", how="left")

            # Build display
            wk_tbl = (
                m2[["owner_name","week","points_for"]]
                .sort_values("points_for", ascending=False)
                .head(TOP_N)
                .copy()
            )
            if wk_tbl.empty:
                st.info("No team-week performances found.")
            else:
                wk_tbl["_owner_week"] = wk_tbl["owner_name"].astype(str).fillna("-") + " (Wk " + wk_tbl["week"].astype("Int64").astype(str) + ")"
                wk_tbl["Rank"] = wk_tbl["points_for"].rank(method="dense", ascending=False).astype(int)
                view = wk_tbl[["Rank","_owner_week","points_for"]].copy()
                view = view.sort_values(["Rank","points_for"], ascending=[True, False]).reset_index(drop=True)
                view.rename(columns={
                    "_owner_week": "Owner (Week)",
                    "points_for": "Points",
                }, inplace=True)

                st.dataframe(
                    view,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Rank": st.column_config.NumberColumn("Rank", format="%d", pinned="left"),
                        "Owner (Week)": st.column_config.TextColumn("Owner (Week)"),
                        "Total Points": st.column_config.NumberColumn("Total Points", format="%d"),
                    },
                    height=_fit_height(len(view)),
                )

    # ============================================
    # GAME OUTCOME CARDS — High/Low + Biggest/Closest/Luckiest/Unluckiest
    # ============================================

    # Styles: outlined cards + right-aligned info icon + right-side popover
    st.markdown("""
    <style>
    .cardX { 
      position:relative; 
      border:1px solid #555;
      border-radius:10px; 
      padding:10px 12px; 
      margin:6px 0; 
      background:transparent; 
    }
    .cardX .label-row {
      display:flex; 
      align-items:center; 
      justify-content:space-between;
      gap:8px;
      margin-bottom:2px;
    }
    .cardX .title { 
      font-size:15px; 
      font-weight:700; 
      margin:0;
    }
    .cardX .value { 
      font-size:18px; 
      font-weight:800; 
    }
    .cardX .sub { 
      font-size:12px; 
      color:#aaa; 
      margin-top:2px; 
    }

    /* Info (ⓘ) trigger on right */
    .anno { position:relative; }
    .anno details { position:relative; }
    .anno summary {
      cursor:pointer;
      list-style:none;
      display:inline-flex;
      align-items:center;
      justify-content:center;
      width:22px; height:22px;
      border-radius:50%;
      border:1px solid #6b9cff;
      color:#cfe1ff;
      font-weight:700;
      user-select:none;
    }
    .anno summary::-webkit-details-marker { display:none; }

    /* Popover to the RIGHT of the card */
    .anno .anno-panel {
      position:absolute;
      left:calc(100% + 8px);     /* open to the RIGHT of the card */
      top:0;
      min-width:220px;
      max-width:280px;
      background:#1b1b1b;
      color:#ccc;
      border:1px solid #444;
      border-radius:8px;
      padding:10px 12px;
      box-shadow:0 8px 20px rgba(0,0,0,0.45);
      z-index:50;
    }

    /* Tiny caret pointing back to the icon */
    .anno .anno-panel:before {
      content:"";
      position:absolute;
      left:-6px; top:10px;
      width:0; height:0;
      border-top:6px solid transparent;
      border-bottom:6px solid transparent;
      border-right:6px solid #444;
    }
    .anno .anno-panel:after {
      content:"";
      position:absolute;
      left:-5px; top:11px;
      width:0; height:0;
      border-top:5px solid transparent;
      border-bottom:5px solid transparent;
      border-right:5px solid #1b1b1b;
    }

    /* On very small screens, drop the popover BELOW instead of right */
    @media (max-width: 640px) {
      .anno .anno-panel { 
        left:auto; right:0; top:calc(100% + 8px); 
      }
      .anno .anno-panel:before, .anno .anno-panel:after {
        left:auto; right:10px; top:-6px; transform:rotate(90deg);
        border:none;
      }
    }
    </style>
    """, unsafe_allow_html=True)

    # ---------- Guards ----------
    need_m = {"team_key","opponent_team_key","points_for","points_against","week"}
    if not need_m.issubset(matchups.columns):
        st.info(f"Matchups missing columns: {', '.join(sorted(need_m - set(matchups.columns)))}")
    else:
        # -------- Build & filter season dataframe m --------
        m = matchups.copy()

        # attach year via teams if not present
        if "year" not in m.columns:
            t_year = teams[["team_key", year_col]].dropna().drop_duplicates().rename(columns={year_col:"year"})
            m = m.merge(t_year, on="team_key", how="left", validate="m:1")

        # filter to selected season & regular season only
        m = m[m["year"] == selected_year].copy()
        if "is_playoffs" in m.columns:
            m["is_playoffs"] = pd.to_numeric(m["is_playoffs"], errors="coerce").fillna(0).astype(int)
            m = m[m["is_playoffs"] == 0]

        # numerics
        for c in ["points_for","points_against","week"]:
            m[c] = pd.to_numeric(m[c], errors="coerce")

        # team/owner info (this season)
        t_info = (
            teams[teams[year_col] == selected_year][["team_key","owner_name","team_name"]]
            .dropna(subset=["team_key"]).copy()
        )
        t_info["team_key"] = t_info["team_key"].astype(str)
        m["team_key"] = m["team_key"].astype(str)
        m["opponent_team_key"] = m["opponent_team_key"].astype(str)

        # join this side as 'owner'/'team'
        m = m.merge(
            t_info.rename(columns={"owner_name":"owner","team_name":"team"}),
            on="team_key", how="left"
        )

        # join OPPONENT info via opponent_team_key
        opp_info = t_info.rename(columns={
            "team_key":  "opponent_team_key",
            "owner_name":"opponent_owner_from_teams",
            "team_name": "opponent_team_name"
        })
        m = m.merge(opp_info, on="opponent_team_key", how="left")

        # compute margin & result
        m["margin"] = m["points_for"] - m["points_against"]
        m["result"] = np.where(m["margin"] > 0, "win",
                        np.where(m["margin"] < 0, "loss", "tie"))

        # ---------- Helpers ----------
        def _anno(icon_hint: str) -> str:
            """Right-aligned ⓘ with popover; no 'What's this?' text."""
            return f"""
            <div class="anno">
              <details>
                <summary title="{icon_hint}">i</summary>
                <div class="anno-panel">{icon_hint}</div>
              </details>
            </div>
            """

        def _card(owner, opp_owner, week, pf, pa, label, emoji, hint: str):
            owner = (owner if pd.notna(owner) and str(owner).strip() else "-")
            opp_owner = (opp_owner if pd.notna(opp_owner) and str(opp_owner).strip() else "-")
            wk = int(week) if pd.notna(week) else "-"
            # one decimal place for scores
            pf_s = f"{float(pf):.1f}" if pd.notna(pf) else "0.0"
            pa_s = f"{float(pa):.1f}" if pd.notna(pa) else "0.0"
            return f"""
            <div class="cardX">
              <div class="label-row">
                <div class="title">{emoji} {label}</div>
                {_anno(hint)}
              </div>
              <div class="value">{owner}</div>
              <div class="sub">Week {wk} vs {opp_owner} • {pf_s} – {pa_s}</div>
            </div>
            """

        # ---------- Build each card ----------
        wins = m[m["result"] == "win"].copy()

        # Highest Team Score (any result)
        if not m.empty and m["points_for"].notna().any():
            hi = m.loc[m["points_for"].idxmax()]
            highest_html = _card(
                hi.get("owner"), hi.get("opponent_owner_from_teams"), hi.get("week"),
                hi.get("points_for"), hi.get("points_against"),
                "Highest Team Score", "🚀",
                "The single highest weekly points scored by any team (regular season only)"
            )
        else:
            highest_html = _card(None, None, None, 0, 0, "Highest Team Score", "🚀",
                                 "No team-week scoring found.")

        # Lowest Team Score (any result)
        if not m.empty and m["points_for"].notna().any():
            lo = m.loc[m["points_for"].idxmin()]
            lowest_html = _card(
                lo.get("owner"), lo.get("opponent_owner_from_teams"), lo.get("week"),
                lo.get("points_for"), lo.get("points_against"),
                "Lowest Team Score", "🧊",
                "The single lowest weekly points scored by any team (regular season only)"
            )
        else:
            lowest_html = _card(None, None, None, 0, 0, "Lowest Team Score", "🧊",
                                "No team-week scoring found.")

        # Biggest Win (largest positive margin)
        if not wins.empty:
            bw = wins.loc[wins["margin"].idxmax()]
            biggest_html = _card(
                bw["owner"], bw["opponent_owner_from_teams"], bw["week"],
                bw["points_for"], bw["points_against"],
                "Biggest Win", "📏",
                "The win with the biggest points margin (points for − points against)"
            )
        else:
            biggest_html = _card(None, None, None, 0, 0, "Biggest Win", "📏",
                                 "No qualifying wins found.")

        # Closest Win (smallest positive margin)
        cw = wins[wins["margin"] > 0]
        if not cw.empty:
            row = cw.loc[cw["margin"].idxmin()]
            closest_html = _card(
                row["owner"], row["opponent_owner_from_teams"], row["week"],
                row["points_for"], row["points_against"],
                "Closest Win", "🤏",
                "The win with the smallest points margin (points for − points against)"
            )
        else:
            closest_html = _card(None, None, None, 0, 0, "Closest Win", "🤏",
                                 "No qualifying wins found.")

        # Luckiest Win (lowest PF among wins)
        if not wins.empty:
            lw = wins.loc[wins["points_for"].idxmin()]
            luckiest_html = _card(
                lw["owner"], lw["opponent_owner_from_teams"], lw["week"],
                lw["points_for"], lw["points_against"],
                "Luckiest Win", "🍀",
                "The win with the fewest points scored by a winner all season."
            )
        else:
            luckiest_html = _card(None, None, None, 0, 0, "Luckiest Win", "🍀",
                                  "No wins recorded in the selected regular season.")

        # Unluckiest Loss (highest PF among losses)
        losses = m[m["result"] == "loss"].copy()
        if not losses.empty:
            ul = losses.loc[losses["points_for"].idxmax()]
            unluckiest_html = _card(
                ul["owner"], ul["opponent_owner_from_teams"], ul["week"],
                ul["points_for"], ul["points_against"],
                "Unluckiest Loss", "☔",
                "The loss with the most points scored by a loser all season."
            )
        else:
            unluckiest_html = _card(None, None, None, 0, 0, "Unluckiest Loss", "☔",
                                    "No losses recorded in the selected regular season.")

        # ---------- Render (3 columns × 2 rows, in your requested order) ----------
        st.markdown(
            '<div style="font-size:20px;font-weight:600;line-height:1.1;margin-top:8px;margin-bottom:6px;">Season Superlatives</div>',
            unsafe_allow_html=True
        )

        row1 = st.columns(3, gap="small")
        with row1[0]: st.markdown(highest_html, unsafe_allow_html=True)
        with row1[1]: st.markdown(lowest_html,  unsafe_allow_html=True)
        with row1[2]: st.markdown(biggest_html, unsafe_allow_html=True)

        row2 = st.columns(3, gap="small")
        with row2[0]: st.markdown(closest_html,    unsafe_allow_html=True)
        with row2[1]: st.markdown(luckiest_html,   unsafe_allow_html=True)
        with row2[2]: st.markdown(unluckiest_html, unsafe_allow_html=True)
