from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def test_main_window_constructs_offscreen(qtbot, store, item, tmp_path):
    from minutory_worker.gui.window import MainWindow
    from minutory_worker.presentation import QueueController

    class Api:
        def list_clients(self):
            return [{"id": 52, "name": "Client"}]

    class Orchestrator:
        def __init__(self):
            self.store = store
            self.api = Api()
            self.work_dir = tmp_path / "work"

        def process(self, item_id, *, cancel, on_stage):
            return store.get_item(item_id)

    orchestrator = Orchestrator()
    window = MainWindow(
        QueueController(store, orchestrator.api, timezone="Europe/Bucharest"),
        orchestrator,
    )
    qtbot.addWidget(window)
    assert item.item_id in window.cards
    assert window.isWindow()
