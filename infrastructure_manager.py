"""Member 4: innovation infrastructure records and calculations."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from csv_manager import CSVManager

ROOT = Path(__file__).resolve().parent
INFRASTRUCTURE_FILE = ROOT / "data" / "infrastructure.csv"
# Audit trail owned solely by this page. No other module reads or writes it.
LOG_FILE = ROOT / "data" / "infrastructure_log.csv"
LOG_COLUMNS = ["logged_at_utc", "action", "record_id", "detail"]
COLUMNS = ["record_id", "country", "year", "internet_penetration_pct", "hightech_exports_pct",
           "stem_graduates_per_1000", "innovation_index_score", "infrastructure_tier"]
TIERS = ["High", "Medium", "Low"]
NUMERIC = ["year", "internet_penetration_pct", "hightech_exports_pct",
           "stem_graduates_per_1000", "innovation_index_score"]
PERCENTAGE = ["internet_penetration_pct", "hightech_exports_pct", "innovation_index_score"]
# Graduates per 1000 people is a density, not a percentage; 100 is a generous upper bound.
MAXIMUM = {column: 100.0 for column in PERCENTAGE}
MAXIMUM["stem_graduates_per_1000"] = 100.0
CURRENT_YEAR = datetime.now().year
# Connectivity bands used to classify a country-year. High is the most connected band.
TIER_BANDS = [("High", 85.0), ("Medium", 60.0), ("Low", 0.0)]


def tier_for(internet_pct):
    """Return the connectivity tier implied by an internet penetration percentage."""
    if internet_pct is None or pd.isna(internet_pct):
        return pd.NA
    for name, floor in TIER_BANDS:
        if float(internet_pct) >= floor:
            return name
    return pd.NA


class ActivityLog(CSVManager):
    """Append-only audit trail for infrastructure changes, owned by this page alone."""

    def __init__(self, file_path=LOG_FILE):
        super().__init__(file_path, LOG_COLUMNS)

    def summary(self, df=None):
        if df is None:
            df = self.read()
        return {"entries": len(df), "actions": df["action"].value_counts().to_dict()}

    def read(self):
        """Return the log, or an empty log if it is missing or unreadable."""
        try:
            return super().load()
        except (OSError, ValueError, UnicodeError):
            return self._empty_frame()

    def append(self, action, record_id, detail):
        """Record one change. A failed log write must never lose the data change."""
        try:
            df = self.read()
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            df.loc[len(df)] = [stamp, action, str(record_id), detail]
            self.save(df)
            return True
        except (OSError, ValueError, UnicodeError):
            return False

    def recent(self, limit=10):
        df = self.read()
        if df.empty:
            return df
        # Entries within the same second keep file order, so reverse first: newest wins ties.
        return df.iloc[::-1].sort_values("logged_at_utc", ascending=False, kind="stable").head(limit)


class InfrastructureManager(CSVManager):
    """Innovation infrastructure: connectivity, exports, STEM supply and index score."""

    def __init__(self, file_path=INFRASTRUCTURE_FILE, log_path=None):
        super().__init__(file_path, COLUMNS)
        if log_path is None:
            log_path = Path(self.file_path).with_name("infrastructure_log.csv")
        self.activity_log = ActivityLog(log_path)

    def load(self):
        df = super().load()
        # Keep text identifiers (including leading zeroes) exactly as stored.
        if not df.empty:
            text_columns = [column for column in COLUMNS if column not in NUMERIC]
            text = pd.read_csv(self.file_path, dtype="string", usecols=text_columns, keep_default_na=False)
            for column in text_columns:
                df[column] = text[column].str.strip().replace("", pd.NA)
        return df

    def clean_data(self, df):
        """Return an analysis copy. Invalid source values become missing, never zero."""
        clean = df.copy()
        for column in COLUMNS:
            if column not in NUMERIC:
                clean[column] = clean[column].astype("string").str.strip().replace("", pd.NA)
        for column in NUMERIC:
            values = pd.to_numeric(clean[column], errors="coerce").astype(float)
            valid = np.isfinite(values) & (values >= 0)
            if column == "year":
                valid &= values.between(1900, CURRENT_YEAR) & (values % 1 == 0)
            else:
                valid &= values <= MAXIMUM[column]
            clean[column] = values.where(valid)
        return clean

    def data_quality(self, df):
        clean = self.clean_data(df)
        present = df.copy().replace(r"^\s*$", pd.NA, regex=True)
        invalid = {}
        for column in NUMERIC:
            invalid[column] = int((present[column].notna() & clean[column].isna()).sum())
        mismatched = 0
        if not clean.empty:
            expected = clean["internet_penetration_pct"].map(tier_for)
            known = expected.notna() & clean["infrastructure_tier"].notna()
            mismatched = int((known & expected.ne(clean["infrastructure_tier"])).sum())
        return {
            "total": len(df),
            "duplicate_ids": int(clean["record_id"].dropna().duplicated().sum()),
            "duplicate_country_years": int(clean.duplicated(["country", "year"]).sum()),
            "tier_mismatches": mismatched,
            "missing_pct": present.isna().mean().mul(100).fillna(0).round(2),
            "invalid_numeric": pd.Series(invalid, name="invalid_values"),
        }

    def validate(self, record, df, ignore_id=None):
        errors = []
        for column in ["record_id", "country", "infrastructure_tier"]:
            value = record.get(column)
            if value is None or pd.isna(value) or not str(value).strip():
                errors.append(f"{column} is required.")
        record_id = str(record.get("record_id", "")).strip()
        others = df.copy()
        if ignore_id is not None:
            others = others[others["record_id"].astype(str) != str(ignore_id)]
        if record_id in others["record_id"].astype(str).str.strip().values:
            errors.append(f"Record ID '{record_id}' already exists.")
        if str(record.get("infrastructure_tier", "")).strip() not in TIERS:
            errors.append("Choose a valid infrastructure tier.")
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
                if column != "year" and value > MAXIMUM[column]:
                    errors.append(f"{column.replace('_', ' ')} must be between 0 and {MAXIMUM[column]:.0f}.")
            except (ValueError, TypeError, OverflowError):
                errors.append(f"{column} must be a finite, non-negative number.")
        country = str(record.get("country", "")).strip()
        clean = self.clean_data(others)
        country_match = clean["country"].str.casefold().eq(country.casefold()).fillna(False)
        if "year" in numbers and (country_match & clean["year"].eq(numbers["year"])).any():
            errors.append("A record already exists for this country and year.")
        internet = numbers.get("internet_penetration_pct")
        # Only classify a value that is itself within range; otherwise the range error stands alone.
        if internet is not None and internet <= MAXIMUM["internet_penetration_pct"]:
            expected = tier_for(internet)
            if expected is not pd.NA and str(record.get("infrastructure_tier", "")).strip() != expected:
                errors.append(f"Internet penetration of {internet:.1f}% belongs to the {expected} tier.")
        return errors

    def _clean_record(self, record, existing):
        row = {}
        for column in COLUMNS:
            row[column] = str(record[column]).strip()
        # Reuse the spelling already on file so one country cannot appear twice.
        names = existing.loc[existing["country"].astype("string").str.casefold()
                             .eq(row["country"].casefold()).fillna(False), "country"].dropna()
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
            df.loc[len(df)] = [row[column] for column in COLUMNS]
            self.save(df)
            self.activity_log.append("ADD", row["record_id"],
                                     f"{row['country']} {row['year']}, tier {row['infrastructure_tier']}")
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
            # Object columns also allow repairing a CSV that holds invalid numeric text.
            df = df.astype(object)
            previous = df.loc[mask].iloc[0].to_dict()
            df.loc[mask, COLUMNS] = [row[column] for column in COLUMNS]
            self.save(df)
            changed = [column for column in COLUMNS
                       if str(previous.get(column)) != str(row[column])]
            self.activity_log.append("UPDATE", record_id,
                                     "changed " + (", ".join(changed) if changed else "nothing"))
            return True, [f"Record {record_id} updated."]
        except (OSError, ValueError, UnicodeError) as error:
            return False, [f"Could not update record: {error}"]

    def delete_record(self, record_id):
        try:
            df = self.load()
            mask = df["record_id"].astype(str).eq(str(record_id))
            if mask.sum() != 1:
                return False, ["Select a unique existing record ID; missing or duplicate IDs cannot be deleted."]
            removed = df[mask].iloc[0].to_dict()
            self.save(df[~mask])
            self.activity_log.append("DELETE", record_id,
                                     f"{removed.get('country')} {removed.get('year')} removed")
            return True, [f"Record {record_id} deleted."]
        except (OSError, ValueError, UnicodeError) as error:
            return False, [f"Could not delete record: {error}"]

    def filter_data(self, df, country="", tiers=None, years=None,
                    sort_by="record_id", ascending=True):
        view = self.clean_data(df)
        if country.strip():
            view = view[view["country"].str.contains(country.strip(), case=False, regex=False, na=False)]
        if tiers:
            view = view[view["infrastructure_tier"].isin(tiers)]
        if years:
            view = view[view["year"].isin(years)]
        return view.sort_values(sort_by, ascending=ascending, na_position="last", kind="stable")

    def analysis_rows(self, df):
        """Rows with unambiguous keys and a usable tier, safe to aggregate."""
        clean = self.clean_data(df)
        valid = clean[["record_id", "country", "year", "infrastructure_tier"]].notna().all(axis=1)
        valid &= clean["infrastructure_tier"].isin(TIERS)
        valid &= ~clean["record_id"].duplicated(keep=False)
        valid &= ~clean.duplicated(["country", "year"], keep=False)
        return clean[valid].copy()

    def derived_columns(self, df):
        """Add the computed column and the rank column used on the page."""
        view = df.copy()
        graduates = view["stem_graduates_per_1000"].where(view["stem_graduates_per_1000"] > 0)
        # Computed column: index points produced per STEM graduate per 1000 people.
        view["index_per_stem_graduate"] = view["innovation_index_score"] / graduates
        view["innovation_rank"] = view["innovation_index_score"].rank(ascending=False, method="min")
        return view

    def summary(self, df=None):
        if df is None:
            df = self.load()
        rows = self.analysis_rows(df)
        grouped = rows.groupby("infrastructure_tier", dropna=True)
        by_tier = pd.DataFrame({
            "records": grouped["record_id"].count(),
            "countries": grouped["country"].nunique(),
            "avg_innovation_index": grouped["innovation_index_score"].mean(),
            "avg_stem_graduates_per_1000": grouped["stem_graduates_per_1000"].mean(),
            "avg_internet_penetration_pct": grouped["internet_penetration_pct"].mean(),
        }).reindex([tier for tier in TIERS if tier in grouped.groups])
        latest = rows.dropna(subset=["innovation_index_score"]).sort_values("year").groupby("country").tail(1)
        latest = self.derived_columns(latest).sort_values("innovation_index_score", ascending=False)
        yearly = rows.groupby(["infrastructure_tier", "year"], as_index=False)["stem_graduates_per_1000"].mean()
        gap = np.nan
        if {"High", "Low"}.issubset(set(by_tier.index)):
            gap = by_tier.loc["High", "avg_innovation_index"] - by_tier.loc["Low", "avg_innovation_index"]
        return {
            "total": len(df),
            "analysis_records": len(rows),
            "countries": int(rows["country"].nunique()),
            "avg_innovation_index": rows["innovation_index_score"].mean(),
            "by_tier": by_tier,
            "latest_by_country": latest,
            "tier_year_graduates": yearly,
            "high_low_gap": gap,
            "scores": rows["innovation_index_score"].dropna(),
        }


def build_report(view, filters, stats):
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = ["INNOVATION INFRASTRUCTURE - SUMMARY REPORT",
             f"Generated (UTC): {generated}",
             f"Records in view: {len(view)}",
             "Filters applied: " + "; ".join(filters),
             f"Country-years with unambiguous keys: {stats['analysis_records']}",
             "Tiers are connectivity bands: High from 85%, Medium from 60%, Low below 60%.",
             "Missing or invalid values are excluded from averages, never treated as zero.",
             "Source: synthetic demonstration records unless replaced with documented observations."]
    if pd.notna(stats["high_low_gap"]):
        lines.append(f"High minus Low average innovation index: {stats['high_low_gap']:.2f} points.")
    for key in ["by_tier", "latest_by_country", "tier_year_graduates"]:
        lines.extend(["", key.replace("_", " ").title(), stats[key].round(2).to_string()])
    return "\n".join(lines)
