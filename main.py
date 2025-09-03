import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from tab_hall_of_fame import show_hall_of_fame
from tab_league_rules import show_league_rules
from tab_league_insights import show_league_insights
from tab_draft_board import show_draft_board
from tab_owner_insights import show_owner_insights
from tab_team_insights import show_team_insights
import base64
from pathlib import Path
import streamlit as st

# Read and embed the logos
logo_path = Path(__file__).parent / "assets" / "logo.png"  # robust relative path
logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

# Page config and styling
st.set_page_config(page_title="Dayton Boyz Fantasy Football", layout="wide")

st.markdown("""
<style>
header.stAppHeader {
    background-color: transparent;
}
section.stMain .block-container {
    padding-top: 0rem;
    z-index: 1;
}
</style>""", unsafe_allow_html=True)

st.markdown("""
    <style>
        .block-container { padding-top: 2rem; }
        .card { padding: 1rem; background-color: #0e1117; border-radius: 0rem; margin-bottom: 1rem; }
        .card-label { font-size: 1rem; color: #bbb; text-align: left; }
        .card-value { font-size: 2.5rem; font-weight: bold; margin: 0; color: white; text-align: left; }
        .card-sub { margin-top: 0.1rem; font-size: 0.8rem; background-color: #444; color: #eee;
                    padding: 0rem 0.5rem; border-radius: 0.4rem; display: inline-block; }
    </style>
    
""", unsafe_allow_html=True)

st.markdown("""
    <style>
        /* Fixed scroll hint at bottom */
        .scroll-hint {
            position: fixed;
            bottom: 6px;
            left: 12px;
            font-size: 12px;
            color: #aaa;
            z-index: 9999;
            pointer-events: none;
        }
        /* Hide on larger screens (desktop/tablet) */
        @media (min-width: 768px) {
            .scroll-hint { display: none; }
        }
    </style>
    <div class="scroll-hint">↓ Scroll for more</div>
""", unsafe_allow_html=True)

st.markdown(f"""
</style>
    <div style="
  display:flex;
  align-items:center;
  gap:15px;
  padding:12px 0;           /* gives breathing room to prevent clipping */
  overflow:visible;         /* make sure nothing gets cut */
">
  <img
    src="data:image/png;base64,{logo_b64}"
    alt="Dayton Boyz"
    style="
      height:80px;          /* adjust size here */
      display:block;        /* avoids inline line-box clipping */
      margin:0;             /* reset margins */
      object-fit:contain;   /* safe scaling */
    "
  />
  <div style="
    font-size:2rem;         /* ~ H2 size */
    font-weight:700;
    line-height:1.05;       /* tighter line-height to center nicely */
    margin:0;               /* no default margins */
  ">
    Dayton Boyz Fantasy Football
  </div>
</div>

""", unsafe_allow_html=True)


# Load data
teams_csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?output=csv"
matchups_csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?gid=625049670&single=true&output=csv"
players_csv = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?gid=1947173700&single=true&output=csv"
draft_roster_csv = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?gid=1611857667&single=true&output=csv"
final_roster_csv = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?gid=148379330&single=true&output=csv"

teams_df = pd.read_csv(teams_csv_url)
matchups_df = pd.read_csv(matchups_csv_url)
players_df = pd.read_csv(players_csv)
draft_roster_df = pd.read_csv(draft_roster_csv)
final_roster_df = pd.read_csv(final_roster_csv)

print("Draft Roster columns:", draft_roster_df.columns.tolist())

for df in [teams_df, matchups_df, players_df, draft_roster_df, final_roster_df]:
    df.columns = df.columns.str.strip().str.lower()

# Dropdown (label hidden)
page = st.selectbox(
    label="Navigation",  # accessibility only
    options=[
        "League Rankings",
        "Owner Metrics",
        "Team Insights",
        "Hall of Fame/ Shame",
        "Draft Boards",
        "Rulebook"
    ],
    index=0,
    label_visibility="collapsed"
)

if page == "League Rankings":
    show_league_insights(st, go, teams_df, matchups_df)

elif page == "Owner Metrics":
    show_owner_insights(st, go, teams_df, matchups_df)

elif page == "Team Insights":
    show_team_insights(st, go, teams_df, matchups_df, players_df)

elif page == "Hall of Fame/ Shame":
    show_hall_of_fame(st, teams_df, matchups_df, players_df)

elif page == "Draft Boards":
    show_draft_board(st, teams_df, draft_roster_df, players_df, matchups_df)

elif page == "Rulebook":
    show_league_rules(st)
