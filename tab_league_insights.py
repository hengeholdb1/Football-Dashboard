import pandas as pd  # make sure this is at top of file

def show_league_insights(st, go, teams_df, matchups_df):
    st.markdown('<div style="font-size:20px;font-weight:600;margin-bottom:0;">League Trophy Count</div>', unsafe_allow_html=True)

    # ---------- Base ranking & win% ----------
    ranking_df = teams_df[
        (teams_df['is_finished'] == 1) & 
        (teams_df['regular_season_ranking'].notnull())
    ]
    show_current = st.toggle("Show only current owners", value=True)
    last_season = teams_df['year'].max()
    current_owners = teams_df[teams_df['year'] == last_season]['owner_name'].unique()

    avg_rankings = ranking_df.groupby('owner_name', dropna=False).agg(
        avg_rank=('regular_season_ranking', 'mean'),
        seasons=('year', 'nunique')
    )

    win_df = teams_df.dropna(subset=['wins', 'losses']).copy()
    win_df['total_games'] = win_df['wins'] + win_df['losses']
    win_df = win_df[win_df['total_games'] > 0].copy()
    win_df['win_pct'] = win_df['wins'] / win_df['total_games']

    win_stats = win_df.groupby('owner_name', dropna=False).agg(
        wins=('wins', 'sum'),
        losses=('losses', 'sum'),
        total_games=('total_games', 'sum'),
        win_pct=('win_pct', 'mean'),
        seasons=('year', 'nunique')
    )

    insights_df = avg_rankings.merge(win_stats, left_index=True, right_index=True, how='left').reset_index()

    # ---------- Playoff/champ/runner-up/loser counts ----------
    def playoff_count(owner):
        owner_seasons = teams_df[teams_df['owner_name'] == owner]
        playoff_denominator = owner_seasons[owner_seasons['year'] != 2017]
        playoff_seasons = playoff_denominator[playoff_denominator['league_result'].isin(['Playoffs', 'Runner-up', 'Winner'])]
        return len(playoff_seasons), len(owner_seasons)

    def champ_count(owner):
        return (teams_df[(teams_df['owner_name'] == owner) & (teams_df['league_result'] == 'Winner')].shape[0])

    def runnerup_count(owner):
        return (teams_df[(teams_df['owner_name'] == owner) & (teams_df['league_result'] == 'Runner-up')].shape[0])

    def loser_count(owner):
        return (teams_df[(teams_df['owner_name'] == owner) & (teams_df['league_result'] == 'Loser')].shape[0])

    insights_df['Avg Regular Season Rank'] = insights_df['avg_rank'].round(2)
    insights_df['Win %'] = (insights_df['win_pct'] * 100).round(1)
    insights_df['Playoff Seasons'] = insights_df['owner_name'].apply(lambda x: playoff_count(x)[0])
    insights_df['Total Seasons'] = insights_df['owner_name'].apply(lambda x: playoff_count(x)[1])
    insights_df['Playoff Appearance %'] = (insights_df['Playoff Seasons'] / insights_df['Total Seasons'] * 100).round(1)
    insights_df['# League Champs'] = insights_df['owner_name'].apply(champ_count)
    insights_df['# League Runner-Ups'] = insights_df['owner_name'].apply(runnerup_count)
    insights_df['# League Losers'] = insights_df['owner_name'].apply(loser_count)

    # ---------- Power Ranking ----------
    insights_df['Power Ranking Score'] = (
        insights_df['# League Champs'] * 5 +
        insights_df['# League Runner-Ups'] * 3 - 
        insights_df['# League Losers'] * 2 -
        insights_df['Avg Regular Season Rank'] +
        insights_df['Total Seasons'] * 0.5
    ).round(2)
    insights_df['Power Ranking'] = insights_df['Power Ranking Score'].rank(method='min', ascending=False).astype(int)

    # ---------- New metrics (exclude 2017) ----------
    non_2017 = teams_df[teams_df['year'] != 2017].copy()

    aggr_team_year = non_2017.groupby(['owner_name', 'year'], dropna=False).agg(
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

    # ---------- High/Low score avgs (exclude 2017, regular season only) ----------
    owner_map = teams_df[['team_key', 'owner_name', 'year']].drop_duplicates()
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
            m[col] = pd.to_numeric(m[col], errors='coerce')

    m['is_playoffs'] = m['is_playoffs'].fillna(0).astype(int)
    m['high_score_flag'] = m['high_score_flag'].fillna(0).astype(int)
    m['low_score_flag']  = m['low_score_flag'].fillna(0).astype(int)

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

    # ---------- Plot: stack champs + runner-ups (right), losers (left) ----------
    awards_df = insights_df.copy()
    if show_current:
        awards_df = awards_df[awards_df['owner_name'].isin(current_owners)]
    awards_df = awards_df.sort_values('Power Ranking', ascending=False)

    y_vals = awards_df['owner_name']

    # Build "#rank Owner" labels for the y-axis
    y_labels = [
        f"#{int(rank)} {owner}"
        for owner, rank in zip(awards_df['owner_name'], awards_df['Power Ranking'])
    ]

    fig = go.Figure()

    # Champs (right)
    fig.add_trace(go.Bar(
        y=y_vals,
        x=awards_df['# League Champs'].astype(int),
        name='Champ',
        marker_color='#FFD700',
        orientation='h'
    ))

    # Runner-Ups (right)
    fig.add_trace(go.Bar(
        y=y_vals,
        x=awards_df['# League Runner-Ups'].astype(int),
        name='Runner-Up',
        marker_color='#C0C0C0',
        orientation='h'
    ))

    # Losers (left)
    fig.add_trace(go.Bar(
        y=y_vals,
        x=-awards_df['# League Losers'].astype(int),
        name='Loser',
        marker_color='red',
        orientation='h'
    ))

    fig.update_layout(
        barmode='relative',
        yaxis=dict(
            title=dict(
                text='Power Ranking / Owner',
                standoff=12,                 # distance from tick labels → smaller = closer
                font=dict(size=14)
            ),
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
            range=[-2, 2],         # <<< clamp axis to -2 through 2
            showgrid=True,
            gridcolor='rgba(200,200,200,0.5)',
            gridwidth=1,
            dtick=1,
            showline=True,         # <<< draw axis lines
            mirror=True,           # <<< put them on both top and bottom
            linecolor='white',     # <<< make them visible
            linewidth=1,
            ticks='outside',
            zeroline=False,
            constrain='range',
            tickfont=dict(size=12),
        ),
        legend=dict(
            orientation='h',
            yanchor='top',
            y=-0.2,
            xanchor='center',
            x=0.5,
            font=dict(size=10, color="white")
        ),
        height=370,
        margin=dict(l=20, r=10, t=0, b=10),
        bargap=0.18
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})


        # ---------- Final table (Streamlit dataframe w/ frozen first col) ----------
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

    # Sort by Power Ranking ascending (1 = best)
    if 'Power Ranking' in final_df.columns:
        final_df = final_df.sort_values('Power Ranking', ascending=True).reset_index(drop=True)

    st.markdown(
        '<div style="font-size:20px;font-weight:600;line-height:1.1;margin-top:15px;margin-bottom:2px;">'
        'League Summary</div>',
        unsafe_allow_html=True
    )

    # Fit height to show all rows (similar to sample)
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

