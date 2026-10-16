import pandas as pd

from wikicard.pages import analytics


def test_histogram_bins_cover_0_to_1500():
    counts = analytics.histogram_counts(pd.Series([0, 99, 100, 1499, 1500]))
    assert len(counts) == len(analytics.bin_labels()) == 15
    assert counts[0] == 2 and counts[1] == 1 and counts[14] == 2


def test_quiz_chart_dots_vs_daily_line():
    base = pd.Timestamp("2026-01-01")
    few = pd.DataFrame({"date": [base, base + pd.Timedelta(days=1)], "score": [50.0, 80.0],
                        "username": ["a", "b"], "correct_answers": [1, 2], "questions_attempted": [2, 3]})
    assert analytics.quiz_figure(few).data[0].mode == "markers"
    many = pd.concat([few, few.assign(date=base + pd.Timedelta(days=3))], ignore_index=True)
    fig = analytics.quiz_figure(many)
    assert fig.data[0].mode == "lines+markers" and tuple(fig.layout.yaxis.range) == (0, 100)


def test_top_students_limited_to_ten():
    comp = pd.DataFrame({"student": [f"s{i}" for i in range(15)], "score": list(range(15))})
    assert len(analytics.top_students_figure(comp).data[0].x) == 10
