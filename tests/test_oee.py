import pytest

from src import checks, oee


@pytest.fixture(scope="module")
def facts(tables):
    return oee.shift_facts(tables)


def test_every_shift_is_480_minutes(facts):
    assert (facts.calendar_min == 480).all()


def test_oee_equals_a_times_p_times_q(facts):
    r = oee.aggregate(facts, ["machine_id"])
    assert ((r.availability * r.performance * r.quality - r.oee).abs() < 1e-9).all()


def test_aggregate_sums_minutes_not_averages_percentages(facts):
    # a short "shift" with terrible OEE must not drag the total down like an average would
    f = facts.head(2).copy()
    f.loc[f.index[1], ["ppt_min", "run_min", "ideal_min", "good_ideal_min"]] = [10, 10, 1, 1]
    correct = oee.aggregate(f).oee.iloc[0]
    naive = oee.ratios(f).oee.mean()
    assert correct == pytest.approx(f.good_ideal_min.sum() / f.ppt_min.sum())
    assert abs(correct - naive) > 0.1


def test_waterfall_adds_up(facts):
    wf = oee.loss_waterfall(facts)
    assert wf.minutes.iloc[0] + wf.minutes.iloc[1:-1].sum() == pytest.approx(wf.minutes.iloc[-1])


def test_planted_stories_are_visible(tables, facts):
    w = oee.aggregate(facts[facts.machine_id == "CNC-02"], ["week"]).set_index("week").oee
    assert w["2026-W31"] < w["2026-W25"] - 0.15          # spindle failure week
    s = oee.aggregate(facts[facts.machine_id == "PRESS-01"], ["shift"]).set_index("shift")
    assert s.loc["Night", "Setup and adjustments"] > 1.5 * s.loc["Early", "Setup and adjustments"]
    inc = oee.failure_incidents(tables)
    spindle = inc[inc.reason_code == "BRK_SPINDLE"]
    assert len(spindle) == 1                              # one failure, though split by breaks/shifts


def test_checks_fix_duplicates_and_wrong_product(raw_tables):
    _, results = checks.run_checks(raw_tables)
    status = {r.check: r.status for r in results}
    assert status["Duplicate count records"] == "FIXED"
    assert status["Performance <= 105 %"] == "FIXED"
    assert status["Event timeline complete"] == "OK"
