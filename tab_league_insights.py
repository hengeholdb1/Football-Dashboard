import pandas as pd  # make sure this is at top of file

def show_league_insights(st, go, teams_df, matchups_df):
    st.markdown('<div style="font-size:20px;font-weight:600;margin-bottom:0;">Owner Power Rankings</div>', unsafe_allow_html=True)

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
    insights_df['# League Runner-Ups'] = insights_df['owner_name'].apply(runnerup_count)     # renamed label
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

    for col in ['high_score_flag', 'low_score_flag']:
        if col in m.columns:
            m[col] = m[col].fillna(0).astype(int)
        else:
            m[col] = 0

    owner_year_flags = m.groupby(['owner_name', 'year'], dropna=False).agg(
        high_scores=('high_score_flag', 'sum'),
        low_scores=('low_score_flag', 'sum')
    ).reset_index()

    owner_avg_flags = owner_year_flags.groupby('owner_name', dropna=False).agg(
        **{'Avg High Scores/Year': ('high_scores', 'mean'),
           'Avg Low Scores/Year': ('low_scores', 'mean')}
    ).round(2).reset_index()

    insights_df = insights_df.merge(owner_avg_flags, on='owner_name', how='left')

    # ---------- Plot at top (unchanged visual style) ----------
# ---------- Plot at top (stack champs + runner-ups, losers to left) ----------
    awards_df = insights_df.copy()
    if show_current:
        awards_df = awards_df[awards_df['owner_name'].isin(current_owners)]
    awards_df = awards_df.sort_values('Power Ranking', ascending=False)

    y_vals = awards_df['owner_name']
    y_labels = [
        f"<span style='font-size:15px;font-weight:bold;line-height:1;'>#{row['Power Ranking']} {owner}</span>"
        for owner, (_, row) in zip(y_vals, awards_df.iterrows())
    ]

    fig = go.Figure()

    # Champs (positive)
    fig.add_trace(go.Bar(
        y=y_vals,
        x=awards_df['# League Champs'].astype(int),
        name='Champ',
        marker_color='#FFD700',
        orientation='h'
    ))

    # Runner-Ups (also positive -> stacks on champs)
    fig.add_trace(go.Bar(
        y=y_vals,
        x=awards_df['# League Runner-Ups'].astype(int),
        name='Runner-Up',
        marker_color='#C0C0C0',
        orientation='h'
    ))

    # Losers (negative -> stacks to the left of zero)
    fig.add_trace(go.Bar(
        y=y_vals,
        x=-awards_df['# League Losers'].astype(int),
        name='Loser',
        marker_color='red',
        orientation='h'
    ))

    fig.update_layout(
        barmode='relative',  # positive stacks together; negatives stack on the left
        yaxis_title='Owner/ Power Ranking',
        yaxis=dict(
            tickmode='array',
            tickvals=list(y_vals),
            ticktext=y_labels,
            title='Owner/ Power Ranking',
            side='left',
            showgrid=True,
            gridcolor='#bbb',
            gridwidth=1,
            dtick=1,
            zeroline=False,
            automargin=True,
            tickfont=dict(size=13),
            ticklabeloverflow='allow',
            categoryorder='array',
            categoryarray=list(y_vals),
            constrain='range'
        ),
        xaxis=dict(
            title='Awards Count',
            showgrid=True,
            gridcolor='#bbb',
            gridwidth=1,
            dtick=1,
            ticks='outside',
            showline=False,
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
        height=380,
        margin=dict(l=10, r=10, t=0, b=10),
        bargap=0.18
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})


    # ---------- Final table (same HTML look, new order) ----------
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

    # Initial sort by Power Ranking ascending (1 = best)
    if 'Power Ranking' in final_df.columns:
        final_df = final_df.sort_values('Power Ranking', ascending=True).reset_index(drop=True)

    st.markdown('<div style="font-size:20px;font-weight:600;line-height:1.1;margin-top:15px;margin-bottom:2px;">Owner Performance Summary</div>', unsafe_allow_html=True)
    
    def make_html_table(df):
        min_col_width = 90
        col_width = f"{max(min_col_width, 100/len(df.columns)):.2f}px"
        hdr = ''.join(
            f'<th style="min-width:{col_width};padding:4px;background-color:#333;color:white;'
            f'border:1px solid #555;position:sticky;top:0;z-index:2;font-size:12px;'
            f'text-align:center;">{col}</th>'
            for col in df.columns
        )
        body = ''
        for _, vals in df.iterrows():
            body += '<tr>'
            for j, val in enumerate(vals):
                if j == 0:
                    body += f'<td style="min-width:{col_width};text-align:center;padding:4px;background-color:#222;color:white;border:1px solid #333;position:sticky;left:0;z-index:1;font-size:12px;">{val}</td>'
                else:
                    body += f'<td style="min-width:{col_width};text-align:center;padding:4px;background-color:#1a1a1a;color:white;border:1px solid #333;font-size:12px;">{val}</td>'
            body += '</tr>'
        return f'''
        <div style="overflow-x:auto;max-width:100vw;">
        <table style="width:100%;border-collapse:collapse;font-size:12px;min-width:{min_col_width*len(df.columns)}px;">
            <thead><tr>{hdr}</tr></thead><tbody>{body}</tbody>
        </table>
        <div style="font-size:11px;color:#aaa;margin-top:4px;text-align:right;">
            ↔️ Table is scrollable
        </div>
        </div>
        '''

    st.markdown(make_html_table(final_df), unsafe_allow_html=True)
