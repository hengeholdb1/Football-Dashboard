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
    owners = sorted(teams["owner_name"].dropna().unique().tolist()) if "owner_name" in teams.columns else []
    owner_options = ["Select an owner..."] + owners

    # (optional) stable key for owner select
    selected_owner_label = st.selectbox("Select Owner:", owner_options, index=0, key="owner_select")

    if selected_owner_label == "Select an owner..." or not selected_owner_label:
        st.info("Please select an owner to continue")
        return

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
        # newest first
        owner_years = sorted([y for y in owner_years if y != 2017], reverse=True)
    else:
        owner_years = []

    year_options = ["Select a year..."] + owner_years

    # Default to the newest year for this owner (index=1 because of the placeholder at 0).
    # Using a key that includes the owner forces Streamlit to reset the widget when owner changes.
    default_year_index = 1 if owner_years else 0
    selected_year_label = st.selectbox(
        "Select Year:",
        year_options,
        index=default_year_index,
        key=f"year_for_{owner}"
    )

    if selected_year_label == "Select a year..." or selected_year_label is None:
        st.info("Please select a year to continue")
        return

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
    # Compute league ranks for PF/PA (within selected year)
    # -----------------------------
    def _ordinal(n: int) -> str:
        try:
            n = int(n)
        except Exception:
            return "-"
        if 10 <= n % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    pf_rank_val = np.nan
    pa_rank_val = np.nan
    if "team_key" in teams.columns and "points_for_total" in teams.columns and "points_against_total" in teams.columns:
        year_df = teams[teams["year"] == year].copy()
        year_df["points_for_total"] = pd.to_numeric(year_df["points_for_total"], errors="coerce")
        year_df["points_against_total"] = pd.to_numeric(year_df["points_against_total"], errors="coerce")

        # Rank descending so 1 = most points (PF) and 1 = most against (PA).
        # If you prefer PA where 1 = fewest against, change ascending=True below for pa_rank.
        year_df["pf_rank"] = year_df["points_for_total"].rank(ascending=False, method="min")
        year_df["pa_rank"] = year_df["points_against_total"].rank(ascending=False, method="min")  # flip to ascending=True if desired

        rmap_pf = dict(zip(year_df["team_key"], year_df["pf_rank"]))
        rmap_pa = dict(zip(year_df["team_key"], year_df["pa_rank"]))
        pf_rank_val = rmap_pf.get(team_key, np.nan)
        pa_rank_val = rmap_pa.get(team_key, np.nan)

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

    # OPTION 1: Make team name a hyperlink (kept)
    team_name_html = (
        f'<a href="{team_url}" target="_blank" style="color:inherit; text-decoration:none;">{card_team_name}</a>'
        if pd.notna(team_url) and str(team_url).strip()
        else card_team_name
    )

    # OPTION 2: Link icon (kept)
    link_icon_html = (
        f'<a href="{team_url}" target="_blank" class="link-icon" aria-label="Team link">🔗</a>'
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
        border-radius:8px; border:1px solid #333; background:#111; flex:0 0 auto;
      }}
      .team-header .name-wrap {{
        display:flex; align-items:center; gap:6px;
        min-width:0;
        flex:1 1 auto;
      }}
      .team-header .name {{
        font-weight:800;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
        line-height:1.05;
        font-size:30px;
      }}
      .team-header .link-icon {{
        margin-left:2px; text-decoration:none;
        color:#1E90FF; flex:0 0 auto;
      }}
      @media (max-width:480px) {{
        .team-header img {{ width:40px; height:40px; }}
        .team-header .name {{ font-size:26px; }}
      }}
    </style>

    <div class="team-header">
      <img src="{logo_url}" onerror="this.onerror=null;this.src='assets/logo.png';" />
      <div class="name-wrap">
        <div class="name" id="team-name-el">{team_name_html}</div>
        {link_icon_html}
      </div>
    </div>

    <script>
    (function() {{
      const el = document.getElementById('team-name-el');
      if (!el) return;
      const minPx = 14;
      const step  = 1;
      const style = window.getComputedStyle(el);
      let size = parseFloat(style.fontSize) || 30;
      const wrap = el.parentElement;
      if (wrap) wrap.style.minWidth = '0';
      const fits = () => el.scrollWidth <= el.clientWidth;
      let guard = 60;
      while (!fits() && size > minPx && guard-- > 0) {{
        size -= step;
        el.style.fontSize = size + 'px';
      }}
    }})();
    </script>
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
    pf_raw = _fmt_int(points_for_total)
    pa_raw = _fmt_int(points_against_total)

    # Attach ranks (e.g., "1284 (7th)")
    pf = pf_raw
    pa = pa_raw
    if pf_raw != "-" and not pd.isna(pf_rank_val):
        pf = f"{pf_raw} ({_ordinal(int(pf_rank_val))})"
    if pa_raw != "-" and not pd.isna(pa_rank_val):
        pa = f"{pa_raw} ({_ordinal(int(pa_rank_val))})"

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

    # --- New: compute Record and formatted Reg Season Rank ---
    record = "-"
    w_i, l_i = _fmt_int(wins), _fmt_int(losses)
    if w_i != "-" and l_i != "-":
        record = f"{w_i}-{l_i}"

    reg_rank = _fmt_int(card_rank)

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

        html = f"""
        <style>
        .cards {{
            display:grid;
            grid-template-columns: repeat(3, minmax(0,1fr));
            column-gap:15px;
            row-gap:14px;
            margin:10px 0;
        }}
        .card {{
            background:transparent;
            border:none;
            padding:0;
            min-width:0;
            display:flex;
            flex-direction:column;
        }}
        .label {{
            font-size:16px;
            font-weight:500;
            color:#aaa;
            border-bottom:1px solid #555;
            padding-bottom:2px;
            margin-bottom:4px;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
            text-align:left;
            width:100%;
        }}
        .value {{
            color:#fff;
            font-size:20px;
            font-weight:800;
            line-height:1.3;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
            text-align:left;
        }}
        .value.small-text {{
            color:#fff;
            font-size:16px;
            font-weight:700;
            line-height:1.3;
            text-align:left;
        }}
        .sub {{
            font-size:10px;
            color:#999;
            margin-top:2px;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
            text-align:left;
        }}
        @media (max-width:480px){{
            .label{{font-size:14px;}}
            .value{{font-size:18px;}}
            .value.small-text{{font-size:14px; transform: translateY(4px);}}
            .sub{{font-size:9px;}}
        }}
        </style>
        <div class="cards">{cards_html}</div>
        """

        st_html(html, height=70 * len(rows))

    render_cards_block([
        [("Record", record), ("Reg Season Rank", reg_rank), ("League Result", league_result_clean)],
        [("Points For", pf), ("Points Against", pa), ("Points Diff", pdiff)],
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

    # =============================
    # BAR CHART ONLY (Neutral, no error bars): Weekly Position Scoring vs League
    # =============================
    required = {"selected_position", "player_week_points", "team_key", "week"}
    if not required.issubset(pm.columns):
        miss = sorted(required - set(pm.columns))
        st.info(f"Missing columns for bar chart: {', '.join(miss)}")
    else:
        dfb = pm.copy()
        dfb["selected_position"]  = dfb["selected_position"].astype(str).str.upper()
        dfb["player_week_points"] = pd.to_numeric(dfb["player_week_points"], errors="coerce").fillna(0.0)
        dfb["team_key"]           = dfb["team_key"].astype(str)
        dfb["week"]               = pd.to_numeric(dfb["week"], errors="coerce").astype("Int64")

        # Map slots -> position groups; DST->DEF; any non-pure slot -> FLEX
        BASE = {"QB","RB","WR","TE","K","DEF"}
        def map_slot(s: str) -> str:
            s = (s or "").strip().upper()
            if s == "DST": return "DEF"
            return s if s in BASE else "FLEX"
        dfb["pos"] = dfb["selected_position"].map(map_slot)

        # Average per TEAM × WEEK × POS (avg of starters that week)
        twpos_avg = (
            dfb.groupby(["team_key","week","pos"], as_index=False)["player_week_points"]
               .mean()
               .rename(columns={"player_week_points":"weekly_avg"})
        )

        # Meta for hover
        meta = (
            teams[teams["year"] == year][["team_key","team_name","owner_name"]]
            .dropna(subset=["team_key"]).drop_duplicates(subset=["team_key"])
            .assign(team_key=lambda d: d["team_key"].astype(str))
        )
        twpos_avg = twpos_avg.merge(meta, on="team_key", how="left")

        team_key_str = str(team_key)
        team_long    = twpos_avg[twpos_avg["team_key"] == team_key_str].copy()
        league_long  = twpos_avg[twpos_avg["team_key"] != team_key_str].copy()

        if team_long.empty or league_long.empty:
            st.info("Not enough data to render the bar chart for this team/season.")
        else:
            def stats_df(df_):
                return (
                    df_.groupby("pos", dropna=False)["weekly_avg"]
                       .agg(mean="mean",
                            median="median",
                            std="std",
                            p25=lambda s: s.quantile(0.25),
                            p75=lambda s: s.quantile(0.75),
                            min="min",
                            max="max",
                            n="count")
                       .reset_index()
                )

            s_owner  = stats_df(team_long).assign(group="Owner")
            s_league = stats_df(league_long).assign(group="League")

            desired_order = ["QB","RB","WR","TE","FLEX","K","DEF"]
            present = set(pd.concat([s_owner["pos"], s_league["pos"]]).dropna().unique())
            pos_present = [p for p in desired_order if p in present] or sorted(list(present))

            def aligned_arrays(stats: pd.DataFrame, positions):
                if stats is None or stats.empty:
                    return [None]*len(positions), [(None,)*7]*len(positions), {}
                m = stats.set_index("pos").to_dict(orient="index")
                y  = [(m[p]["mean"]   if p in m else None) for p in positions]
                cd = [(
                        (m[p]["median"] if p in m else None),
                        (m[p]["std"]    if p in m else None),
                        (m[p]["p25"]    if p in m else None),
                        (m[p]["p75"]    if p in m else None),
                        (m[p]["min"]    if p in m else None),
                        (m[p]["max"]    if p in m else None),
                        (m[p]["n"]      if p in m else 0),
                      ) for p in positions]
                return y, cd, m

            y_owner,  cd_owner,  _ = aligned_arrays(s_owner,  pos_present)
            y_league, cd_league, _ = aligned_arrays(s_league, pos_present)

            # High-contrast neutrals
            OWNER_COLOR  = "#E3E3E3"   # light gray
            LEAGUE_COLOR = "#2F2F2F"   # charcoal

            # Pattern on League for differentiation (still neutral)
            league_marker = dict(
                color=LEAGUE_COLOR,
                line=dict(color="#B0B0B0", width=1.2),
                pattern=dict(shape="/", fgcolor="#BDBDBD", bgcolor=LEAGUE_COLOR, size=6, solidity=0.25)
            )

            fig_bar = go.Figure()

            fig_bar.add_trace(go.Bar(
                x=pos_present, y=y_owner, customdata=cd_owner,
                name=str(owner), legendgroup="owner",
                marker=dict(color=OWNER_COLOR, line=dict(color="#FFFFFF", width=1.4)),
                opacity=1.0,
                hovertemplate=(
                    "<b>%{x}</b> • " + str(owner) +
                    "<br>Avg: %{y:.2f}" +
                    "<br>Median: %{customdata[0]:.2f}" +
                    "<br>Std: %{customdata[1]:.2f}" +
                    "<br>P25–P75: %{customdata[2]:.2f} – %{customdata[3]:.2f}" +
                    "<br>Min / Max: %{customdata[4]:.2f} / %{customdata[5]:.2f}" +
                    "<br>Samples: %{customdata[6]}" +
                    "<extra></extra>"
                )
            ))

            fig_bar.add_trace(go.Bar(
                x=pos_present, y=y_league, customdata=cd_league,
                name="League", legendgroup="league",
                marker=league_marker,
                opacity=1.0,
                hovertemplate=(
                    "<b>%{x}</b> • League" +
                    "<br>Avg: %{y:.2f}" +
                    "<br>Median: %{customdata[0]:.2f}" +
                    "<br>Std: %{customdata[1]:.2f}" +
                    "<br>P25–P75: %{customdata[2]:.2f} – %{customdata[3]:.2f}" +
                    "<br>Min / Max: %{customdata[4]:.2f} / %{customdata[5]:.2f}" +
                    "<br>Samples: %{customdata[6]}" +
                    "<extra></extra>"
                )
            ))

            fig_bar.update_layout(
                barmode="group",
                bargroupgap=0.12,   # within-position gap
                bargap=0.30,        # between positions
                height=300,
                margin=dict(l=8, r=28, t=0, b=0),
                legend=dict(
                    orientation="h",
                    x=0.99, y=1.02, xanchor="right", yanchor="top",  # top-right
                    bgcolor="rgba(0,0,0,0)"
                ),
                xaxis=dict(
                    title=None,
                    categoryorder="array",
                    categoryarray=pos_present,
                    tickfont=dict(size=12, color="#DDDDDD"),
                    showgrid=False, zeroline=False, fixedrange=True
                ),
                yaxis=dict(
                    title=dict(text="Avg Started Position Points", font=dict(color="#EAEAEA")),
                    tickfont=dict(color="#D0D0D0"),
                    showgrid=True, gridcolor="#3F3F3F", gridwidth=1,
                    zeroline=False, rangemode="tozero", fixedrange=True
                ),
            )

            st.markdown(
                '<div style="font-size:20px;font-weight:600;margin:6px 0 2px;">Weekly Position Scoring vs League</div>',
                unsafe_allow_html=True
            )
            st.plotly_chart(
                fig_bar,
                use_container_width=True,
                config={'displayModeBar': False},
                key=f"bar_pos_vs_league_{year}_{str(team_key)}_contrast_noerr"
            )

    # =============================
    # MATCHUPS TABLE (neutral background, Opponent as "Team (Owner)")
    # =============================
    from streamlit.components.v1 import html as st_html

    # 1) Normalize working copies
    m = matchups_df.copy()
    t = teams_df.copy()
    p = players_df.copy()

    for df in (m, t, p):
        df.columns = df.columns.str.strip().str.lower()

    # 2) team_key -> (year, team_name, owner_name)
    team_info = t[["team_key", "year", "team_name", "owner_name"]].drop_duplicates()

    # 3) Join THIS team info (get year/team/owner)
    m1 = m.merge(team_info, on="team_key", how="left", validate="m:1", suffixes=("", "_team"))

    # 4) Join OPPONENT info via opponent_team_key
    opp_info = team_info.rename(columns={
        "team_key":  "opponent_team_key",
        "team_name": "opponent_team_name",
        "owner_name":"opponent_owner_from_teams",
        "year":      "opponent_year"
    })
    m2 = m1.merge(opp_info, on="opponent_team_key", how="left", validate="m:1")

    # 5) Filter to selected season + current team
    # 5) Filter to selected season + current team + only regular season (is_playoffs = 0)
    m2 = m2[
        (m2["year"] == year) &
        (m2["team_key"].astype(str) == str(team_key)) &
        (m2["is_playoffs"].fillna(0).astype(int) == 0)   # 👈 NEW FILTER
    ].copy()


    # 6) Build Opponent as "Team (Owner)" with fallbacks
    def _pick_opponent(row):
        team  = (row.get("opponent_team_name") or "").strip()
        owner = (row.get("opponent_owner_from_teams") or row.get("opponent_owner") or "").strip()
        if team and owner: return f"{team} ({owner})"
        if team:           return team
        if owner:          return owner
        return "-"

    m2["Opponent"] = m2.apply(_pick_opponent, axis=1)

    # 7) Coerce numerics + compute points diff if needed
    for c in ["points_for", "points_against", "points_difference", "week"]:
        if c in m2.columns:
            m2[c] = pd.to_numeric(m2[c], errors="coerce")

    if "points_difference" not in m2.columns or m2["points_difference"].isna().any():
        m2["points_difference"] = (m2["points_for"] - m2["points_against"])

    # 7.5) ✨ TOP PLAYER SPLIT: name + integer points in separate columns
    # ---- Normalize players_df & filter to RS + valid positions
    if "is_playoffs" in p.columns:
        p = p[p["is_playoffs"].fillna(0).astype(int) == 0]
    if "selected_position" in p.columns:
        p = p[~p["selected_position"].astype(str).str.upper().isin(["BN","IR"])]

    # Coerce numerics
    for c in ["week", "player_week_points"]:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")

    # Choose a player-name column defensively
    name_col = next((c for c in ["player_name","name","full_name","player_full_name"] if c in p.columns), None)

    if name_col and {"team_key","week","player_week_points"}.issubset(p.columns):
        # idx of max per (team_key, week)
        idx = p.groupby(["team_key","week"])["player_week_points"].idxmax()
        top = p.loc[idx, ["team_key","week", name_col, "player_week_points"]].copy()
        top.rename(columns={name_col: "Top Player"}, inplace=True)

        # Clean fields
        top["Top Player"] = top["Top Player"].astype(str).str.strip()
        top["Top Player"] = top["Top Player"].where(top["Top Player"].ne(""), "-")
        top["Player Points"] = pd.to_numeric(top["player_week_points"], errors="coerce").round(0).astype("Int64")

        # Keep only needed
        top = top[["team_key","week","Top Player","Player Points"]]
        m2 = m2.merge(top, on=["team_key","week"], how="left")
    else:
        m2["Top Player"] = "-"
        m2["layer Pts"] = pd.Series([pd.NA] * len(m2), dtype="Int64")

    # 8) Normalize Result
    if "week_result" in m2.columns:
        m2["Result"] = (
            m2["week_result"].astype(str).str.strip().str.lower()
              .map({"win":"Win", "loss":"Loss", "tie":"Tie"})
              .fillna(m2["week_result"].astype(str).str.title())
        )
    else:
        m2["Result"] = "-"

    # 9) Final display DataFrame
    tbl = (
        m2[["week", "Opponent", "points_for", "points_against", "points_difference",
            "Top Player", "Player Points", "Result", "matchup_recap_url"]]
        .rename(columns={
            "week":               "Week",
            "points_for":         "Points For",
            "points_against":     "Points Against",
            "points_difference":  "Points Diff",
            "matchup_recap_url":  "Matchup Recap",
        })
        .sort_values(["Week"], ascending=True)
    )

    for c in ["Week", "Points For", "Points Against", "Points Diff", "Top Player Pts"]:
        if c in tbl.columns:
            tbl[c] = pd.to_numeric(tbl[c], errors="coerce").round(0).astype("Int64")

    
    # =============================
    # MATCHUPS TABLE — Interactive with short Link (no CSS colors)
    # =============================

    # Make a copy so we don't mutate tbl
    view = tbl.copy()

    # Build a separate display column with short "Link" label for the recap
    def _link_text(u):
        u = "" if pd.isna(u) else str(u).strip()
        return u if u else None  # LinkColumn handles None/NaN gracefully

    view["Matchup Recap (link)"] = view["Matchup Recap"].map(_link_text)

    # Optional: add a simple visual cue for Result (emoji), since we can't color cells
    def _result_badge(v: str) -> str:
        v2 = (v or "").strip().lower()
        return {"win": "🟢 Win", "loss": "🔴 Loss", "tie": "🟠 Tie"}.get(v2, v or "-")

    view["Result (badge)"] = view["Result"].map(_result_badge)

    # Choose column order (add Top Scorer)
    cols = ["Week", "Opponent", "Points For", "Points Against", "Points Diff",
            "Top Player", "Player Points", "Result (badge)", "Matchup Recap (link)"]
    view = view[cols]

    st.markdown(
        '<div style="font-size:20px;font-weight:600;margin:6px 0 2px;">Matchup Summary</div>',
        unsafe_allow_html=True
    )

    # Compute a height that fits all rows (approximate row & header heights in px)
    n_rows = len(view)
    row_px = 34
    header_px = 40
    padding_px = 16
    max_px = 1200  # safety cap so it doesn't get absurdly tall
    fit_height = min(max_px, header_px + n_rows * row_px + padding_px)

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Week": st.column_config.NumberColumn(format="%d", pinned="left"),
            "Points For": st.column_config.NumberColumn(format="%d"),
            "Points Against": st.column_config.NumberColumn(format="%d"),
            "Points Diff": st.column_config.NumberColumn(format="%d"),
            "Top Player": st.column_config.TextColumn("Top Player"),
            "Points Diff": st.column_config.NumberColumn(format="%d"),
            "Matchup Recap (link)": st.column_config.LinkColumn("Matchup Recap", display_text="Link"),
            "Result (badge)": st.column_config.TextColumn("Result"),
        },
        height=fit_height,  # 👈 fits all records on screen (page scroll only)
    )
