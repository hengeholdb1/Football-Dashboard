import pandas as pd
import numpy as np
import plotly.graph_objects as go

def show_team_insights(st, go, teams_df, matchups_df, players_df):
    # -----------------------------
    # Normalize & light coercions
    # -----------------------------
    teams = teams_df.copy()
    matchups = matchups_df.copy()
    players = players_df.copy()

    for df in (teams, matchups, players):
        df.columns = df.columns.str.strip().str.lower()

    # coerce numerics (only if present)
    for c in ["year","regular_season_ranking","wins","losses",
              "points_for_total","points_against_total",
              "number_of_waiver_moves","number_of_trades"]:
        if c in teams.columns:
            teams[c] = pd.to_numeric(teams[c], errors="coerce")

    for c in ["year","week","is_playoffs","points_for","points_against"]:
        if c in matchups.columns:
            matchups[c] = pd.to_numeric(matchups[c], errors="coerce")

    for c in ["week","player_week_points"]:
        if c in players.columns:
            players[c] = pd.to_numeric(players[c], errors="coerce")

    # -----------------------------
    # Owner & Year selectors (with placeholders)
    # -----------------------------

    # --- Owner selector ---
    owners = sorted(teams["owner_name"].dropna().unique().tolist()) if "owner_name" in teams.columns else []
    owner_options = ["Select an owner..."] + owners

    selected_owner_label = st.selectbox(
        "Select Owner:",
        owner_options,
        index=0
    )

    if selected_owner_label == "Select an owner..." or not selected_owner_label:
        st.info("Please select an owner to continue")
        return  # or st.stop() if outside a function flow is acceptable

    owner = selected_owner_label

    # --- Year selector (filtered by owner, exclude 2017) ---
    if "year" in teams.columns:
        owner_years = (
            teams.loc[teams["owner_name"] == owner, "year"]
            .pipe(pd.to_numeric, errors="coerce")
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
        owner_years = sorted([y for y in owner_years if y != 2017], reverse=True)  # exclude 2017
    else:
        owner_years = []

    year_options = ["Select a year..."] + owner_years

    selected_year_label = st.selectbox(
        "Select Year:",
        year_options,
        index=0
    )

    if selected_year_label == "Select a year..." or selected_year_label is None:
        st.info("Please select a year to continue")
        return  # or st.stop()

    year = int(selected_year_label)

    # Optional slices (keep if you use them later)
    teams_owner_all = teams[teams["owner_name"] == owner].copy()                # includes 2017
    teams_owner     = teams_owner_all[teams_owner_all["year"] != 2017].copy()   # excludes 2017

    # -----------------------------
    # DF EDITS
    # -----------------------------
    team_row = (
        teams[(teams["owner_name"] == owner) & (teams["year"] == year)]
        .sort_values("team_key")
        .head(1)
    )
    if team_row.empty:
        st.warning("No team found for this owner/year.")
        return

    g = lambda col: (team_row[col].iloc[0] if col in team_row.columns else np.nan)
    card_team_name          = g("team_name") if pd.notna(g("team_name")) else "-"
    card_league_result      = g("league_result") if pd.notna(g("league_result")) else "-"
    card_rank               = g("regular_season_ranking")
    wins                    = g("wins")
    losses                  = g("losses")
    points_for_total        = g("points_for_total")
    points_against_total    = g("points_against_total")
    number_of_waiver_moves  = g("number_of_waiver_moves")
    number_of_trades        = g("number_of_trades")
    team_key                = g("team_key")

        # -----------------------------
    # Team header (Logo + Name) ABOVE the cards
    # -----------------------------
    def _pick_logo_url(row):
        for c in ("logo_url", "team_logo_url", "team_logo"):
            if c in row.index:
                v = row[c]
                if pd.notna(v) and str(v).strip():
                    return str(v).strip()
        return None

    logo_url = _pick_logo_url(team_row.iloc[0]) or "assets/logo.png"
    team_url = g("team_url")

    # --- OPTION 1: Make team name itself a hyperlink ---
    team_name_html = (
        f'<a href="{team_url}" target="_blank" style="color:inherit; text-decoration:none;">{card_team_name}</a>'
        if pd.notna(team_url) and str(team_url).strip()
        else card_team_name
    )

    # --- OPTION 2: Keep plain team name + link icon ---
    link_icon_html = (
        f'<a href="{team_url}" target="_blank" style="margin-left:6px; color:#1E90FF; text-decoration:none;">🔗</a>'
        if pd.notna(team_url) and str(team_url).strip()
        else ""
    )

    st.markdown(f"""
    <style>
      .team-header {{
        display:flex; align-items:center; gap:10px;
        margin:6px 0 8px; line-height:1;
      }}
      .team-header img {{
        width:60px; height:60px; object-fit:contain;
        border-radius:8px; border:1px solid #333; background:#111;
      }}
      .team-header .name {{
        font-size:30px; font-weight:800; white-space:nowrap;
      }}
      @media (max-width:480px) {{
        .team-header .name {{ font-size:26px; }}
        .team-header img {{ width:40px; height:40px; }}
      }}
    </style>
    <div class="team-header">
      <img src="{logo_url}" onerror="this.onerror=null;this.src='assets/logo.png';" />
      <div class="name">
        {team_name_html}{link_icon_html}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ---------- CARD SECTION (3 rows x 3 cards) ----------
    from streamlit.components.v1 import html as st_html

    def _fmt_int(v):
        try:
            x = pd.to_numeric(v, errors="coerce")
            if pd.isna(x):
                return "-"
            return str(int(round(x)))
        except Exception:
            return "-"

    def _fmt_val(v):
        if v is None:
            return "-"
        try:
            x = pd.to_numeric(v, errors="coerce")
            if pd.isna(x):
                return "-"
            return str(int(x)) if float(x).is_integer() else str(x)
        except Exception:
            return str(v) if str(v).strip() else "-"

    # Force integer formatting for PF/PA/PDiff
    pf   = _fmt_int(points_for_total)
    pa   = _fmt_int(points_against_total)
    pdiff = "-"
    try:
        pf_n = pd.to_numeric(points_for_total, errors="coerce")
        pa_n = pd.to_numeric(points_against_total, errors="coerce")
        if not pd.isna(pf_n) and not pd.isna(pa_n):
            pdiff = str(int(round(pf_n - pa_n)))
    except Exception:
        pass

    # FAAB Used from teams_df
    faab_used = g("faab_balance_used")
    faab_used = _fmt_val(faab_used)

    # League Result (smaller text value)
    league_result_clean = (str(card_league_result).strip().title()
                           if pd.notna(card_league_result) and str(card_league_result).strip()
                           else "-")

    def render_cards_block(rows):
        flat = [t for row in rows for t in row]
        cards_html = "".join(
            f"""
            <div class="card">
              <div class="label">{lbl}</div>
              <div class="value {'small-text' if lbl=='League Result' else ''}">
                {('-' if (val is None or (isinstance(val,float) and pd.isna(val))) else val)}
              </div>
              {f'<div class="sub">{sub}</div>' if (len(tup)>2 and (sub:=tup[2])) else ''}
            </div>
            """
            for tup in flat for lbl,val,*_ in [tup]
        )

        html = f"""<style>.cards {{display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); column-gap:15px; row-gap:14px; margin:10px 0;}} .card {{background:transparent; border:none; padding:0; color:#fff; min-width:0; display:flex; flex-direction:column;}} .label {{font-size:20px; font-weight:600; border-bottom:1px solid #666; padding-bottom:2px; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:left; width:100%;}} .value {{color:#d4af37; font-size:18px; font-weight:900; line-height:1.3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:left;}} .value.small-text {{color:#d4af37; font-size:18px; font-weight:900; line-height:1.3; text-align:left;}} .sub {{font-size:10px; opacity:.8; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:left;}} @media (max-width:480px){{ .label{{font-size:16px;}} .value{{font-size:18px;}} .value.small-text{{font-size:14px; transform: translateY(4px);}} .sub{{font-size:9px;}} }}</style><div class="cards">{cards_html}</div>"""

        st_html(html, height=70 * len(rows))

    render_cards_block([
        # Row 1
        [("Wins", _fmt_int(wins)), ("Losses", _fmt_int(losses)), ("League Result", league_result_clean)],
        # Row 2
        [("Points For", pf), ("Points Against", pa), ("Points Diff", pdiff)],
        # Row 3
        [("Waiver Moves", _fmt_int(number_of_waiver_moves)), ("FAAB Used", faab_used), ("Trades", _fmt_int(number_of_trades))],
    ])

    # =============================
    # NEXT VISUAL: Weekly Team Stacks by Player + League Avg Line
    # =============================

    def is_started(selected_position):
        if selected_position is None:
            return False
        s = str(selected_position).strip().upper()
        return s not in ("BN","IR")   # per your rule

    POS_COLORS = {
        "WR":"#1f77b4",  # Blue
        "RB":"#2ca02c",  # Green
        "QB":"#d62728",  # Red
        "TE":"#ff7f0e",  # Orange
        "K":"#9467bd",   # Purple
        "DEF":"#8c564b", "DST":"#8c564b"
    }
    def norm_pos(p):
        s = str(p).upper() if p is not None else ""
        return "DEF" if s == "DST" else s

    # ---- Stamp YEAR onto matchups via teams (team_key -> year), filter regular season
    teams_key_year = teams[["team_key","year"]].dropna().drop_duplicates()
    m_y = matchups.merge(teams_key_year, on="team_key", how="left", validate="m:1")
    m_y = m_y[m_y["year"] == year].copy()

    if "is_playoffs" in m_y.columns:
        m_regular = m_y[m_y["is_playoffs"] == 0].copy()
    else:
        m_regular = m_y.copy()

    if "week" not in m_regular.columns:
        st.info("Missing 'week' in matchups; cannot plot weekly chart.")
        st.stop()
    m_regular["week"] = pd.to_numeric(m_regular["week"], errors="coerce")

    # Weeks continuity (render zeros for byes/missing)
    weeks = sorted(m_regular["week"].dropna().astype(int).unique().tolist())

    # ---- Stamp YEAR onto players via teams (team_key -> year), join to regular-season matchups
    t1_y = teams[teams["year"] == year].drop_duplicates(subset=["team_key"])[["team_key","year"]]
    p1 = players.merge(t1_y, on="team_key", how="left", validate="m:1")
    p1 = p1[p1["year"].notna()].copy()
    p1["year"] = p1["year"].astype(int)

    pm = p1.merge(
        m_regular[["team_key","week","year"]],
        on=["team_key","week","year"],
        how="inner"  # only scheduled weeks
    )

    # Started only (BN/IR excluded)
    if "selected_position" not in pm.columns:
        st.info("Missing 'selected_position' in players; cannot build weekly stacks.")
        st.stop()
    pm = pm[pm["selected_position"].apply(is_started)].copy()

    # Ensure necessary columns exist
    if "player_week_points" not in pm.columns:
        st.info("Missing 'player_week_points' in players; cannot build weekly stacks.")
        st.stop()
    if "player_name" not in pm.columns:
        # Fallback to player_key if name is missing
        pm["player_name"] = pm.get("player_key").astype(str)

    pm["player_week_points"] = pd.to_numeric(pm["player_week_points"], errors="coerce").fillna(0.0)

    # ---- Filter to this team
    team_key_str = str(team_key)
    team_started = pm[pm["team_key"] == team_key_str].copy()
    if team_started.empty:
        st.info("No started-player rows for this team in the regular season.")
        st.stop()

    # Determine each player's PRIMARY position (mode across started weeks)
    team_started["player_position_norm"] = team_started["player_position"].map(norm_pos)
    primary_pos_by_player = (
        team_started
        .dropna(subset=["player_name"])
        .groupby("player_name")["player_position_norm"]
        .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else (s.dropna().iloc[0] if not s.dropna().empty else ""))
        .to_dict()
    )

    # Build per-player weekly arrays aligned to 'weeks'
    points_by_player_week = (
        team_started.groupby(["player_name","week"], dropna=False)["player_week_points"].sum().reset_index()
    )

    # Make a quick lookup for faster plotting
    from collections import defaultdict
    weekly_series = defaultdict(dict)
    for _, r in points_by_player_week.iterrows():
        weekly_series[r["player_name"]][int(r["week"])] = float(r["player_week_points"])

    # Sort players by total season points (descending) for visual stacking order
    player_totals = (
        team_started.groupby("player_name", dropna=False)["player_week_points"].sum().sort_values(ascending=False)
    )
    player_order = player_totals.index.tolist()

        # ---- League median line (median of points_for across all teams that week)
    # ---- League median line (median of points_for across all teams that week)
    if "points_for" not in m_regular.columns:
        st.info("Missing 'points_for' in matchups; cannot compute league median line.")
        st.stop()

    league_median = (
        m_regular.groupby("week", as_index=False)["points_for"]
        .median()
        .rename(columns={"points_for": "league_median_pts"})
    )
    league_median = pd.DataFrame({"week": weeks}).merge(league_median, on="week", how="left")
    league_median["league_median_pts"] = pd.to_numeric(league_median["league_median_pts"], errors="coerce").fillna(0.0)

    # ---- Plot: stacked bars by PLAYER + league median line
    fig_week = go.Figure()

    # Bars per player
    for player in player_order:
        y_vals = [weekly_series[player].get(w, 0.0) for w in weeks]
        pos = primary_pos_by_player.get(player, "")
        color = POS_COLORS.get(pos, "#444")
        fig_week.add_trace(go.Bar(
            name=str(player),
            x=weeks,
            y=y_vals,
            marker_color=color,
            offsetgroup="team",
            hovertemplate="Week %{x}<br>"+f"{player}: "+"%{y:.1f} pts<extra></extra>",
            showlegend=False
        ))

    # League median line
    fig_week.add_trace(go.Scatter(
        name=None,
        x=weeks,
        y=league_median["league_median_pts"],
        mode="lines+markers",
        line=dict(width=2, color="#ffffff"),
        marker=dict(size=6, color="#ffffff"),
        hovertemplate="Week %{x}<br>League Median: %{y:.1f}<extra></extra>",
        showlegend=False 
    ))

    # --- Bottom-row W/L annotations (no emojis here)
    team_wk = (
        m_regular[m_regular["team_key"] == str(team_key)]
        [["week","week_result","high_score_flag","low_score_flag","points_for"]]
        .dropna(subset=["week"])
        .copy()
    )
    team_wk["week"] = team_wk["week"].astype(int)
    team_wk["week_result"] = team_wk["week_result"].astype(str).str.strip().str.lower()
    for flag in ("high_score_flag","low_score_flag"):
        if flag in team_wk.columns:
            team_wk[flag] = pd.to_numeric(team_wk[flag], errors="coerce").fillna(0).astype(int)
    team_wk["points_for"] = pd.to_numeric(team_wk["points_for"], errors="coerce").fillna(0.0)

    def wl_style(r):
        if r == "win":  return "W", "#2ca02c"   # green
        if r == "loss": return "L", "#d62728"   # red
        if r == "tie":  return "Tie", "#ff7f0e" # orange (optional)
        return r.title(), "#aaaaaa"

    ann = []
    for w in weeks:
        row = team_wk[team_wk["week"] == w]
        if not row.empty:
            label, color = wl_style(row.iloc[0]["week_result"])
            ann.append(dict(
                x=w, xref="x",
                y=-0.12, yref="paper",     # tweak vertical placement; -0.10 closer, -0.12 lower
                yshift=-1,                 # tiny nudge downward from tick labels
                text=f"<b>{label}</b>",
                showarrow=False,
                align="center",
                font=dict(size=11, color=color)
            ))

    # --- Emoji annotations ABOVE the bars (🔥 weekly high, ❄️ weekly low)
    emoji_anns = []
    for _, r in team_wk.iterrows():
        wk = int(r["week"])
        pts = float(r["points_for"])
        emoji = "🔥" if r.get("high_score_flag", 0) == 1 else ("❄️" if r.get("low_score_flag", 0) == 1 else None)
        if emoji:
            emoji_anns.append(dict(
                x=wk, xref="x",
                y=pts, yref="y",       # at the top of the team’s stacked bar
                yshift=16,              # nudge above the bar; tweak 6–12
                text=emoji,
                showarrow=False,
                align="center",
                font=dict(size=18)     # emoji size; tweak 16–22
            ))

    # --- League median trace already added above ---

    # --- Bottom-row W/L annotations (ann) already built above ---

    # --- Emoji annotations above bars (emoji_anns) already built above ---

    # --- Custom week-number tick labels (replace built-in labels) ---
    TICK_Y = -0.08   # move week numbers up/down
    tick_labels = [
        dict(
            x=w, xref="x",
            y=TICK_Y, yref="paper",
            text=str(w),
            showarrow=False,
            align="center",
            font=dict(size=11, color="#cccccc")
        )
        for w in weeks
    ]

    # Hide built-in tick labels
    fig_week.update_xaxes(
        showticklabels=False,
        ticks="outside",
        ticklen=2,
        showline=False,
        linecolor="#888",
        linewidth=1
    )

    # --- Combine all annotations ---
    all_annotations = tick_labels + ann + emoji_anns

    # --- Layout ---
    fig_week.update_layout(
        barmode="relative",
        bargap=0.25,
        height=360,
        xaxis=dict(
            dtick=1,
            fixedrange=True,
            title=None
        ),
        yaxis=dict(
            title=dict(text="Points Scored", standoff=12),
            fixedrange=True
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        annotations=all_annotations,
        margin=dict(l=8, r=8, t=0, b=72)
    )

    # --- Title + render ---
    st.markdown('<div style="font-size:20px;font-weight:600;margin-top:0px; margin-bottom:0px; line-height:1;">Weekly Team Performance</div>', unsafe_allow_html=True)
    #st.plotly_chart(fig_week, use_container_width=True, config={'displayModeBar': False})


    # --- Legend (emoji + league median + position chips) ---
    # --- Legend (single-row, horizontally aligned; scrolls on mobile) ---
    legend_html = """
    <style>
    .legend-wrap {
      display:flex;
      flex-wrap:nowrap;          /* single line */
      align-items:center;
      gap:8px;
      margin:6px 0 10px;
      overflow-x:auto;           /* allow sideways scroll on small screens */
      -webkit-overflow-scrolling: touch;
      scrollbar-width: thin;     /* Firefox */
    }
    .legend-chip {
      display:flex; align-items:center; gap:6px;
      background:#222; border:1px solid #333; color:#ddd;
      padding:2px 8px; border-radius:8px; font-size:11px; line-height:1.1;
      white-space:nowrap;        /* keep each chip on one line */
      flex:0 0 auto;             /* prevent shrinking/wrapping */
    }
    .legend-swatch {
      width:10px; height:10px; border-radius:3px; display:inline-block;
    }
    .legend-line {
      width:18px; height:0; border-top:2px solid #ffffff; display:inline-block;
    }
    .legend-emoji { font-size:14px; line-height:1; }
    </style>

    <div class="legend-wrap">
      <span class="legend-chip"><span class="legend-emoji">🔥</span> High Score</span>
      <span class="legend-chip"><span class="legend-emoji">❄️</span> Low Score</span>
      <span class="legend-chip"><span class="legend-line"></span> League Median</span>
    </div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)

    st.plotly_chart(fig_week, use_container_width=True, config={'displayModeBar': False})

    # =============================
    # TREEMAP: Season Points by Player (started only, regular season)
    # =============================

    if 'team_started' not in locals() or team_started.empty:
        st.info("No started-player data available for this team/year to build the treemap.")
    else:
        import plotly.express as px

        df = team_started.copy()

        # Ensure core columns
        if "player_week_points" not in df.columns:
            st.info("Missing 'player_week_points'; cannot build treemap.")
        else:
            df["player_week_points"] = pd.to_numeric(df["player_week_points"], errors="coerce").fillna(0.0)

            # Player name fallback
            if "player_name" not in df.columns or df["player_name"].isna().all():
                df["player_name"] = df.get("player_key").astype(str)

            # Normalize positions
            VALID_POS = {"QB","RB","WR","TE","K","DEF"}
            POS_COLORS = {
                "WR":"#1f77b4",  # Blue
                "RB":"#2ca02c",  # Green
                "QB":"#d62728",  # Red
                "TE":"#ff7f0e",  # Orange
                "K":"#9467bd",   # Purple
                "DEF":"#8c564b",
                "UNK":"#444444"  # fallback/unknown
            }

            def norm_pos_main(p):
                s = str(p).upper() if p is not None else ""
                return "DEF" if s == "DST" else s

            def norm_pos_from_selected(s):
                # Use selected_position only as a fallback; ignore BN/IR/FLEX-type categories
                x = str(s).upper() if s is not None else ""
                if x in ("BN","IR","NA","OUT"): return None
                if x == "DST": return "DEF"
                # If it's a pure position we support, use it; otherwise return None (e.g., W/R/T)
                return x if x in VALID_POS else None

            # Pick a primary position per player: prefer player_position mode, else selected_position mode
            def primary_pos_for(player_sub):
                pm = player_sub["player_position"].dropna().map(norm_pos_main)
                if not pm.empty and not pm.mode().empty and pm.mode().iloc[0] in VALID_POS:
                    return pm.mode().iloc[0]
                sm = player_sub["selected_position"].dropna().map(norm_pos_from_selected)
                if not sm.empty and not sm.mode().empty and sm.mode().iloc[0] in VALID_POS:
                    return sm.mode().iloc[0]
                return "UNK"

            # Build season totals and primary position
            df["player_position_norm"] = df["player_position"].map(norm_pos_main)
            season_player = (
                df.groupby("player_name", dropna=False)
                .apply(lambda sub: pd.Series({
                    "season_points": sub["player_week_points"].sum(),
                    "primary_pos": primary_pos_for(sub)
                }))
                .reset_index()
            )

            # Filter out non-positive totals (treemap can't render zero-size boxes)
            season_player = season_player[season_player["season_points"] > 0]

            if season_player.empty:
                st.info("No positive started-player scoring found for this team/year (regular season).")
            else:
                # Prefer to show only valid positions if present; else include UNK
                if season_player["primary_pos"].isin(VALID_POS).any():
                    season_player = season_player[season_player["primary_pos"].isin(VALID_POS)]
                    color_map = {k: POS_COLORS[k] for k in VALID_POS}
                else:
                    color_map = POS_COLORS  # includes UNK

                st.markdown('<div style="font-size:20px;font-weight:600;margin-top:0px; margin-bottom:0px; line-height:1;">Total Points by Roster</div>', unsafe_allow_html=True)
                fig_tree = px.treemap(
                    season_player,
                    path=["primary_pos","player_name"],
                    values="season_points",
                    color="primary_pos",
                    color_discrete_map=color_map,
                    height=340
                )
                fig_tree.update_layout(margin=dict(l=8, r=8, t=0, b=8))
                st.plotly_chart(fig_tree, use_container_width=True, config={"displayModeBar": False})
