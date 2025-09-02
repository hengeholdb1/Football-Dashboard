import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from tab_hall_of_fame import show_hall_of_fame
from tab_league_rules import show_league_rules
from tab_league_insights import show_league_insights
from tab_draft_board import show_draft_board

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

# Tabs for different views
tab1, tab2, tab3, tab4 = st.tabs(["League Standings", "Hall of Fame/ Shame", "Draft Boards", "League Rules"])
with tab1:
    show_league_insights(st, go, teams_df, matchups_df)
with tab2:
    show_hall_of_fame(st, teams_df, matchups_df, players_df)
with tab3:
    show_draft_board(st, teams_df, draft_roster_df, players_df, matchups_df)
with tab4:
    show_league_rules(st)