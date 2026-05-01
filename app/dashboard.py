import warnings
warnings.filterwarnings('ignore')

import streamlit as st
import duckdb
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GK Scout",
    page_icon="🧤",
    layout="wide"
)

# ── Data loading ──────────────────────────────────────────────────────────
@st.cache_data(ttl=0)
def load_data():
    con = duckdb.connect('../data/gk_scout.duckdb', read_only=True)
    players = con.execute("SELECT * FROM gk_player_level").df()
    matches = con.execute("SELECT * FROM gk_match_level").df()
    con.close()
    return players, matches

players, matches = load_data()

# ── Percentile ranks ──────────────────────────────────────────────────────
metric_cols = ['save_pct', 'psxg_ga', 'sweeper_p90', 'claiming_p90', 'avg_pass_completion']
for col in metric_cols:
    players[f'{col}_pct'] = players[col].rank(pct=True) * 100

# ── Sidebar ───────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🧤")
st.sidebar.title("GK Scout")
st.sidebar.markdown("*Goalkeeper Recruitment Tool*")
st.sidebar.divider()

st.sidebar.subheader("🔍 Filter Candidates")

min_minutes = st.sidebar.slider(
    "Minimum minutes played",
    min_value=450, max_value=1400,
    value=450, step=90
)

min_save_pct = st.sidebar.slider(
    "Minimum save %",
    min_value=0, max_value=100,
    value=0, step=5
)

min_psxg_ga = st.sidebar.slider(
    "Minimum PSxG-GA",
    min_value=-10.0, max_value=5.0,
    value=-10.0, step=0.5
)

competition_options = ['All'] + sorted(players['primary_competition'].dropna().unique().tolist())
selected_comp = st.sidebar.selectbox("Competition", options=competition_options)

st.sidebar.divider()
st.sidebar.caption("PSxG-GA: positive = saving more than expected")
st.sidebar.caption("Sweeper p90: actions outside box per 90 mins")
st.sidebar.caption("Data: StatsBomb Open Data")

# ── Filter ────────────────────────────────────────────────────────────────
filtered = players[
    (players['total_minutes'] >= min_minutes) &
    (players['save_pct'] >= min_save_pct) &
    (players['psxg_ga'] >= min_psxg_ga)
].copy()

if selected_comp != 'All':
    filtered = filtered[filtered['primary_competition'] == selected_comp]

# ── Main view toggle ──────────────────────────────────────────────────────
view = st.radio("View", ["📋 Shortlist", "👤 Player Profile"], horizontal=True)
st.divider()

# ═════════════════════════════════════════════════════════════════════════
# VIEW 1: SHORTLIST
# ═════════════════════════════════════════════════════════════════════════
if view == "📋 Shortlist":

    st.subheader(f"Goalkeeper Shortlist — {len(filtered)} candidates")

    if filtered.empty:
        st.warning("No players match the current filters.")
    else:
        # Sort selector
        sort_by = st.selectbox(
            "Sort by",
            options=['psxg_ga', 'save_pct', 'sweeper_p90', 'claiming_p90', 'total_minutes'],
            format_func=lambda x: {
                'psxg_ga': 'PSxG-GA',
                'save_pct': 'Save %',
                'sweeper_p90': 'Sweeper Actions p90',
                'claiming_p90': 'Claiming Actions p90',
                'total_minutes': 'Minutes Played'
            }[x]
        )

        filtered_sorted = filtered.sort_values(sort_by, ascending=False).reset_index(drop=True)

        # Display table
        display_cols = {
            'player_name': 'Player',
            'primary_competition': 'Competition',
            'matches_played': 'Matches',
            'total_minutes': 'Minutes',
            'save_pct': 'Save %',
            'psxg_ga': 'PSxG-GA',
            'sweeper_p90': 'Sweeper p90',
            'claiming_p90': 'Claiming p90',
            'avg_pass_completion': 'Pass Cmp %',
            'avg_long_ball_pct': 'Long Ball %'
        }

        table = filtered_sorted[list(display_cols.keys())].rename(columns=display_cols)
        table['Save %'] = table['Save %'].round(1)
        table['PSxG-GA'] = table['PSxG-GA'].round(2)
        table['Sweeper p90'] = table['Sweeper p90'].round(2)
        table['Claiming p90'] = table['Claiming p90'].round(2)
        table['Pass Cmp %'] = table['Pass Cmp %'].round(1)
        table['Long Ball %'] = table['Long Ball %'].round(1)

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                'PSxG-GA': st.column_config.NumberColumn(format="%.2f"),
                'Save %': st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
            }
        )

        # Scatter plot
        st.subheader("PSxG-GA vs Save %")
        fig_scatter = px.scatter(
            filtered_sorted,
            x='save_pct',
            y='psxg_ga',
            size='total_minutes',
            hover_name='player_name',
            hover_data={
                'total_minutes': True,
                'sweeper_p90': ':.2f',
                'save_pct': ':.1f',
                'psxg_ga': ':.2f'
            },
            labels={
                'save_pct': 'Save %',
                'psxg_ga': 'PSxG-GA',
                'total_minutes': 'Minutes Played'
            },
            color='psxg_ga',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=0,       # anchor green/red split exactly at zero
            range_color=[-5, 5],               # symmetric scale so colour is meaningful
        )
        fig_scatter.add_hline(y=0, line_dash='dash', line_color='grey', annotation_text='Expected level')
        fig_scatter.add_vline(x=75, line_dash='dot', line_color='lightgrey', annotation_text='75% threshold')
        fig_scatter.update_layout(height=500, showlegend=False)
        fig_scatter.add_hline(y=0, line_dash='dash', line_color='grey', annotation_text='Expected level')
        fig_scatter.update_layout(height=500, showlegend=False)
        st.plotly_chart(fig_scatter, use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════
# VIEW 2: PLAYER PROFILE
# ═════════════════════════════════════════════════════════════════════════
else:
    selected_name = st.selectbox(
        "Select goalkeeper",
        options=sorted(players['player_name'].tolist())
    )

    player = players[players['player_name'] == selected_name].iloc[0]
    player_matches = matches[matches['player_name'] == selected_name].copy()

    # ── Header ────────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Minutes", f"{int(player['total_minutes'])}")
    col2.metric("Save %", f"{player['save_pct']:.1f}%")
    col3.metric("PSxG-GA", f"{player['psxg_ga']:+.2f}")
    col4.metric("Sweeper p90", f"{player['sweeper_p90']:.2f}")
    col5.metric("Claiming p90", f"{player['claiming_p90']:.2f}")

    st.divider()

    col_left, col_right = st.columns(2)

    # ── Radar chart ───────────────────────────────────────────────────────
    with col_left:
        st.subheader("Percentile Radar")

        radar_metrics = {
            'Save %': 'save_pct_pct',
            'PSxG-GA': 'psxg_ga_pct',
            'Sweeper p90': 'sweeper_p90_pct',
            'Claiming p90': 'claiming_p90_pct',
            'Pass Completion': 'avg_pass_completion_pct'
        }

        labels = list(radar_metrics.keys())
        values = [player[v] for v in radar_metrics.values()]
        values_closed = values + [values[0]]
        labels_closed = labels + [labels[0]]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill='toself',
            fillcolor='rgba(99, 110, 250, 0.3)',
            line=dict(color='rgb(99, 110, 250)', width=2),
            name=selected_name
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False,
            height=400
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # ── PSxG-GA match by match ────────────────────────────────────────────
    with col_right:
        st.subheader("PSxG-GA per Match")

        player_matches = player_matches.sort_values('match_id')
        player_matches['match_label'] = [f"M{i+1}" for i in range(len(player_matches))]
        player_matches['color'] = player_matches['psxg_ga'].apply(
            lambda x: 'green' if x >= 0 else 'red'
        )

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=player_matches['match_label'],
            y=player_matches['psxg_ga'],
            marker_color=player_matches['color'],
            hovertemplate='%{x}<br>PSxG-GA: %{y:.2f}<extra></extra>'
        ))
        fig_bar.add_hline(y=0, line_dash='dash', line_color='grey')
        fig_bar.update_layout(
            height=400,
            yaxis_title='PSxG-GA',
            xaxis_title='Match'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ── Distribution breakdown ────────────────────────────────────────────
    st.subheader("Distribution Profile")

    comp_label = player.get('primary_competition', 'Unknown')
    st.markdown(f"**Competition:** {comp_label} &nbsp;|&nbsp; **Matches:** {int(player['matches_played'])}")
    st.divider()
    
    col_d1, col_d2, col_d3 = st.columns(3)
    col_d1.metric("Avg Pass Completion", f"{player['avg_pass_completion']:.1f}%")
    col_d2.metric("Avg Long Ball %", f"{player['avg_long_ball_pct']:.1f}%")
    col_d3.metric("Total Passes", f"{int(player['total_passes'])}")

    # Pass completion vs peers
    fig_dist = px.histogram(
        players,
        x='avg_pass_completion',
        nbins=20,
        labels={'avg_pass_completion': 'Avg Pass Completion %'},
        title='Pass Completion % — All GKs'
    )
    fig_dist.add_vline(
        x=player['avg_pass_completion'],
        line_dash='dash',
        line_color='red',
        annotation_text=selected_name,
        annotation_position='top right'
    )
    fig_dist.update_layout(height=300)
    st.plotly_chart(fig_dist, use_container_width=True)
    
    # ── Scouting Note ─────────────────────────────────────────────────────────
    st.subheader("📝 Scouting Note")

    note_key = f"note_{selected_name.replace(' ', '_')}"

    note = st.text_area(
        label="Add your observations for this player",
        value=st.session_state.get(note_key, ""),
        height=150,
        placeholder="e.g. Strong sweeper, comfortable in possession. Struggles with low shots to his right. Worth monitoring in next 3 matches..."
    )

    col_save, col_clear, _ = st.columns([1, 1, 6])

    with col_save:
        if st.button("Save note", type="primary"):
            st.session_state[note_key] = note
            st.success("Note saved.")

    with col_clear:
        if st.button("Clear note"):
            st.session_state[note_key] = ""
            st.rerun()