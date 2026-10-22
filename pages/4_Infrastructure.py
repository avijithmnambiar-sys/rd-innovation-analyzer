import pandas as pd
import plotly.express as px
import streamlit as st

from infrastructure_manager import (COLUMNS, CURRENT_YEAR, MAXIMUM, NUMERIC, TIERS,
                                    InfrastructureManager, build_report, tier_for)
from ui_style import CHART_COLORS, apply_style, style_chart

st.set_page_config(page_title="Innovation Infrastructure", layout="wide", initial_sidebar_state="expanded")
apply_style()
manager = InfrastructureManager()


def record_form(key, row=None):
    row = {} if row is None else row
    with st.form(key):
        record = {}
        identity_columns = st.columns(2)
        for index, (column, label) in enumerate([("record_id", "Record ID"), ("country", "Country")]):
            value = row.get(column, "")
            value = "" if pd.isna(value) else str(value)
            record[column] = identity_columns[index].text_input(
                label, value=value, disabled=bool(row) and column == "record_id")
        for index, column in enumerate(NUMERIC):
            if index % 2 == 0:
                number_columns = st.columns(2)
            input_column = number_columns[index % 2]
            default = CURRENT_YEAR if column == "year" else 0
            value = row.get(column, default)
            # A malformed source value must be repaired explicitly, not defaulted to zero.
            if pd.isna(value):
                value = None
            if column == "year":
                record[column] = input_column.number_input(
                    "Year", 1900, CURRENT_YEAR, value=int(value) if value is not None else None, step=1)
            else:
                record[column] = input_column.number_input(
                    column.replace("_", " ").title(), min_value=0.0, max_value=MAXIMUM[column],
                    value=float(value) if value is not None else None)
        suggested = tier_for(record.get("internet_penetration_pct"))
        tier = row.get("infrastructure_tier", suggested)
        tier = suggested if pd.isna(tier) else tier
        index = TIERS.index(tier) if tier in TIERS else 0
        record["infrastructure_tier"] = st.selectbox("Infrastructure tier", TIERS, index=index)
        st.caption("Tiers follow internet penetration: High from 85%, Medium from 60%, Low below 60%.")
        submitted = st.form_submit_button("Save changes" if row else "Add record", type="primary")
    return submitted, record


def show_result(result):
    success, messages = result[0], result[1]
    if success:
        st.session_state["infra_flash"] = messages[0]
        st.rerun()
    for message in messages:
        st.error(message)


st.caption(":orange[ENABLER LAYER · SDG 9]")
st.title("Innovation Infrastructure")
st.write("Connectivity, high-technology exports and STEM graduate supply: the enabling layer "
         "that decides whether research investment can turn into innovation.")
st.info("The supplied SYN_INF records are synthetic demonstration data, not official country statistics.")
st.caption("Each row is one country-year. SDG target 9.c concerns access to information and "
           "communications technology, which internet penetration stands in for here.")
if "infra_flash" in st.session_state:
    st.success(st.session_state.pop("infra_flash"))
try:
    df = manager.load()
except (OSError, ValueError, UnicodeError) as error:
    st.error(f"Could not load innovation infrastructure data: {error}")
    st.stop()

st.header("Data Quality")
quality = manager.data_quality(df)
left, middle, right = st.columns(3)
left.metric("Total records", quality["total"])
middle.metric("Duplicate identifiers", quality["duplicate_ids"])
right.metric("Duplicate country-years", quality["duplicate_country_years"])
with st.expander("Missing values by column"):
    st.dataframe(quality["missing_pct"].rename("Missing (%)"), width="stretch")
if quality["invalid_numeric"].sum():
    st.warning("Invalid numeric values are treated as missing in analysis. Source values stay on disk until edited.")
    st.dataframe(quality["invalid_numeric"])
if quality["duplicate_ids"] or quality["duplicate_country_years"]:
    st.warning("Ambiguous duplicate IDs or country-year rows are excluded from analysis. Duplicate IDs must be "
               "corrected in the source CSV before they can be edited or deleted.")
if quality["tier_mismatches"]:
    st.warning(f"{quality['tier_mismatches']} record(s) carry a tier that does not match their internet "
               "penetration. Edit the record to repair it.")

st.header("Create")
with st.expander("Add an infrastructure record"):
    submitted, record = record_form("infra_create")
if submitted:
    show_result(manager.add_record(record))

st.header("Read")
st.caption("All records are shown by default. Filters, statistics, charts and downloads use the current view.")
clean = manager.clean_data(df)
with st.container(border=True, key="infra_filters"):
    search = st.text_input("Search country", placeholder="Enter a country name")
    tier_column, year_column = st.columns(2)
    tiers = tier_column.multiselect("Filter infrastructure tier",
                                    [tier for tier in TIERS if tier in set(clean["infrastructure_tier"].dropna())])
    years = year_column.multiselect("Filter year", sorted(clean["year"].dropna().astype(int).unique()))
    sort_column, order_column = st.columns(2)
    sort_by = sort_column.selectbox("Sort by", COLUMNS)
    ascending = order_column.radio("Sort order", ["Ascending", "Descending"], horizontal=True) == "Ascending"
view = manager.filter_data(df, search, tiers, years, sort_by, ascending)
st.dataframe(view, hide_index=True, width="stretch")
analysis_view = manager.filter_data(manager.analysis_rows(df), search, tiers, years, sort_by, ascending)
stats = manager.summary(analysis_view)
st.metric("Records shown", f"{len(view)} of {len(df)}")
st.caption(f"{stats['analysis_records']} country-years have unambiguous keys and a usable tier. "
           "Averages skip missing values rather than counting them as zero.")
if tiers:
    st.warning("A tier filter narrows the comparison, so the group gap below describes the selected tiers only.")
if view.empty:
    st.info("No records match these filters.")
else:
    overview_tab, analysis_tab = st.tabs(["Infrastructure overview", "Group comparison"])
    with overview_tab:
        if not stats["scores"].empty:
            histogram = px.histogram(stats["scores"].to_frame("innovation_index_score"),
                                     x="innovation_index_score", nbins=12,
                                     color_discrete_sequence=CHART_COLORS,
                                     title="Distribution of innovation index scores",
                                     labels={"innovation_index_score": "Innovation index score"})
            histogram.update_layout(height=420, yaxis_title="Country-years", bargap=0.08)
            st.plotly_chart(style_chart(histogram), width="stretch")
            st.caption("One observation per country-year in the current view.")
        graduates = stats["tier_year_graduates"]
        if not graduates.empty:
            line = px.line(graduates, x="year", y="stem_graduates_per_1000", color="infrastructure_tier",
                           markers=True, color_discrete_sequence=CHART_COLORS,
                           title="Average STEM graduates by connectivity tier",
                           labels={"stem_graduates_per_1000": "STEM graduates per 1000 people",
                                   "year": "Year", "infrastructure_tier": "Tier"})
            line.update_layout(height=440, legend={"orientation": "h", "y": -0.2, "x": 0, "title_text": ""})
            line.update_xaxes(tickformat="d", dtick=1)
            st.plotly_chart(style_chart(line), width="stretch")
        tier_summary, rank_summary = st.columns(2)
        with tier_summary:
            st.subheader("Statistics by connectivity tier")
            st.dataframe(stats["by_tier"].round(2), width="stretch")
            st.caption("Three statistics per tier: average innovation index, average STEM graduates "
                       "per 1000 people, and the number of countries observed.")
        with rank_summary:
            st.subheader("Latest year per country, ranked")
            st.dataframe(stats["latest_by_country"][["country", "year", "innovation_index_score",
                                                     "innovation_rank", "index_per_stem_graduate"]].round(2),
                         hide_index=True, width="stretch")
            st.caption("Computed column: innovation index divided by STEM graduates per 1000 people. "
                       "Rank orders the latest observed score, highest first.")
    with analysis_tab:
        st.subheader("Does better connectivity come with higher innovation?")
        st.dataframe(stats["by_tier"][["countries", "avg_internet_penetration_pct",
                                       "avg_innovation_index"]].round(2), width="stretch")
        if pd.notna(stats["high_low_gap"]):
            high = stats["by_tier"].loc["High", "avg_innovation_index"]
            low = stats["by_tier"].loc["Low", "avg_innovation_index"]
            st.success(f"Country-years in the High tier average {high:.1f} on the innovation index, "
                       f"against {low:.1f} in the Low tier: a gap of {stats['high_low_gap']:.1f} points.")
        else:
            st.info("A High and a Low tier must both be present in the current view before the gap can be compared.")
        st.caption("This is a group comparison of averages within a small synthetic sample. It describes the "
                   "sample only and does not establish that connectivity causes innovation.")

st.header("Update")
unique = clean[clean["record_id"].notna() & ~clean["record_id"].duplicated(keep=False)]
ids = unique["record_id"].tolist()
if not ids:
    st.info("No records with a unique identifier are available to update.")
else:
    with st.expander("Edit an existing record"):
        selected = st.selectbox("Select record to update", ids)
        row = unique[unique["record_id"] == selected].iloc[0].to_dict()
        submitted, record = record_form(f"infra_update_{selected}", row)
    if submitted:
        show_result(manager.update_record(selected, record))

st.header("Delete")
if not ids:
    st.info("No records with a unique identifier are available to delete.")
else:
    with st.expander("Review and delete a record"):
        selected = st.selectbox("Select record to delete", ids)
        target = df[df["record_id"].astype(str) == selected]
        st.dataframe(target, hide_index=True, width="stretch")
        confirmed = st.checkbox("I confirm permanent deletion of this record", key=f"infra_confirm_{selected}")
        if st.button("Delete record", disabled=not confirmed):
            show_result(manager.delete_record(selected))

st.header("Activity Log")
st.caption("Every add, edit and delete made on this page appends a timestamped entry to "
           "`data/infrastructure_log.csv`. Only this page writes that file.")
entries = manager.activity_log.recent(10)
if entries.empty:
    st.info("No changes have been recorded yet. Add, edit or delete a record to start the audit trail.")
else:
    st.dataframe(entries, hide_index=True, width="stretch",
                 column_config={"logged_at_utc": "Logged (UTC)", "action": "Action",
                                "record_id": "Record ID", "detail": "Detail"})
    log_summary = manager.activity_log.summary()
    st.caption(f"{log_summary['entries']} entries in total: "
               + ", ".join(f"{count} {action}" for action, count in sorted(log_summary["actions"].items()))
               + ". The ten most recent are shown.")

st.header("Report")
filters = [f"Country search: {search or 'all'}",
           f"Tiers: {', '.join(tiers) or 'all'}",
           f"Years: {', '.join(str(year) for year in years) or 'all'}",
           f"Sort: {sort_by}, {'ascending' if ascending else 'descending'}"]
st.caption("Export the current view with your selected filters.")
csv_column, report_column = st.columns(2)
with csv_column:
    st.download_button("Download filtered data (CSV)", view.to_csv(index=False).encode("utf-8"),
                       file_name="infrastructure_filtered.csv", mime="text/csv", type="primary", width="stretch")
with report_column:
    st.download_button("Download summary report", build_report(view, filters, stats),
                       file_name="infrastructure_summary.txt", mime="text/plain", width="stretch")
