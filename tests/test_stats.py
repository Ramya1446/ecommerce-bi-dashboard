import numpy as np
import pytest
from scipy import stats

from ecombi import stats as st


def test_ztest_matches_chi_square():
    r = st.two_proportion_ztest(120, 2000, 160, 2000)
    # for a 2x2 table without continuity correction, z^2 == chi^2
    assert r.statistic ** 2 == pytest.approx(r.extra["chi2"], rel=1e-9)
    assert r.p_value == pytest.approx(r.extra["chi2_p"], rel=1e-9)
    assert r.significant
    assert r.ci_low < r.difference < r.ci_high


def test_ztest_no_difference():
    r = st.two_proportion_ztest(100, 1000, 100, 1000)
    assert r.p_value == pytest.approx(1.0)
    assert not r.significant
    assert "Fail to reject" in r.verdict()


def test_one_sided_halves_p():
    two = st.two_proportion_ztest(100, 1000, 125, 1000)
    one = st.two_proportion_ztest(100, 1000, 125, 1000, alternative="larger")
    assert one.p_value == pytest.approx(two.p_value / 2)


def test_welch_matches_scipy():
    rng = np.random.default_rng(0)
    a, b = rng.lognormal(4, 0.6, 300), rng.lognormal(4.1, 0.7, 350)
    r = st.welch_ttest(a, b)
    t, p = stats.ttest_ind(b, a, equal_var=False)
    assert r.statistic == pytest.approx(t)
    assert r.p_value == pytest.approx(p)
    assert r.ci_low < r.difference < r.ci_high


def test_bootstrap_ci_contains_true_difference():
    rng = np.random.default_rng(1)
    a, b = rng.normal(10, 2, 2000), rng.normal(11, 2, 2000)
    lo, hi, _ = st.bootstrap_diff_ci(a, b, n_boot=800)
    assert lo < 1.0 < hi


def test_sample_size_textbook_value():
    # 10% -> 12% (20% relative lift), alpha .05, power .8 ~ 3,840 per group
    n = st.required_sample_size(0.10, 0.20)
    assert 3700 < n < 4000


def test_power_increases_with_n():
    assert st.achieved_power(0.05, 0.06, 20000, 20000) > st.achieved_power(0.05, 0.06, 2000, 2000)
