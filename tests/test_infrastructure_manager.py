import pandas as pd
import pytest

from csv_manager import CSVManager
from infrastructure_manager import (COLUMNS, LOG_COLUMNS, InfrastructureManager, build_report, tier_for)


def record(record_id="INF1", **changes):
    row = dict(record_id=record_id, country="India", year=2021,
               internet_penetration_pct=43.0, hightech_exports_pct=10.0,
               stem_graduates_per_1000=5.1, innovation_index_score=36.0,
               infrastructure_tier="Low")
    row.update(changes)
    return row


def high(record_id="INF2", **changes):
    row = dict(record_id=record_id, country="Germany", year=2021,
               internet_penetration_pct=91.5, hightech_exports_pct=15.0,
               stem_graduates_per_1000=11.2, innovation_index_score=57.0,
               infrastructure_tier="High")
    row.update(changes)
    return row


@pytest.fixture
def manager(tmp_path):
    return InfrastructureManager(tmp_path / "infrastructure.csv")


def test_shared_interface_and_empty_files(manager):
    assert isinstance(manager, CSVManager)
    assert manager.columns == COLUMNS
    assert manager.load().empty
    with pytest.raises(AttributeError):
        manager.file_path = "elsewhere.csv"
    columns = manager.columns
    columns.clear()
    assert manager.columns == COLUMNS
    manager.save(pd.DataFrame(columns=COLUMNS))
    assert manager.load().empty
    with open(manager.file_path, "w") as handle:
        handle.write("")
    assert manager.load().empty
    assert manager.summary()["by_tier"].empty


@pytest.mark.parametrize("value,expected", [(99.0, "High"), (85.0, "High"), (84.9, "Medium"),
                                            (60.0, "Medium"), (59.9, "Low"), (0.0, "Low")])
def test_tier_bands(value, expected):
    assert tier_for(value) == expected


def test_tier_of_missing_value_is_missing():
    assert pd.isna(tier_for(None))
    assert pd.isna(tier_for(float("nan")))


@pytest.mark.parametrize("identifier", ["001", "NA"])
def test_crud_persists_and_preserves_identifier(manager, identifier):
    assert manager.add_record(record(identifier))[0]
    reopened = InfrastructureManager(manager.file_path)
    assert reopened.load().iloc[0]["record_id"] == identifier
    assert manager.update_record(identifier, record(identifier, innovation_index_score=38.0))[0]
    assert manager.load().iloc[0]["innovation_index_score"] == 38.0
    assert manager.delete_record(identifier)[0]
    assert manager.load().empty
    actions = manager.activity_log.read()["action"].tolist()
    assert actions == ["ADD", "UPDATE", "DELETE"]


def test_duplicate_identifier_and_country_year_are_rejected(manager):
    assert manager.add_record(record())[0]
    assert "Record ID 'INF1' already exists." in manager.add_record(record())[1]
    errors = manager.add_record(record("INF9"))[1]
    assert "A record already exists for this country and year." in errors
    assert manager.add_record(record("INF9", year=2022))[0]


def test_tier_must_match_connectivity(manager):
    errors = manager.add_record(record(infrastructure_tier="High"))[1]
    assert any("belongs to the Low tier" in message for message in errors)
    assert "Choose a valid infrastructure tier." in manager.add_record(record(infrastructure_tier="Great"))[1]


@pytest.mark.parametrize("changes,fragment", [
    ({"internet_penetration_pct": 140.0}, "internet penetration pct must be between 0 and 100."),
    ({"innovation_index_score": -1}, "innovation_index_score must be a finite, non-negative number."),
    ({"year": 2100}, "Year must be a whole number between 1900 and"),
    ({"year": 2021.5}, "Year must be a whole number between 1900 and"),
    ({"country": "  "}, "country is required."),
    ({"stem_graduates_per_1000": "many"}, "stem_graduates_per_1000 must be a finite, non-negative number."),
])
def test_invalid_input_is_rejected_with_a_message(manager, changes, fragment):
    errors = manager.add_record(record(**changes))[1]
    assert any(fragment in message for message in errors)


def test_out_of_range_connectivity_does_not_also_claim_a_tier(manager):
    errors = manager.add_record(record(internet_penetration_pct=140.0))[1]
    assert not any("belongs to the" in message for message in errors)


def test_missing_and_invalid_source_values_become_missing_not_zero(manager):
    manager.save(pd.DataFrame([record(), high()])[COLUMNS])
    with open(manager.file_path) as handle:
        text = handle.read().replace("36.0", "").replace("15.0", "oops")
    with open(manager.file_path, "w") as handle:
        handle.write(text)
    df = manager.load()
    quality = manager.data_quality(df)
    assert quality["missing_pct"]["innovation_index_score"] == 50.0
    assert quality["invalid_numeric"]["hightech_exports_pct"] == 1
    clean = manager.clean_data(df)
    assert clean["innovation_index_score"].isna().sum() == 1
    assert clean["hightech_exports_pct"].isna().sum() == 1
    # A missing score must not be averaged in as zero.
    assert clean["innovation_index_score"].mean() == 57.0


def test_ambiguous_rows_are_excluded_from_analysis(manager):
    manager.save(pd.DataFrame([record(), record(), high()])[COLUMNS])
    df = manager.load()
    assert manager.data_quality(df)["duplicate_ids"] == 1
    assert manager.data_quality(df)["duplicate_country_years"] == 1
    assert len(manager.analysis_rows(df)) == 1
    assert not manager.update_record("INF1", record())[0]
    assert not manager.delete_record("INF1")[0]


def test_tier_mismatch_is_reported_without_changing_the_file(manager):
    manager.save(pd.DataFrame([record(infrastructure_tier="High"), high()])[COLUMNS])
    df = manager.load()
    assert manager.data_quality(df)["tier_mismatches"] == 1
    assert manager.load().iloc[0]["infrastructure_tier"] == "High"


def test_summary_group_comparison_and_derived_columns(manager):
    manager.save(pd.DataFrame([record(), high(), high("INF3", year=2022, innovation_index_score=59.0)])[COLUMNS])
    stats = manager.summary(manager.load())
    assert stats["analysis_records"] == 3 and stats["countries"] == 2
    assert stats["by_tier"].loc["High", "countries"] == 1
    assert stats["by_tier"].loc["High", "avg_innovation_index"] == 58.0
    assert stats["high_low_gap"] == pytest.approx(22.0)
    latest = stats["latest_by_country"].set_index("country")
    assert latest.loc["Germany", "year"] == 2022
    assert latest.loc["Germany", "index_per_stem_graduate"] == pytest.approx(59.0 / 11.2)
    assert latest.loc["Germany", "innovation_rank"] == 1


def test_zero_graduates_give_an_unavailable_ratio(manager):
    manager.save(pd.DataFrame([record(stem_graduates_per_1000=0.0)])[COLUMNS])
    stats = manager.summary(manager.load())
    assert pd.isna(stats["latest_by_country"].iloc[0]["index_per_stem_graduate"])


def test_single_tier_view_has_no_comparable_gap(manager):
    manager.save(pd.DataFrame([high()])[COLUMNS])
    assert pd.isna(manager.summary(manager.load())["high_low_gap"])


def test_filter_search_tier_year_and_sort(manager):
    manager.save(pd.DataFrame([record(), high(), high("INF3", year=2022)])[COLUMNS])
    df = manager.load()
    assert len(manager.filter_data(df, country="ger")) == 2
    assert len(manager.filter_data(df, tiers=["Low"])) == 1
    assert len(manager.filter_data(df, years=[2022])) == 1
    descending = manager.filter_data(df, sort_by="innovation_index_score", ascending=False)
    assert descending.iloc[0]["innovation_index_score"] == 57.0


def test_report_states_filters_and_provenance(manager):
    manager.save(pd.DataFrame([record(), high()])[COLUMNS])
    df = manager.load()
    stats = manager.summary(df)
    report = build_report(df, ["Tiers: all"], stats)
    assert "INNOVATION INFRASTRUCTURE - SUMMARY REPORT" in report
    assert "Records in view: 2" in report
    assert "Tiers: all" in report
    assert "synthetic demonstration records" in report


def test_unreadable_file_is_reported_not_raised(manager):
    with open(manager.file_path, "w") as handle:
        handle.write("record_id,country\nX,India\n")
    with pytest.raises(ValueError):
        manager.load()
    assert not manager.add_record(record())[0]


def test_activity_log_records_each_change_with_a_timestamp(manager):
    assert manager.activity_log.read().empty
    manager.add_record(record())
    manager.update_record("INF1", record(innovation_index_score=37.0))
    manager.delete_record("INF1")
    log = manager.activity_log.read()
    assert log.columns.tolist() == LOG_COLUMNS
    assert log["action"].tolist() == ["ADD", "UPDATE", "DELETE"]
    assert log["record_id"].tolist() == ["INF1", "INF1", "INF1"]
    assert all(entry.endswith("+00:00") for entry in log["logged_at_utc"])
    assert "innovation_index_score" in log.iloc[1]["detail"]
    assert manager.activity_log.summary()["entries"] == 3
    assert manager.activity_log.summary()["actions"]["ADD"] == 1


def test_rejected_change_is_not_logged(manager):
    manager.add_record(record())
    manager.add_record(record())
    manager.update_record("NOPE", record())
    manager.delete_record("NOPE")
    assert manager.activity_log.read()["action"].tolist() == ["ADD"]


def test_log_shows_most_recent_first_and_survives_a_damaged_file(manager):
    for index in range(1, 13):
        manager.add_record(record(f"INF{index}", year=2000 + index))
    recent = manager.activity_log.recent(10)
    assert len(recent) == 10
    assert recent.iloc[0]["logged_at_utc"] >= recent.iloc[-1]["logged_at_utc"]
    with open(manager.activity_log.file_path, "w") as handle:
        handle.write("not,a,valid,log\n")
    assert manager.activity_log.read().empty
    assert manager.add_record(record("INF99", year=1999))[0]


def test_log_file_is_separate_from_the_dataset(manager):
    manager.add_record(record())
    assert str(manager.activity_log.file_path) != str(manager.file_path)
    assert manager.load().columns.tolist() == COLUMNS
