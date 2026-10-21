from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from csv_manager import CSVManager
from rd_manager import COLUMNS, ResearchSpendingManager, build_report


def record(record_id="RD1", **changes):
    row = dict(record_id=record_id, country="India", iso_code="IND", year=2021,
               gerd_pct_gdp=1.0, gerd_usd_millions=100.0,
               researchers_per_million=250.0, funding_sector="Business")
    row.update(changes)
    return row


@pytest.fixture
def manager(tmp_path):
    return ResearchSpendingManager(tmp_path / "rd.csv")


def test_shared_interface_and_empty_files(manager):
    assert isinstance(manager, CSVManager)
    assert manager.load().empty
    assert manager.columns == COLUMNS
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
    assert manager.summary()["country_year"].empty


@pytest.mark.parametrize("identifier", ["001", "NA"])
def test_crud_persists_and_preserves_identifier(manager, identifier):
    assert manager.add_record(record(identifier))[0]
    reopened = ResearchSpendingManager(manager.file_path)
    assert reopened.load().iloc[0]["record_id"] == identifier
    assert not manager.add_record(record(identifier))[0]
    assert manager.update_record(identifier, record(gerd_usd_millions=150))[0]
    assert reopened.load().iloc[0]["gerd_usd_millions"] == 150
    assert not manager.update_record("absent", record())[0]
    assert not manager.delete_record("absent")[0]
    assert manager.delete_record(identifier)[0]
    assert reopened.load().empty


@pytest.mark.parametrize("field,value", [
    ("record_id", " "), ("country", None), ("iso_code", "IN"), ("iso_code", "123"),
    ("funding_sector", "Other"), ("year", 2021.5), ("year", 1899), ("year", 9999),
    ("year", "bad"), ("gerd_pct_gdp", 101), ("gerd_pct_gdp", -1),
    ("gerd_usd_millions", -10), ("gerd_usd_millions", "bad"),
    ("researchers_per_million", float("inf")), ("gerd_pct_gdp", float("nan")),
    ("researchers_per_million", True), ("gerd_usd_millions", None),
])
def test_invalid_input_never_writes(manager, field, value):
    assert manager.add_record(record())[0]
    before = open(manager.file_path, "rb").read()
    bad = record("RD2", year=2022)
    bad[field] = value
    success, messages = manager.add_record(bad)
    assert not success and messages
    assert open(manager.file_path, "rb").read() == before


def test_sector_keys_workforce_and_country_identity(manager):
    assert manager.add_record(record())[0]
    assert not manager.add_record(record("RD2"))[0]
    assert not manager.add_record(record("RD2", funding_sector="Government", researchers_per_million=300))[0]
    assert not manager.add_record(record("RD2", country="Bharat", year=2022))[0]
    assert not manager.add_record(record("RD2", iso_code="USA", year=2022))[0]
    assert manager.add_record(record("RD2", funding_sector="Government"))[0]
    assert manager.summary()["country_year"].iloc[0]["researchers_per_million"] == 250


def test_normalized_keys_do_not_create_duplicate_countries_or_sectors(manager):
    assert manager.add_record(record())[0]
    assert not manager.add_record(record("RD2", funding_sector=" Business "))[0]
    assert manager.add_record(record("RD2", country="india", year=2022))[0]
    assert manager.load()["country"].unique().tolist() == ["India"]


def test_failed_atomic_write_leaves_original(manager):
    assert manager.add_record(record())[0]
    before = open(manager.file_path, "rb").read()
    with patch("csv_manager.os.replace", side_effect=OSError("simulated interruption")):
        assert not manager.update_record("RD1", record(gerd_usd_millions=500))[0]
    assert open(manager.file_path, "rb").read() == before
    from pathlib import Path
    assert not list(Path(manager.file_path).parent.glob("*.tmp"))


def test_invalid_source_preserved_and_ambiguous_ids_rejected(manager):
    rows = [record(), record("RD2", year=2022, gerd_usd_millions="bad", country=" ")]
    manager.save(pd.DataFrame(rows))
    data = manager.load()
    quality = manager.data_quality(data)
    assert quality["missing_pct"]["country"] == 50
    assert quality["invalid_numeric"]["gerd_usd_millions"] == 1
    assert manager.add_record(record("RD3", year=2023))[0]
    assert manager.load().iloc[1]["gerd_usd_millions"] == "bad"
    manager.save(pd.DataFrame([record(), record()]))
    assert manager.summary()["analysis_records"] == 0
    assert not manager.update_record("RD1", record())[0]
    assert not manager.delete_record("RD1")[0]


def test_wrong_columns_and_malformed_csv(manager):
    with open(manager.file_path, "w") as handle:
        handle.write('wrong,columns\n1,2\n')
    assert not manager.add_record(record())[0]
    with pytest.raises(ValueError, match="Missing columns"):
        manager.load()
    with open(manager.file_path, "w") as handle:
        handle.write(','.join(COLUMNS) + '\n"unterminated')
    with pytest.raises(ValueError, match="Not a valid CSV"):
        manager.load()


def test_statistics_filters_and_report(manager):
    rows = [
        record("A", funding_sector="Business", gerd_pct_gdp=1.2, gerd_usd_millions=100),
        record("B", funding_sector="Government", gerd_pct_gdp=0.8, gerd_usd_millions=50),
        record("C", year=2022, gerd_pct_gdp=1.3, gerd_usd_millions=110),
        record("D", year=2022, funding_sector="Government", gerd_pct_gdp=0.9, gerd_usd_millions=55),
    ]
    frame = pd.DataFrame(rows)
    stats = manager.summary(frame)
    assert stats["average_by_sector"]["Business"] == 105
    assert stats["total_by_year"]["gerd_usd_millions"].tolist() == [150, 165]
    assert len(stats["benchmark"]) == 2
    assert stats["country_year"]["gap_to_2_pct_points"].tolist() == [0, 0]
    assert stats["country_year"].iloc[1]["yoy_change_pct"] == pytest.approx(10)
    assert stats["country_year"].iloc[1]["direction"] == "Up"
    assert stats["growth"].iloc[0]["total_growth_pct"] == pytest.approx(10)
    assert len(stats["top_spenders"]) == 1
    assert stats["top_spenders"].iloc[0]["year"] == 2022
    view = manager.filter_data(frame, "IND", ["Business"], [2022], "gerd_usd_millions", False)
    assert view["record_id"].tolist() == ["C"]
    assert manager.filter_data(frame, "[", [], []).empty
    report = build_report(view, ["Year: 2022", "Sector: Business"], manager.summary(view))
    assert "Generated (UTC):" in report and "Records in view: 1" in report
    assert "Year: 2022" in report and "Sector: Business" in report
    assert len(pd.read_csv(__import__("io").StringIO(view.to_csv(index=False)))) == 1


def test_missing_values_zero_baseline_and_nonconsecutive_years(manager):
    rows = [record("A", gerd_usd_millions=0), record("B", year=2023, gerd_usd_millions=100)]
    stats = manager.summary(pd.DataFrame(rows))
    assert stats["country_year"]["yoy_change_pct"].isna().all()
    assert stats["growth"]["total_growth_pct"].isna().all()
    rows.append(record("C", year=2023, funding_sector="Government", gerd_usd_millions=None))
    stats = manager.summary(pd.DataFrame(rows))
    assert pd.isna(stats["total_by_year"].iloc[-1]["gerd_usd_millions"])


def test_changed_sector_coverage_has_no_false_growth(manager):
    rows = [record("A"), record("B", year=2022), record("C", year=2022, funding_sector="Government")]
    stats = manager.summary(pd.DataFrame(rows))
    assert stats["country_year"]["yoy_change_pct"].isna().all()
    assert stats["growth"]["total_growth_pct"].isna().all()


@pytest.mark.parametrize("last,direction", [(80, "Down"), (100, "Unchanged"), (120, "Up")])
def test_growth_directions(manager, last, direction):
    stats = manager.summary(pd.DataFrame([record("A"), record("B", year=2022, gerd_usd_millions=last)]))
    assert stats["country_year"].iloc[-1]["direction"] == direction


def test_sample_dataset_valid():
    manager = ResearchSpendingManager()
    data = manager.load()
    assert len(data) == 144 and data["country"].nunique() == 12
    assert data["record_id"].str.startswith("SYN_RD").all()
    for _, row in data.iterrows():
        assert not manager.validate(row.to_dict(), data, ignore_id=row["record_id"])
    assert manager.data_quality(data)["missing_pct"].sum() == 0
    assert len(manager.summary(data)["top_spenders"]) == 10
