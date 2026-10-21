from pathlib import Path

import pandas as pd
import streamlit as st

from country_profile import METRICS, load_profiles, score_profiles
from ui_style import apply_style

st.set_page_config(page_title="Global R&D and Systems Innovation Analyzer", layout="wide", initial_sidebar_state="expanded")
apply_style()
ROOT = Path(__file__).resolve().parent

st.caption(":orange[GLOBAL INNOVATION · COUNTRY PROFILES]")
st.title("Global R&D and Systems Innovation Analyzer")
st.write("Which countries get the most innovation out of what they put in? Explore research investment, "
         "patents, research institutions and innovation infrastructure as parts of one system.")
with st.container(border=True, key="home_sdg"):
    st.subheader("SDG 9: Industry, Innovation and Infrastructure")
    st.write("Target 9.5 calls for stronger research capacity, more researchers and increased R&D investment. "
             "Target 9.c concerns access to information and communications technology. The spending page "
             "compares investment with a project benchmark of 2% of GDP; this is not an official SDG threshold.")

st.header("Explore the four modules")
team = [
    ["Manish J", "Research Spending", "Home, combined country profile, composite score and README", "1_RD_Investment.py"],
    ["Avijith M Nambiar", "Patents & IP Output", "Shared CSVManager base class", "2_Patents.py"],
    ["Jayasurya Jay Nair", "Research Institutions", "Dependencies and clean-install verification", "3_Institutions.py"],
    ["Surya R", "Innovation Infrastructure", "Repository, screenshots and demonstration video", "4_Infrastructure.py"],
]
layers = ["01 · INVESTMENT", "02 · RESULTS", "03 · RESEARCH ACTORS", "04 · ENABLERS"]
for start in [0, 2]:
    module_columns = st.columns(2)
    for index in range(start, start + 2):
        member, module, responsibility, page = team[index]
        with module_columns[index - start].container(border=True, key=f"home_module_{index}"):
            st.caption(layers[index])
            if (ROOT / "pages" / page).exists():
                st.page_link("pages/" + page, label=f"**{module}**", use_container_width=True)
            else:
                st.button(module + " (page not supplied)", disabled=True, width="stretch")
            st.caption(member)
with st.expander("Team responsibilities"):
    st.dataframe(pd.DataFrame([row[:3] for row in team], columns=["Member", "Dataset", "Team responsibility"]),
                 hide_index=True, width="stretch")

st.header("Combined country profile")
st.caption("The Research Spending file contains clearly labelled synthetic sample records. Teammate files are "
           "read without modification. Missing components are shown as unavailable.")
profiles, warnings = load_profiles(ROOT / "data")
for warning in warnings:
    st.warning(warning)
years = sorted(profiles["year"].dropna().astype(int).unique())
if not years:
    st.info("No annual observations are available yet. Institution snapshots remain visible below.")
    st.dataframe(profiles, hide_index=True)
    st.stop()
year_column, country_column = st.columns([1, 2])
year = year_column.selectbox("Observation year", years, index=len(years) - 1)
scored = score_profiles(profiles, year)
country = country_column.selectbox("Country profile", scored["country"].tolist())
selected = scored[scored["country"] == country]
row = selected.iloc[0]
left, middle, right = st.columns(3)
left.metric("Composite innovation score / 100", "Unavailable" if pd.isna(row["composite_score"]) else row["composite_score"])
middle.metric("Components available", f"{int(row['components_available'])} / 4")
right.metric("Provisional score / 100", "Unavailable" if pd.isna(row["provisional_score"]) else row["provisional_score"])
st.caption("Provisional scores average only available components and cannot be compared as complete four-component scores.")
columns = ["country", "year", "gerd_pct_gdp", "gerd_usd_millions", "researchers_per_million",
           "patent_grants", "institution_count", "citations_per_publication", "innovation_index_score"]
st.dataframe(selected[columns].round(2), hide_index=True, width="stretch", column_config={
    "country": "Country", "year": st.column_config.NumberColumn("Year", format="%d"),
    "gerd_pct_gdp": st.column_config.NumberColumn("R&D (% GDP)", format="%.2f"),
    "gerd_usd_millions": st.column_config.NumberColumn("R&D (USD m)", format="%.2f"),
    "researchers_per_million": "Researchers / million", "patent_grants": "Patent grants",
    "institution_count": "Institutions", "citations_per_publication": "Citations / publication",
    "innovation_index_score": "Innovation index",
})
st.caption("Institution count and citations per publication describe the undated institution snapshot, repeated "
           "for context. Founded year is not an observation year. Annual datasets match the selected year exactly.")
st.subheader("Normalized headline metrics")
score_labels = ["R&D spending", "Patent grants", "Research impact", "Infrastructure"]
st.dataframe(selected[[metric + "_score" for metric in METRICS]].round(2), hide_index=True, width="stretch",
             column_config={metric + "_score": st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%.1f")
                            for metric, label in zip(METRICS, score_labels)})
with st.expander("Composite score methodology"):
    st.write("For the selected year, scale each available headline metric across countries using "
             "100 × (value - minimum) / (maximum - minimum). An identical-valued component scores 50. "
             "Headline metrics are R&D as % of GDP, total patent grants, institution citations per publication, "
             "and the infrastructure innovation index. All are higher-is-better.")
    st.write("The composite is the equal-weight mean of all four scores. If any is missing, the composite "
             "is unavailable and a separate provisional average shows available coverage. Institution impact "
             "is total citations / total publications for valid positive-publication records, not a mean of ratios. "
             "Scores describe this sample and depend on its country coverage; they are not official rankings.")
st.subheader("Country comparison for the selected year")
st.dataframe(scored[["country", "components_available", "composite_score", "provisional_score"]], hide_index=True,
             width="stretch", column_config={"country": "Country", "components_available": "Components (of 4)",
                                            "composite_score": "Composite / 100", "provisional_score": "Provisional / 100"})
