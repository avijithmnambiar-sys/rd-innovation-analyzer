import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import infrastructure_manager
from infrastructure_manager import COLUMNS, InfrastructureManager
from test_infrastructure_manager import high, record

ROOT = Path(__file__).resolve().parents[1]
PAGE = str(ROOT / "pages" / "4_Infrastructure.py")


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def seed(path):
    manager = InfrastructureManager(path)
    manager.save(pd.DataFrame([record("INF1"), high("INF2"),
                               high("INF3", year=2022, innovation_index_score=59.0)])[COLUMNS])
    return manager


@pytest.fixture
def infrastructure_app(tmp_path, monkeypatch):
    manager = seed(tmp_path / "infrastructure.csv")
    monkeypatch.setattr(infrastructure_manager, "InfrastructureManager", lambda: manager)
    app = AppTest.from_file(PAGE, default_timeout=20).run()
    assert not app.exception
    return app, manager


def test_create_update_delete_and_activity_log(infrastructure_app):
    app, manager = infrastructure_app
    widget(app.button, "Add record").click().run()
    assert app.error and len(manager.load()) == 3
    app.text_input[0].set_value("INF4")
    app.text_input[1].set_value("Brazil")
    app.number_input[0].set_value(2023)
    app.number_input[1].set_value(77.2)
    app.number_input[2].set_value(10.3)
    app.number_input[3].set_value(4.96)
    app.number_input[4].set_value(34.9)
    # Form values only reach the manager when the form is submitted, so set them all, then submit once.
    widget(app.selectbox, "Infrastructure tier").select("Medium")
    widget(app.button, "Add record").click().run()
    assert not app.exception and app.success
    stored = manager.load().set_index("record_id")
    assert stored.loc["INF4", "country"] == "Brazil"
    assert stored.loc["INF4", "infrastructure_tier"] == "Medium"

    widget(app.selectbox, "Select record to update").select("INF4").run()
    edit_scores = [element for element in app.number_input if element.label == "Innovation Index Score"]
    assert edit_scores[-1].value == pytest.approx(34.9)
    edit_scores[-1].set_value(36.4)
    widget(app.button, "Save changes").click().run()
    assert not app.exception
    assert manager.load().set_index("record_id").loc["INF4", "innovation_index_score"] == 36.4

    widget(app.selectbox, "Select record to delete").select("INF4").run()
    assert widget(app.button, "Delete record").disabled
    app.checkbox[0].check().run()
    assert not widget(app.button, "Delete record").disabled
    widget(app.button, "Delete record").click().run()
    assert not app.exception and len(manager.load()) == 3
    assert "INF4" not in manager.load()["record_id"].tolist()

    # The audit trail is on the page and records all three changes in order.
    log = manager.activity_log.read()
    assert log["action"].tolist() == ["ADD", "UPDATE", "DELETE"]
    shown = app.dataframe[-1].value
    assert shown["action"].tolist() == ["DELETE", "UPDATE", "ADD"]
    reloaded = AppTest.from_file(PAGE).run(timeout=20)
    assert not reloaded.exception


def test_rejected_record_shows_a_message_and_changes_nothing(infrastructure_app):
    app, manager = infrastructure_app
    before = manager.load()
    app.text_input[0].set_value("INF9")
    app.text_input[1].set_value("India")
    app.number_input[0].set_value(2021)
    app.number_input[1].set_value(43.0)
    app.number_input[2].set_value(10.0)
    app.number_input[3].set_value(5.1)
    app.number_input[4].set_value(36.0)
    widget(app.button, "Add record").click().run()
    assert not app.exception and app.error
    assert manager.load().equals(before)


def test_filters_sorting_charts_and_group_comparison(infrastructure_app):
    app, _ = infrastructure_app
    assert len(app.get("plotly_chart")) == 2
    assert len(app.get("download_button")) == 2
    histogram = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert histogram["data"][0]["type"] == "histogram"
    assert any("gap of" in str(element.value) for element in app.success)

    widget(app.multiselect, "Filter year").set_value([2022]).run()
    assert not app.exception
    view = app.dataframe[1].value
    assert len(view) == 1 and view.iloc[0]["year"] == 2022

    widget(app.multiselect, "Filter year").set_value([]).run()
    widget(app.multiselect, "Filter infrastructure tier").set_value(["High"]).run()
    assert not app.exception and app.warning
    assert any("both be present" in str(element.value) for element in app.info)

    widget(app.multiselect, "Filter infrastructure tier").set_value([]).run()
    widget(app.selectbox, "Sort by").select("innovation_index_score").run()
    app.radio[0].set_value("Descending").run()
    assert app.dataframe[1].value["record_id"].tolist() == ["INF3", "INF2", "INF1"]

    widget(app.text_input, "Search country").set_value("No matching country").run()
    assert not app.exception and app.dataframe[1].value.empty
    assert not app.get("plotly_chart")
    assert len(app.get("download_button")) == 2


def test_report_download_payloads(tmp_path, monkeypatch):
    manager = seed(tmp_path / "infrastructure.csv")
    monkeypatch.setattr(infrastructure_manager, "InfrastructureManager", lambda: manager)
    downloads = {}
    original = st.download_button

    def capture_download(label, data, **kwargs):
        downloads[label] = data
        return original(label, data, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    app = AppTest.from_file(PAGE).run(timeout=20)
    widget(app.multiselect, "Filter year").set_value([2022]).run()
    assert not app.exception
    exported = pd.read_csv(BytesIO(downloads["Download filtered data (CSV)"]))
    assert exported["record_id"].tolist() == ["INF3"]
    summary = downloads["Download summary report"]
    assert "Generated (UTC):" in summary
    assert "Records in view: 1" in summary and "Years: 2022" in summary
    app.get("download_button")[1].click().run()
    assert not app.exception


@pytest.mark.parametrize("source", ["missing", "empty", "invalid", "wrong_headers"])
def test_unavailable_or_bad_source_never_raises(tmp_path, monkeypatch, source):
    path = tmp_path / "infrastructure.csv"
    if source == "empty":
        path.write_text("")
    if source == "wrong_headers":
        path.write_text("wrong,columns\n1,2\n")
    if source == "invalid":
        data = pd.DataFrame([record()])[COLUMNS].astype(object)
        data.loc[0, "year"] = "bad"
        data.loc[0, "innovation_index_score"] = None
        data.loc[0, "infrastructure_tier"] = None
        data.to_csv(path, index=False)
    manager = InfrastructureManager(path)
    monkeypatch.setattr(infrastructure_manager, "InfrastructureManager", lambda: manager)
    app = AppTest.from_file(PAGE).run(timeout=20)
    assert not app.exception
    if source == "wrong_headers":
        assert app.error


def test_page_does_not_modify_teammate_files():
    files = list((ROOT / "data").glob("*.csv"))
    before = {path: path.read_bytes() for path in files}
    app = AppTest.from_file(PAGE).run(timeout=20)
    assert not app.exception
    assert before == {path: path.read_bytes() for path in files}
