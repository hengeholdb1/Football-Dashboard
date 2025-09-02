# tab_final_rosters.py

import streamlit as st
import pandas as pd

def show_final_rosters(st, teams_df, final_roster_df):
    st.title("🏆 Final Rosters Viewer")

    if final_roster_df is None or final_roster_df.empty:
        st.error("⚠️ No final roster data provided.")
        return

    # Normalize
    for df in [teams_df, final_roster_df]:
        df.columns = df.columns.str.strip().str.lower()

    # Join with teams_df to add year/owner/team info
    if not {"team_key", "year", "owner_name", "team_name"}.issubset(teams_df.columns):
        st.error("⚠️ teams_df missing required columns (team_key, year, owner_name, team_name).")
        return

    roster_full = final_roster_df.merge(
        teams_df[["team_key", "owner_name", "team_name", "year"]],
        on="team_key",
        how="left"
    )

    # Build display table
    display_df = roster_full[[
        "year", "owner_name", "team_name", "player_key"
    ]].rename(columns={
        "year": "Season",
        "owner_name": "Owner",
        "team_name": "Team",
        "player_key": "Player Key"
    })

    # --- Filter by season ---
    seasons = sorted(display_df["Season"].dropna().unique(), reverse=True)
    selected_season = st.selectbox("Select Season/Year", seasons)

    season_df = display_df[display_df["Season"] == selected_season]

    if season_df.empty:
        st.warning("No roster data found for this season.")
        return

    # Sort by Owner
    season_df = season_df.sort_values(by=["Owner", "Player Key"])

    st.markdown(f"### Final Rosters – {selected_season}")
    st.dataframe(season_df, use_container_width=True)

    #st.markdown(f"Test")