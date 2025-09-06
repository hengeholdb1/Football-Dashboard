import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit.components.v1 import html as st_html


def show_owner_insights(st, go_unused, teams_df, matchups_df):
    # -----------------------------
    # Normalize columns & aliases
    # -----------------------------
    for df in (teams_df, matchups_df):
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
        'season': 'year'
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

    for df in (teams_df, matchups_df):
        if 'team_key' in df.columns: df['team_key'] = df['team_key'].astype(str).str.strip()
        if 'opponent_team_key' in df.columns: df['opponent_team_key'] = df['opponent_team_key'].astype(str).str.strip()
        if 'year' in df.columns: df['year'] = pd.to_numeric(df['year'], errors='coerce').astype('Int64')
        if 'owner_name' in df.columns: df['owner_name'] = df['owner_name'].astype(str).str.strip()

    # Minimal numeric coercions we use later
    for c in ['regular_season_ranking','wins','losses','points_for_total','points_against_total',
              'number_of_waiver_moves','number_of_trades']:
        if c in teams_df.columns:
            teams_df[c] = pd.to_numeric(teams_df[c], errors='coerce')

    for c in ['is_playoffs','high_score_flag','low_score_flag','week']:
        if c in matchups_df.columns:
            matchups_df[c] = pd.to_numeric(matchups_df[c], errors='coerce')

    # -----------------------------
    # Select Box for Owner
    # -----------------------------
    # --- Owner selector with placeholder ---
    owners = sorted(teams_df["owner_name"].dropna().unique().tolist())
    owner_options = ["Select an owner..."] + owners
    selected_owner_label = st.selectbox(
        "Select Owner:",
        owner_options,
        index=0
    )

    if selected_owner_label == "Select an owner...":
        st.info("Please select an owner to continue.")
        return  # use st.stop() if you're not inside a function

    owner = selected_owner_label

    # Optional slices (keep if you use them later)
    teams_owner_all = teams_df[teams_df["owner_name"] == owner].copy()                # includes 2017 for cards
    teams_owner = teams_owner_all[teams_owner_all["year"] != 2017].copy()             # excludes 2017 for other visuals


    # -----------------------------
    # Cards (styled like example)
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
            # tidy trailing zeros
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
            row-gap:4px;        /* no vertical gap between rows */
            margin:0;           /* remove top/bottom margin */
            padding:0;          /* remove padding */
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
            color:#aaa;               /* lighter gray label */
            border-bottom:1px solid #555;  /* gray underline */
            padding-bottom:1px; 
            margin-bottom:2px; 
            white-space:nowrap; 
            overflow:hidden;
            text-overflow:ellipsis; 
            text-align:left; 
            width:100%;
          }}
          .value {{
            color:#fff;               /* bold white values */
            font-size:20px; 
            font-weight:800; 
            line-height:1.2;
            margin-top:0;             /* tighter spacing */
            white-space:nowrap; 
            overflow:hidden; 
            text-overflow:ellipsis; 
            text-align:left;
          }}
          .sub {{
            font-size:10px; 
            color:#999;               /* subtle gray subtext */
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

    # Format values for display
    champs_s      = _fmt_int(champs)
    runnerups_s   = _fmt_int(runnerups)
    losers_s      = _fmt_int(losers)
    avg_rank_s    = _fmt_float(avg_rank, nd=2)
    win_pct_s     = _fmt_pct(win_pct)            # win_pct is a number like 65.3
    playoff_pct_s = _fmt_pct(playoff_pct)        # playoff_pct is a number like 58.3

    # Render two rows as requested
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
        if s == 'winner':
            return '🏆'
        if s in ('runner-up', 'runner up', 'runnerup'):
            return '🥈'
        if s == 'loser':
            return '🗑️'
        if s in ('playoffs', 'playoff'):
            return '✅'
        if s in ('missed playoffs', 'no playoffs', 'did not qualify', 'dnq', 'consolation', 'toilet bowl'):
            return '❌'
        return '❌'  # default to "missed playoffs" if unknown

    if not line_df.empty:
        st.markdown('<div style="font-size:20px;font-weight:600;margin-top:-10px; margin-bottom:-10px; line-height:1;">Performance by Year</div>', unsafe_allow_html=True)

        line_df['year_str'] = line_df['year'].astype(int).astype(str)
        line_df['emoji'] = line_df['league_result'].map(result_emoji)

        ticks = [str(y) for y in sorted(line_df['year'].dropna().astype(int).unique())]

        fig_rank = go.Figure()

        # Base line (no markers)
        fig_rank.add_trace(go.Scatter(
            x=line_df['year_str'],
            y=line_df['regular_season_ranking'],
            mode='lines',
            line=dict(width=2),
            hovertemplate='Year: %{x}<br>Rank: %{y:.0f}<extra></extra>',
            name=''
        ))

        # Emoji at each point (acts like a "marker")
        fig_rank.add_trace(go.Scatter(
            x=line_df['year_str'],
            y=line_df['regular_season_ranking'],
            mode='text',
            text=line_df['emoji'],
            textposition='middle center',
            textfont=dict(
                size=16,
                family="Segoe UI Emoji, Noto Color Emoji, Apple Color Emoji, sans-serif"
            ),
            hoverinfo='skip',   # avoid duplicate hover
            showlegend=False,
            name=''
        ))

        fig_rank.update_xaxes(
            type='category',
            categoryorder='array',
            categoryarray=ticks,
            tickmode='array',
            tickvals=ticks,
            ticktext=ticks,     # just the years (no emojis under)
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
        # No extra bottom margin needed since emojis are on the points
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
    # Box & Whisker: Weekly Points by Year (force-drop 2017 via Categorical)
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

    # join matchups -> owner + year
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

    # plot
    fig_box_year = px.box(
        po,
        x='year_cat',
        y=POINTS_COL,
        points='outliers'
    )
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
    fig_box_year.update_yaxes(
        showgrid=True, gridcolor="#444",
        zeroline=False
    )

    st.plotly_chart(fig_box_year, use_container_width=True, config={'displayModeBar': False})

    # -----------------------------
    # Rivalry “heat map” (horizontal bar of Win% vs opponents)
    # -----------------------------
    # Build matchups with owner/opponent
    t_map = teams_df[['team_key','year','owner_name']].drop_duplicates()
    m_self = matchups_df.merge(t_map, on='team_key', how='left')

    # Map opponent owner (also needs year from teams_df)
    t_map_opp = teams_df[['team_key','year','owner_name']].drop_duplicates()
    t_map_opp = t_map_opp.rename(columns={
        'team_key': 'opponent_team_key',
        'owner_name': 'opponent_owner_name'
    })
    m_full = m_self.merge(t_map_opp, on=['opponent_team_key','year'], how='left')

    # Filter to selected owner, regular season, and valid week_result
    mh = m_full[(m_full['owner_name'] == owner) & (m_full['is_playoffs'] == 0)].copy()
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
        # keep a hairline bar for 0% so labels still place nicely
        vs_bar['plot_value'] = vs_bar['win_pct'].replace(0, 0.01)

        # ---- FIX FOR 100% LABELS GETTING CUT OFF ----
        # Add a small buffer to the right so "outside" labels at 100% have space.
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

        # Remove the color bar on the right
        fig.update_layout(coloraxis_showscale=False)

        fig.update_layout(
            margin=dict(l=8, r=28, t=0, b=0),  # keep a bit of right padding for labels
            bargap=0.2, bargroupgap=0,
            yaxis=dict(automargin=True, showgrid=False, zeroline=False),
            xaxis=dict(range=[0, x_max], showgrid=True, gridcolor="#444", zeroline=False),
            height=300
        )

        st.markdown('<div style="font-size:20px;font-weight:600;margin-top:10px;margin-bottom:0px;line-height:1;">Head-to-Head Rivalry Win Rate</div>', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # ----------------------------------------------------------------
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
    padding_px = 16
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
