import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from tab_hall_of_fame import show_hall_of_fame
from tab_league_rules import show_league_rules
from tab_league_insights import show_league_insights
from tab_draft_board import show_draft_board
from tab_owner_insights import show_owner_insights
from tab_team_insights import show_team_insights
from tab_season_insights import show_season_insights
import base64
from pathlib import Path

# Read and embed the logos
logo_path = Path(__file__).parent / "assets" / "logo.png"  # robust relative path
logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

# Page config and styling
st.set_page_config(page_title="Dayton Boyz Fantasy Football", layout="wide")

# Core CSS
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap" rel="stylesheet">

<style>
header.stAppHeader {
    background-color: transparent;
}
section.stMain .block-container {
    padding-top: 0rem;
    z-index: 1;
}
.block-container { padding-top: 2rem; }
.card { padding: 1rem; background-color: #0e1117; border-radius: 0rem; margin-bottom: 1rem; }
.card-label { font-size: 1rem; color: #bbb; text-align: left; }
.card-value { font-size: 2.5rem; font-weight: bold; margin: 0; color: white; text-align: left; }
.card-sub { margin-top: 0.1rem; font-size: 0.8rem; background-color: #444; color: #eee;
            padding: 0rem 0.5rem; border-radius: 0.4rem; display: inline-block; }

/* Scroll hint */
.scroll-hint {
    position: fixed;
    bottom: 6px;
    left: 12px;
    font-size: 12px;
    color: #aaa;
    z-index: 9999;
    pointer-events: none;
}
@media (min-width: 768px) {
    .scroll-hint { display: none; }
}
</style>
<div class="scroll-hint">↓ Scroll for more</div>
""", unsafe_allow_html=True)

# Banner with red underline + Bebas Neue font
st.markdown(f"""
<div style="
  display:flex;
  align-items:center;
  gap:15px;
  padding:12px 0;
  border-bottom: 3px solid #E63946;  /* red line under banner */
  margin-bottom: 10px; 
  margin-top: 5px; 
">
  <img
    src="data:image/png;base64,{logo_b64}"
    alt="Dayton Boyz"
    style="
      height:70px;
      display:block;
      margin:0;
      object-fit:contain;
    "
  />
  <div style="
    font-family:'Bebas Neue', sans-serif;
    font-size:2.2rem;
    font-weight:800;
    margin:0;
    letter-spacing:1.5px;
    color:#ffffff;
    line-height:1.05;   /* tighten spacing between lines */
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

for df in [teams_df, matchups_df, players_df, draft_roster_df, final_roster_df]:
    df.columns = df.columns.str.strip().str.lower()

# Dropdown with label text in a separate column
# --- Force *all* selectboxes to render label + control inline (mobile-safe) ---
st.markdown("""
<style>
/* Turn the selectbox container into a single-row flex layout */
div[data-testid="stSelectbox"]{
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 10px !important;
  flex-wrap: nowrap !important;             /* never stack on small screens */
}

/* Keep the label inline and tidy */
div[data-testid="stSelectbox"] > label{
  margin: 0 !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  color: #fff !important;
  white-space: nowrap !important;           /* prevents wrapping "Select Page:" */
  line-height: 1.2 !important;
}

/* Let the dropdown expand while avoiding overflow on tiny screens */
div[data-testid="stSelectbox"] > div{
  flex: 1 1 auto !important;                /* stretch the control */
  min-width: 0 !important;                  /* avoid flex overflow */
}
</style>
""", unsafe_allow_html=True)

# IMPORTANT: Don't collapse the label here—use the real label.
page = st.selectbox(
    "Select Page:",
    [
        "Season Summary",
        "Team Summary",
        "Owner History",
        "League History",
        "Hall of Fame/ Shame",
        "Draft Boards",
        "Rulebook"
    ],
    index=0,
    key="page_select"
)

if page == "Season Summary":
    show_season_insights(st, go, teams_df, matchups_df, players_df, draft_roster_df)

elif page == "Team Summary":
    show_team_insights(st, go, teams_df, matchups_df, players_df)

elif page == "Owner History":
    show_owner_insights(st, go, teams_df, matchups_df, players_df)

if page == "League History":
    show_league_insights(st, go, teams_df, matchups_df)

elif page == "Hall of Fame/ Shame":
    show_hall_of_fame(st, teams_df, matchups_df, players_df)

elif page == "Draft Boards":
    show_draft_board(st, teams_df, draft_roster_df, players_df, matchups_df)

elif page == "Rulebook":
    show_league_rules(st)