import pandas as pd
import numpy as np

def show_owner_insights(st, go, teams_df, matchups_df):

    # -----------------------------
    # Normalize columns & dtypes
    # -----------------------------
    for df in (teams_df, matchups_df):
        df.columns = df.columns.str.strip().str.lower()
    # helpful aliases if your sheet uses slightly different names
    alias_map = {
        'teamkey': 'team_key',
        'opponentteamkey': 'opponent_team_key',
        'owner': 'owner_name',
        'league_result_final': 'league_result',
        'regular_season_rank': 'regular_season_ranking',
        'points_for': 'points_for_total',
        'points_against': 'points_against_total',
        'waiver_moves': 'number_of_waiver_moves',
        'trades': 'number_of_trades',
        'url': 'team_url',
        'draft_report_card': 'draft_grade'
    }
    teams_df = teams_df.rename(columns={k:v for k,v in alias_map.items() if k in teams_df.columns})
    matchups_df = matchups_df.rename(columns={k:v for k,v in alias_map.items() if k in matchups_df.columns})

    # Strongly-expected columns (create if missing so visuals don’t die)
    need_cols_teams = [
        'year','team_key','team_name','owner_name','league_result','regular_season_ranking','wins','losses',
        'points_for_total','points_against_total','number_of_waiver_moves','number_of_trades','team_url','draft_grade'
    ]
    for c in need_cols_teams:
        if c not in teams_df.columns:
            teams_df[c] = np.nan

    need_cols_matchups = [
        'year','week','team_key','opponent_team_key','is_playoffs','high_score_flag','low_score_flag','points_for','points_against'
    ]
    for c in need_cols_matchups:
        if c not in matchups_df.columns:
            matchups_df[c] = np.nan

    # Coerce numeric types where helpful
    for df, cols in [(teams_df,['year','regular_season_ranking','wins','losses','points_for_total','points_against_total',
                                'number_of_waiver_moves','number_of_trades']),
                     (matchups_df,['year','week','is_playoffs','high_score_flag','low_score_flag','points_for','points_against'])]:
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')

    # -----------------------------
    # Build opponent owner join
    # -----------------------------
    # (1) attach owner_name to matchups via team_key
    owner_map_self = teams_df[['team_key','owner_name','year']].drop_duplicates()
    m = matchups_df.merge(owner_map_self, on=['team_key','year'], how='left', suffixes=('',''))

    # (2) attach opponent owner_name via opponent_team_key
    owner_map_opp = teams_df[['team_key','owner_name','year']].drop_duplicates().rename(
        columns={'team_key':'opponent_team_key','owner_name':'opponent_owner_name'}
    )
    m = m.merge(owner_map_opp, on=['opponent_team_key','year'], how='left')

    # Ensure flags are ints (0/1) for grouping
    for flag in ['high_score_flag','low_score_flag']:
        if flag in m.columns:
            m[flag] = m[flag].fillna(0).astype(int)

    # -----------------------------
    # UI: Header & Owner filter
    # -----------------------------
    st.markdown('<div style="font-size:25px;font-weight:600;line-height:.5;margin-top:5px;margin-bottom:0px;">Owner Metrics</div>',
    unsafe_allow_html=True)
    #st.markdown('<div style="font-size:20px;font-weight:700;margin:0;">Owner Insights</div>', unsafe_allow_html=True)
    all_owners = sorted(teams_df['owner_name'].dropna().unique().tolist())
    default_owner = all_owners[0] if all_owners else None

    # Tighten spacing specifically around the selectbox ("slicer")
    # Put this RIGHT BEFORE you render the selectbox
    st.markdown("""
    <style>
    /* Compact the whole selectbox block */
    div[data-testid="stSelectbox"]{
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;            /* <= compress block line height */
    }

    /* Make everything inside the block use tight line-height */
    div[data-testid="stSelectbox"] *{
    line-height: 1.05 !important;         /* <= effective for trimming top/bottom */
    }

    /* Hide the label completely (we use the placeholder) */
    div[data-testid="stSelectbox"] label{
    display: none !important;
    }

    /* The clickable control */
    div[data-testid="stSelectbox"] div[role="combobox"]{
    min-height: 32px;                      /* shorter control */
    height: 32px;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    line-height: 32px !important;          /* center text vertically */
    }

    /* Text/placeholder inside the control */
    div[data-testid="stSelectbox"] div[role="combobox"] > div:first-child,
    div[data-testid="stSelectbox"] span,
    div[data-testid="stSelectbox"] input{
    line-height: 1.05 !important;          /* tighter text lines */
    }

    /* Dropdown menu items (when opened) */
    ul[role="listbox"] li{
    line-height: 1.1 !important;
    padding-top: 4px;
    padding-bottom: 4px;
    }

    /* Optional tiny caption with no extra space */
    .slicer-caption{
    font-size: 12px;
    color: #bbb;
    margin: 0 !important;
    line-height: 1 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Optional caption (remove if you want absolutely nothing above it)
    # st.markdown('<div class="slicer-caption">Owner</div>', unsafe_allow_html=True)

    owner = st.selectbox(
        "",  # no visible label
        options=all_owners,
        index=(all_owners.index(default_owner) if default_owner in all_owners else 0) if all_owners else None,
        placeholder="Select owner",
        label_visibility="collapsed"
    )

    # Slices
    teams_owner_all = teams_df[teams_df['owner_name'] == owner].copy()                # includes 2017 (for champs/runner/loser cards)
    teams_owner = teams_owner_all[teams_owner_all['year'] != 2017].copy()             # excludes 2017 (for all other visuals/metrics)
    m_owner = m[(m['owner_name'] == owner) & (m['year'] != 2017)].copy()

    # -----------------------------
    # Card Row 1: Championships / Runner-ups / Losers  (INCLUDES 2017)
    # -----------------------------
    get_count = lambda res: int(teams_owner_all[teams_owner_all['league_result'].astype(str).str.lower() == res].shape[0])
    champs = get_count('winner')
    runnerups = get_count('runner-up')
    losers = get_count('loser')

    # -----------------------------
    # Card Row 2: Avg regular season rank, Win %, Playoff appearance % (EXCLUDES 2017)
    # -----------------------------
    # Avg regular season rank
    avg_rank = np.nan
    if 'regular_season_ranking' in teams_owner.columns and not teams_owner.empty:
        avg_rank = round(teams_owner['regular_season_ranking'].dropna().astype(float).mean(), 2)

    # Win %
    win_pct = np.nan
    if {'wins','losses'}.issubset(teams_owner.columns):
        tmp = teams_owner[['wins','losses']].dropna()
        if not tmp.empty:
            total_wins = tmp['wins'].sum()
            total_losses = tmp['losses'].sum()
            if (total_wins + total_losses) > 0:
                win_pct = round(100 * total_wins / (total_wins + total_losses), 1)

    # Playoff appearance % (count seasons with league_result in playoffs-ish) / (seasons excluding 2017)
    playoff_mask = teams_owner['league_result'].astype(str).str.lower().isin(['playoffs','runner-up','winner'])
    playoff_appearances = int(playoff_mask.sum())
    total_seasons_excl_2017 = int(teams_owner['year'].nunique())
    playoff_pct = round(100 * playoff_appearances / total_seasons_excl_2017, 1) if total_seasons_excl_2017 > 0 else np.nan

    # -----------------------------
    # Render cards
    # -----------------------------
    from streamlit.components.v1 import html as st_html

    def render_cards_block(rows):
        """
        rows: list of rows; each row is a list of (label, value[, sub]) tuples.
        We flatten to one 3-col grid so columns stay the same width across both rows.
        """
        flat = [t for row in rows for t in row]

        cards_html = "".join(
            f"""
            <div class="card">
            <div class="label">{lbl}</div>
            <div class="value">{('-' if (val is None or (isinstance(val,float) and pd.isna(val))) else val)}</div>
            {f'<div class="sub">{sub}</div>' if (len(tup)>2 and (sub:=tup[2])) else ''}
            </div>
            """
            for tup in flat for lbl,val,*_ in [tup]
        )

        html = f"""
        <style>
        /* one grid for all six cards -> identical column widths */
        .cards {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr)); /* equal columns regardless of label length */
            column-gap: 6px;
            row-gap: 8px;
            margin: 4px 0;
        }}
        .card {{
            background: #222;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 2px 10px;
            color: #fff;
            box-sizing: border-box;
            min-width: 0; /* allow shrinking within the grid column */
        }}
        .label {{ font-size: 10px; line-height: 1.3; opacity: 0.9; }}
        .value {{ font-size: 20px; font-weight: 700; line-height: 1.1; margin-top: 4px; }}
        .sub   {{ font-size: 10px; opacity: 0.9; margin-top: 2px; }}
        .label, .value, .sub {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

        /* keep 3 across on phones too */
        @media (max-width: 480px) {{
            .value {{ font-size: 18px; }}
            .label {{ font-size: 12px; }}
            .sub   {{ font-size: 9px;  }}
        }}
        </style>

        <div class="cards">
        {cards_html}
        </div>
        """

        # height: ~86px per row
        height = 55 * len(rows)
        st_html(html, height=height)

    # --- Use it like this (same metrics you already compute) ---
    render_cards_block([
        [("🏆 Champs", champs), ("🥈 Runner-ups", runnerups), ("💀 Losers", losers)],
        [("Avg Season Rank", avg_rank), ("Win %", f"{win_pct}%" if pd.notna(win_pct) else "-"),
        ("Playoff Appear %", f"{playoff_pct}%" if pd.notna(playoff_pct) else "-")]
    ])

    # -----------------------------
    # Line graph: Regular-season rank by year (EXCLUDES 2017)
    # -----------------------------
    # ---- Line graph: Regular-season rank by year (EXCLUDES 2017) ----
    # ---- Line graph: Regular-season rank by year (EXCLUDES 2017) ----
    # ---- Line graph: Regular-season rank by year (EXCLUDES 2017) ----
    line_df = teams_owner[['year', 'regular_season_ranking']].dropna().copy()
    line_df['year'] = pd.to_numeric(line_df['year'], errors='coerce').astype('Int64')

    # remove 2017 entirely
    line_df = line_df[line_df['year'] != 2017].sort_values('year')

    if not line_df.empty:
        st.markdown(
            '<div style="font-size:20px;font-weight:600;line-height:1.1;margin:0;">Regular Season Ranking by Year</div>',
            unsafe_allow_html=True
        )

        # categorical labels (no gap for missing years)
        line_df['year_label'] = line_df['year'].astype(int).astype(str)
        ticks = [str(y) for y in sorted(line_df['year'].dropna().astype(int).unique())]

        fig_rank = go.Figure()
        fig_rank.add_trace(go.Scatter(
            x=line_df['year_label'],          # <- categorical axis
            y=line_df['regular_season_ranking'],
            mode='lines+markers',
            marker=dict(size=6),
            line=dict(width=2)
        ))

        # X-axis: categories only (2016, 2018, 2019, ...), no 2017 placeholder
        fig_rank.update_xaxes(
            type='category',
            categoryorder='array',
            categoryarray=ticks,
            tickmode='array',
            tickvals=ticks,
            fixedrange=True,
            title_text="Year"
        )

        # Y-axis: fixed 1..12, reversed (1 at top)
        fig_rank.update_yaxes(
            range=[12, 0],
            dtick=1,
            title_text="Rank (1 = best)",
            fixedrange=True
        )

        fig_rank.update_layout(
            height=200,
            margin=dict(l=8, r=8, t=0, b=8),
            showlegend=False
        )

        st.plotly_chart(fig_rank, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info("No ranking data to plot (after excluding 2017).")


    # -----------------------------
    # Heatmap: Win% vs other owners (regular season only, EXCLUDES 2017)
    # -----------------------------
    # ---- Build & preview heatmap-ready dataframe ----
    # ---- Build heatmap source with matchups_df as BASE (2 joins back to teams_df) ----
     # --- Minimal: matchups_df LEFT JOIN teams_df (owner_name) on team_key ---

    # --- Build matchups + owner_name + opponent_owner_name table ---
    def add_owner_and_opponent(teams_df, matchups_df):
        import pandas as pd

        teams = teams_df.copy()
        mtchs = matchups_df.copy()
        teams.columns = teams.columns.str.strip().str.lower()
        mtchs.columns = mtchs.columns.str.strip().str.lower()

        # Normalize key names
        teams_alias = {'teamkey': 'team_key', 'owner': 'owner_name', 'season': 'year'}
        mtchs_alias = {'teamkey': 'team_key', 'opponentteamkey': 'opponent_team_key', 'season': 'year'}
        teams.rename(columns={k:v for k,v in teams_alias.items() if k in teams.columns}, inplace=True)
        mtchs.rename(columns={k:v for k,v in mtchs_alias.items() if k in mtchs.columns}, inplace=True)

        # Ensure join key type matches
        if 'team_key' in teams.columns: teams['team_key'] = teams['team_key'].astype(str)
        if 'team_key' in mtchs.columns: mtchs['team_key'] = mtchs['team_key'].astype(str)
        if 'opponent_team_key' in mtchs.columns: mtchs['opponent_team_key'] = mtchs['opponent_team_key'].astype(str)

        # Map team owner
        owner_map = teams[['team_key', 'owner_name']].dropna().drop_duplicates()
        out = mtchs.merge(owner_map, on='team_key', how='left')

        # Map opponent owner
        opp_map = teams[['team_key', 'owner_name']].dropna().drop_duplicates()
        opp_map = opp_map.rename(columns={'team_key': 'opponent_team_key', 'owner_name': 'opponent_owner_name'})
        out = out.merge(opp_map, on='opponent_team_key', how='left')

        # Reorder some useful fields
        preferred = [c for c in [
            'year','week','team_key','owner_name',
            'opponent_team_key','opponent_owner_name',
            'is_playoffs','week_result','points_for','points_against'
        ] if c in out.columns]
        out = out[preferred + [c for c in out.columns if c not in preferred]]

        return out


    # --- Use it ---
    joined_full = add_owner_and_opponent(teams_df, matchups_df)

    # Filter to owner selected from slicer
    if owner:
        joined_full = joined_full[joined_full['owner_name'] == owner]

    # Preview table
    #st.markdown(f"**Matchups for {owner} (with opponent owner names)**")
    #st.dataframe(joined_full.head(100), use_container_width=True, hide_index=True)
    # --- Compute head-to-head Win % vs opponents ---
    # --- Compute head-to-head Win % vs opponents (using week_result only) ---
    mh = joined_full.copy()

    # Only regular season (not playoffs)
    if 'is_playoffs' in mh.columns:
        mh = mh[mh['is_playoffs'] == 0].copy()

    # Normalize week_result values
    mh['week_result'] = mh['week_result'].astype(str).str.lower().str.strip()
    mh = mh[mh['week_result'].isin(['win', 'loss'])].copy()

    # Map to 1/0
    mh['win'] = mh['week_result'].map({'win': 1, 'loss': 0})

    # Aggregate by opponent
    vs = mh.groupby('opponent_owner_name', dropna=False).agg(
        games=('win','count'),
        wins=('win','sum')
    ).reset_index()

    vs['losses'] = vs['games'] - vs['wins']
    vs['win_pct'] = (vs['wins'] / vs['games'] * 100).round(1)

    # Sort by Win%
    vs = vs.sort_values('win_pct', ascending=False).reset_index(drop=True)

    import plotly.express as px

    vs_bar = vs.copy().sort_values('win_pct', ascending=True)

    # Add a "plot_value" that's never exactly zero
    # Add a "plot_value" that's never exactly zero
    vs_bar['plot_value'] = vs_bar['win_pct'].replace(0, 0.01)

    fig = px.bar(
        vs_bar,
        x='plot_value',
        y='opponent_owner_name',
        orientation='h',
        text='win_pct',
        color='win_pct',
        color_continuous_scale='Blues',
        range_x=[0, 100],
        labels={'plot_value':'Win %','opponent_owner_name':'Opponent'}
    )

    fig.update_traces(
        texttemplate='%{text:.1f}%',
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Win %%: %{text}<br>Games: %{customdata[0]}<extra></extra>',
        customdata=vs_bar[['games']].values
    )

    # 🔑 Remove extra margins/padding
    fig.update_layout(
        margin=dict(l=8, r=8, t=0, b=0),   # eliminate top/bottom/side whitespace
        bargap=0.2,                        # tighten vertical spacing between bars
        bargroupgap=0,                     # no gap inside groups
        yaxis=dict(
            automargin=True,
            showgrid=False,
            zeroline=False
        ),
        xaxis=dict(
            range=[0, 100],
            showgrid=True,
            gridcolor="#444",
            zeroline=False
        ),
        height=300 
        #+ 18*len(vs_bar)        # grow chart only as needed
    )

    st.markdown(
        '<div style="font-size:20px;;font-weight:600;margin-top:0px;margin-bottom:0px;line-height:1;margin:0;">Owner Rivalry Heat Map</div>',
        unsafe_allow_html=True
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


    # Team Summary Table (EXCLUDES 2017)
    #   Year, Team_Name, league_result, regular_season_ranking, wins, losses,
    #   points_for_total, points_against_total, number_of_waiver_moves, number_of_trades,
    #   # high score_flags, # low_scores_flags, draft_grade, team_url
    # -----------------------------
    # Count high/low flags per year for this owner (reg season only, excl 2017)
    # ---------- Flags by team_key + year (regular season only, exclude 2017) ----------
    # Ensure flags exist and are numeric 0/1
    m_flags = m.copy()
    for col in ['high_score_flag', 'low_score_flag']:
        if col not in m_flags.columns:
            m_flags[col] = 0
        m_flags[col] = pd.to_numeric(m_flags[col], errors='coerce').fillna(0).astype(int)

    flags = (
        m_flags[
            (m_flags['owner_name'] == owner) &
            (m_flags['is_playoffs'] == 0) &
            (m_flags['year'] != 2017)
        ]
        .groupby(['team_key', 'year'], dropna=False)
        .agg(high_scores=('high_score_flag', 'sum'),
            low_scores=('low_score_flag', 'sum'))
        .reset_index()
    )

    # ---------- Base summary (make sure team_key is included) ----------
    summary_cols = [
        'year', 'team_key', 'team_name', 'league_result', 'regular_season_ranking', 'wins', 'losses',
        'points_for_total', 'points_against_total', 'number_of_waiver_moves', 'number_of_trades',
        'draft_grade', 'team_url'
    ]
    base_summary = teams_owner[summary_cols].copy()

    # ---------- Merge flag counts on (team_key, year) ----------
    summary = base_summary.merge(flags, on=['team_key', 'year'], how='left')
    summary['high_scores'] = summary['high_scores'].fillna(0).astype(int)
    summary['low_scores']  = summary['low_scores'].fillna(0).astype(int)

    # ---------- Order & rename for display ----------
    display = summary.rename(columns={
        'year': 'Year',
        'team_name': 'Team Name',
        'league_result': 'League Result',
        'regular_season_ranking': 'Regular Season Rank',
        'wins': 'Wins',
        'losses': 'Losses',
        'points_for_total': 'Points For (Total)',
        'points_against_total': 'Points Against (Total)',
        'number_of_waiver_moves': 'Waiver Moves',
        'number_of_trades': 'Trades',
        'high_scores': '# High Scores',
        'low_scores': '# Low Scores',
        'draft_grade': 'Draft Grade',
        'team_url': 'Team URL'
    }).sort_values('Year', ascending=True)

    # keep only the columns you want to show (hide team_key)
    ordered_cols = [
        'Year', 'Team Name', 'League Result', 'Regular Season Rank', 'Wins', 'Losses',
        'Points For (Total)', 'Points Against (Total)', 'Waiver Moves', 'Trades',
        '# High Scores', '# Low Scores', 'Draft Grade', 'Team URL'
    ]
    display = display[ordered_cols]

    st.markdown('<div style="font-size:20px;font-weight:600;margin-top:0px;margin-bottom:4px;">Team Summary</div>',
                unsafe_allow_html=True)

    # HTML table with sticky header + first column, mobile-scrollable
    def make_html_table(df):
        if df.empty:
            return '<div style="color:#aaa;">No rows to display.</div>'
        min_col_width = 110
        hdr = ''.join(
            f'<th style="min-width:{min_col_width}px;padding:6px;background:#333;color:#fff;'
            f'border:1px solid #555;position:sticky;top:0;z-index:2;font-size:12px;text-align:center;">{col}</th>'
            for col in df.columns
        )
        body = ''
        for _, row in df.iterrows():
            body += '<tr>'
            for j, val in enumerate(row):
                val = '' if pd.isna(val) else val
                if j == 0:
                    body += f'<td style="min-width:{min_col_width}px;text-align:center;padding:6px;background:#222;color:#fff;border:1px solid #333;position:sticky;left:0;z-index:1;font-size:12px;">{val}</td>'
                else:
                    # clickable URL cells
                    if df.columns[j] == 'Team URL' and isinstance(val, str) and val.strip():
                        cell = f'<a href="{val}" target="_blank" style="color:#6cf;text-decoration:none;">Link</a>'
                    else:
                        cell = val
                    body += f'<td style="min-width:{min_col_width}px;text-align:center;padding:6px;background:#1a1a1a;color:#fff;border:1px solid #333;font-size:12px;">{cell}</td>'
            body += '</tr>'
        return f'''
        <div style="overflow-x:auto;max-width:100vw;">
          <table style="width:100%;border-collapse:collapse;">
            <thead><tr>{hdr}</tr></thead>
            <tbody>{body}</tbody>
          </table>
          <div style="font-size:11px;color:#aaa;margin-top:4px;text-align:right;">↔️ Table is scrollable</div>
        </div>
        '''

    st.markdown(make_html_table(display), unsafe_allow_html=True)
