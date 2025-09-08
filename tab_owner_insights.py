import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit.components.v1 import html as st_html


def show_owner_insights(st, go_unused, teams_df, matchups_df, players_df):
    # -----------------------------
    # Normalize columns & aliases
    # -----------------------------
    for df in (teams_df, matchups_df, players_df):
        df.columns = df.columns.str.strip().str.lower()

    # === Replace the single alias_map with two maps ===
    team_alias_map = {
        'teamkey': 'team_key',
        'owner': 'owner_name',
        'league_result_final': 'league_result',
        'regular_season_rank': 'regular_season_ranking',
        'points_for': 'points_for_total',            # <- totals live in teams_df
        'points_against': 'points_against_total',    # <- totals live in teams_df
        'waiver_moves': 'number_of_waiver_moves',
        'trades': 'number_of_trades',
        'url': 'team_url',
        'draft_report_card': 'draft_grade',
        'season': 'year',
        'isfinished': 'is_finished'
    }
    matchup_alias_map = {
        'teamkey': 'team_key',
        'opponentteamkey': 'opponent_team_key',
        'owner': 'owner_name',
        'league_result_final': 'league_result',
        'regular_season_rank': 'regular_season_ranking',
        # IMPORTANT: do NOT rename weekly points here
        'url': 'matchup_url',
        'season': 'year'
    }

    # Apply them separately
    teams_df    = teams_df.rename(columns={k:v for k,v in team_alias_map.items() if k in teams_df.columns})
    matchups_df = matchups_df.rename(columns={k:v for k,v in matchup_alias_map.items() if k in matchups_df.columns})

    # Light coercions
    for df in (teams_df, matchups_df):
        if 'team_key' in df.columns: df['team_key'] = df['team_key'].astype(str).str.strip()
        if 'opponent_team_key' in df.columns: df['opponent_team_key'] = df['opponent_team_key'].astype(str).str.strip()
        if 'year' in df.columns: df['year'] = pd.to_numeric(df['year'], errors='coerce').astype('Int64')
        if 'owner_name' in df.columns: df['owner_name'] = df['owner_name'].astype(str).str.strip()

    # Minimal numeric coercions we use later
    for c in ['regular_season_ranking','wins','losses','points_for_total','points_against_total',
              'number_of_waiver_moves','number_of_trades','is_finished']:
        if c in teams_df.columns:
            teams_df[c] = pd.to_numeric(teams_df[c], errors='coerce')

    for c in ['is_playoffs','high_score_flag','low_score_flag','week','year']:
        if c in matchups_df.columns:
            matchups_df[c] = pd.to_numeric(matchups_df[c], errors='coerce')

    # Players coercions (light)
    if 'team_key' in players_df.columns:
        players_df['team_key'] = players_df['team_key'].astype(str).str.strip()
    for c in ['week','player_week_points','year']:
        if c in players_df.columns:
            players_df[c] = pd.to_numeric(players_df[c], errors='coerce')

    # =================================================
    # GLOBAL FILTER: restrict to finished seasons only
    # =================================================
    if 'is_finished' in teams_df.columns:
        teams_df = teams_df[teams_df['is_finished'].fillna(0) == 1].copy()

    # Cascade filter to matchups/players using team_key
    if not teams_df.empty and 'team_key' in teams_df.columns:
        finished_keys = teams_df['team_key'].astype(str).unique()

        if 'team_key' in matchups_df.columns:
            matchups_df['team_key'] = matchups_df['team_key'].astype(str)
            matchups_df = matchups_df[matchups_df['team_key'].isin(finished_keys)].copy()

        if 'team_key' in players_df.columns:
            players_df = players_df[players_df['team_key'].isin(finished_keys)].copy()

    # Safety: if nothing left, exit early
    if teams_df.empty:
        st.info("No finished seasons available.")
        return

    # -----------------------------
    # Select Box for Owner
    # -----------------------------
    owners = sorted(teams_df["owner_name"].dropna().unique().tolist())
    owner_options = ["Select an owner..."] + owners
    selected_owner_label = st.selectbox(
        "Select Owner:",
        owner_options,
        index=0
    )
    if selected_owner_label == "Select an owner...":
        st.info("Please select an owner to continue.")
        return

    owner = selected_owner_label

    # Optional slices (keep if you use them later)
    teams_owner_all = teams_df[teams_df["owner_name"] == owner].copy()                # includes 2017 (within finished seasons)
    teams_owner = teams_owner_all[teams_owner_all["year"] != 2017].copy()             # excludes 2017 for other visuals

    # -----------------------------
    # Cards
    # -----------------------------
    from streamlit.components.v1 import html as st_html

    get_count = lambda res: int(teams_owner_all[teams_owner_all['league_result'].astype(str).str.lower() == res].shape[0])
    champs = get_count('winner')
    runnerups = get_count('runner-up')
    losers = get_count('loser')

    avg_rank = round(teams_owner['regular_season_ranking'].dropna().astype(float).mean(), 2) if not teams_owner.empty else np.nan

    win_pct = np.nan
    if {'wins','losses'}.issubset(teams_owner.columns) and not teams_owner.empty:
        tw, tl = teams_owner['wins'].sum(), teams_owner['losses'].sum()
        if (tw + tl) > 0:
            win_pct = round(100 * tw / (tw + tl), 1)

    playoff_mask = teams_owner['league_result'].astype(str).str.lower().isin(['playoffs','runner-up','winner'])
    playoff_appearances = int(playoff_mask.sum())
    total_seasons_excl_2017 = int(teams_owner['year'].nunique())
    playoff_pct = round(100 * playoff_appearances / total_seasons_excl_2017, 1) if total_seasons_excl_2017 > 0 else np.nan

    def _fmt_int(v):
        try:
            x = pd.to_numeric(v, errors="coerce")
            return "-" if pd.isna(x) else str(int(round(x)))
        except Exception:
            return "-"

    def _fmt_pct(v):
        try:
            x = pd.to_numeric(v, errors="coerce")
            return "-" if pd.isna(x) else f"{round(float(x), 1)}%"
        except Exception:
            return "-"

    def _fmt_float(v, nd=2):
        try:
            x = pd.to_numeric(v, errors="coerce")
            if pd.isna(x):
                return "-"
            s = f"{x:.{nd}f}"
            return s.rstrip("0").rstrip(".")
        except Exception:
            return "-"

    def render_cards_block(rows):
        flat = [t for row in rows for t in row]
        cards_html = "".join(
            f"""
            <div class="card">
              <div class="label">{lbl}</div>
              <div class="value">{val}</div>
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
            row-gap:4px;
            margin:0;
            padding:0;
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
            font-size:14px; 
            font-weight:500; 
            color:#aaa;
            border-bottom:1px solid #555;
            padding-bottom:1px; 
            margin-bottom:2px; 
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
            line-height:1.2;
            margin-top:0;
            white-space:nowrap; 
            overflow:hidden; 
            text-overflow:ellipsis; 
            text-align:left;
          }}
          .sub {{
            font-size:10px; 
            color:#999;
            margin-top:1px; 
            white-space:nowrap; 
            overflow:hidden;
            text-overflow:ellipsis; 
            text-align:left;
          }}
          @media (max-width:480px){{
            .label{{font-size:12px;}}
            .value{{font-size:18px;}}
            .sub{{font-size:9px;}}
          }}
        </style>
        <div class="cards">{cards_html}</div>
        """
        st_html(html, height=60 * len(rows))

    champs_s      = _fmt_int(champs)
    runnerups_s   = _fmt_int(runnerups)
    losers_s      = _fmt_int(losers)
    avg_rank_s    = _fmt_float(avg_rank, nd=2)
    win_pct_s     = _fmt_pct(win_pct)
    playoff_pct_s = _fmt_pct(playoff_pct)

    render_cards_block([
        [("Champs", champs_s), ("Runner-ups", runnerups_s), ("Losers", losers_s)],
        [("Avg Season Rank", avg_rank_s), ("Win %", win_pct_s), ("Playoff Appear %", playoff_pct_s)],
    ])

    # -----------------------------
    # Line chart: Regular-season rank by year (excl 2017) with emoji markers
    # -----------------------------
    line_df = teams_owner[['year','regular_season_ranking','league_result']].copy()
    line_df = line_df.dropna(subset=['regular_season_ranking'])
    line_df = line_df[line_df['year'] != 2017].sort_values('year')

    def result_emoji(x: str) -> str:
        s = '' if pd.isna(x) else str(x).strip().lower()
        if s == 'winner': return '🏆'
        if s in ('runner-up', 'runner up', 'runnerup'): return '🥈'
        if s == 'loser': return '🗑️'
        if s in ('playoffs', 'playoff'): return '✅'
        if s in ('missed playoffs', 'no playoffs', 'did not qualify', 'dnq', 'consolation', 'toilet bowl'): return '❌'
        return '❌'

    if not line_df.empty:
        st.markdown('<div style="font-size:20px;font-weight:600;margin-top:-10px; margin-bottom:-10px; line-height:1;">Performance by Year</div>', unsafe_allow_html=True)

        line_df['year_str'] = line_df['year'].astype(int).astype(str)
        line_df['emoji'] = line_df['league_result'].map(result_emoji)
        ticks = [str(y) for y in sorted(line_df['year'].dropna().astype(int).unique())]

        fig_rank = go.Figure()
        fig_rank.add_trace(go.Scatter(
            x=line_df['year_str'],
            y=line_df['regular_season_ranking'],
            mode='lines',
            line=dict(width=2),
            hovertemplate='Year: %{x}<br>Rank: %{y:.0f}<extra></extra>',
            name=''
        ))
        fig_rank.add_trace(go.Scatter(
            x=line_df['year_str'],
            y=line_df['regular_season_ranking'],
            mode='text',
            text=line_df['emoji'],
            textposition='middle center',
            textfont=dict(size=16, family="Segoe UI Emoji, Noto Color Emoji, Apple Color Emoji, sans-serif"),
            hoverinfo='skip',
            showlegend=False,
            name=''
        ))
        fig_rank.update_xaxes(
            type='category',
            categoryorder='array',
            categoryarray=ticks,
            tickmode='array',
            tickvals=ticks,
            ticktext=ticks,
            fixedrange=True,
            showline=True,
            linecolor="#444",
            linewidth=1,
            automargin=True
        )
        fig_rank.update_yaxes(
            range=[12.5, 0],
            dtick=1,
            title_text="Regular Season Rank",
            fixedrange=True,
            gridcolor="#444"
        )
        fig_rank.update_layout(height=210, margin=dict(l=8, r=8, t=0, b=8), showlegend=False)
        st.markdown("""
        <style>
          .emoji-legend { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-top:4px;}
          .emoji-legend .item { display:flex; align-items:center; gap:2px; background:#222; border:1px solid #333; padding:2px 4px; border-radius:8px; font-size:10px; color:#ddd; }
          .emoji-legend .emoji { font-size:14px; line-height:1; }
        </style>
        <div class="emoji-legend">
          <div class="item"><span class="emoji">🏆</span><span>Champ</span></div>
          <div class="item"><span class="emoji">🥈</span><span>2nd</span></div>
          <div class="item"><span class="emoji">🗑️</span><span>Loser</span></div>
          <div class="item"><span class="emoji">✅</span><span>Playoffs</span></div>
          <div class="item"><span class="emoji">❌</span><span>No Playoffs</span></div>
        </div>
        """, unsafe_allow_html=True)
        st.plotly_chart(fig_rank, use_container_width=True, config={'displayModeBar': False})

    # -----------------------------
    # Box & Whisker: Weekly Points by Year (force-drop 2017)
    # -----------------------------
    st.markdown(
        '<div style="font-size:20px;font-weight:600;line-height:1.1;margin-top:10px;margin:6px 0 0;">Weekly Points by Year</div>',
        unsafe_allow_html=True
    )

    # detect weekly points column
    POINTS_COL = 'points for' if 'points for' in matchups_df.columns else (
                 'points_for' if 'points_for' in matchups_df.columns else None)
    if POINTS_COL is None:
        raise KeyError(f"Weekly points column not found in matchups_df. Have: {list(matchups_df.columns)}")

    # join matchups -> owner + year (already finished-only)
    points_all = matchups_df.merge(
        teams_df[['team_key','owner_name','year']].drop_duplicates(),
        on='team_key', how='left'
    )

    # regular season only
    if 'is_playoffs' in points_all.columns:
        points_all = points_all[points_all['is_playoffs'].fillna(0) == 0]

    # clean numeric & filter to selected owner
    points_all[POINTS_COL] = pd.to_numeric(points_all[POINTS_COL], errors='coerce')
    po = points_all[points_all['owner_name'] == owner].dropna(subset=[POINTS_COL, 'year']).copy()

    # build clean year string and remove 2017
    po['year_str'] = po['year'].astype(str).str.strip()
    po = po[po['year_str'] != '2017'].copy()

    # create categorical with only desired years
    final_years = sorted([y for y in po['year_str'].unique()], key=lambda y: int(y))
    po['year_cat'] = pd.Categorical(po['year_str'], categories=final_years, ordered=True)

    fig_box_year = px.box(po, x='year_cat', y=POINTS_COL, points='outliers')
    fig_box_year.update_layout(
        xaxis_title=None,
        yaxis_title='Points For (per week)',
        margin=dict(l=8, r=8, t=0, b=8),
        showlegend=False,
        height=300
    )
    fig_box_year.update_xaxes(
        showgrid=True, gridcolor="#444",
        showline=True, linecolor="#444", linewidth=1,
        categoryorder='category ascending',
        type='category',
        tickvals=list(range(len(final_years))),
        ticktext=final_years
    )
    fig_box_year.update_yaxes(showgrid=True, gridcolor="#444", zeroline=False)
    st.plotly_chart(fig_box_year, use_container_width=True, config={'displayModeBar': False})

    # -----------------------------
    # Rivalry “heat map” (horizontal bar of Win% vs opponents)
    # -----------------------------
    # Build matchups with owner/opponent (finished-only)
    t_map = teams_df[['team_key','year','owner_name']].drop_duplicates()
    m_self = matchups_df.merge(t_map, on='team_key', how='left')

    # Map opponent owner (finished-only)
    t_map_opp = teams_df[['team_key','year','owner_name']].drop_duplicates().rename(columns={
        'team_key': 'opponent_team_key',
        'owner_name': 'opponent_owner_name'
    })
    m_full = m_self.merge(t_map_opp, on=['opponent_team_key','year'], how='left')

    # Filter to selected owner, regular season, and valid week_result
    mh = m_full[(m_full['owner_name'] == owner)].copy()
    if 'is_playoffs' in mh.columns:
        mh = mh[mh['is_playoffs'].fillna(0) == 0]
    mh['week_result'] = mh['week_result'].astype(str).str.lower().str.strip()
    mh = mh[mh['week_result'].isin(['win','loss'])]
    mh['win'] = (mh['week_result'] == 'win').astype(int)

    vs = (mh.groupby('opponent_owner_name', dropna=False)
            .agg(games=('win','count'), wins=('win','sum'))
            .reset_index())

    if not vs.empty:
        vs['losses'] = vs['games'] - vs['wins']
        vs['win_pct'] = (vs['wins'] / vs['games'] * 100).round(1)
        vs_bar = vs.sort_values('win_pct', ascending=True).copy()
        vs_bar['plot_value'] = vs_bar['win_pct'].replace(0, 0.01)
        x_max = min(110, max(100.0, float(vs_bar['plot_value'].max())) + 5)

        fig = px.bar(
            vs_bar, x='plot_value', y='opponent_owner_name',
            orientation='h', text='win_pct', color='win_pct',
            color_continuous_scale='Blues',
            labels={'plot_value':'Win %','opponent_owner_name':'Opponent'}
        )
        fig.update_traces(
            texttemplate='%{text:.1f}%',
            textposition='outside',
            cliponaxis=False,
            hovertemplate='<b>%{y}</b><br>Win %%: %{text}<br>Games: %{customdata[0]}<extra></extra>',
            customdata=vs_bar[['games']].values
        )
        fig.update_layout(coloraxis_showscale=False)
        fig.update_layout(
            margin=dict(l=8, r=28, t=0, b=0),
            bargap=0.2, bargroupgap=0,
            yaxis=dict(automargin=True, showgrid=False, zeroline=False),
            xaxis=dict(range=[0, x_max], showgrid=True, gridcolor="#444", zeroline=False),
            height=300
        )
        st.markdown('<div style="font-size:20px;font-weight:600;margin-top:10px;margin-bottom:0px;line-height:1;">Head-to-Head Rivalry Win Rate</div>', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # =========================================================
    # ALL TIME PLAYERS (Owner-level; regular season starters)
    # =========================================================
    st.markdown('<div style="font-size:20px;font-weight:600;margin:10px 0 2px;">All Time Players</div>', unsafe_allow_html=True)

    if players_df is None or players_df.empty:
        st.info("Players data not provided — skipping 'All Time Players'.")
    else:
        need_cols_players = {"team_key","week","player_week_points","selected_position","player_position"}
        pcols_lower = set(players_df.columns.str.lower())
        if not need_cols_players.issubset(pcols_lower):
            missing = ", ".join(sorted(need_cols_players - pcols_lower))
            st.info(f"Players table missing columns: {missing}. Cannot compute All Time Players.")
        else:
            # ---- normalize inputs (already normalized above) ----
            tdf = teams_df.copy()
            mdf = matchups_df.copy()
            pdf = players_df.copy()

            # owner team/year map
            t_owner = (
                tdf.loc[tdf["owner_name"] == owner, ["team_key", "year"]]
                   .dropna(subset=["team_key"])
                   .drop_duplicates()
                   .copy()
            )
            if t_owner.empty:
                st.info("No teams found for this owner.")
            else:
                t_owner["team_key"] = t_owner["team_key"].astype(str)

                # matchups: attach year from teams (ensuring finished-only), RS only
                m = mdf.copy()
                if "team_key" not in m.columns or "week" not in m.columns:
                    st.info("matchups_df missing required columns (team_key/week).")
                else:
                    m["team_key"] = m["team_key"].astype(str)
                    m["week"] = pd.to_numeric(m["week"], errors="coerce").astype("Int64")
                    m = m.merge(t_owner, on="team_key", how="inner")  # only this owner's teams (has year now)

                    if "is_playoffs" not in m.columns:
                        m["is_playoffs"] = 0
                    m["is_playoffs"] = pd.to_numeric(m["is_playoffs"], errors="coerce").fillna(0).astype(int)

                    m_owner = m[(m["is_playoffs"] == 0) & m["team_key"].notna() & m["week"].notna()].copy()
                    if m_owner.empty:
                        st.info("No regular-season matchups found for this owner.")
                    else:
                        # players: keep only rows that match the owner's scheduled weeks (adds year)
                        pdf["team_key"] = pdf["team_key"].astype(str)
                        pmo = pdf.merge(
                            m_owner[["team_key", "week", "year"]],
                            on=["team_key", "week"],
                            how="inner",
                            validate="m:1"
                        )

                        # starters only
                        def _is_started(slot):
                            s = (str(slot).strip().upper() if slot is not None else "")
                            return s not in ("BN", "IR")
                        pmo = pmo[pmo["selected_position"].apply(_is_started)].copy()

                        if pmo.empty:
                            st.info("No started-player rows found for this owner in the regular season.")
                        else:
                            # numeric points
                            pmo["player_week_points"] = pd.to_numeric(pmo["player_week_points"], errors="coerce").fillna(0.0)

                            # position normalization
                            def _norm_pos(p):
                                s = str(p).strip().upper() if p is not None else ""
                                return "DEF" if s in ("DST","D/ST","DEFENSE") else s
                            pmo["player_position_norm"] = pmo["player_position"].map(_norm_pos)

                            # choose player name column
                            player_name_col = next((c for c in ["player_name","name","full_name","player_full_name","player_key"] if c in pmo.columns), None)
                            if player_name_col is None:
                                st.info("No player name/key column found; cannot compute All Time Players.")
                            else:
                                pmo["player_name_display"] = pmo[player_name_col].astype(str)
                                if "player_key" in pmo.columns:
                                    pmo["player_key"] = pmo["player_key"].astype(str)

                                # ---------- aggregate to single-season totals per player ----------
                                season_totals = (
                                    pmo.groupby(["player_position_norm","player_name_display","player_key","year"], dropna=False)["player_week_points"]
                                       .sum()
                                       .reset_index()
                                       .rename(columns={"player_week_points":"points"})
                                )
                                season_totals["player_name"] = season_totals["player_name_display"].astype(str)
                                season_totals["year"] = season_totals["year"].astype("Int64")

                                POS_ORDER = ["QB","RB","WR","TE","K","DEF"]
                                tabs = st.tabs(["First Team All Pro"] + POS_ORDER)

                                def render_top5(df_in):
                                    df = df_in.sort_values("points", ascending=False).head(5).copy()
                                    view = df[["player_name","year","points"]].rename(columns={
                                        "player_name": "Player Name",
                                        "year": "Year Owned",
                                        "points": "Points"
                                    })
                                    n_rows = len(view)
                                    fit_height = min(500, 40 + n_rows*34 + 10)
                                    st.dataframe(
                                        view,
                                        use_container_width=True,
                                        hide_index=True,
                                        column_config={
                                            "Player Name": st.column_config.TextColumn("Player Name", pinned="left"),
                                            "Year": st.column_config.NumberColumn("Year", format="%d"),
                                            "Points": st.column_config.NumberColumn("Points", format="%d"),
                                        },
                                        height=fit_height,
                                    )

                                # ---- First Team All Pro tab (QB, RB, RB, WR, WR, TE, K, DEF) ----
                                with tabs[0]:
                                    def top_n(pos, n):
                                        tmp = season_totals[season_totals["player_position_norm"] == pos].copy()
                                        if tmp.empty:
                                            return tmp
                                        tmp = tmp.sort_values("points", ascending=False).head(n)
                                        tmp["Pos"] = pos
                                        return tmp

                                    # Build in exact order (and amounts): QB(1), RB(2), WR(2), TE(1), K(1), DEF(1)
                                    blocks = [
                                        top_n("QB", 1),
                                        top_n("RB", 2),
                                        top_n("WR", 2),
                                        top_n("TE", 1),
                                        top_n("K",  1),
                                        top_n("DEF",1),
                                    ]
                                    blocks = [b for b in blocks if b is not None and not b.empty]

                                    if not blocks:
                                        st.info("No data available to determine First Team All Pro.")
                                    else:
                                        ftp = pd.concat(blocks, ignore_index=True)

                                        # Include Pos as first column
                                        view = ftp[["Pos", "player_name", "year", "points"]].rename(columns={
                                            "player_name": "Player Name",
                                            "year": "Year Owned",
                                            "points": "Points"
                                        })

                                        n_rows = len(view)
                                        fit_height = min(500, 40 + n_rows * 34 + 10)
                                        st.dataframe(
                                            view,
                                            use_container_width=True,
                                            hide_index=True,
                                            column_config={
                                                "Pos": st.column_config.TextColumn("Pos", pinned="left"),
                                                "Player Name": st.column_config.TextColumn("Player Name"),
                                                "Year Owned": st.column_config.NumberColumn("Year", format="%d"),
                                                "Points": st.column_config.NumberColumn("Points", format="%d"),
                                            },
                                            height=fit_height,
                                        )


                                # ---- Position tabs (TOP 5) ----
                                for i, pos in enumerate(POS_ORDER, start=1):
                                    with tabs[i]:
                                        pos_tbl = season_totals[season_totals["player_position_norm"] == pos].copy()
                                        if pos_tbl.empty:
                                            st.info(f"No data for {pos}.")
                                        else:
                                            render_top5(pos_tbl)

    # Team Summary (dataframe w/ pinned first col + link)
    # ----------------------------------------------------------------
    # 1) Trim to just flags we need
    matchups_flags_df = matchups_df[['team_key','is_playoffs','high_score_flag','low_score_flag']].copy()
    # 2) RS only
    matchups_flags_df = matchups_flags_df[matchups_flags_df['is_playoffs'] == 0].copy()
    # 3) Sum by team_key
    flag_sums = (
        matchups_flags_df.groupby('team_key', as_index=False)
        .agg(high_scores=('high_score_flag','sum'),
             low_scores =('low_score_flag','sum'))
    )
    # 4) Base summary for this owner (exclude 2017) + include FAAB
    summary_cols = [
        'year','team_key','team_name','league_result','regular_season_ranking','wins','losses',
        'points_for_total','points_against_total','number_of_waiver_moves','faab_balance_used','number_of_trades',
        'draft_grade','team_url'
    ]
    base_summary = teams_owner[summary_cols].copy()
    # 5) LEFT JOIN on team_key
    summary = base_summary.merge(flag_sums, on='team_key', how='left')

    # Ensure numeric, then compute points diff
    summary['points_for_total'] = pd.to_numeric(summary['points_for_total'], errors='coerce')
    summary['points_against_total'] = pd.to_numeric(summary['points_against_total'], errors='coerce')
    summary['points_diff'] = (summary['points_for_total'] - summary['points_against_total']).fillna(0).astype(int)

    # 6) force ints (exclude FAAB so we can render it as text)
    for c in [
        'regular_season_ranking','wins','losses','points_for_total','points_against_total',
        'number_of_waiver_moves','number_of_trades','high_scores','low_scores'
    ]:
        if c in summary.columns:
            summary[c] = pd.to_numeric(summary[c], errors='coerce').fillna(0).astype(int)

    # 7) rename & order (insert FAAB Used after Waiver Moves)
    display = summary.rename(columns={
        'year': 'Year',
        'team_name': 'Team Name',
        'league_result': 'League Result',
        'regular_season_ranking': 'Regular Season Rank',
        'wins': 'Wins',
        'losses': 'Losses',
        'points_for_total': 'Points For (Total)',
        'points_against_total': 'Points Against (Total)',
        'points_diff': 'Points Difference',
        'number_of_waiver_moves': 'Waiver Moves',
        'faab_balance_used': 'FAAB Used',         
        'number_of_trades': 'Trades',
        'high_scores': '# High Scores',
        'low_scores': '# Low Scores',
        'draft_grade': 'Draft Grade',
        'team_url': 'Team URL'
    }).sort_values('Year', ascending=True)

    # --- Force FAAB Used to literal text (no decimals, show "NA" when missing) ---
    def _faab_to_text(x):
        if x is None or (isinstance(x, float) and np.isnan(x)) or (x is pd.NA):
            return "NA"
        if isinstance(x, str):
            s = x.strip()
            try:
                f = float(s)
                return str(int(f)) if f.is_integer() else s
            except Exception:
                return s or "NA"
        if isinstance(x, (int, np.integer)):
            return str(int(x))
        if isinstance(x, float):
            return str(int(x)) if x.is_integer() else str(x).rstrip('0').rstrip('.')
        return str(x)

    if 'FAAB Used' in display.columns:
        display['FAAB Used'] = display['FAAB Used'].apply(_faab_to_text).astype(object)

    # Build a small link column from Team URL
    display['Team URL (link)'] = display['Team URL'].map(
        lambda u: (None if (pd.isna(u) or str(u).strip() == "") else str(u).strip())
    )

    ordered_cols = [
        'Year','Team Name','League Result','Regular Season Rank','Wins','Losses',
        'Points For (Total)','Points Against (Total)','Points Difference',
        'Waiver Moves','FAAB Used','Trades',     
        '# High Scores','# Low Scores','Draft Grade','Team URL (link)'
    ]
    display = display[ordered_cols]

    st.markdown(
        '<div style="font-size:20px;font-weight:600;margin-top:8px;margin-bottom:4px;">Team Summary</div>',
        unsafe_allow_html=True
    )

    # Compute a height that fits all rows (approximate)
    n_rows = len(display)
    row_px = 34
    header_px = 40
    padding_px = 10
    max_px = 1200
    fit_height = min(max_px, header_px + n_rows * row_px + padding_px)

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            # Pin the first column (Year). If you'd rather pin Team Name, move pinned="left" there.
            "Year": st.column_config.NumberColumn(format="%d", pinned="left"),
            "Team Name": st.column_config.TextColumn("Team Name"),
            "League Result": st.column_config.TextColumn("League Result"),
            "Regular Season Rank": st.column_config.NumberColumn(format="%d"),
            "Wins": st.column_config.NumberColumn(format="%d"),
            "Losses": st.column_config.NumberColumn(format="%d"),
            "Points For (Total)": st.column_config.NumberColumn(format="%d"),
            "Points Against (Total)": st.column_config.NumberColumn(format="%d"),
            "Points Difference": st.column_config.NumberColumn(format="%d"),
            "Waiver Moves": st.column_config.NumberColumn(format="%d"),
            # Keep FAAB as text to avoid numeric coercion/decimals
            "FAAB Used": st.column_config.TextColumn("FAAB Used"),
            "Trades": st.column_config.NumberColumn(format="%d"),
            "# High Scores": st.column_config.NumberColumn(format="%d"),
            "# Low Scores": st.column_config.NumberColumn(format="%d"),
            "Draft Grade": st.column_config.TextColumn("Draft Grade"),
            "Team URL (link)": st.column_config.LinkColumn("Team URL", display_text="Link"),
        },
        height=fit_height,
    )
