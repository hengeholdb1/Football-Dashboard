import pandas as pd  # make sure this is at top of file

def show_league_insights(st, go, teams_df, matchups_df):
    st.markdown('<div style="font-size:20px;font-weight:600;margin-bottom:0;">League Trophy Count</div>', unsafe_allow_html=True)

    # -----------------------------
    # Global: restrict to finished seasons
    # -----------------------------
    teams_df = teams_df.copy()
    matchups_df = matchups_df.copy()

    # Coerce minimal numerics we rely on
    for c in ['year','wins','losses','regular_season_ranking','is_finished']:
        if c in teams_df.columns:
            teams_df[c] = pd.to_numeric(teams_df[c], errors='coerce')

    for c in ['year','is_playoffs','high_score_flag','low_score_flag','week']:
        if c in matchups_df.columns:
            matchups_df[c] = pd.to_numeric(matchups_df[c], errors='coerce')

    # Keep only finished seasons in teams_df
    if 'is_finished' in teams_df.columns:
        teams_df = teams_df[teams_df['is_finished'].fillna(0) == 1].copy()

    # Cascade: only matchups for those finished-season teams
    if 'team_key' in matchups_df.columns and 'team_key' in teams_df.columns:
        finished_team_keys = teams_df['team_key'].astype(str)
        matchups_df['team_key'] = matchups_df['team_key'].astype(str)
        matchups_df = matchups_df[matchups_df['team_key'].isin(finished_team_keys)].copy()

    # Safety: if no finished seasons, short-circuit
    if teams_df.empty:
        st.info("No finished seasons available.")
        return

    # -----------------------------
    # Split dataset by 2017 rule
    # -----------------------------
    teams_all = teams_df.copy()                     # finished seasons only
    teams_no17 = teams_all[teams_all['year'] != 2017].copy()

    # ---------- Base ranking & win% (EXCLUDE 2017) ----------
    ranking_df = teams_no17[
        (teams_no17['regular_season_ranking'].notnull())
    ]

    show_current = st.toggle("Show only current owners", value=True)
    last_season = teams_all['year'].max()
    current_owners = teams_all[teams_all['year'] == last_season]['owner_name'].unique()

    avg_rankings = ranking_df.groupby('owner_name', dropna=False).agg(
        avg_rank=('regular_season_ranking', 'mean'),
        seasons_no17=('year', 'nunique')
    )

    win_df = teams_no17.dropna(subset=['wins', 'losses']).copy()
    win_df['total_games'] = win_df['wins'] + win_df['losses']
    win_df = win_df[win_df['total_games'] > 0].copy()
    win_df['win_pct'] = win_df['wins'] / win_df['total_games']

    win_stats = win_df.groupby('owner_name', dropna=False).agg(
        wins=('wins', 'sum'),
        losses=('losses', 'sum'),
        total_games=('total_games', 'sum'),
        win_pct=('win_pct', 'mean'),
        seasons_no17=('year', 'nunique')
    )

    insights_df = avg_rankings.merge(win_stats, left_index=True, right_index=True, how='left').reset_index()

    # ---------- Seasons counts (INCLUDE 2017 for Total Seasons ONLY) ----------
    total_seasons_incl2017 = teams_all.groupby('owner_name', dropna=False)['year'].nunique().rename('Total Seasons')
    seasons_no17_series = teams_no17.groupby('owner_name', dropna=False)['year'].nunique().rename('Seasons no2017')

    insights_df = (insights_df
                   .merge(total_seasons_incl2017, on='owner_name', how='left')
                   .merge(seasons_no17_series, on='owner_name', how='left'))

    # ---------- Playoff/champ/runner-up/loser counts ----------
    # Playoff Appearance % should IGNORE 2017 for both numerator & denominator
    def playoff_counts_no17(owner):
        owner_seasons_no17 = teams_no17[teams_no17['owner_name'] == owner]
        playoff_seasons = owner_seasons_no17[
            owner_seasons_no17['league_result'].isin(['Playoffs', 'Runner-up', 'Winner'])
        ]
        return len(playoff_seasons), len(owner_seasons_no17)

    # Champs/Runner-Ups/Losers must INCLUDE 2017 (still within finished seasons only)
    def champ_count(owner):
        return (teams_all[(teams_all['owner_name'] == owner) & (teams_all['league_result'] == 'Winner')].shape[0])

    def runnerup_count(owner):
        return (teams_all[(teams_all['owner_name'] == owner) & (teams_all['league_result'] == 'Runner-up')].shape[0])

    def loser_count(owner):
        return (teams_all[(teams_all['owner_name'] == owner) & (teams_all['league_result'] == 'Loser')].shape[0])

    insights_df['Avg Regular Season Rank'] = insights_df['avg_rank'].round(2)
    insights_df['Win %'] = (insights_df['win_pct'] * 100).round(1)

    # Playoff % from no-2017 seasons
    insights_df['Playoff Seasons'] = insights_df['owner_name'].apply(lambda x: playoff_counts_no17(x)[0])
    insights_df['Seasons (no 2017)'] = insights_df['owner_name'].apply(lambda x: playoff_counts_no17(x)[1])

    with pd.option_context('mode.use_inf_as_na', True):
        insights_df['Playoff Appearance %'] = (
            (insights_df['Playoff Seasons'] / insights_df['Seasons (no 2017)']) * 100
        ).round(1).fillna(0)

    # Trophy counts (INCLUDE 2017, finished seasons only)
    insights_df['# League Champs'] = insights_df['owner_name'].apply(champ_count)
    insights_df['# League Runner-Ups'] = insights_df['owner_name'].apply(runnerup_count)
    insights_df['# League Losers'] = insights_df['owner_name'].apply(loser_count)

    # ---------- Power Ranking (EXCLUDE 2017 except trophy counts; finished seasons only)
    insights_df['Power Ranking Score'] = (
        insights_df['# League Champs'] * 5 +
        insights_df['# League Runner-Ups'] * 3 - 
        insights_df['# League Losers'] * 2 -
        insights_df['Avg Regular Season Rank'] +
        insights_df['Seasons (no 2017)'] * 0.5
    ).round(2)
    insights_df['Power Ranking'] = insights_df['Power Ranking Score'].rank(method='min', ascending=False).astype(int)

    # ---------- Transaction averages (EXCLUDE 2017)
    aggr_team_year = teams_no17.groupby(['owner_name', 'year'], dropna=False).agg(
        waiver_moves=('number_of_waiver_moves', 'sum'),
        trades=('number_of_trades', 'sum'),
        faab_used=('faab_balance_used', 'sum')
    ).reset_index()

    per_owner_avgs = aggr_team_year.groupby('owner_name', dropna=False).agg(
        **{'Avg Waiver Moves/Year': ('waiver_moves', 'mean'),
           'Avg Trades/Year': ('trades', 'mean'),
           'Avg FAAB Used/Year': ('faab_used', 'mean')}
    ).round(2).reset_index()

    insights_df = insights_df.merge(per_owner_avgs, on='owner_name', how='left')

    # ---------- High/Low score avgs (EXCLUDE 2017, regular season only)
    owner_map = teams_all[['team_key', 'owner_name', 'year']].drop_duplicates()
    m = matchups_df.merge(owner_map, on='team_key', how='left')
    m = m[(m['is_playoffs'] == 0) & (m['year'] != 2017)].copy()

    # unify year if needed
    if 'year_x' in m.columns or 'year_y' in m.columns:
        m['year'] = m.get('year_x', pd.NA)
        if 'year_y' in m.columns:
            m['year'] = m['year'].fillna(m['year_y'])
        for c in ['year_x', 'year_y']:
            if c in m.columns:
                m.drop(columns=c, inplace=True)

    for col in ['year', 'is_playoffs', 'high_score_flag', 'low_score_flag']:
        if col in m.columns:
            m[col] = pd.to_numeric(m[col], errors='coerce').fillna(0).astype(int)

    if {'team_key','week'}.issubset(m.columns):
        m = (m
             .sort_values(['team_key','year','week'])
             .groupby(['team_key','year','week'], as_index=False, dropna=False)
             .agg({
                 'owner_name': 'first',
                 'is_playoffs': 'max',
                 'high_score_flag': 'max',
                 'low_score_flag': 'max'
             }))

    owner_year_flags = (m
        .groupby(['owner_name', 'year'], dropna=False)
        .agg(high_scores=('high_score_flag', 'sum'),
             low_scores =('low_score_flag',  'sum'))
        .reset_index()
    )

    owner_avg_flags = owner_year_flags.groupby('owner_name', dropna=False).agg(
        **{'Avg High Scores/Year': ('high_scores', 'mean'),
           'Avg Low Scores/Year': ('low_scores', 'mean')}
    ).round(2).reset_index()

    insights_df = insights_df.merge(owner_avg_flags, on='owner_name', how='left')

    # ---------- Plot ----------
    awards_df = insights_df.copy()
    if show_current:
        awards_df = awards_df[awards_df['owner_name'].isin(current_owners)]
    awards_df = awards_df.sort_values('Power Ranking', ascending=False)

    y_vals = awards_df['owner_name']
    y_labels = [f"#{int(rank)} {owner}" for owner, rank in zip(awards_df['owner_name'], awards_df['Power Ranking'])]

    fig = go.Figure()
    fig.add_trace(go.Bar(y=y_vals, x=awards_df['# League Champs'].astype(int),      name='Champ',     marker_color='#FFD700', orientation='h'))
    fig.add_trace(go.Bar(y=y_vals, x=awards_df['# League Runner-Ups'].astype(int),  name='Runner-Up', marker_color='#C0C0C0', orientation='h'))
    fig.add_trace(go.Bar(y=y_vals, x=-awards_df['# League Losers'].astype(int),     name='Loser',     marker_color='red',     orientation='h'))

    fig.update_layout(
        barmode='relative',
        yaxis=dict(
            title=dict(text='Power Ranking / Owner', standoff=12, font=dict(size=14)),
            tickmode='array',
            tickvals=list(y_vals),
            ticktext=y_labels,
            tickson='boundaries',
            ticks='',
            showgrid=True,
            gridcolor='rgba(200,200,200,0.5)',
            gridwidth=1,
            categoryorder='array',
            categoryarray=list(y_vals),
            automargin=True
        ),
        xaxis=dict(
            title='Awards Count',
            range=[-2, 2],
            showgrid=True,
            gridcolor='rgba(200,200,200,0.5)',
            gridwidth=1,
            dtick=1,
            showline=True,
            mirror=True,
            linecolor='white',
            linewidth=1,
            ticks='outside',
            zeroline=False,
            constrain='range',
            tickfont=dict(size=12),
        ),
        legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5, font=dict(size=10, color="white")),
        height=370,
        margin=dict(l=20, r=10, t=0, b=10),
        bargap=0.18
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})

    # ---------- Final table ----------
    final_df = insights_df.rename(columns={'owner_name': 'Owner Name'})

    ordered_cols = [
        'Owner Name', 'Power Ranking',
        '# League Champs', '# League Runner-Ups', '# League Losers',
        'Total Seasons', 'Avg Regular Season Rank', 'Win %', 'Playoff Appearance %',
        'Avg Waiver Moves/Year', 'Avg Trades/Year', 'Avg FAAB Used/Year',
        'Avg High Scores/Year', 'Avg Low Scores/Year'
    ]
    ordered_cols = [c for c in ordered_cols if c in final_df.columns]
    final_df = final_df[ordered_cols]

    if show_current:
        final_df = final_df[final_df['Owner Name'].isin(current_owners)]

    if 'Power Ranking' in final_df.columns:
        final_df = final_df.sort_values('Power Ranking', ascending=True).reset_index(drop=True)

    st.markdown(
        '<div style="font-size:20px;font-weight:600;line-height:1.1;margin-top:15px;margin-bottom:2px;">'
        'League Summary</div>',
        unsafe_allow_html=True
    )

    n_rows = len(final_df)
    row_px = 34
    header_px = 40
    padding_px = 16
    max_px = 1200
    fit_height = min(max_px, header_px + n_rows * row_px + padding_px)

    st.dataframe(
        final_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Owner Name": st.column_config.TextColumn("Owner Name", pinned="left"),
            "Power Ranking": st.column_config.NumberColumn(format="%d"),
            "# League Champs": st.column_config.NumberColumn(format="%d"),
            "# League Runner-Ups": st.column_config.NumberColumn(format="%d"),
            "# League Losers": st.column_config.NumberColumn(format="%d"),
            "Total Seasons": st.column_config.NumberColumn(format="%d"),
            "Avg Regular Season Rank": st.column_config.NumberColumn(format="%.2f"),
            "Win %": st.column_config.NumberColumn(format="%.1f%%"),
            "Playoff Appearance %": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg Waiver Moves/Year": st.column_config.NumberColumn(format="%.2f"),
            "Avg Trades/Year": st.column_config.NumberColumn(format="%.2f"),
            "Avg FAAB Used/Year": st.column_config.NumberColumn(format="%.2f"),
            "Avg High Scores/Year": st.column_config.NumberColumn(format="%.2f"),
            "Avg Low Scores/Year": st.column_config.NumberColumn(format="%.2f"),
        },
        height=fit_height,
    )
