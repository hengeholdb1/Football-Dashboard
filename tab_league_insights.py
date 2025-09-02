def show_league_insights(st, go, teams_df):

    st.markdown('<div style="font-size:20px;font-weight:600;margin-bottom:0;">Owner Power Rankings</div>', unsafe_allow_html=True)
    # Calculate avg regular season rank and win % for each owner
    ranking_df = teams_df[
        (teams_df['is_finished'] == 1) & 
        (teams_df['regular_season_ranking'].notnull())
    ]
    # Slicer/toggle for current owners or all owners
    show_current = st.toggle("Show only current owners", value=True)
    last_season = teams_df['year'].max()
    current_owners = teams_df[teams_df['year'] == last_season]['owner_name'].unique()

    avg_rankings = ranking_df.groupby('owner_name').agg(
        avg_rank=('regular_season_ranking', 'mean'),
        seasons=('year', 'nunique')
    )
    win_df = teams_df.dropna(subset=['wins', 'losses'])
    win_df['total_games'] = win_df['wins'] + win_df['losses']
    win_df = win_df[win_df['total_games'] > 0]
    win_df['win_pct'] = win_df['wins'] / win_df['total_games']
    win_stats = win_df.groupby('owner_name').agg(
        wins=('wins', 'sum'),
        losses=('losses', 'sum'),
        total_games=('total_games', 'sum'),
        win_pct=('win_pct', 'mean'),
        seasons=('year', 'nunique')
    )

    # Merge on index, use 'left' to keep only owners in avg_rankings
    insights_df = avg_rankings.merge(win_stats, left_index=True, right_index=True, how='left')
    insights_df = insights_df.reset_index()  # owner_name becomes a column
    
    # Calculate playoff %, #championships, #runner-ups, #losers
    def playoff_count(owner):
        # All seasons played (including 2017)
        owner_seasons = teams_df[teams_df['owner_name'] == owner]
        # Playoff denominator: exclude 2017
        playoff_denominator = owner_seasons[owner_seasons['year'] != 2017]
        playoff_seasons = playoff_denominator[playoff_denominator['league_result'].isin(['Playoffs', 'Runner-up', 'Winner'])]
        return len(playoff_seasons), len(owner_seasons)
    def champ_count(owner):
        return (teams_df[(teams_df['owner_name'] == owner) & (teams_df['league_result'] == 'Winner')].shape[0])
    def runnerup_count(owner):
        return (teams_df[(teams_df['owner_name'] == owner) & (teams_df['league_result'] == 'Runner-up')].shape[0])
    def loser_count(owner):
        return (teams_df[(teams_df['owner_name'] == owner) & (teams_df['league_result'] == 'Loser')].shape[0])

    insights_df = insights_df.reset_index(drop=True)
    insights_df['Avg Regular Season Rank'] = insights_df['avg_rank'].round(2)
    insights_df['Win %'] = (insights_df['win_pct'] * 100).round(1)
    insights_df['Playoff Seasons'] = insights_df['owner_name'].apply(lambda x: playoff_count(x)[0])
    insights_df['Total Seasons'] = insights_df['owner_name'].apply(lambda x: playoff_count(x)[1])
    insights_df['Playoff Appearance %'] = (insights_df['Playoff Seasons'] / insights_df['Total Seasons'] * 100).round(1)
    insights_df['# Championships'] = insights_df['owner_name'].apply(champ_count)
    insights_df['# Runner-Ups'] = insights_df['owner_name'].apply(runnerup_count)
    insights_df['# League Losers'] = insights_df['owner_name'].apply(loser_count)
    # Power Ranking score calculation
    insights_df['Power Ranking Score'] = (
        insights_df['# Championships'] * 5 +
        insights_df['# Runner-Ups'] * 3 -
        insights_df['# League Losers'] * 2 -
        insights_df['Avg Regular Season Rank'] +
        insights_df['Total Seasons'] * 0.5
    ).round(2)
    # Power Ranking: rank (1 = best)
    insights_df['Power Ranking'] = insights_df['Power Ranking Score'].rank(method='min', ascending=False).astype(int)
    # Select and rename columns
    final_cols = ['owner_name', 'Total Seasons', 'Avg Regular Season Rank', 'Win %', 'Playoff Appearance %', '# Championships', '# Runner-Ups', '# League Losers', 'Power Ranking']
    final_df = insights_df[final_cols].rename(columns={
        'owner_name': 'Owner',
        'Total Seasons': 'Seasons Played'
    })
    # Filter for current owners if toggle is on
    if show_current:
        final_df = final_df[final_df['Owner'].isin(current_owners)]
    # Sort by Power Ranking ascending (1 = best)
    final_df = final_df.sort_values('Power Ranking', ascending=True)

    def make_html_table(df):
        min_col_width = 90
        col_width = f"{max(min_col_width, 100/len(df.columns)):.2f}px"
        hdr = ''.join(
            f'<th style="min-width:{col_width};padding:4px;background-color:#333;color:white;border:1px solid #555;position:sticky;top:0;z-index:2;font-size:12px;">{col}</th>'
            for col in df.columns
        )
        body = ''
        for i, row in enumerate(df.iterrows()):
            idx, vals = row
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
        </div>
        '''

    # Awards visual: bar and line chart
    awards_df = insights_df.copy()
    if show_current:
        awards_df = awards_df[awards_df['owner_name'].isin(current_owners)]
    # Sort by Power Ranking ascending (1 = best)
    awards_df = awards_df.sort_values('Power Ranking', ascending=False)
    y_vals = awards_df['owner_name']
    # Bar chart: championships, runner-ups, league losers (as int)
    bar_champ = awards_df['# Championships'].astype(int)
    bar_runnerup = awards_df['# Runner-Ups'].astype(int)
    bar_loser = -awards_df['# League Losers'].astype(int)  # negative for downward bars
    # Owner label only for y-axis, stats in tooltip
    seasons_col = 'Total Seasons'
    y_labels = [
        f"<span style='font-size:15px;font-weight:bold;line-height:1;'>#{row['Power Ranking']} {owner}</span>"
        for owner, (_, row) in zip(y_vals, awards_df.iterrows())
    ]

    fig = go.Figure()
    # Stack championships and runner-ups, overlay league losers, add custom hovertext, horizontal orientation
    fig.add_trace(go.Bar(
        y=y_vals,
        x=bar_champ,
        name='Championships',
        marker_color='#FFD700',
        orientation='h',
        offsetgroup='awards',
        base=0
    ))
    fig.add_trace(go.Bar(
        y=y_vals,
        x=bar_runnerup,
        name='Runner-Ups',
        marker_color='#C0C0C0',
        orientation='h',
        offsetgroup='awards',
        base=bar_champ
    ))
    fig.add_trace(go.Bar(
        y=y_vals,
        x=bar_loser,
        name='League Losers',
        marker_color='red',
        orientation='h',
        offsetgroup='awards',
        base=0
    ))
    # No annotation needed; stats are part of x-axis tick labels
    fig.update_layout(
        barmode='relative',
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
            y=-0.2,        # push below chart
            xanchor='center',
            x=0.5,
            font=dict(size=12, color="white")
        ),
        height=380,
        margin=dict(l=10, r=10, t=0, b=10),
        bargap=0.18
    )
    st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': False,
        'staticPlot': True
    })
    
    st.markdown('<span style="font-size:20px;font-weight:500;line-height:1.2;padding:2px 0;">Owner Performance Summary</span>', unsafe_allow_html=True)

    st.markdown(make_html_table(final_df), unsafe_allow_html=True)
