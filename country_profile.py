"""Read-only Home integration. Institution records are an undated snapshot."""

from pathlib import Path

import numpy as np
import pandas as pd

from rd_manager import CURRENT_YEAR, ResearchSpendingManager

METRICS = ["gerd_pct_gdp", "patent_grants", "citations_per_publication", "innovation_index_score"]
COUNTRY_NAMES = {"usa": "United States", "us": "United States", "united states": "United States",
                 "united states of america": "United States", "uk": "United Kingdom",
                 "united kingdom": "United Kingdom", "republic of korea": "South Korea",
                 "south korea": "South Korea"}


def country_name(value):
    text = str(value).strip()
    return COUNTRY_NAMES.get(text.casefold(), text.title())


def read_dataset(path, required, identifier, warnings):
    try:
        df = pd.read_csv(path, dtype={identifier: "string"})
        missing = [column for column in required if column not in df.columns]
        if missing:
            warnings.append(f"{path.name}: unavailable; missing columns: {', '.join(missing)}.")
            return pd.DataFrame(columns=required)
        for column in ["country", identifier]:
            df[column] = df[column].astype("string").str.strip().replace("", pd.NA)
        usable = df["country"].notna() & df[identifier].notna() & ~df[identifier].duplicated(keep=False)
        if not usable.all():
            warnings.append(f"{path.name}: rows with missing keys or duplicate identifiers were excluded.")
        df = df[usable].copy()
        df["country"] = df["country"].map(country_name)
        return df
    except FileNotFoundError:
        warnings.append(f"{path.name}: file not supplied yet.")
        return pd.DataFrame(columns=required)
    except (OSError, ValueError, UnicodeError) as error:
        warnings.append(f"{path.name}: unavailable ({error}).")
        return pd.DataFrame(columns=required)


def number_column(df, column, maximum=None, integer=False):
    values = pd.to_numeric(df[column], errors="coerce").astype(float)
    valid = np.isfinite(values) & (values >= 0)
    if maximum is not None:
        valid &= values <= maximum
    if integer:
        valid &= values % 1 == 0
    return values.where(valid)


def load_profiles(data_dir):
    data_dir = Path(data_dir)
    warnings = []
    manager = ResearchSpendingManager(data_dir / "rd_investment.csv")
    try:
        rd = manager.load()
        rd["country"] = rd["country"].map(lambda value: country_name(value) if pd.notna(value) else pd.NA)
        rd = manager.country_year_totals(rd)
    except (OSError, ValueError, UnicodeError) as error:
        warnings.append(f"rd_investment.csv: unavailable ({error}).")
        rd = pd.DataFrame(columns=["country", "year", "gerd_pct_gdp", "gerd_usd_millions", "researchers_per_million"])
    if rd.empty:
        warnings.append("No usable research spending observations are available.")

    patents = read_dataset(data_dir / "patents.csv", ["patent_id", "country", "filing_year", "grants_count"],
                           "patent_id", warnings)
    patents["year"] = number_column(patents, "filing_year", integer=True)
    patents["year"] = patents["year"].where(patents["year"].between(1900, CURRENT_YEAR))
    patents["patent_grants"] = number_column(patents, "grants_count", integer=True)
    patents = patents.groupby(["country", "year"], as_index=False)["patent_grants"].agg(
        lambda values: values.sum(min_count=len(values)))

    infrastructure = read_dataset(data_dir / "infrastructure.csv", ["record_id", "country", "year", "innovation_index_score"],
                                  "record_id", warnings)
    infrastructure["year"] = number_column(infrastructure, "year", integer=True)
    infrastructure["year"] = infrastructure["year"].where(infrastructure["year"].between(1900, CURRENT_YEAR))
    infrastructure["innovation_index_score"] = number_column(infrastructure, "innovation_index_score", maximum=100)
    duplicate = infrastructure.duplicated(["country", "year"], keep=False)
    if duplicate.any():
        warnings.append("infrastructure.csv: ambiguous duplicate country-year observations were excluded.")
    infrastructure = infrastructure[~duplicate].dropna(subset=["year"])[["country", "year", "innovation_index_score"]]

    institutions = read_dataset(data_dir / "institutions.csv", ["institution_id", "country", "publications_count", "citations_total"],
                                "institution_id", warnings)
    institutions["publications_count"] = number_column(institutions, "publications_count", integer=True)
    institutions["citations_total"] = number_column(institutions, "citations_total", integer=True)
    snapshot = []
    for country, group in institutions.groupby("country"):
        pairs = group.dropna(subset=["publications_count", "citations_total"])
        pairs = pairs[pairs["publications_count"] > 0]
        publications = pairs["publications_count"].sum()
        impact = pairs["citations_total"].sum() / publications if publications > 0 else np.nan
        snapshot.append({"country": country, "institution_count": len(group),
                         "citations_per_publication": impact})
    snapshot = pd.DataFrame(snapshot, columns=["country", "institution_count", "citations_per_publication"])
    for frame in [rd, patents, infrastructure]:
        frame["country"] = frame["country"].astype("string")
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype(float)
    snapshot["country"] = snapshot["country"].astype("string")
    profiles = rd.merge(patents, on=["country", "year"], how="outer")
    profiles = profiles.merge(infrastructure, on=["country", "year"], how="outer")
    # Founded year is deliberately unused: institutions have no observation year.
    profiles = profiles.merge(snapshot, on="country", how="outer")
    return profiles, warnings


def score_profiles(profiles, year):
    # Include institution-only countries without assigning them an observation year.
    countries = profiles[["country"]].drop_duplicates()
    annual = profiles[profiles["year"].eq(year)].drop(columns=["institution_count", "citations_per_publication"])
    snapshot = profiles[["country", "institution_count", "citations_per_publication"]].drop_duplicates("country")
    result = countries.merge(annual, on="country", how="left").merge(snapshot, on="country", how="left")
    score_columns = []
    for metric in METRICS:
        values = pd.to_numeric(result[metric], errors="coerce")
        low, high = values.min(), values.max()
        column = metric + "_score"
        if pd.isna(low):
            result[column] = np.nan
        elif low == high:
            result[column] = values.where(values.isna(), 50.0)
        else:
            result[column] = 100 * (values - low) / (high - low)
        score_columns.append(column)
    result["components_available"] = result[score_columns].notna().sum(axis=1)
    result["provisional_score"] = result[score_columns].mean(axis=1).round(2)
    result["composite_score"] = result["provisional_score"].where(result["components_available"] == 4)
    return result.sort_values("country").reset_index(drop=True)
