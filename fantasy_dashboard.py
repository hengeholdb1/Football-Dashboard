import streamlit as st
import pandas as pd

# Page config and styling
st.set_page_config(page_title="Dayton Boyz Fantasy Football", layout="wide")
st.markdown("""
    <style>
        .block-container { padding-top: 2rem; }
        .card { padding: .5rem; background-color: #0e1117; border-radius: 0rem; margin-bottom: 1rem; }
        .card-label { font-size: 1rem; color: #bbb; text-align: left; }
        .card-value { font-size: 2.5rem; font-weight: bold; margin: 0; color: white; text-align: left; }
        .card-sub { margin-top: 0.1rem; font-size: 0.8rem; background-color: #444; color: #eee;
                    padding: 0rem 0.5rem; border-radius: 0.4rem; display: inline-block; }
    </style>
""", unsafe_allow_html=True)

st.title("🏈 Dayton Boyz Fantasy Football")

# CSV export links
teams_csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?output=csv"
matchups_csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?gid=625049670&single=true&output=csv"
players_csv = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?gid=1947173700&single=true&output=csv"

try:
    # Load data
    teams_df = pd.read_csv(teams_csv_url)
    matchups_df = pd.read_csv(matchups_csv_url)
    players_df = pd.read_csv(players_csv)
    teams_df.columns = teams_df.columns.str.strip().str.lower()
    matchups_df.columns = matchups_df.columns.str.strip().str.lower()
    players_df.columns = players_df.columns.str.strip().str.lower()

    # Merge to get owner_name and year
    df = matchups_df.merge(
        teams_df[['team_key', 'owner_name', 'year']],
        on='team_key', how='left'
    )
    regular_df = df[df['is_playoffs'] == 0]

    # Merge matchup info into players_df (only bring in is_playoffs)
    players_df = players_df.merge(
        matchups_df[['matchup_key', 'is_playoffs']],
        on='matchup_key', how='left')

    # Merge team owner/year info into players_df using players' team_key
    players_df = players_df.merge(
        teams_df[['team_key', 'owner_name', 'year']],
        on='team_key', how='left')
    
    # Single-tab layout
    tab1, tab2 = st.tabs(["Hall of Fame/ Shame", "League Rules"])
    with tab1:
        # Champs & Chumps table
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
        st.subheader("Champs & Chumps")
        st.markdown(make_html_table(clean_table), unsafe_allow_html=True)

        # All Time Perfomers
        st.subheader("All Time Legends")
        col11, col4, col1, col2, col3, col8 = st.columns(6)

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
    

        # New Section: All Time Duds 
        st.subheader("All Time Duds")
        col12, col7, col5, col6, col10, col9 = st.columns(6)

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
        owner_stats = owner_stats[owner_stats['seasons'] > 1]  # ✅ Only multi-season owners
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


    with tab2:
        st.title("📜 League Rules – 2025")

        st.markdown("""
    ### Scoring
    **Format:** ½ Point PPR

    **Offensive:**
    - Passing Yards: 25 yards = 1 point  
    - Passing Touchdown: 4 points  
    - Interceptions: -2 points  
    - Rushing Yards: 10 yards = 1 point  
    - Receiving Yards: 10 yards = 1 point  
    - Receptions: 0.5 points  
    - Receiving Touchdowns: 6 points  
    - Return Touchdowns: 6 points  
    - 2 Point Conversions: 2 points  
    - Fumbles Lost: -2 points  
    - Offensive Fumble Return TD: 6 points

    **Kickers:**
    - FG 0–39 yards: 3 points  
    - FG 40–49 yards: 4 points  
    - FG 50+ yards: 5 points  
    - Extra Point Made: 1 point

    **Defense:**
    - Sack: 1 point  
    - Interception: 2 points  
    - Fumble Recovery: 2 points  
    - Touchdown: 6 points  
    - Safety: 2 points  
    - Block Kick: 2 points  
    - Kick/Punt Return TD: 6 points  
    - Points Allowed 0: 10 points  
    - 1–6: 7 points  
    - 7–13: 4 points  
    - 14–20: 1 point  
    - 21–27: 0 points  
    - 28–34: -2 points  
    - 35+: -4 points

    ---

    ### Rosters
    - **Starting Lineup:** 1 QB, 2 WR, 2 RB, 1 TE, 1 Flex (W/R/T), 1 K, 1 DEF  
    - **Bench:** 5 BN, 1 IR

    ---

    ### Draft
    - **Type:** Online Live Snake  
    - **Time:** ~Late August  
    - **Order:** Determined via wrestling simulator + draft for draft position  
    - **Pick Time:** 60 seconds  
    - **Keeper:** 1 optional (see below)

    ---

    ### Regular Season
    - 1 Division  
    - 14 Weeks (Weeks 1–14)  
    - Tiebreaker: Points For

    ---

    ### Playoffs
    - 6 Teams  
    - 3 Weeks (Weeks 15–17)  
    - Top 2 seeds get a 1st-round bye  
    - No high score payouts during playoffs

    ---

    ### Keepers
    - Keep 1 player from previous year (optional)  
    - Must be 7th-round pick or later in prior draft  
    - Must be on end-of-season roster  
    - If undrafted: costs your last pick  
    - Cannot be kept in consecutive years

    ---

    ### Waivers
    - **Format:** FAAB  
    - Waiver Time: 2 days after drop  
    - Pickup Day: Wednesday morning  
    - Max Acquisitions: None ($0 bids allowed)

    ---

    ### Trades
    - **Deadline:** Saturday before Week 11  
    - **Review:** Commissioner  
    - **Veto Time:** 1 day

    ---

    ### Rewards & Punishments
    - $60 Buy-in (Venmo to Commissioner)  
    - Weekly High Score: $30  
    - League Champion: $290 + Trophy w/ Nameplate  
    - Loser: Calendar + Loser Trophy

    ---

    ### Rule Changes
    - May be proposed before draft  
    - Needs 1 second to go to a vote  
    - Simple majority passes (Commissioner breaks ties)
        """)

except Exception as e:
    st.error(f"❌ Failed to load or process data.\n\nError: {e}")