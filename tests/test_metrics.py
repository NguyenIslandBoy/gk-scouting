import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_gk_events():
    """Minimal GK events dataframe mirroring StatsBomb structure."""
    return pd.DataFrame({
        'match_id': [1, 1, 1, 1, 2, 2],
        'player_id': [10, 10, 10, 10, 20, 20],
        'player': ['GK Alpha', 'GK Alpha', 'GK Alpha', 'GK Alpha', 'GK Beta', 'GK Beta'],
        'team': ['Team A', 'Team A', 'Team A', 'Team A', 'Team B', 'Team B'],
        'goalkeeper_type': ['Shot Saved', 'Shot Saved', 'Goal Conceded', 'Keeper Sweeper', 'Shot Saved', 'Goal Conceded'],
        'goalkeeper_outcome': ['Success', 'Touched Out', 'No Touch', 'Clear', 'Success', 'No Touch'],
    })

@pytest.fixture
def sample_shot_events():
    """Minimal shot events dataframe with PSxG values."""
    return pd.DataFrame({
        'match_id': [1, 1, 1, 2, 2],
        'team': ['Team B', 'Team B', 'Team B', 'Team A', 'Team A'],
        'shot_outcome': ['Saved', 'Saved', 'Goal', 'Saved', 'Goal'],
        'shot_statsbomb_xg': [0.10, 0.25, 0.45, 0.30, 0.60],
    })

@pytest.fixture
def sample_minutes():
    """Minutes played per GK per match."""
    return pd.DataFrame({
        'match_id': [1, 2],
        'player_id': [10, 20],
        'player_name': ['GK Alpha', 'GK Beta'],
        'team': ['Team A', 'Team B'],
        'minutes_played': [90, 90],
    })

@pytest.fixture
def sample_player_agg():
    """Aggregated player-level dataframe for percentile tests."""
    return pd.DataFrame({
        'player_id': [10, 20, 30, 40],
        'player_name': ['GK Alpha', 'GK Beta', 'GK Gamma', 'GK Delta'],
        'total_minutes': [900, 900, 900, 900],
        'total_saves': [30, 20, 25, 15],
        'total_goals_conceded': [10, 15, 12, 20],
        'total_psxg': [12.0, 16.0, 13.5, 18.0],
        'sweeper_p90': [1.5, 0.5, 1.0, 0.2],
        'claiming_p90': [2.0, 1.0, 1.5, 0.5],
        'avg_pass_completion': [75.0, 60.0, 68.0, 55.0],
    })

# ── Save percentage tests ─────────────────────────────────────────────────

class TestSavePercentage:

    def test_basic_calculation(self, sample_gk_events):
        saves = sample_gk_events[sample_gk_events['goalkeeper_type'] == 'Shot Saved']
        goals = sample_gk_events[sample_gk_events['goalkeeper_type'] == 'Goal Conceded']

        n_saves = len(saves[saves['player_id'] == 10])
        n_goals = len(goals[goals['player_id'] == 10])
        save_pct = n_saves / (n_saves + n_goals) * 100

        assert save_pct == pytest.approx(66.67, abs=0.01)

    def test_perfect_save_pct(self):
        saves, goals = 10, 0
        shots_faced = saves + goals
        save_pct = saves / shots_faced * 100 if shots_faced > 0 else np.nan
        assert save_pct == 100.0

    def test_zero_shots_faced_returns_nan(self):
        saves, goals = 0, 0
        shots_faced = saves + goals
        save_pct = saves / shots_faced * 100 if shots_faced > 0 else np.nan
        assert np.isnan(save_pct)

    def test_save_pct_bounds(self, sample_player_agg):
        df = sample_player_agg.copy()
        df['shots_faced'] = df['total_saves'] + df['total_goals_conceded']
        df['save_pct'] = df['total_saves'] / df['shots_faced'] * 100
        assert (df['save_pct'] >= 0).all()
        assert (df['save_pct'] <= 100).all()

# ── PSxG-GA tests ─────────────────────────────────────────────────────────

class TestPSxGGA:

    def test_positive_psxg_ga_means_outperforming(self):
        """GK who concedes fewer goals than PSxG should have positive PSxG-GA."""
        psxg = 2.5
        goals_conceded = 1
        psxg_ga = psxg - goals_conceded
        assert psxg_ga > 0

    def test_negative_psxg_ga_means_underperforming(self):
        psxg = 1.0
        goals_conceded = 3
        psxg_ga = psxg - goals_conceded
        assert psxg_ga < 0

    def test_psxg_assigned_to_correct_team(self, sample_shot_events, sample_minutes):
        """Shots by Team B should be assigned to Team A's GK."""
        gk_teams = sample_minutes.copy()
        shots = sample_shot_events[
            sample_shot_events['shot_outcome'].isin(['Goal', 'Saved'])
        ].copy()

        shots.columns = ['match_id', 'shooting_team', 'shot_outcome', 'xg']
        merged = gk_teams.merge(shots[['match_id', 'shooting_team', 'xg']], on='match_id')
        gk_faced = merged[merged['team'] != merged['shooting_team']]

        alpha_psxg = gk_faced[gk_faced['player_name'] == 'GK Alpha']['xg'].sum()
        assert alpha_psxg == pytest.approx(0.80, abs=0.01)

    def test_psxg_ga_computed_correctly(self, sample_player_agg):
        df = sample_player_agg.copy()
        df['psxg_ga'] = df['total_psxg'] - df['total_goals_conceded']
        alpha = df[df['player_name'] == 'GK Alpha']['psxg_ga'].iloc[0]
        assert alpha == pytest.approx(2.0, abs=0.01)  # 12.0 - 10

# ── Per-90 normalisation tests ────────────────────────────────────────────

class TestPer90Normalisation:

    def test_per90_scales_correctly(self):
        raw_count = 9
        minutes = 810
        per90 = raw_count / minutes * 90
        assert per90 == pytest.approx(1.0, abs=0.001)

    def test_per90_with_different_minutes(self):
        """Two GKs with same raw count but different minutes should differ per 90."""
        count = 5
        per90_a = count / 90 * 90   # exactly 90 mins
        per90_b = count / 45 * 90   # only 45 mins = double the rate
        assert per90_b == pytest.approx(per90_a * 2, abs=0.001)

    def test_minimum_minutes_filter(self, sample_player_agg):
        """Players below 450 minutes should be excluded."""
        df = sample_player_agg.copy()
        df.loc[0, 'total_minutes'] = 400  # GK Alpha below threshold
        filtered = df[df['total_minutes'] >= 450]
        assert 'GK Alpha' not in filtered['player_name'].values
        assert len(filtered) == 3

# ── Percentile rank tests ─────────────────────────────────────────────────

class TestPercentileRanks:

    def test_best_player_near_100th_percentile(self, sample_player_agg):
        df = sample_player_agg.copy()
        df['save_pct'] = df['total_saves'] / (df['total_saves'] + df['total_goals_conceded']) * 100
        df['save_pct_pct'] = df['save_pct'].rank(pct=True) * 100
        best = df.loc[df['save_pct'].idxmax(), 'save_pct_pct']
        assert best == pytest.approx(100.0, abs=0.01)

    def test_worst_player_near_25th_percentile_with_4_players(self, sample_player_agg):
        df = sample_player_agg.copy()
        df['sweeper_pct'] = df['sweeper_p90'].rank(pct=True) * 100
        worst = df.loc[df['sweeper_p90'].idxmin(), 'sweeper_pct']
        assert worst == pytest.approx(25.0, abs=0.01)

    def test_percentiles_between_0_and_100(self, sample_player_agg):
        df = sample_player_agg.copy()
        df['pct'] = df['avg_pass_completion'].rank(pct=True) * 100
        assert (df['pct'] >= 0).all()
        assert (df['pct'] <= 100).all()

# ── Data integrity tests ──────────────────────────────────────────────────

class TestDataIntegrity:

    def test_no_duplicate_player_ids(self, sample_player_agg):
        assert sample_player_agg['player_id'].nunique() == len(sample_player_agg)

    def test_minutes_played_positive(self, sample_minutes):
        assert (sample_minutes['minutes_played'] > 0).all()

    def test_psxg_non_negative(self, sample_shot_events):
        assert (sample_shot_events['shot_statsbomb_xg'] >= 0).all()

    def test_required_columns_present(self, sample_player_agg):
        required = ['player_id', 'player_name', 'total_minutes', 'total_saves',
                    'total_goals_conceded', 'total_psxg', 'sweeper_p90']
        for col in required:
            assert col in sample_player_agg.columns, f"Missing column: {col}"