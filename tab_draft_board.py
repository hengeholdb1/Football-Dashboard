import streamlit as st
import pandas as pd

def show_draft_board(st, teams_df, draft_roster_df, players_df, matchups_df):
    # --- Normalize ---
    for df in (teams_df, draft_roster_df, players_df, matchups_df):
        df.columns = df.columns.str.strip().str.lower()

    # --- Force key cols to string early (avoids merge misses) ---
    for df in (draft_roster_df, players_df, matchups_df):
        for col in ("player_key", "team_key"):
            if col in df.columns:
                df[col] = df[col].astype(str)

    # Weeks should be numeric for joins/comparisons
    if "week" in players_df.columns:
        players_df["week"] = pd.to_numeric(players_df["week"], errors="coerce").astype("Int64")
    if "week" in matchups_df.columns:
        matchups_df["week"] = pd.to_numeric(matchups_df["week"], errors="coerce").astype("Int64")

    # --- Robust keys (year_code + player_key_clean) ---
    # e.g., "423.p.32692" --> year_code="423", player_key_clean="32692"
    def split_keys(s):
        s = str(s)
        parts = s.split(".")
        year_code = parts[0] if parts else ""
        tail = s.split("p.")[-1]  # after 'p.'
        return year_code, tail

    draft_roster_df[["year_code", "player_key_clean"]] = draft_roster_df["player_key"].apply(
        lambda k: pd.Series(split_keys(k))
    )
    players_df[["year_code", "player_key_clean"]] = players_df["player_key"].apply(
        lambda k: pd.Series(split_keys(k))
    )

    # --- Merge Draft Roster with Teams (owner/year) ---
    roster_full = draft_roster_df.merge(
        teams_df[["team_key", "owner_name", "year"]],
        on="team_key",
        how="left"
    )

    # Ensure is_keeper exists
    if "is_keeper" not in roster_full.columns:
        roster_full["is_keeper"] = False

    # --- Position Draft Rank (within season & position by pick_num) ---
    roster_full["position_draft_rank"] = (
        roster_full.sort_values("pick_num")
        .groupby(["year", "player_position"])
        .cumcount() + 1
    )

    # ---------- REGULAR-SEASON FINISH RANK (players_df + matchups_df) ----------
    # Join players_df to matchups_df on team_key + week to bring in is_playoffs,
    # then filter to regular season only (is_playoffs == 0) before summing.
    reg_players = players_df.merge(
        matchups_df[["team_key", "week", "is_playoffs"]],
        on=["team_key", "week"],
        how="left"
    )
    # Treat NaN as regular season if missing (defensive)
    reg_players["is_playoffs"] = reg_players["is_playoffs"].fillna(0)
    reg_players = reg_players[reg_players["is_playoffs"] == 0]

    # Rank table keyed by CLEAN key
    pts_clean = (
        reg_players.groupby(["year_code", "player_key_clean", "player_position"])["player_week_points"]
        .sum()
        .reset_index(name="total_points")
    )
    pts_clean["position_finish_rank"] = (
        pts_clean.groupby(["year_code", "player_position"])["total_points"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    # Fallback rank table keyed by FULL key
    pts_full = (
        reg_players.groupby(["year_code", "player_key", "player_position"])["player_week_points"]
        .sum()
        .reset_index(name="total_points")
    )
    pts_full["position_finish_rank"] = (
        pts_full.groupby(["year_code", "player_position"])["total_points"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    # Merge by clean key first
    roster_full = roster_full.merge(
        pts_clean[["year_code", "player_key_clean", "position_finish_rank"]],
        on=["year_code", "player_key_clean"],
        how="left"
    )
    # Fallback by full key
    roster_full = roster_full.merge(
        pts_full[["year_code", "player_key", "position_finish_rank"]]
               .rename(columns={"position_finish_rank": "position_finish_rank_full"}),
        on=["year_code", "player_key"],
        how="left"
    )
    roster_full["position_finish_rank"] = roster_full["position_finish_rank"].fillna(
        roster_full["position_finish_rank_full"]
    )
    roster_full.drop(columns=["position_finish_rank_full"], inplace=True)

    # --- Safe integers & arrow diff formatting ---
    roster_full["position_draft_rank"]  = roster_full["position_draft_rank"].astype(int)
    roster_full["position_finish_rank"] = roster_full["position_finish_rank"].fillna(-1).astype(int)

    def format_rank_line(draft, finish):
        if finish == -1:
            return f"Draft/Finish Rank: {draft} / N/A"
        diff = finish - draft
        if diff == 0:
            arrow = "(=)"
        elif diff > 0:
            arrow = f"(↓{diff})"   # finished worse than drafted
        else:
            arrow = f"(↑{abs(diff)})"  # finished better than drafted
        return f"Draft/Finish Rank: {draft} / {finish} {arrow}"

    roster_full["rank_line"] = roster_full.apply(
        lambda r: format_rank_line(r["position_draft_rank"], r["position_finish_rank"]),
        axis=1
    )

    # --- Build cell HTML ---
    roster_full["cell_value"] = (
        "<span style='font-size:12px; font-weight:600; white-space:nowrap; display:inline-block;'>"
        + roster_full["pick_num"].astype(str) + ". "
        + roster_full["player_name"] + " ("
        + roster_full["player_position"] + ")</span>"
        + "<br><span style='font-size:10px; color:#ffffff; white-space:nowrap;'>"
        + roster_full["rank_line"] + "</span>"
    )

    # --- Season selector with placeholder ---
    seasons = sorted(roster_full["year"].dropna().unique(), reverse=True)
    season_options = ["Select a season..."] + [str(s) for s in seasons]
    selected = st.selectbox("Select Season/Year", season_options, index=0)
    if selected == "Select a season...":
        st.info("Please select a season to view the draft board.")
        return

    selected_season = int(selected)
    season_df = roster_full[roster_full["year"] == selected_season].copy()

    # --- Draft order from Round 1 (columns left→right) ---
    round1 = season_df[season_df["round_num"] == 1].copy().sort_values("pick_num")
    owner_order = round1["owner_name"].tolist()

    # --- Pivot (after cell_value is final) ---
    draft_board = season_df.pivot_table(
        index="round_num",
        columns="owner_name",
        values="cell_value",
        aggfunc=lambda x: " / ".join(x)  # guard for unexpected dup picks
    ).sort_index()

    draft_board = draft_board.reindex(columns=owner_order)
    draft_board = draft_board.dropna(how="all")
    draft_board.index.name = "Round"

    # --- Coloring by position + keeper override ---
    def color_cell(val, is_keeper):
        if is_keeper:
            return "background-color:#808080; color:white;"   # Keeper
        if "(WR)" in val:
            return "background-color:#1f77b4; color:white;"   # Blue
        elif "(RB)" in val:
            return "background-color:#2ca02c; color:white;"   # Green
        elif "(QB)" in val:
            return "background-color:#d62728; color:white;"   # Red
        elif "(TE)" in val:
            return "background-color:#ff7f0e; color:white;"   # Orange
        elif "(K)" in val:
            return "background-color:#9467bd; color:white;"   # Purple
        elif "(DEF)" in val or "(DST)" in val:
            return "background-color:#8c564b; color:white;"   # Brown
        return "background-color:#222; color:white;"

    # --- Build HTML table (centered owner headers + mobile scroll) ---
    # --- Build HTML table (sticky top row + sticky left column) ---
    header_html = "".join(
        [f"<th style='background:#666; color:white; font-size:12px; font-weight:700; "
          f"padding:1px 4px; text-align:center; position:sticky; top:0; z-index:2;'>{col}</th>"
         for col in ["Round"] + owner_order]
    )

    body_html = ""
    for rnd, row in draft_board.iterrows():
        body_html += "<tr>"
        # Round number on left (sticky left col)
        body_html += (
            f"<td style='background:#666; color:white; font-size:11px; font-weight:700; "
            f"padding:1px 4px; text-align:center; white-space:nowrap; "
            f"position:sticky; left:0; z-index:1;'>{rnd}</td>"
        )
        # Picks per owner
        for owner in owner_order:
            val = row[owner]
            if pd.isna(val):
                body_html += "<td style='background:#222; color:white; font-size:10px; padding:1px 4px; text-align:center;'>–</td>"
            else:
                is_keeper = season_df[
                    (season_df["round_num"] == rnd) &
                    (season_df["owner_name"] == owner) &
                    (season_df["cell_value"] == val)
                ]["is_keeper"].any()
                style = color_cell(val, is_keeper)
                body_html += (
                    f"<td style='{style} font-size:10px; padding:1px 4px; "
                    f"text-align:center; white-space:normal;'>{val}</td>"
                )
        body_html += "</tr>"

    table_html = f"""
    <div style="overflow:auto; -webkit-overflow-scrolling: touch; width:100%;">
      <table style="border-collapse:collapse; width:100%; min-width:900px;">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{body_html}</tbody>
      </table>
    </div>
    """

    # --- Legend (simple chips) ---
    legend_html = """
    <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin:6px 0 12px;">
      <span style="background:#d62728; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px;">QB</span>
      <span style="background:#1f77b4; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px;">WR</span>
      <span style="background:#2ca02c; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px;">RB</span>
      <span style="background:#ff7f0e; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px;">TE</span>
      <span style="background:#9467bd; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px;">K</span>
      <span style="background:#8c564b; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px;">DEF</span>
      <span style="background:#808080; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px;">Keeper</span>
    </div>
    """

    st.markdown(legend_html, unsafe_allow_html=True)
    st.markdown(table_html, unsafe_allow_html=True)
