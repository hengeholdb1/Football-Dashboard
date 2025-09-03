def show_hall_of_fame(st, teams_df, matchups_df, players_df):
    # --- Inject CSS to tighten spacing ---
    st.markdown("""
        <style>
        .card {
            background-color: #222;
            border-radius: 8px;
            padding: 8px 12px;
            margin: 4px 0; /* reduce vertical space between cards */
        }
        .card-label {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 2px;
        }
        .card-value {
            font-size: 16px;
            font-weight: 500;
        }
        .card-sub {
            font-size: 12px;
            color: #aaa;
            margin-top: 2px;
        }
    """, unsafe_allow_html=True)

    # Merge to get owner_name and year
    df = matchups_df.merge(
        teams_df[['team_key', 'owner_name', 'year']],
        on='team_key', how='left'
    )
    regular_df = df[df['is_playoffs'] == 0]

    # Champs & Chumps
    wl_df = teams_df[teams_df['league_result'].isin(['Winner', 'Runner-up', 'Loser'])][
        ['year', 'owner_name', 'league_result']
    ]
    result_table = (
        wl_df.pivot(index="year", columns="league_result", values="owner_name")
             .rename(columns={
                 "Winner": "🥇 Winner",
                 "Runner-up": "🥈 Runner-up",
                 "Loser": "🗑️ Loser"
             })
             .reset_index()
             .rename(columns={"year": "Year"})
    )
    clean_table = result_table[["Year", "🥇 Winner", "🥈 Runner-up", "🗑️ Loser"]]

    def make_html_table(df):
        hdr = ''.join(
            f'<th style="padding:8px;background-color:#333;color:white;border:1px solid #555;">{col}</th>'
            for col in df.columns
        )
        body = ''
        for _, row in df.iterrows():
            body += '<tr>' + ''.join(
                f'<td style="text-align:center;padding:8px;background-color:#1a1a1a;color:white;border:1px solid #333;">{val}</td>'
                for val in row
            ) + '</tr>'
        return f'''
        <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;font-size:16px;">
            <thead><tr>{hdr}</tr></thead><tbody>{body}</tbody>
          </table>
        </div>
        '''

    st.markdown(
    '<div style="font-size:25px;font-weight:600;line-height:1.1;margin-top:-12px;margin-bottom:2px;">Champs & Chumps</div>',
    unsafe_allow_html=True)

    st.markdown(make_html_table(clean_table), unsafe_allow_html=True)

    # All Time Legends
    st.markdown(
    '<div style="font-size:25px;font-weight:600;line-height:1.1;margin-top:15px;margin-bottom:2px;">All Time Legends</div>',
    unsafe_allow_html=True)
    
    col11, col4, col1, col2, col3, col8 = st.columns(6, gap="small")

    # Best Avg Regular Season Rank
    ranking_df = teams_df[
        (teams_df['is_finished'] == 1) & 
        (teams_df['regular_season_ranking'].notnull())
    ]
    avg_rankings = ranking_df.groupby('owner_name').agg(
        avg_rank=('regular_season_ranking', 'mean'),
        seasons=('year', 'nunique')
    )
    avg_rankings = avg_rankings[avg_rankings['seasons'] > 1]

    if not avg_rankings.empty:
        best_rank_owner = avg_rankings['avg_rank'].idxmin()
        best_avg_rank = round(avg_rankings.loc[best_rank_owner, 'avg_rank'], 1)
        col11.markdown(f"""
            <div class="card">
            <div class="card-label">📈 Best Avg Regular Season Rank</div>
            <div class="card-value">{best_rank_owner} ({best_avg_rank})</div>
            </div>
        """, unsafe_allow_html=True)

    # Highest Win %
    win_df = teams_df.dropna(subset=['wins', 'losses'])
    win_df['total_games'] = win_df['wins'] + win_df['losses']
    win_df = win_df[win_df['total_games'] > 0]
    win_df['win_pct'] = win_df['wins'] / win_df['total_games']

    owner_stats = win_df.groupby('owner_name').agg(
        wins=('wins', 'sum'),
        losses=('losses', 'sum'),
        seasons=('year', 'nunique') 
    )
    owner_stats['total_games'] = owner_stats['wins'] + owner_stats['losses']
    owner_stats = owner_stats[owner_stats['seasons'] > 1]  
    owner_stats['win_pct'] = owner_stats['wins'] / owner_stats['total_games']

    if not owner_stats.empty:
        best_owner = owner_stats['win_pct'].idxmax()
        best_pct = round(owner_stats.loc[best_owner, 'win_pct'] * 100)
        col4.markdown(f"""
            <div class="card">
            <div class="card-label">🏋️ Highest Regular Season Win %</div>
            <div class="card-value">{best_owner} ({best_pct}%)</div>
            </div>
        """, unsafe_allow_html=True)

    # Most Weekly High Scores
    high_counts = regular_df[regular_df['high_score_flag'] == 1].groupby('owner_name').size()
    if not high_counts.empty:
        mh = high_counts.max()
        owners_hi = high_counts[high_counts == mh].index.tolist()
        text_hi = ", ".join(f"{o} ({mh})" for o in owners_hi)
    else:
        text_hi = "No data"
    col1.markdown(f"""
        <div class="card">
            <div class="card-label">🔥 Most Weekly High Scores</div>
            <div class="card-value">{text_hi}</div>
        </div>
    """, unsafe_allow_html=True)

    # Highest Weekly Score
    if not regular_df['points_for'].isnull().all():
        maxr = regular_df.loc[regular_df['points_for'].idxmax()]
        hv = maxr['points_for']; ho = maxr['owner_name']
        hy = int(maxr['year']); hw = int(maxr['week'])
        col2.markdown(f"""
            <div class="card">
                <div class="card-label">🌟 Highest Weekly Score</div>
                <div class="card-value">{ho} ({hv})</div>
                <div class="card-sub">Year: {hy}, Week: {hw}</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        col2.markdown(f"""
            <div class="card">
                <div class="card-label">🌟 Highest Weekly Score</div>
                <div class="card-value">No data</div>
            </div>
        """, unsafe_allow_html=True)

    # Biggest margin of victory
    biggest = df[df['is_playoffs'] == 0].copy()
    if 'points_difference' in biggest.columns and not biggest['points_difference'].isnull().all():
        max_row = biggest.loc[biggest['points_difference'].idxmax()]
        col3.markdown(f"""
            <div class="card">
            <div class="card-label">📏 <b>Biggest Margin of Victory</b></div>
            <div class="card-value">{max_row['owner_name']} ({max_row['points_difference']})</div>
            <div class="card-sub">
                Year: {int(max_row['year'])}, Week: {int(max_row['week'])}, vs {max_row['opponent_owner']}, 
                {max_row['points_for']} - {max_row['points_against']}
            </div>
            </div>
        """, unsafe_allow_html=True)

    # --- Ensure players_df has is_playoffs and owner/year info ---
    matchups_df['team_week_key'] = matchups_df['team_key'].astype(str) + '_' + matchups_df['week'].astype(str)
    players_df['team_week_key'] = players_df['team_key'].astype(str) + '_' + players_df['week'].astype(str)
    players_df = players_df.merge(
        matchups_df[['team_week_key', 'is_playoffs']],
        on='team_week_key', how='left')
    players_df = players_df.merge(
        teams_df[['team_key', 'owner_name', 'year']],
        on='team_key', how='left')

    # Highest Player Score 
    regular_starters = players_df[
        (players_df['is_playoffs'] == 0) &
        (~players_df['selected_position'].isin(['BN', 'IR']))
    ]

    if not regular_starters.empty:
        top = regular_starters.loc[regular_starters['player_week_points'].idxmax()]
        col8.markdown(f"""
            <div class="card">
            <div class="card-label">🚀 Highest Scoring Starter</div>
            <div class="card-value">{top['owner_name']} ({top['player_week_points']})</div>
            <div class="card-sub">Year: {int(top['year'])}, Week: {int(top['week'])}, {top['player_name']}</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        col8.markdown(f"""
            <div class="card">
            <div class="card-label">🚀 Highest Scoring Starter</div>
            <div class="card-value">No data</div>
            </div>
        """, unsafe_allow_html=True)

    # All Time Duds
    st.markdown('<div style="font-size:25px;font-weight:600;line-height:1.1;margin-top:15px;margin-bottom:2px;">All Time Duds</div>',
    unsafe_allow_html=True)

    col12, col7, col5, col6, col10, col9 = st.columns(6, gap="small")

    # Worst Avg Regular Season Rank
    ranking_df = teams_df[
        (teams_df['is_finished'] == 1) & 
        (teams_df['regular_season_ranking'].notnull())
    ]
    avg_rankings = ranking_df.groupby('owner_name').agg(
        avg_rank=('regular_season_ranking', 'mean'),
        seasons=('year', 'nunique')
    )
    avg_rankings = avg_rankings[avg_rankings['seasons'] > 1]

    if not avg_rankings.empty:
        worst_rank_owner = avg_rankings['avg_rank'].idxmax()
        worst_avg_rank = round(avg_rankings.loc[worst_rank_owner, 'avg_rank'], 1)
        col12.markdown(f"""
            <div class="card">
            <div class="card-label">❌Worst Avg Regular Season Rank</div>
            <div class="card-value">{worst_rank_owner} ({worst_avg_rank})</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        col12.markdown(f"""
            <div class="card">
            <div class="card-label">❌Worst Avg Regular Season Rank</div>
            <div class="card-value">No data</div>
            </div>
        """, unsafe_allow_html=True)

    # Lowest Win %
    win_df = teams_df.dropna(subset=['wins', 'losses'])
    win_df['total_games'] = win_df['wins'] + win_df['losses']
    win_df = win_df[win_df['total_games'] > 0]
    win_df['win_pct'] = win_df['wins'] / win_df['total_games']

    owner_stats = win_df.groupby('owner_name').agg(
        wins=('wins', 'sum'),
        losses=('losses', 'sum'),
        seasons=('year', 'nunique')
    )
    owner_stats['total_games'] = owner_stats['wins'] + owner_stats['losses']
    owner_stats = owner_stats[owner_stats['seasons'] > 1]  
    owner_stats['win_pct'] = owner_stats['wins'] / owner_stats['total_games']

    if not owner_stats.empty:
        worst_owner = owner_stats['win_pct'].idxmin()
        worst_pct = round(owner_stats.loc[worst_owner, 'win_pct'] * 100)
        col7.markdown(f"""
            <div class="card">
            <div class="card-label">📉 Lowest Regular Season Win %</div>
            <div class="card-value">{worst_owner} ({worst_pct}%)</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        col7.markdown(f"""
            <div class="card">
            <div class="card-label">📉 Lowest Regular Season Win %</div>
            <div class="card-value">No data</div>
            </div>
        """, unsafe_allow_html=True)

    # Most Weekly Low Scores
    low_counts = regular_df[regular_df['low_score_flag'] == 1].groupby('owner_name').size()
    if not low_counts.empty:
        ml = low_counts.max()
        owners_lo = low_counts[low_counts == ml].index.tolist()
        text_lo = ", ".join(f"{o} ({ml})" for o in owners_lo)
    else:
        text_lo = "No data"
    col5.markdown(f"""
        <div class="card">
            <div class="card-label">💤 Most Weekly Low Scores</div>
            <div class="card-value">{text_lo}</div>
        </div>
    """, unsafe_allow_html=True)

    # Lowest Weekly Score
    if not regular_df['points_for'].isnull().all():
        minr = regular_df.loc[regular_df['points_for'].idxmin()]
        lv = minr['points_for']; lo = minr['owner_name']
        ly = int(minr['year']); lw = int(minr['week'])
        col6.markdown(f"""
            <div class="card">
                <div class="card-label">☠️ Lowest Weekly Score</div>
                <div class="card-value">{lo} ({lv})</div>
                <div class="card-sub">Year: {ly}, Week: {lw}</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        col6.markdown(f"""
            <div class="card">
                <div class="card-label">☠️ Lowest Weekly Score</div>
                <div class="card-value">No data</div>
            </div>
        """, unsafe_allow_html=True)

    # Most times starting a player with ≤ 0 points
    bad_starts = players_df[
        (players_df['is_playoffs'] == 0) &
        (~players_df['selected_position'].isin(['BN', 'IR'])) &
        (players_df['player_week_points'] <= 0)
    ]
    zero_counts = bad_starts.groupby('owner_name').size()

    if not zero_counts.empty:
        max_count = zero_counts.max()
        worst_owners = zero_counts[zero_counts == max_count].index.tolist()
        worst_owners_text = ", ".join(f"{owner} ({max_count})" for owner in worst_owners)
        col10.markdown(f"""
            <div class="card">
            <div class="card-label">🥚 Most Goose Egg Starters (<=0 pts)</div>
            <div class="card-value">{worst_owners_text}</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        col10.markdown(f"""
            <div class="card">
            <div class="card-label">🥚 Most Goose Egg Starters (<=0 pts)</div>
            <div class="card-value">No data</div>
            </div>
        """, unsafe_allow_html=True)

    # Highest Player Score (Bench)
    bench_players = players_df[
        (players_df['is_playoffs'] == 0) &
        (players_df['selected_position'] == 'BN')
    ]

    if not bench_players.empty:
        high_bench = bench_players.loc[bench_players['player_week_points'].idxmax()]
        col9.markdown(f"""
            <div class="card">
            <div class="card-label">🪑 Highest Scoring Bench</div>
            <div class="card-value">{high_bench['owner_name']} ({high_bench['player_week_points']})</div>
            <div class="card-sub">Year: {int(high_bench['year'])}, Week: {int(high_bench['week'])}, {high_bench['player_name']}</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        col9.markdown(f"""
            <div class="card">
            <div class="card-label">🪑 Highest Scoring Bench</div>
            <div class="card-value">No data</div>
            </div>
        """, unsafe_allow_html=True)
