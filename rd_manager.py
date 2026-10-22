"""Member 1: research spending records and calculations."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from csv_manager import CSVManager

ROOT = Path(__file__).resolve().parent
RD_FILE = ROOT / "data" / "rd_investment.csv"
COLUMNS = ["record_id", "country", "iso_code", "year", "gerd_pct_gdp",
           "gerd_usd_millions", "researchers_per_million", "funding_sector"]
SECTORS = ["Business", "Government", "Higher Education", "Private Non-profit"]
NUMERIC = ["year", "gerd_pct_gdp", "gerd_usd_millions", "researchers_per_million"]
CURRENT_YEAR = datetime.now().year


class ResearchSpendingManager(CSVManager):
    def __init__(self, file_path=RD_FILE):
        super().__init__(file_path, COLUMNS)

    def load(self):
        df = super().load()
        # Keep text identifiers (including leading zeroes) intact.
        if not df.empty:
            text_columns = [c for c in COLUMNS if c not in NUMERIC]
            text = pd.read_csv(self.file_path, dtype="string", usecols=text_columns, keep_default_na=False)
            for column in text_columns:
                df[column] = text[column].str.strip().replace("", pd.NA)
        return df

    def clean_data(self, df):
        """Return an analysis copy; never replace invalid source values on disk."""
        clean = df.copy()
        for column in COLUMNS:
            if column not in NUMERIC:
                clean[column] = clean[column].astype("string").str.strip().replace("", pd.NA)
        for column in NUMERIC:
            values = pd.to_numeric(clean[column], errors="coerce").astype(float)
            valid = np.isfinite(values) & (values >= 0)
            if column == "year":
                valid &= values.between(1900, CURRENT_YEAR) & (values % 1 == 0)
            if column == "gerd_pct_gdp":
                valid &= values <= 100
            clean[column] = values.where(valid)
        return clean

    def data_quality(self, df):
        clean = self.clean_data(df)
        missing = df.copy().replace(r"^\s*$", pd.NA, regex=True)
        percentages = missing.isna().mean().mul(100).fillna(0).round(2)
        invalid = {}
        for column in NUMERIC:
            invalid[column] = int((missing[column].notna() & clean[column].isna()).sum())
        keys = ["country", "year", "funding_sector"]
        return {
            "total": len(df),
            "duplicate_ids": int(clean["record_id"].dropna().duplicated().sum()),
            "duplicate_sector_rows": int(clean.duplicated(keys).sum()),
            "missing_pct": percentages,
            "invalid_numeric": pd.Series(invalid, name="invalid_values"),
        }

    def validate(self, record, df, ignore_id=None):
        errors = []
        for column in ["record_id", "country", "iso_code", "funding_sector"]:
            value = record.get(column)
            if value is None or pd.isna(value) or not str(value).strip():
                errors.append(f"{column} is required.")
        record_id = str(record.get("record_id", "")).strip()
        others = df.copy()
        if ignore_id is not None:
            others = others[others["record_id"].astype(str) != str(ignore_id)]
        if record_id in others["record_id"].astype(str).str.strip().values:
            errors.append(f"Record ID '{record_id}' already exists.")
        iso = str(record.get("iso_code", "")).strip().upper()
        if len(iso) != 3 or not iso.isascii() or not iso.isalpha():
            errors.append("ISO code must contain three letters, for example IND.")
        if str(record.get("funding_sector", "")).strip() not in SECTORS:
            errors.append("Choose a valid funding sector.")
        numbers = {}
        for column in NUMERIC:
            try:
                if isinstance(record.get(column), (bool, np.bool_)):
                    raise ValueError
                value = float(record.get(column))
                if not np.isfinite(value) or value < 0:
                    raise ValueError
                numbers[column] = value
                if column == "year" and (value % 1 or not 1900 <= value <= CURRENT_YEAR):
                    errors.append(f"Year must be a whole number between 1900 and {CURRENT_YEAR}.")
                if column == "gerd_pct_gdp" and value > 100:
                    errors.append("GDP percentage must be between 0 and 100.")
            except (ValueError, TypeError, OverflowError):
                errors.append(f"{column} must be a finite, non-negative number.")
        country = str(record.get("country", "")).strip()
        clean = self.clean_data(others)
        country_match = clean["country"].str.casefold().eq(country.casefold()).fillna(False)
        iso_match = clean["iso_code"].str.upper().eq(iso).fillna(False)
        known_country = clean["country"].notna() & clean["iso_code"].notna()
        if (((country_match & ~iso_match) | (iso_match & ~country_match)) & known_country).any():
            errors.append("Country and ISO code must match the existing country spelling and code.")
        if "year" in numbers:
            same_year = clean[(country_match | iso_match) & clean["year"].eq(numbers["year"])]
            if same_year["funding_sector"].eq(str(record.get("funding_sector", "")).strip()).any():
                errors.append("A record already exists for this country, year and funding sector.")
            if "gerd_pct_gdp" in numbers:
                total = same_year["gerd_pct_gdp"].sum() + numbers["gerd_pct_gdp"]
                if total > 100:
                    errors.append("Combined sector GDP percentages cannot exceed 100.")
            if "researchers_per_million" in numbers:
                workforce = same_year["researchers_per_million"].dropna()
                if not np.isclose(workforce, numbers["researchers_per_million"]).all():
                    errors.append("Researchers per million must agree across this country's sectors in this year.")
        return errors

    def _clean_record(self, record, existing):
        row = {}
        for column in COLUMNS:
            row[column] = str(record[column]).strip()
        row["iso_code"] = row["iso_code"].upper()
        names = existing.loc[existing["iso_code"].astype(str).str.upper().eq(row["iso_code"]), "country"].dropna()
        if not names.empty:
            row["country"] = str(names.iloc[0]).strip()
        for column in NUMERIC:
            row[column] = float(record[column])
        row["year"] = int(row["year"])
        return row

    def add_record(self, record):
        try:
            df = self.load()
            errors = self.validate(record, df)
            if errors:
                return False, errors
            row = self._clean_record(record, df)
            df.loc[len(df)] = [row[c] for c in COLUMNS]
            self.save(df)
            return True, [f"Record {row['record_id']} added."]
        except (OSError, ValueError, UnicodeError) as error:
            return False, [f"Could not add record: {error}"]

    def update_record(self, record_id, record):
        try:
            df = self.load()
            mask = df["record_id"].astype(str).eq(str(record_id))
            if mask.sum() != 1:
                return False, ["Select a unique existing record ID; missing or duplicate IDs cannot be updated."]
            record = dict(record, record_id=record_id)
            errors = self.validate(record, df, ignore_id=record_id)
            if errors:
                return False, errors
            row = self._clean_record(record, df[~mask])
            # Object columns also allow repairing a CSV containing invalid numeric text.
            df = df.astype(object)
            df.loc[mask, COLUMNS] = [row[c] for c in COLUMNS]
            self.save(df)
            return True, [f"Record {record_id} updated."]
        except (OSError, ValueError, UnicodeError) as error:
            return False, [f"Could not update record: {error}"]

    def delete_record(self, record_id):
        try:
            df = self.load()
            mask = df["record_id"].astype(str).eq(str(record_id))
            if mask.sum() != 1:
                return False, ["Select a unique existing record ID; missing or duplicate IDs cannot be deleted."]
            self.save(df[~mask])
            return True, [f"Record {record_id} deleted."]
        except (OSError, ValueError, UnicodeError) as error:
            return False, [f"Could not delete record: {error}"]

    def filter_data(self, df, country="", sectors=None, years=None,
                    sort_by="record_id", ascending=True):
        view = self.clean_data(df)
        if country.strip():
            view = view[view["country"].str.contains(country.strip(), case=False, regex=False, na=False)]
        if sectors:
            view = view[view["funding_sector"].isin(sectors)]
        if years:
            view = view[view["year"].isin(years)]
        return view.sort_values(sort_by, ascending=ascending, na_position="last", kind="stable")

    def analysis_rows(self, df):
        clean = self.clean_data(df)
        valid = clean[["record_id", "country", "iso_code", "year", "funding_sector"]].notna().all(axis=1)
        valid &= clean["iso_code"].str.fullmatch(r"[A-Za-z]{3}", na=False)
        valid &= clean["funding_sector"].isin(SECTORS)
        valid &= ~clean["record_id"].duplicated(keep=False)
        valid &= ~clean.duplicated(["country", "year", "funding_sector"], keep=False)
        return clean[valid].copy()

    def country_year_totals(self, df):
        rows = self.analysis_rows(df)
        output = []
        for (country, year), group in rows.groupby(["country", "year"]):
            workforce = group["researchers_per_million"].dropna().unique()
            pct = group["gerd_pct_gdp"].sum(min_count=len(group))
            output.append({
                "country": country, "year": int(year),
                "gerd_usd_millions": group["gerd_usd_millions"].sum(min_count=len(group)),
                "gerd_pct_gdp": pct if pct <= 100 else np.nan,
                "researchers_per_million": workforce[0] if len(workforce) == 1 else np.nan,
                "sectors_observed": ", ".join(sorted(group["funding_sector"])),
            })
        return pd.DataFrame(output, columns=["country", "year", "gerd_usd_millions",
                                             "gerd_pct_gdp", "researchers_per_million", "sectors_observed"])

    def summary(self, df=None):
        if df is None:
            df = self.load()
        rows = self.analysis_rows(df)
        totals = self.country_year_totals(df).sort_values(["country", "year"])
        totals["gap_to_2_pct_points"] = (2 - totals["gerd_pct_gdp"]).clip(lower=0)
        totals["yoy_change_pct"] = np.nan
        totals["direction"] = "N/A"
        growth = []
        for country, group in totals.groupby("country"):
            previous = group["gerd_usd_millions"].shift()
            consecutive = group["year"].diff().eq(1) & group["sectors_observed"].eq(group["sectors_observed"].shift())
            change = (group["gerd_usd_millions"] / previous.where(previous > 0) - 1) * 100
            totals.loc[group.index, "yoy_change_pct"] = change.where(consecutive)
            available = group.dropna(subset=["gerd_usd_millions"])
            value = np.nan
            if (len(available) > 1 and available.iloc[0]["gerd_usd_millions"] > 0
                    and available.iloc[0]["sectors_observed"] == available.iloc[-1]["sectors_observed"]):
                value = (available.iloc[-1]["gerd_usd_millions"] / available.iloc[0]["gerd_usd_millions"] - 1) * 100
            growth.append({"country": country, "start_year": available["year"].min(),
                           "end_year": available["year"].max(), "total_growth_pct": value})
        for index, change in totals["yoy_change_pct"].items():
            if pd.notna(change):
                totals.at[index, "direction"] = "Up" if change > 0 else ("Down" if change < 0 else "Unchanged")
        latest = totals.dropna(subset=["gerd_usd_millions"]).groupby("country").tail(1)
        yearly = []
        for year, group in totals.groupby("year"):
            yearly.append({"year": year, "gerd_usd_millions": group["gerd_usd_millions"].sum(min_count=len(group)),
                           "countries_observed": len(group)})
        return {
            "total": len(df), "analysis_records": len(rows), "country_year": totals,
            "average_by_sector": rows.groupby("funding_sector")["gerd_usd_millions"].mean(),
            "total_by_year": pd.DataFrame(yearly, columns=["year", "gerd_usd_millions", "countries_observed"]),
            "benchmark": totals[totals["gerd_pct_gdp"] >= 2],
            "growth": pd.DataFrame(growth, columns=["country", "start_year", "end_year", "total_growth_pct"]),
            "top_spenders": latest.sort_values("gerd_usd_millions", ascending=False).head(10),
        }


def build_report(view, filters, stats):
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = ["RESEARCH SPENDING - SUMMARY REPORT", f"Generated (UTC): {generated}",
             f"Records in view: {len(view)}", "Filters applied: " + "; ".join(filters),
             "Sector contributions are summed once per country-year; workforce is not summed.",
             "Filtered sector totals are partial coverage, not national estimates.",
             "Source: synthetic demonstration records unless replaced with documented observations."]
    for key in ["average_by_sector", "total_by_year", "benchmark", "country_year", "growth"]:
        lines.extend(["", key.replace("_", " ").title(), stats[key].to_string()])
    return "\n".join(lines)
