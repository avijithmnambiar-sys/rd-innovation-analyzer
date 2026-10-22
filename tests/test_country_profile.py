import pandas as pd
import pytest

from country_profile import METRICS, load_profiles, score_profiles
from rd_manager import ResearchSpendingManager
from test_rd_manager import record


def write_sources(tmp_path):
    ResearchSpendingManager(tmp_path / "rd_investment.csv").save(pd.DataFrame([
        record("R1", country="USA", iso_code="USA", gerd_pct_gdp=3),
        record("R2", country="India", iso_code="IND", gerd_pct_gdp=1),
    ]))
    pd.DataFrame([
        ["P1", "United States", 2021, 100], ["P2", "India", 2021, 20], ["P3", "India", 2022, 999],
    ], columns=["patent_id", "country", "filing_year", "grants_count"]).to_csv(tmp_path / "patents.csv", index=False)
    pd.DataFrame([
        ["I1", "USA", 10, 100, 1800], ["I2", "United States", 90, 450, 2000],
        ["I3", "India", 10, 20, 2021], ["I4", "India", 0, 1000, 1990],
    ], columns=["institution_id", "country", "publications_count", "citations_total", "founded_year"]).to_csv(
        tmp_path / "institutions.csv", index=False)
    pd.DataFrame([
        ["F1", "USA", 2021, 80], ["F2", "India", 2021, 40],
    ], columns=["record_id", "country", "year", "innovation_index_score"]).to_csv(tmp_path / "infrastructure.csv", index=False)


def test_exact_year_join_aliases_impact_and_complete_score(tmp_path):
    write_sources(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.glob("*.csv")}
    profiles, warnings = load_profiles(tmp_path)
    assert not warnings
    assert set(profiles["year"].dropna()) == {2021, 2022}
    scored = score_profiles(profiles, 2021).set_index("country")
    assert set(scored.index) == {"India", "United States"}
    assert scored.loc["United States", "citations_per_publication"] == 5.5
    assert scored.loc["India", "citations_per_publication"] == 2
    assert scored.loc["India", "patent_grants"] == 20
    assert scored.loc["United States", "composite_score"] == 100
    assert scored.loc["India", "composite_score"] == 0
    assert before == {path.name: path.read_bytes() for path in tmp_path.glob("*.csv")}


def test_missing_teammate_data_and_empty_installation(tmp_path):
    profiles, warnings = load_profiles(tmp_path)
    assert profiles.empty and warnings
    write_sources(tmp_path)
    (tmp_path / "infrastructure.csv").unlink()
    profiles, warnings = load_profiles(tmp_path)
    scored = score_profiles(profiles, 2021)
    assert scored["composite_score"].isna().all()
    assert scored["components_available"].eq(3).all()
    assert scored["provisional_score"].between(0, 100).all()
    assert any("infrastructure.csv" in text for text in warnings)
    (tmp_path / "patents.csv").write_text("wrong,columns\n1,2\n")
    (tmp_path / "institutions.csv").write_text("")
    profiles, warnings = load_profiles(tmp_path)
    assert score_profiles(profiles, 2021)["components_available"].eq(1).all()


def test_constant_metrics_score_fifty_and_missing_stays_missing(tmp_path):
    write_sources(tmp_path)
    profiles, _ = load_profiles(tmp_path)
    for metric in METRICS:
        profiles[metric] = 5.0
    scored = score_profiles(profiles, 2021)
    assert scored["composite_score"].eq(50).all()
    profiles["patent_grants"] = float("nan")
    scored = score_profiles(profiles, 2021)
    assert scored["patent_grants_score"].isna().all()


def test_incomplete_numbers_and_duplicate_infrastructure(tmp_path):
    write_sources(tmp_path)
    path = tmp_path / "infrastructure.csv"
    data = pd.read_csv(path)
    duplicate = data.iloc[0].copy()
    duplicate["record_id"] = "F3"
    pd.concat([data, duplicate.to_frame().T], ignore_index=True).to_csv(path, index=False)
    profiles, warnings = load_profiles(tmp_path)
    result = score_profiles(profiles, 2021).set_index("country")
    assert pd.isna(result.loc["United States", "innovation_index_score"])
    assert any("duplicate country-year" in text for text in warnings)
    path = tmp_path / "patents.csv"
    data = pd.read_csv(path).astype(object)
    data.loc[len(data)] = ["P4", "India", 2021, "bad"]
    data.to_csv(path, index=False)
    result = score_profiles(load_profiles(tmp_path)[0], 2021).set_index("country")
    assert pd.isna(result.loc["India", "patent_grants"])


def test_institution_only_country_is_not_given_a_year(tmp_path):
    write_sources(tmp_path)
    path = tmp_path / "institutions.csv"
    data = pd.read_csv(path)
    data.loc[len(data)] = ["I5", "Singapore", 10, 70, 1960]
    data.to_csv(path, index=False)
    profiles, _ = load_profiles(tmp_path)
    result = score_profiles(profiles, 2021).set_index("country")
    assert pd.isna(result.loc["Singapore", "year"])
    assert result.loc["Singapore", "components_available"] == 1
    assert result.loc["Singapore", "citations_per_publication"] == 7
