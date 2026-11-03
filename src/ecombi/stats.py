"""Hypothesis testing utilities for comparing two customer groups.

Each test returns a TestResult with the statistic, p-value, a confidence interval for the
difference, an effect size and a plain-English verdict, so the dashboard can show both the
numbers and what they mean.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class TestResult:
    test: str
    metric: str
    group_a: str
    group_b: str
    n_a: int
    n_b: int
    value_a: float
    value_b: float
    difference: float           # value_b - value_a
    relative_lift: float        # difference / value_a
    statistic: float
    p_value: float
    ci_low: float
    ci_high: float
    effect_size: float
    effect_label: str
    alpha: float
    extra: dict = field(default_factory=dict)

    @property
    def significant(self) -> bool:
        return self.p_value < self.alpha

    def p_text(self) -> str:
        return f"{self.p_value:.4f}" if self.p_value >= 1e-4 else f"{self.p_value:.1e}"

    def verdict(self, fmt: str = "{:.2%}") -> str:
        a, b = fmt.format(self.value_a), fmt.format(self.value_b)
        direction = "higher" if self.difference > 0 else "lower"
        if self.significant:
            return (f"Reject H0 (p = {self.p_text()} < alpha = {self.alpha}). "
                    f"{self.group_b} has a statistically significant {direction} {self.metric} "
                    f"than {self.group_a} ({b} vs {a}, {self.relative_lift:+.1%} relative). "
                    f"Standardised effect size is {self.effect_label} ({self.effect_size:+.2f}); "
                    f"{'large samples make even modest differences detectable - judge the business value by the absolute difference.' if self.effect_label in ('negligible', 'small') else 'the difference is material as well as significant.'}")
        return (f"Fail to reject H0 (p = {self.p_text()} >= alpha = {self.alpha}). "
                f"The observed difference in {self.metric} ({b} vs {a}) is consistent with random "
                f"variation; we do not have evidence the groups differ.")


def _label_h(h: float) -> str:
    h = abs(h)
    return "negligible" if h < 0.2 else "small" if h < 0.5 else "medium" if h < 0.8 else "large"


def two_proportion_ztest(success_a: int, n_a: int, success_b: int, n_b: int, *,
                         group_a: str = "A", group_b: str = "B", metric: str = "conversion rate",
                         alpha: float = 0.05, alternative: str = "two-sided") -> TestResult:
    """Pooled two-proportion z-test with an unpooled Wald CI for p_b - p_a and Cohen's h."""
    if min(n_a, n_b) == 0:
        raise ValueError("Both groups need at least one observation.")
    p_a, p_b = success_a / n_a, success_b / n_b
    pooled = (success_a + success_b) / (n_a + n_b)
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / se_pooled if se_pooled > 0 else 0.0
    if alternative == "two-sided":
        p = 2 * stats.norm.sf(abs(z))
    elif alternative == "larger":   # H1: p_b > p_a
        p = stats.norm.sf(z)
    else:                           # H1: p_b < p_a
        p = stats.norm.cdf(z)
    se = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    zc = stats.norm.ppf(1 - alpha / 2)
    h = 2 * np.arcsin(np.sqrt(p_b)) - 2 * np.arcsin(np.sqrt(p_a))
    chi2, chi_p, _, _ = stats.chi2_contingency([[success_a, n_a - success_a], [success_b, n_b - success_b]],
                                               correction=False)
    return TestResult(
        test="Two-proportion z-test", metric=metric, group_a=group_a, group_b=group_b,
        n_a=n_a, n_b=n_b, value_a=p_a, value_b=p_b, difference=p_b - p_a,
        relative_lift=(p_b - p_a) / p_a if p_a else np.nan, statistic=float(z), p_value=float(p),
        ci_low=float(p_b - p_a - zc * se), ci_high=float(p_b - p_a + zc * se),
        effect_size=float(h), effect_label=_label_h(h), alpha=alpha,
        extra={"chi2": float(chi2), "chi2_p": float(chi_p), "alternative": alternative},
    )


def welch_ttest(a: np.ndarray, b: np.ndarray, *, group_a: str = "A", group_b: str = "B",
                metric: str = "average order value", alpha: float = 0.05,
                alternative: str = "two-sided") -> TestResult:
    """Welch's t-test (unequal variances) + Mann-Whitney U as a non-parametric cross-check."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2:
        raise ValueError("Each group needs at least two observations.")
    alt = {"two-sided": "two-sided", "larger": "greater", "smaller": "less"}[alternative]
    t, p = stats.ttest_ind(b, a, equal_var=False, alternative=alt)
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    se = np.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    tc = stats.t.ppf(1 - alpha / 2, df)
    diff = b.mean() - a.mean()
    pooled_sd = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    d = diff / pooled_sd if pooled_sd > 0 else 0.0
    u, mw_p = stats.mannwhitneyu(b, a, alternative=alt)
    return TestResult(
        test="Welch's t-test", metric=metric, group_a=group_a, group_b=group_b,
        n_a=len(a), n_b=len(b), value_a=float(a.mean()), value_b=float(b.mean()), difference=float(diff),
        relative_lift=float(diff / a.mean()) if a.mean() else np.nan, statistic=float(t), p_value=float(p),
        ci_low=float(diff - tc * se), ci_high=float(diff + tc * se),
        effect_size=float(d), effect_label=_label_h(d), alpha=alpha,
        extra={"df": float(df), "mann_whitney_u": float(u), "mann_whitney_p": float(mw_p),
               "median_a": float(np.median(a)), "median_b": float(np.median(b)), "alternative": alternative},
    )


def bootstrap_diff_ci(a: np.ndarray, b: np.ndarray, stat=np.mean, n_boot: int = 2000,
                      alpha: float = 0.05, seed: int = 0) -> tuple[float, float, np.ndarray]:
    """Percentile bootstrap CI for stat(b) - stat(a). Returns (low, high, samples)."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    ia = rng.integers(0, len(a), (n_boot, len(a)))
    ib = rng.integers(0, len(b), (n_boot, len(b)))
    diffs = stat(b[ib], axis=1) - stat(a[ia], axis=1)
    lo, hi = np.quantile(diffs, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi), diffs


def required_sample_size(p_base: float, mde_rel: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Per-group sample size to detect a relative lift `mde_rel` on baseline rate `p_base`."""
    p2 = p_base * (1 + mde_rel)
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    pbar = (p_base + p2) / 2
    num = (za * np.sqrt(2 * pbar * (1 - pbar)) + zb * np.sqrt(p_base * (1 - p_base) + p2 * (1 - p2))) ** 2
    return int(np.ceil(num / (p2 - p_base) ** 2))


def achieved_power(p_a: float, p_b: float, n_a: int, n_b: int, alpha: float = 0.05) -> float:
    se = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    if se == 0:
        return float("nan")
    z = abs(p_b - p_a) / se
    zc = stats.norm.ppf(1 - alpha / 2)
    return float(stats.norm.sf(zc - z) + stats.norm.cdf(-zc - z))
