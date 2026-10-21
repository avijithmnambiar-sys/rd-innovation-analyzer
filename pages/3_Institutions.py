from csv_manager import CSVManager
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Research Institutions",
    page_icon="🔬",
    layout="wide"
)

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "institutions.csv"

COLUMNS = [
    "institution_id",
    "institution_name",
    "country",
    "institution_type",
    "publications_count",
    "citations_total",
    "intl_collab_pct",
    "primary_field",
    "founded_year"
]


class InstitutionManager(CSVManager):
    def __init__(self):
        super().__init__(CSV_PATH, COLUMNS)

    def summary(self, df=None):
        if df is None:
            df = self.load()

        if df.empty:
            return {
                "total": 0,
                "countries": 0,
                "publications": 0
            }

        return {
            "total": len(df),
            "countries": df["country"].nunique(),
            "publications": pd.to_numeric(
                df["publications_count"], errors="coerce"
            ).sum()
        }
    
    def validate(self, record, df):
        errors = []

        # Required text fields
        for field in [
            "institution_id",
            "institution_name",
            "country",
            "institution_type",
            "primary_field"
        ]:
            if not str(record.get(field, "")).strip():
                errors.append(f"{field.replace('_', ' ').title()} is required.")

        # Unique institution ID
        institution_id = str(record.get("institution_id", "")).strip()
        if institution_id in df["institution_id"].astype(str).values:
            errors.append("This institution ID already exists.")

        # Numeric validation
        for field in ["publications_count", "citations_total", "founded_year"]:
            try:
                value = float(record[field])
                if not value.is_integer():
                    raise ValueError
                if value < 0:
                    errors.append(f"{field} cannot be negative.")
                if field == "founded_year" and not 1000 <= value <= datetime.now().year:
                    errors.append(
                        f"Founded year must be between 1000 and {datetime.now().year}."
                    )
            except (ValueError, TypeError, KeyError):
                errors.append(f"{field} must be a whole number.")

        # Collaboration percentage
        try:
            pct = float(record["intl_collab_pct"])
            if not 0 <= pct <= 100:
                errors.append("Collaboration percentage must be between 0 and 100.")
        except (ValueError, TypeError, KeyError):
            errors.append("Collaboration percentage must be a number.")

        return errors

    def add_institution(self, record):
        df = self.load()
        errors = self.validate(record, df)

        if errors:
            return False, errors

        record = {
            "institution_id": str(record["institution_id"]).strip(),
            "institution_name": str(record["institution_name"]).strip(),
            "country": str(record["country"]).strip(),
            "institution_type": str(record["institution_type"]).strip(),
            "publications_count": int(record["publications_count"]),
            "citations_total": int(record["citations_total"]),
            "intl_collab_pct": float(record["intl_collab_pct"]),
            "primary_field": str(record["primary_field"]).strip(),
            "founded_year": int(record["founded_year"])
        }

        df.loc[len(df)] = [record[c] for c in COLUMNS]
        self.save(df)

        return True, ["Institution added successfully."]



st.title("🔬 Research Institutions")
st.write(
    "Analyse universities, laboratories and research organisations "
    "as part of SDG 9: Industry, Innovation and Infrastructure."
)

manager = InstitutionManager()

try:
    df = manager.load()
except (OSError, ValueError) as error:
    st.error(f"Could not load institutions data: {error}")
    st.stop()

stats = manager.summary(df)

c1, c2, c3 = st.columns(3)
c1.metric("Institutions", stats["total"])
c2.metric("Countries", stats["countries"])
c3.metric("Publications", int(stats["publications"]))

st.header("Add a new institution")

with st.form("add_institution_form", clear_on_submit=True):
    c1, c2 = st.columns(2)

    new_id = c1.text_input("Institution ID")
    new_name = c2.text_input("Institution Name")
    new_country = c1.text_input("Country")

    new_type = c2.selectbox(
        "Institution Type",
        [
            "University",
            "Government Laboratory",
            "Private Research Institute",
            "Public Research Institute",
            "Other"
        ]
    )

    new_publications = c1.number_input(
        "Publications Count", min_value=0, step=1
    )
    new_citations = c2.number_input(
        "Total Citations", min_value=0, step=1
    )
    new_collab = c1.number_input(
        "International Collaboration (%)",
        min_value=0.0, max_value=100.0, step=0.5
    )

    new_field = c2.selectbox(
        "Primary Research Field",
        [
            "Computer Science", "Engineering", "Medicine",
            "Physics", "Biology", "Chemistry",
            "Environmental Science", "Mathematics", "Other"
        ]
    )

    new_year = st.number_input(
        "Founded Year", min_value=1000,
        max_value=datetime.now().year, value=2000, step=1
    )

    submitted = st.form_submit_button("Add Institution")

if submitted:
    record = {
        "institution_id": new_id,
        "institution_name": new_name,
        "country": new_country,
        "institution_type": new_type,
        "publications_count": new_publications,
        "citations_total": new_citations,
        "intl_collab_pct": new_collab,
        "primary_field": new_field,
        "founded_year": new_year
    }

    try:
        success, messages = manager.add_institution(record)

        if success:
            st.success(messages[0])
            st.rerun()
        else:
            for message in messages:
                st.error(message)

    except (OSError, ValueError) as error:
        st.error(f"Could not save institution: {error}")


st.subheader("Institution records")

# Search
search = st.text_input(
    "Search by institution name or country"
)

view = df.copy()

if search.strip():
    mask = (
        view["institution_name"].astype(str).str.contains(
            search, case=False, na=False, regex=False
        )
        | view["country"].astype(str).str.contains(
            search, case=False, na=False, regex=False
        )
    )
    view = view[mask]

# Filters
col1, col2, col3 = st.columns(3)

countries = sorted(df["country"].dropna().unique().tolist())
types = sorted(df["institution_type"].dropna().unique().tolist())
fields = sorted(df["primary_field"].dropna().unique().tolist())

selected_countries = col1.multiselect(
    "Filter by country", countries
)
selected_types = col2.multiselect(
    "Filter by institution type", types
)
selected_fields = col3.multiselect(
    "Filter by research field", fields
)

if selected_countries:
    view = view[view["country"].isin(selected_countries)]

if selected_types:
    view = view[view["institution_type"].isin(selected_types)]

if selected_fields:
    view = view[view["primary_field"].isin(selected_fields)]

# Sorting
sort_column = st.selectbox(
    "Sort records by",
    [
        "institution_name",
        "country",
        "publications_count",
        "citations_total",
        "founded_year"
    ]
)

sort_order = st.radio(
    "Sort order",
    ["Ascending", "Descending"],
    horizontal=True
)

view = view.sort_values(
    sort_column,
    ascending=(sort_order == "Ascending"),
    na_position="last"
)

st.caption(f"Showing {len(view)} of {len(df)} institutions")

st.dataframe(
    view,
    use_container_width=True,
    hide_index=True
)

st.divider()
st.header("Edit an institution")

if df.empty:
    st.info("No institutions available to edit.")
else:
    ids = df["institution_id"].astype(str).tolist()

    selected_id = st.selectbox(
        "Select institution to edit",
        ids,
        key="edit_institution"
    )

    row = df[df["institution_id"].astype(str) == selected_id].iloc[0]

    with st.form("edit_institution_form"):
        edit_name = st.text_input(
            "Institution Name",
            value=str(row["institution_name"])
        )
        edit_country = st.text_input(
            "Country",
            value=str(row["country"])
        )
        edit_type = st.selectbox(
            "Institution Type",
            [
                "University",
                "Government Laboratory",
                "Private Research Institute",
                "Public Research Institute",
                "Other"
            ],
            index=[
                "University",
                "Government Laboratory",
                "Private Research Institute",
                "Public Research Institute",
                "Other"
            ].index(row["institution_type"])
            if row["institution_type"] in [
                "University",
                "Government Laboratory",
                "Private Research Institute",
                "Public Research Institute",
                "Other"
            ] else 0
        )

        edit_publications = st.number_input(
            "Publications Count",
            min_value=0,
            value=int(row["publications_count"]),
            step=1
        )
        edit_citations = st.number_input(
            "Total Citations",
            min_value=0,
            value=int(row["citations_total"]),
            step=1
        )
        edit_collab = st.number_input(
            "International Collaboration (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(row["intl_collab_pct"]),
            step=0.5
        )
        edit_field = st.text_input(
            "Primary Research Field",
            value=str(row["primary_field"])
        )
        edit_year = st.number_input(
            "Founded Year",
            min_value=1000,
            max_value=datetime.now().year,
            value=int(row["founded_year"]),
            step=1
        )

        save_changes = st.form_submit_button("Save Changes")

    if save_changes:
        updated = {
            "institution_id": selected_id,
            "institution_name": edit_name,
            "country": edit_country,
            "institution_type": edit_type,
            "publications_count": edit_publications,
            "citations_total": edit_citations,
            "intl_collab_pct": edit_collab,
            "primary_field": edit_field,
            "founded_year": edit_year
        }

        # Validate the edited record while ignoring its existing ID.
        errors = []
        for field in [
            "institution_name", "country",
            "institution_type", "primary_field"
        ]:
            if not str(updated[field]).strip():
                errors.append(f"{field.replace('_', ' ').title()} is required.")

        if not 0 <= edit_collab <= 100:
            errors.append("Collaboration must be between 0 and 100.")

        if errors:
            for error in errors:
                st.error(error)
        else:
            for column, value in updated.items():
                df.loc[
                    df["institution_id"].astype(str) == selected_id,
                    column
                ] = value

            try:
                manager.save(df)
                st.success("Institution updated successfully.")
                st.rerun()
            except (OSError, ValueError) as error:
                st.error(f"Could not save changes: {error}")


st.divider()
st.header("Delete an institution")

if "deleted_institution" not in st.session_state:
    st.session_state["deleted_institution"] = None

if df.empty:
    st.info("No institutions available to delete.")
else:
    delete_id = st.selectbox(
        "Select institution to delete",
        df["institution_id"].astype(str).tolist(),
        key="delete_institution"
    )

    delete_row = df[
        df["institution_id"].astype(str) == delete_id
    ].iloc[0]

    st.warning(
        f"Selected: {delete_row['institution_name']} "
        f"({delete_row['country']})"
    )

    confirm_delete = st.checkbox(
        "I confirm that I want to delete this institution.",
        key="confirm_delete"
    )

    if st.button("Delete Institution", disabled=not confirm_delete):
        deleted_row = df[
            df["institution_id"].astype(str) == delete_id
        ].iloc[0].to_dict()

        remaining = df[
            df["institution_id"].astype(str) != delete_id
        ].copy()

        try:
            manager.save(remaining)
            st.session_state["deleted_institution"] = deleted_row
            st.success("Institution deleted.")
            st.rerun()
        except (OSError, ValueError) as error:
            st.error(f"Could not delete institution: {error}")

deleted = st.session_state.get("deleted_institution")

if deleted:
    st.info(
        f"Last deleted: {deleted['institution_name']} "
        f"({deleted['institution_id']})"
    )

    if st.button("Undo Last Deletion"):
        current = manager.load()
        deleted_id = str(deleted["institution_id"])

        if current["institution_id"].astype(str).eq(deleted_id).any():
            st.error("This ID already exists; the record was not restored.")
        else:
            restored = pd.DataFrame([deleted], columns=COLUMNS)
            current = pd.concat([current, restored], ignore_index=True)

            try:
                manager.save(current)
                st.session_state["deleted_institution"] = None
                st.success("Institution restored.")
                st.rerun()
            except (OSError, ValueError) as error:
                st.error(f"Could not restore institution: {error}")


st.divider()
st.header("Data Quality Report")

# Check missing values, including blank strings in text columns
quality_df = df.copy()
for column in quality_df.select_dtypes(include=["object", "string"]).columns:
    quality_df[column] = quality_df[column].replace(r"^\\s*$", pd.NA, regex=True)

missing_count = int(quality_df.isna().sum().sum())

# Check duplicate institution IDs
duplicate_count = int(
    df["institution_id"].astype(str).duplicated().sum()
)

col1, col2, col3 = st.columns(3)
col1.metric("Total records", len(df))
col2.metric("Missing cells", missing_count)
col3.metric("Duplicate IDs", duplicate_count)

missing_by_column = quality_df.isna().sum()
missing_by_column = missing_by_column[missing_by_column > 0]

if missing_by_column.empty:
    st.success("No missing values found.")
else:
    st.warning("Some fields contain missing values.")
    st.dataframe(
        missing_by_column.rename("Missing values").reset_index(
            names="Column"
        ),
        use_container_width=True,
        hide_index=True
    )

if duplicate_count:
    st.warning("Duplicate institution IDs were found.")
else:
    st.success("All institution IDs are unique.")


st.divider()
st.header("Research Performance Analysis")

# Work on a copy so the original DataFrame stays unchanged.
analysis = view.copy()

analysis["publications_count"] = pd.to_numeric(
    analysis["publications_count"], errors="coerce"
)
analysis["citations_total"] = pd.to_numeric(
    analysis["citations_total"], errors="coerce"
)
analysis["intl_collab_pct"] = pd.to_numeric(
    analysis["intl_collab_pct"], errors="coerce"
)

# Avoid division by zero.
analysis["citations_per_publication"] = (
    analysis["citations_total"]
    / analysis["publications_count"].where(
        analysis["publications_count"] > 0
    )
)

st.subheader("1. Average citations per publication by institution type")

impact = (
    analysis.groupby("institution_type")[
        "citations_per_publication"
    ]
    .mean()
    .round(2)
    .reset_index()
)

st.dataframe(impact, use_container_width=True, hide_index=True)

st.subheader("2. Number of institutions by country")

country_stats = (
    analysis.groupby("country")
    .size()
    .reset_index(name="institution_count")
    .sort_values("institution_count", ascending=False)
)

st.dataframe(
    country_stats,
    use_container_width=True,
    hide_index=True
)

st.subheader("3. Top 5 institutions by international collaboration")

top_collaborators = (
    analysis.dropna(subset=["intl_collab_pct"])
    .sort_values("intl_collab_pct", ascending=False)
    .head(5)
    [["institution_name", "country", "intl_collab_pct"]]
)

st.dataframe(
    top_collaborators,
    use_container_width=True,
    hide_index=True
)

st.divider()
st.header("Download Report")

st.write(
    "Download the institution records currently displayed "
    "after applying your search and filters."
)

report = view.copy()
report["citations_per_publication"] = (
    pd.to_numeric(report["citations_total"], errors="coerce")
    / pd.to_numeric(
        report["publications_count"], errors="coerce"
    ).where(
        pd.to_numeric(
            report["publications_count"], errors="coerce"
        ) > 0
    )
).round(2)

report["report_generated_at"] = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)

csv_report = report.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download Institutions Report (CSV)",
    data=csv_report,
    file_name=f"institutions_report_{datetime.now():%Y%m%d_%H%M%S}.csv",
    mime="text/csv"
)

if not df.empty:
    df["publications_count"] = pd.to_numeric(
        df["publications_count"], errors="coerce"
    )
    df["citations_total"] = pd.to_numeric(
        df["citations_total"], errors="coerce"
    )

    left, right = st.columns(2)

    with left:
        fig = px.scatter(
            df,
            x="publications_count",
            y="citations_total",
            color="institution_type",
            hover_name="institution_name",
            title="Publications vs Citations"
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        counts = df["country"].value_counts().reset_index()
        counts.columns = ["country", "institution_count"]

        fig = px.bar(
            counts,
            x="country",
            y="institution_count",
            title="Institutions per Country"
        )
        st.plotly_chart(fig, use_container_width=True)