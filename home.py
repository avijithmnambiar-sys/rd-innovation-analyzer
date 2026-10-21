from pathlib import Path

import pandas as pd
import streamlit as st

from country_profile import METRICS, load_profiles, score_profiles

st.set_page_config(page_title="Global R&D and Systems Innovation Analyzer", layout="wide")
ROOT = Path(__file__).resolve().parent

st.title("Global R&D and Systems Innovation Analyzer")
st.write("Which countries get the most innovation out of what they put in? Explore research investment, "
         "patents, research institutions and innovation infrastructure as parts of one system.")
st.subheader("SDG 9: Industry, Innovation and Infrastructure")
st.write("Target 9.5 calls for stronger research capacity, more researchers and increased R&D investment. "
         "Target 9.c concerns access to information and communications technology. The spending page "
         "compares investment with a project benchmark of 2% of GDP; this is not an official SDG threshold.")

st.subheader("Team responsibilities and modules")
team = [
    ["Manish J", "Research Spending", "Home, combined country profile, composite score and README", "1_RD_Investment.py"],
    ["Avijith M Nambiar", "Patents & IP Output", "Shared CSVManager base class", "2_Patents.py"],
    ["Jayasurya Jay Nair", "Research Institutions", "Dependencies and clean-install verification", "3_Institutions.py"],
    ["Surya R", "Innovation Infrastructure", "Repository, screenshots and demonstration video", "4_Infrastructure.py"],
]
st.dataframe(pd.DataFrame([row[:3] for row in team], columns=["Member", "Dataset", "Team responsibility"]), hide_index=True)
for member, module, responsibility, page in team:
    if (ROOT / "pages" / page).exists():
        st.page_link("pages/" + page, label=module)
    else:
        st.button(module + " (page not supplied)", disabled=True)

st.subheader("Combined country profile")
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
year = st.selectbox("Observation year", years, index=len(years) - 1)
scored = score_profiles(profiles, year)
country = st.selectbox("Country profile", scored["country"].tolist())
selected = scored[scored["country"] == country]
row = selected.iloc[0]
left, middle, right = st.columns(3)
left.metric("Composite innovation score / 100", "Unavailable" if pd.isna(row["composite_score"]) else row["composite_score"])
middle.metric("Components available", f"{int(row['components_available'])} / 4")
right.metric("Provisional score / 100", "Unavailable" if pd.isna(row["provisional_score"]) else row["provisional_score"])
st.caption("Provisional scores average only available components and cannot be compared as complete four-component scores.")
columns = ["country", "year", "gerd_pct_gdp", "gerd_usd_millions", "researchers_per_million",
           "patent_grants", "institution_count", "citations_per_publication", "innovation_index_score"]
st.dataframe(selected[columns].round(2), hide_index=True)
st.caption("Institution count and citations per publication describe the undated institution snapshot, repeated "
           "for context. Founded year is not an observation year. Annual datasets match the selected year exactly.")
st.subheader("Normalized headline metrics")
st.dataframe(selected[[metric + "_score" for metric in METRICS]].round(2), hide_index=True)
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
st.dataframe(scored[["country", "components_available", "composite_score", "provisional_score"]], hide_index=True)
