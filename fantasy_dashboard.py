import streamlit as st
import pandas as pd

st.set_page_config(page_title="Hall of Fame / Shame", layout="wide")
st.title("🏈 Dayton Boyz Fantasy Football")

# ✅ Published CSV export link (Teams tab)
sheet_csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQvhSWRerxihgW73Bicic4j1wY052Cda0oES-97_oafR6WWueA5P6QN3Vsrv0pknHGwrw4pJ8EBawu2/pub?output=csv"

try:
    # Load sheet
    df = pd.read_csv(sheet_csv_url)
    df.columns = df.columns.str.strip()

    # Ensure required columns exist
    required = {'year', 'owner_name', 'league_result', 'wins', 'losses'}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns: {required - set(df.columns)}")

    # Preprocessing
    df['total_games'] = df['wins'] + df['losses']
    df['win_pct'] = df['wins'] / df['total_games']

    # --- Tab Layout ---
    tab1, = st.tabs(["📜 Hall of Fame / Shame"])

    with tab1:
        st.subheader("📜 Hall of Fame / Shame")

        wl_df = df[df['league_result'].isin(['Winner', 'Runner-up', 'Loser'])][
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
        )

        # Reorder columns
        result_table = result_table.rename(columns={"year": "Year"})
        final_cols = ["Year", "🥇 Winner", "🥈 Runner-up", "🗑️ Loser"]
        clean_table = result_table[final_cols].copy()

        # --- Render as HTML ---
        def make_html_table(df):
            header_html = ''.join(f'<th style="padding: 8px; background-color:#f2f2f2;">{col}</th>' for col in df.columns)
            rows_html = ''
            for _, row in df.iterrows():
                rows_html += '<tr>' + ''.join(
                    f'<td style="text-align:center; padding: 8px;">{val if pd.notna(val) else ""}</td>'
                    for val in row
                ) + '</tr>'
            return f'''
            <table style="width:100%; border-collapse: collapse; border: 1px solid #ddd; font-size: 16px;">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            '''

        table_html = make_html_table(clean_table)
        st.markdown(table_html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"❌ Failed to load or process data.\n\n**Error:** {e}")
