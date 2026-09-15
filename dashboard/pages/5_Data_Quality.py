"""Data Quality - results of data_quality/validate.py, read directly from
quality_report.csv (the single source of truth - not recomputed here).

This page intentionally does NOT use the date/city/status sidebar filters:
the checks validate the full raw generated dataset (data_generator/output/*.csv),
not the already-partially-cleaned Postgres tables the other pages query - see
data_quality/README.md for why. Filtering this page would misrepresent what
was actually checked.
"""

import streamlit as st

from lib import charts, data

st.set_page_config(page_title="Data Quality", layout="wide", page_icon="📦")
st.title("Data Quality")
st.caption(
    "Results of `python data_quality/validate.py` against the raw generated "
    "CSVs. Always reflects the whole dataset, independent of the sidebar "
    "filters used on the other pages."
)

try:
    report = data.load_quality_report()
except Exception as exc:
    st.error(f"Could not read data_quality/quality_report.csv: {exc}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Rules Checked", f"{len(report)}")
c2.metric("Total Records Checked", f"{int(report['records_checked'].sum()):,}")
c3.metric("Total Records Failed", f"{int(report['records_failed'].sum()):,}")
c4.metric("Critical-Severity Rules", f"{int((report['severity'] == 'CRITICAL').sum())}")

st.altair_chart(charts.data_quality_chart(report), width="stretch")

st.subheader("Natural data vs. intentionally corrupted test data")
st.markdown(
    "- **`structural_check`**: correct expected result is zero - validates "
    "the generator's core mechanics (referential integrity, required fields, "
    "non-negative values).\n"
    "- **`intentionally_corrupted`**: targets one of `data_generator`'s "
    "deliberately injected data-quality issues - a nonzero result here is "
    "the expected, correct outcome, proving the check can find a known "
    "problem.\n\n"
    "Full rule-by-rule detail, including the DQ-06 investigation, is in "
    "`data_quality/README.md`."
)

source_summary = (
    report.groupby("expected_source")
    .agg(rules=("rule_id", "count"), records_failed=("records_failed", "sum"))
    .reset_index()
)
st.dataframe(source_summary, width="stretch", hide_index=True)

st.subheader("Full report")
st.dataframe(
    report[["rule_id", "rule_name", "records_checked", "records_failed", "failure_rate_pct", "severity", "expected_source"]],
    width="stretch",
    hide_index=True,
)

with st.expander("Investigation notes (full text)"):
    for _, row in report.iterrows():
        st.markdown(f"**{row['rule_id']} - {row['rule_name']}**")
        st.markdown(row["notes"])
