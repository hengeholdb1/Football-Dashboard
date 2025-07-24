import streamlit as st
import pandas as pd

# Page config and styling
st.set_page_config(page_title="Hall of Fame/ Shame", layout="wide")
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

try:
    # Load data
    teams_df = pd.read_csv(teams_csv_url)
    matchups_df = pd.read_csv(matchups_csv_url)
    teams_df.columns = teams_df.columns.str.strip()
    matchups_df.columns = matchups_df.columns.str.strip()

    # Merge to get owner_name and year
    df = matchups_df.merge(
        teams_df[['team_key', 'owner_name', 'year']],
        on='team_key', how='left'
    )
    regular_df = df[df['is_playoffs'] == 0]

    # Single-tab layout
    tab1, = st.tabs(["Hall of Fame/ Shame"])
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

        # All Time Booms & Busts
        st.subheader("All Time Booms & Busts")
        col1, col2, col3, col4 = st.columns(4)

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

        # Most Weekly Low Scores
        low_counts = regular_df[regular_df['low_score_flag'] == 1].groupby('owner_name').size()
        if not low_counts.empty:
            ml = low_counts.max()
            owners_lo = low_counts[low_counts == ml].index.tolist()
            text_lo = ", ".join(f"{o} ({ml})" for o in owners_lo)
        else:
            text_lo = "No data"
        col2.markdown(f"""
            <div class="card">
              <div class="card-label">💤 Most Weekly Low Scores</div>
              <div class="card-value">{text_lo}</div>
            </div>
        """, unsafe_allow_html=True)

        # Highest Weekly Score
        if not regular_df['points_for'].isnull().all():
            maxr = regular_df.loc[regular_df['points_for'].idxmax()]
            hv = maxr['points_for']; ho = maxr['owner_name']
            hy = int(maxr['year']); hw = int(maxr['week'])
            col3.markdown(f"""
                <div class="card">
                  <div class="card-label">🌟 Highest Weekly Score</div>
                  <div class="card-value">{ho} ({hv})</div>
                  <div class="card-sub">Year: {hy}, Week: {hw}</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            col3.markdown(f"""
                <div class="card">
                  <div class="card-label">🌟 Highest Weekly Score</div>
                  <div class="card-value">No data</div>
                </div>
            """, unsafe_allow_html=True)

        # Lowest Weekly Score
        if not regular_df['points_for'].isnull().all():
            minr = regular_df.loc[regular_df['points_for'].idxmin()]
            lv = minr['points_for']; lo = minr['owner_name']
            ly = int(minr['year']); lw = int(minr['week'])
            col4.markdown(f"""
                <div class="card">
                  <div class="card-label">☠️ Lowest Weekly Score</div>
                  <div class="card-value">{lo} ({lv})</div>
                  <div class="card-sub">Year: {ly}, Week: {lw}</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            col4.markdown(f"""
                <div class="card">
                  <div class="card-label">☠️ Lowest Weekly Score</div>
                  <div class="card-value">No data</div>
                </div>
            """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"❌ Failed to load or process data.\n\nError: {e}")
