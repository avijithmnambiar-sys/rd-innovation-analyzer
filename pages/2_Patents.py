import re                                  # regular expressions for the pattern search
from datetime import datetime              # timestamps and current year
from pathlib import Path                   # build file paths that work on any OS

import pandas as pd
import plotly.express as px                # charts
import streamlit as st                     # the web framework

from csv_manager import CSVManager         # the shared base class

st.set_page_config(page_title="Patents & IP Output", page_icon="📄", layout="wide")  # must be the first st call

BASE_DIR = Path(__file__).resolve().parent.parent        # project root (one level above pages/)
PATENTS_FILE = BASE_DIR / "data" / "patents.csv"         # my dataset
RD_FILE = BASE_DIR / "data" / "rd_investment.csv"        # Manish's dataset (read-only, for efficiency)

PATENT_COLUMNS = ["patent_id", "country", "filing_year", "technology_field",
                  "applicant_type", "grants_count", "citations", "is_green_tech"]
RD_COLUMNS = ["record_id", "country", "iso_code", "year", "gerd_pct_gdp",
              "gerd_usd_millions", "researchers_per_million", "funding_sector"]
FIELDS = ["Artificial Intelligence", "Biotechnology", "Clean Energy", "Semiconductors",
          "Telecommunications", "Materials Science", "Medical Devices", "Robotics"]  # dropdown options
APPLICANT_TYPES = ["University", "Corporation", "Government Lab", "Individual"]    # dropdown options
NUMERIC_COLUMNS = ["filing_year", "grants_count", "citations"]   # columns that must be numbers
CURRENT_YEAR = datetime.now().year


def safe_int(value, default, low=0, high=10**9):
    """Turn a possibly-missing value into an int inside [low, high]."""
    return int(min(max(value, low), high)) if pd.notna(value) else default   # NaN -> default


def index_of(options, value):
    """Position of value in options, or 0 if it is not there (used to pre-select dropdowns)."""
    return options.index(value) if value in options else 0


class PatentManager(CSVManager):                    # INHERITANCE: reuses load() and save()
    def __init__(self, file_path=PATENTS_FILE):
        super().__init__(file_path, PATENT_COLUMNS)  # hand file path and columns to the base class

    def load_patents(self):
        df = self.load()                                             # base-class safe load
        for col in NUMERIC_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")        # bad text becomes NaN instead of crashing
        df["is_green_tech"] = (df["is_green_tech"].astype(str).str.strip()
                               .str.lower().isin(["true", "1", "yes"]))   # text "True"/"False" -> real bool
        return df

    def validate(self, record, df, ignore_id=None):
        errors = []                                                  # collect every problem, not just the first
        patent_id = str(record.get("patent_id", "")).strip()
        if not patent_id:
            errors.append("Patent ID is required.")
        elif patent_id != ignore_id and patent_id in df["patent_id"].astype(str).values:
            errors.append(f"Patent ID '{patent_id}' already exists.")   # uniqueness check
        if not str(record.get("country", "")).strip():
            errors.append("Country is required.")
        try:
            year = int(record.get("filing_year"))
            if not 1900 <= year <= CURRENT_YEAR:
                errors.append(f"Filing year must be between 1900 and {CURRENT_YEAR}.")
        except (TypeError, ValueError):
            errors.append("Filing year must be a whole number.")
        if record.get("technology_field") not in FIELDS:
            errors.append("Choose a valid technology field.")
        if record.get("applicant_type") not in APPLICANT_TYPES:
            errors.append("Choose a valid applicant type.")
        for col in ("grants_count", "citations"):
            try:
                if int(record.get(col)) < 0:
                    errors.append(f"{col} cannot be negative.")
            except (TypeError, ValueError):
                errors.append(f"{col} must be a whole number.")
        if not isinstance(record.get("is_green_tech"), bool):
            errors.append("Green technology must be True or False.")
        return errors                                                # empty list = record is valid

    def _clean(self, record):
        return {                                                     # normalised row, in column order
            "patent_id": str(record["patent_id"]).strip(),
            "country": str(record["country"]).strip(),
            "filing_year": int(record["filing_year"]),
            "technology_field": record["technology_field"],
            "applicant_type": record["applicant_type"],
            "grants_count": int(record["grants_count"]),
            "citations": int(record["citations"]),
            "is_green_tech": bool(record["is_green_tech"]),
        }

    def add_patent(self, record):
        try:
            df = self.load_patents()
            errors = self.validate(record, df)
            if errors:
                return False, errors                                 # nothing is saved
            row = self._clean(record)
            df.loc[len(df)] = [row[c] for c in PATENT_COLUMNS]       # append as a new last row
            self.save(df)                                            # safe write from the base class
            return True, [f"Patent {row['patent_id']} added."]
        except (OSError, ValueError) as err:
            return False, [f"File error: {err}"]

    def update_patent(self, patent_id, record):
        try:
            df = self.load_patents()
            mask = df["patent_id"].astype(str) == str(patent_id)     # which row is this record?
            if not mask.any():
                return False, [f"Patent '{patent_id}' not found."]
            record = dict(record, patent_id=patent_id)               # the ID itself cannot be changed
            errors = self.validate(record, df, ignore_id=str(patent_id))
            if errors:
                return False, errors
            row = self._clean(record)
            idx = df.index[mask][0]                                  # row label of the record
            for col in PATENT_COLUMNS:
                df.at[idx, col] = row[col]                           # overwrite each field in place
            self.save(df)
            return True, [f"Patent {patent_id} updated."]
        except (OSError, ValueError) as err:
            return False, [f"File error: {err}"]

    def delete_patent(self, patent_id):
        try:
            df = self.load_patents()
            mask = df["patent_id"].astype(str) == str(patent_id)
            if not mask.any():
                return False, [f"Patent '{patent_id}' not found."]
            self.save(df[~mask])                                     # keep every row except the target
            return True, [f"Patent {patent_id} deleted."]
        except (OSError, ValueError) as err:
            return False, [f"File error: {err}"]

    def search(self, df, pattern):
        if df.empty or not pattern.strip():
            return df, None                                          # nothing to search / no pattern
        try:
            rx = re.compile(pattern, re.IGNORECASE)                  # compile the user's regex
        except re.error as err:
            return df, f"Invalid search pattern ({err}). Showing all records."   # warning, not a crash
        mask = pd.Series(False, index=df.index)                      # start with "no row matches"
        for col in ("patent_id", "country", "technology_field"):
            mask |= df[col].astype(str).apply(lambda s: bool(rx.search(s)))   # match in any of these columns
        return df[mask], None

    def summary(self, df=None):                                      # implements the abstract base method
        if df is None:
            df = self.load_patents()
        if df.empty:
            return {"total": 0, "per_field": pd.Series(dtype=int),
                    "avg_citations_by_applicant": pd.Series(dtype=float), "green_share_pct": 0.0}
        total = len(df)                                              # > 0 here, so no division by zero below
        return {
            "total": total,
            "per_field": df["technology_field"].value_counts(),      # filings per field
            "avg_citations_by_applicant": df.groupby("applicant_type")["citations"].mean().round(2),
            "green_share_pct": round(float(df["is_green_tech"].sum()) / total * 100, 1),
        }

    def innovation_efficiency(self, df):
        try:
            rd = CSVManager(RD_FILE, RD_COLUMNS).load()              # read-only use of Manish's file
        except (OSError, ValueError):
            return pd.DataFrame(), "Research spending data could not be read."
        if rd.empty or df.empty:
            return pd.DataFrame(), "Efficiency needs both patent and research-spending records."
        rd["year"] = pd.to_numeric(rd["year"], errors="coerce")
        rd["gerd_usd_millions"] = pd.to_numeric(rd["gerd_usd_millions"], errors="coerce")
        grants = (df.groupby(["country", "filing_year"], as_index=False)["grants_count"].sum()
                  .rename(columns={"filing_year": "year"}))          # grants per country-year
        spend = rd.groupby(["country", "year"], as_index=False)["gerd_usd_millions"].sum()
        merged = grants.merge(spend, on=["country", "year"])         # keep only country-years in BOTH files
        if merged.empty:
            return pd.DataFrame(), "No matching country-year pairs between the two datasets."
        out = merged.groupby("country", as_index=False)[["grants_count", "gerd_usd_millions"]].sum()
        out["spend_billion_usd"] = out["gerd_usd_millions"] / 1000   # millions -> billions
        out = out[out["spend_billion_usd"] > 0].copy()               # drop zero spend: avoids division by zero
        out["patents_per_billion"] = (out["grants_count"] / out["spend_billion_usd"]).round(2)
        avg = out["patents_per_billion"].mean()
        out["flag"] = out["patents_per_billion"].apply(
            lambda v: "Above 2x average" if v > 2 * avg else ("Below half average" if v < avg / 2 else "Normal"))
        return out.sort_values("patents_per_billion", ascending=False), None


def build_report(view, filters, stats):
    lines = ["PATENTS & IP OUTPUT - SUMMARY REPORT",
             f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",     # timestamp
             f"Records in view: {len(view)}",                       # record count
             "Filters applied: " + ("; ".join(filters) if filters else "none"),
             "", "Patents per technology field:", stats["per_field"].to_string(),
             "", "Average citations by applicant type:", stats["avg_citations_by_applicant"].to_string(),
             "", f"Green technology share: {stats['green_share_pct']}%"]
    return "\n".join(lines)                                          # one text block for the download


manager = PatentManager()                                            # object for this page

st.title("📄 Patents & IP Output")
st.caption("Results layer: intellectual property produced, by field and applicant type.")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))                        # show the message saved before the last rerun

try:
    df = manager.load_patents()
except (OSError, ValueError) as err:
    st.error(f"Could not load the patents file: {err}")
    st.stop()                                                        # halt the page rather than crash

# ---------- DATA QUALITY ----------
dupes = int(df["patent_id"].duplicated().sum())                      # repeated IDs
missing = {c: round(df[c].isna().mean() * 100, 1) for c in PATENT_COLUMNS if df[c].isna().any()}
missing_text = ", ".join(f"{c} ({p}%)" for c, p in missing.items()) or "none"
st.info(f"{len(df)} records loaded · {dupes} duplicate IDs · missing values: {missing_text}")

# ---------- CREATE ----------
st.header("Create")
with st.form("create_form", clear_on_submit=True):                   # inputs are sent only on submit
    c1, c2 = st.columns(2)
    new_id = c1.text_input("Patent ID (e.g. P0001)")
    new_country = c2.text_input("Country")
    new_year = c1.number_input("Filing year", 1900, CURRENT_YEAR, CURRENT_YEAR, step=1)
    new_field = c2.selectbox("Technology field", FIELDS)
    new_applicant = c1.selectbox("Applicant type", APPLICANT_TYPES)
    new_grants = c2.number_input("Grants count", min_value=0, value=0, step=1)
    new_citations = c1.number_input("Citations", min_value=0, value=0, step=1)
    new_green = c2.checkbox("Green technology")                      # bool input for a bool column
    submitted = st.form_submit_button("Add patent")
if submitted:
    ok, messages = manager.add_patent({
        "patent_id": new_id, "country": new_country, "filing_year": new_year,
        "technology_field": new_field, "applicant_type": new_applicant,
        "grants_count": new_grants, "citations": new_citations, "is_green_tech": new_green})
    if ok:
        st.session_state["flash"] = messages[0]                      # survives the rerun
        st.rerun()                                                   # reload so the new row appears
    else:
        for m in messages:
            st.error(m)                                              # clear on-page message, nothing saved

# ---------- READ ----------
st.header("Read")
pattern = st.text_input("Search (regular expression on ID, country or field)")
f1, f2, f3 = st.columns(3)
field_filter = f1.multiselect("Technology field", FIELDS)
applicant_filter = f2.multiselect("Applicant type", APPLICANT_TYPES)
year_filter = f3.multiselect("Filing year", sorted(df["filing_year"].dropna().astype(int).unique()))
s1, s2 = st.columns(2)
sort_col = s1.selectbox("Sort by", PATENT_COLUMNS)
ascending = s2.radio("Order", ["Ascending", "Descending"], horizontal=True) == "Ascending"

view, warning = manager.search(df, pattern)                          # regex search first
if warning:
    st.warning(warning)
if field_filter:
    view = view[view["technology_field"].isin(field_filter)]
if applicant_filter:
    view = view[view["applicant_type"].isin(applicant_filter)]
if year_filter:
    view = view[view["filing_year"].isin(year_filter)]
view = view.sort_values(sort_col, ascending=ascending)              # apply chosen sort

st.dataframe(view, hide_index=True)
stats = manager.summary(view)                                        # stats come from the filtered view only
k1, k2, k3 = st.columns(3)
k1.metric("Records shown", f"{stats['total']} of {len(df)}")
k2.metric("Green tech share", f"{stats['green_share_pct']}%")
k3.metric("Fields covered", len(stats["per_field"]))

if view.empty:
    st.info("No records match the current filters.")
else:
    t1, t2 = st.columns(2)
    t1.write("**Patents per technology field**")
    t1.dataframe(stats["per_field"])
    t2.write("**Average citations by applicant type**")
    t2.dataframe(stats["avg_citations_by_applicant"])

    field_counts = stats["per_field"].reset_index()
    field_counts.columns = ["technology_field", "filings"]
    st.plotly_chart(px.pie(field_counts, names="technology_field", values="filings",
                           title="Filings by technology field"))
    grouped = view.groupby(["country", "applicant_type"]).size().reset_index(name="filings")
    st.plotly_chart(px.bar(grouped, x="country", y="filings", color="applicant_type",
                           barmode="group", title="Filings by country and applicant type"))

st.subheader("Innovation efficiency (granted patents per billion USD of research spending)")
efficiency, note = manager.innovation_efficiency(df)                 # uses the full dataset, not the filtered view
if note:
    st.info(note)
else:
    st.dataframe(efficiency[["country", "grants_count", "spend_billion_usd",
                             "patents_per_billion", "flag"]], hide_index=True)
    st.plotly_chart(px.bar(efficiency, x="country", y="patents_per_billion", color="flag"))

# ---------- UPDATE ----------
st.header("Update")
if df.empty:
    st.info("No records to update.")
else:
    ids = df["patent_id"].astype(str).tolist()
    update_id = st.selectbox("Select patent ID", ids, key="update_select")
    cur = df[df["patent_id"].astype(str) == update_id].iloc[0]       # the chosen record
    with st.form(f"update_form_{update_id}"):                        # new form per record so defaults refresh
        u1, u2 = st.columns(2)
        up_country = u1.text_input("Country", value=str(cur["country"]))
        up_year = u2.number_input("Filing year", 1900, CURRENT_YEAR,
                                  safe_int(cur["filing_year"], CURRENT_YEAR, 1900, CURRENT_YEAR), step=1)
        up_field = u1.selectbox("Technology field", FIELDS, index=index_of(FIELDS, cur["technology_field"]))
        up_applicant = u2.selectbox("Applicant type", APPLICANT_TYPES,
                                    index=index_of(APPLICANT_TYPES, cur["applicant_type"]))
        up_grants = u1.number_input("Grants count", min_value=0, value=safe_int(cur["grants_count"], 0), step=1)
        up_citations = u2.number_input("Citations", min_value=0, value=safe_int(cur["citations"], 0), step=1)
        up_green = u1.checkbox("Green technology", value=bool(cur["is_green_tech"]))
        update_clicked = st.form_submit_button("Save changes")
    if update_clicked:
        ok, messages = manager.update_patent(update_id, {
            "country": up_country, "filing_year": up_year, "technology_field": up_field,
            "applicant_type": up_applicant, "grants_count": up_grants,
            "citations": up_citations, "is_green_tech": up_green})
        if ok:
            st.session_state["flash"] = messages[0]
            st.rerun()
        else:
            for m in messages:
                st.error(m)

# ---------- DELETE ----------
st.header("Delete")
if df.empty:
    st.info("No records to delete.")
else:
    delete_id = st.selectbox("Select patent ID to delete", ids, key="delete_select")
    target = df[df["patent_id"].astype(str) == delete_id].iloc[0]
    st.warning(f"About to delete {delete_id}: {target['technology_field']} ({target['country']})")
    confirmed = st.checkbox("I confirm I want to permanently delete this record", key=f"confirm_{delete_id}")
    if st.button("Delete record", disabled=not confirmed):           # button stays disabled until confirmed
        ok, messages = manager.delete_patent(delete_id)
        if ok:
            st.session_state["flash"] = messages[0]
            st.rerun()
        else:
            st.error(messages[0])

# ---------- REPORT ----------
st.header("Report")
applied = []                                                         # human-readable list of active filters
if pattern.strip():
    applied.append(f"Search: {pattern}")
if field_filter:
    applied.append("Field: " + ", ".join(field_filter))
if applicant_filter:
    applied.append("Applicant: " + ", ".join(applicant_filter))
if year_filter:
    applied.append("Year: " + ", ".join(str(y) for y in year_filter))
applied.append(f"Sorted by {sort_col} ({'ascending' if ascending else 'descending'})")
st.download_button("Download report of current view", data=build_report(view, applied, stats),
                   file_name=f"patents_report_{datetime.now():%Y%m%d_%H%M%S}.txt", mime="text/plain")