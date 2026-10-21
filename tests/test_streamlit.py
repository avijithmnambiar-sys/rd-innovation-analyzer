import json
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import country_profile
import rd_manager
from rd_manager import ResearchSpendingManager
from test_country_profile import write_sources
from test_rd_manager import record

ROOT = Path(__file__).resolve().parents[1]


def widget(elements, label):
    return next(element for element in elements if element.label == label)


@pytest.fixture
def spending_app(tmp_path, monkeypatch):
    manager = ResearchSpendingManager(tmp_path / "rd.csv")
    manager.save(pd.DataFrame([record("RD1"), record("RD2", year=2022, gerd_usd_millions=110)]))
    monkeypatch.setattr(rd_manager, "ResearchSpendingManager", lambda: manager)
    app = AppTest.from_file(str(ROOT / "pages" / "1_RD_Investment.py"), default_timeout=15).run()
    assert not app.exception
    return app, manager


def test_spending_forms_crud_reload_and_confirmation(spending_app):
    app, manager = spending_app
    widget(app.button, "Add record").click().run()
    assert app.error and len(manager.load()) == 2
    app.text_input[0].set_value("RD3")
    app.text_input[1].set_value("India")
    app.text_input[2].set_value("IND")
    app.number_input[0].set_value(2023)
    app.number_input[1].set_value(1.1)
    app.number_input[2].set_value(120.0)
    app.number_input[3].set_value(250.0)
    widget(app.button, "Add record").click().run()
    assert not app.exception and len(manager.load()) == 3
    assert app.success
    widget(app.selectbox, "Select record to update").select("RD3").run()
    assert app.number_input[6].value == 120
    app.number_input[6].set_value(130.0)
    widget(app.button, "Save changes").click().run()
    assert not app.exception
    assert manager.load().set_index("record_id").loc["RD3", "gerd_usd_millions"] == 130
    widget(app.selectbox, "Select record to update").select("RD2").run()
    assert app.number_input[6].value == 110
    widget(app.selectbox, "Select record to delete").select("RD3").run()
    assert widget(app.button, "Delete record").disabled
    app.checkbox[0].check().run()
    assert not widget(app.button, "Delete record").disabled
    widget(app.selectbox, "Select record to delete").select("RD2").run()
    assert widget(app.button, "Delete record").disabled
    widget(app.selectbox, "Select record to delete").select("RD3").run()
    app.checkbox[0].check().run()
    widget(app.button, "Delete record").click().run()
    assert not app.exception and len(manager.load()) == 2
    reloaded = AppTest.from_file(str(ROOT / "pages" / "1_RD_Investment.py")).run(timeout=15)
    assert not reloaded.exception
    assert "RD3" not in manager.load()["record_id"].tolist()


def test_filters_sorting_charts_and_downloads(spending_app):
    app, _ = spending_app
    assert len(app.get("plotly_chart")) == 2
    assert len(app.get("download_button")) == 2
    widget(app.multiselect, "Filter year").set_value([2022]).run()
    assert not app.exception
    view = app.dataframe[1].value
    assert len(view) == 1 and view.iloc[0]["year"] == 2022
    widget(app.multiselect, "Filter year").set_value([]).run()
    widget(app.selectbox, "Sort by").select("gerd_usd_millions").run()
    app.radio[0].set_value("Descending").run()
    assert app.dataframe[1].value["record_id"].tolist() == ["RD2", "RD1"]
    chart = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert chart["data"][0]["type"] == "bar"
    app.text_input[3].set_value("No matching country").run()
    assert not app.exception and app.dataframe[1].value.empty
    assert not app.get("plotly_chart")
    assert len(app.get("download_button")) == 2


def test_report_download_payloads(tmp_path, monkeypatch):
    manager = ResearchSpendingManager(tmp_path / "rd.csv")
    manager.save(pd.DataFrame([record("RD1"), record("RD2", year=2022)]))
    monkeypatch.setattr(rd_manager, "ResearchSpendingManager", lambda: manager)
    downloads = {}
    original = st.download_button

    def capture_download(label, data, **kwargs):
        downloads[label] = data
        return original(label, data, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    app = AppTest.from_file(str(ROOT / "pages" / "1_RD_Investment.py")).run(timeout=15)
    widget(app.multiselect, "Filter year").set_value([2022]).run()
    assert not app.exception
    from io import BytesIO
    exported = pd.read_csv(BytesIO(downloads["Download filtered data (CSV)"]))
    assert exported["record_id"].tolist() == ["RD2"]
    summary = downloads["Download summary report"]
    assert "Generated (UTC):" in summary
    assert "Records in view: 1" in summary and "Years: 2022" in summary
    app.get("download_button")[1].click().run()
    assert not app.exception


@pytest.mark.parametrize("source", ["missing", "empty", "invalid", "wrong_headers"])
def test_spending_unavailable_or_bad_source(tmp_path, monkeypatch, source):
    path = tmp_path / "rd.csv"
    if source == "empty":
        path.write_text("")
    if source == "wrong_headers":
        path.write_text("wrong,columns\n1,2\n")
    if source == "invalid":
        data = pd.DataFrame([record()]).astype(object)
        data.loc[0, "year"] = "bad"
        data.loc[0, "funding_sector"] = None
        data.loc[0, "country"] = None
        data.to_csv(path, index=False)
    manager = ResearchSpendingManager(path)
    monkeypatch.setattr(rd_manager, "ResearchSpendingManager", lambda: manager)
    app = AppTest.from_file(str(ROOT / "pages" / "1_RD_Investment.py")).run(timeout=15)
    assert not app.exception
    if source == "wrong_headers":
        assert app.error


def test_home_handles_complete_and_partial_sources(tmp_path, monkeypatch):
    write_sources(tmp_path)
    original = country_profile.load_profiles
    monkeypatch.setattr(country_profile, "load_profiles", lambda path: original(tmp_path))
    app = AppTest.from_file(str(ROOT / "home.py")).run(timeout=15)
    assert not app.exception
    widget(app.selectbox, "Observation year").select(2021).run()
    widget(app.selectbox, "Country profile").select("United States").run()
    assert app.metric[0].value == "100.0"
    assert app.metric[1].value == "4 / 4"
    (tmp_path / "infrastructure.csv").unlink()
    app.run()
    assert not app.exception
    assert app.metric[0].value == "Unavailable"
    assert app.metric[1].value == "3 / 4"
    for path in tmp_path.glob("*.csv"):
        path.unlink()
    app.run()
    assert not app.exception and app.info


@pytest.mark.parametrize("page", ["home.py", "pages/2_Patents.py", "pages/3_Institutions.py"])
def test_existing_pages_load_without_modifying_files(page):
    files = list((ROOT / "data").glob("*.csv"))
    before = {path: path.read_bytes() for path in files}
    app = AppTest.from_file(str(ROOT / page)).run(timeout=15)
    assert not app.exception
    assert before == {path: path.read_bytes() for path in files}
