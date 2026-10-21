import pandas as pd
import plotly.express as px
import streamlit as st

from rd_manager import COLUMNS, CURRENT_YEAR, NUMERIC, SECTORS, ResearchSpendingManager, build_report
from ui_style import CHART_COLORS, apply_style, style_chart

st.set_page_config(page_title="Research Spending", layout="wide", initial_sidebar_state="expanded")
apply_style()
manager = ResearchSpendingManager()


def record_form(key, row=None):
    row = {} if row is None else row
    with st.form(key):
        record = {}
        identity_columns = st.columns(3)
        fields = [("record_id", "Record ID"), ("country", "Country"), ("iso_code", "ISO code")]
        for index, (column, label) in enumerate(fields):
            value = row.get(column, "")
            value = "" if pd.isna(value) else str(value)
            record[column] = identity_columns[index].text_input(label, value=value, disabled=bool(row) and column == "record_id")
        for index, column in enumerate(NUMERIC):
            if index % 2 == 0:
                number_columns = st.columns(2)
            input_column = number_columns[index % 2]
            default = CURRENT_YEAR if column == "year" else 0
            value = row.get(column, default)
            # Missing or malformed source values must be repaired explicitly.
            if pd.isna(value):
                value = None
            if column == "year":
                value = int(value) if value is not None else None
                record[column] = input_column.number_input("Year", 1900, CURRENT_YEAR, value=value, step=1)
            else:
                maximum = 100.0 if column == "gerd_pct_gdp" else None
                record[column] = input_column.number_input(column.replace("_", " ").title(),
                                                           min_value=0.0, max_value=maximum,
                                                           value=float(value) if value is not None else None)
        sector = row.get("funding_sector", "")
        sector = "" if pd.isna(sector) else sector
        index = SECTORS.index(sector) if sector in SECTORS else 0
        record["funding_sector"] = st.selectbox("Funding sector", SECTORS, index=index)
        submitted = st.form_submit_button("Save changes" if row else "Add record", type="primary")
    return submitted, record


def show_result(result):
    success, messages = result
    if success:
        st.session_state["rd_flash"] = messages[0]
        st.rerun()
    for message in messages:
        st.error(message)


st.caption(":orange[INVESTMENT LAYER · SDG 9]")
st.title("Research Spending")
st.write("Research investment and workforce: the input layer of the innovation system.")
st.info("The supplied SYN_RD records are synthetic demonstration data, not official country statistics.")
st.caption("Each row is one funding sector's contribution to a country-year. GDP percentages and USD amounts "
           "are sector contributions; researchers per million is the national figure repeated across sectors.")
if "rd_flash" in st.session_state:
    st.success(st.session_state.pop("rd_flash"))
try:
    df = manager.load()
except (OSError, ValueError, UnicodeError) as error:
    st.error(f"Could not load research spending: {error}")
    st.stop()

st.header("Data Quality")
quality = manager.data_quality(df)
left, right = st.columns(2)
left.metric("Total records", quality["total"])
right.metric("Duplicate identifiers", quality["duplicate_ids"])
with st.expander("Missing values by column"):
    st.dataframe(quality["missing_pct"].rename("Missing (%)"), width="stretch")
if quality["invalid_numeric"].sum():
    st.warning("Invalid numeric values are treated as missing in analysis. Source values are preserved until edited.")
    st.dataframe(quality["invalid_numeric"])
if quality["duplicate_ids"] or quality["duplicate_sector_rows"]:
    st.warning("Ambiguous duplicate IDs or country/year/sector rows are excluded from analysis. "
               "Duplicate IDs need correction in the source CSV before editing or deleting them.")

st.header("Create")
with st.expander("Add a research spending record"):
    submitted, record = record_form("rd_create")
if submitted:
    show_result(manager.add_record(record))

st.header("Read")
st.caption("All records are shown by default. Filters, statistics, charts and downloads use the current view.")
clean = manager.clean_data(df)
with st.container(border=True, key="rd_filters"):
    search = st.text_input("Search country", placeholder="Enter a country name")
    sector_column, year_column = st.columns(2)
    sectors = sector_column.multiselect("Filter funding sector", sorted(clean["funding_sector"].dropna().unique()))
    years = year_column.multiselect("Filter year", sorted(clean["year"].dropna().astype(int).unique()))
    sort_column, order_column = st.columns(2)
    sort_by = sort_column.selectbox("Sort by", COLUMNS)
    ascending = order_column.radio("Sort order", ["Ascending", "Descending"], horizontal=True) == "Ascending"
view = manager.filter_data(df, search, sectors, years, sort_by, ascending)
st.dataframe(view, hide_index=True, width="stretch")
analysis_view = manager.filter_data(manager.analysis_rows(df), search, sectors, years, sort_by, ascending)
stats = manager.summary(analysis_view)
st.metric("Records shown", f"{len(view)} of {len(df)}")
st.caption(f"{stats['analysis_records']} records have unambiguous analysis keys. Invalid numeric observations "
           "are not replaced by zero. Missing sector amounts make the corresponding total unavailable.")
if sectors:
    st.warning("Sector filters show partial spending coverage. Benchmark results describe selected sectors only.")
if view.empty:
    st.info("No records match these filters.")
else:
    overview_tab, benchmark_tab = st.tabs(["Spending overview", "Benchmark & growth"])
    with overview_tab:
        if not stats["top_spenders"].empty:
            bar = px.bar(stats["top_spenders"], x="gerd_usd_millions", y="country", hover_data=["year"],
                         orientation="h", color_discrete_sequence=CHART_COLORS,
                         title="Ten highest research spenders",
                         labels={"gerd_usd_millions": "R&D expenditure (USD millions)", "country": ""})
            bar.update_layout(height=420, yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(style_chart(bar), width="stretch")
            st.caption("Latest available year per country within the selected filters.")
        chart_data = stats["country_year"]
        if not chart_data.empty:
            line = px.line(chart_data, x="year", y="gerd_usd_millions", color="country", markers=True,
                           color_discrete_sequence=CHART_COLORS, title="R&D expenditure over time",
                           labels={"gerd_usd_millions": "R&D expenditure (USD millions)", "year": "Year", "country": "Country"})
            line.update_layout(height=460, legend={"orientation": "h", "y": -0.2, "x": 0, "title_text": ""})
            line.update_xaxes(tickformat="d", dtick=1)
            st.plotly_chart(style_chart(line), width="stretch")
        sector_summary, year_summary = st.columns(2)
        with sector_summary:
            st.subheader("Average R&D expenditure by funding sector (USD millions)")
            st.dataframe(stats["average_by_sector"].round(2), width="stretch")
        with year_summary:
            st.subheader("Total expenditure by year (USD millions)")
            st.dataframe(stats["total_by_year"].round(2), hide_index=True, width="stretch")
        st.caption("Year totals cover observed countries only. Changes in country or sector coverage affect comparisons.")
    with benchmark_tab:
        st.subheader("Countries meeting the 2%-of-GDP benchmark")
        st.dataframe(stats["benchmark"].round(2), hide_index=True, width="stretch")
        st.subheader("Benchmark gaps and year-on-year change")
        st.dataframe(stats["country_year"].round(2), hide_index=True, width="stretch")
        st.subheader("Research spending growth over the observed period")
        st.dataframe(stats["growth"].round(2), hide_index=True, width="stretch")
        st.caption("Gap is max(2 - spending % GDP, 0), in percentage points. Year-on-year change requires adjacent "
                   "years, equal sector coverage and a positive previous value. Up/Down/Unchanged indicate direction.")

st.header("Update")
unique = clean[clean["record_id"].notna() & ~clean["record_id"].duplicated(keep=False)]
ids = unique["record_id"].tolist()
if not ids:
    st.info("No records with a unique identifier are available to update.")
else:
    with st.expander("Edit an existing record"):
        selected = st.selectbox("Select record to update", ids)
        row = unique[unique["record_id"] == selected].iloc[0].to_dict()
        submitted, record = record_form(f"rd_update_{selected}", row)
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
        confirmed = st.checkbox("I confirm permanent deletion of this record", key=f"rd_confirm_{selected}")
        if st.button("Delete record", disabled=not confirmed):
            show_result(manager.delete_record(selected))

st.header("Report")
filters = [f"Country search: {search or 'all'}", f"Sectors: {', '.join(sectors) or 'all'}",
           f"Years: {', '.join(str(y) for y in years) or 'all'}",
           f"Sort: {sort_by}, {'ascending' if ascending else 'descending'}"]
st.caption("Export the current view with your selected filters.")
csv_column, report_column = st.columns(2)
with csv_column:
    st.download_button("Download filtered data (CSV)", view.to_csv(index=False).encode("utf-8"),
                       file_name="rd_filtered.csv", mime="text/csv", type="primary", width="stretch")
with report_column:
    st.download_button("Download summary report", build_report(view, filters, stats),
                       file_name="rd_summary.txt", mime="text/plain", width="stretch")
