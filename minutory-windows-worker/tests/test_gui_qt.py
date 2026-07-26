from __future__ import annotations

import os
import threading

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
            self.calls = []

        def process_stages(self, item_id, stages, *, cancel=None, on_stage=None, on_progress=None):
            return store.get_item(item_id)

        def preflight(self, item_id, *, cancel=None, on_stage):
            self.calls.append(("preflight", item_id))
            return store.get_item(item_id)

        def retry_artifact(self, item_id, artifact_name, *, on_stage, on_progress=None):
            self.calls.append((artifact_name, item_id))
            return store.get_item(item_id)

    orchestrator = Orchestrator()
    window = MainWindow(
        QueueController(store, orchestrator.api, timezone="Europe/Bucharest"),
        orchestrator,
    )
    qtbot.addWidget(window)
    assert item.item_id in window.cards
    assert window.isWindow()
    window.coordinator.close()


def test_window_add_edit_clients_and_state_render_offscreen(qtbot, store, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QApplication

    from minutory_worker.domain import Stage
    from minutory_worker.gui.window import MainWindow
    from minutory_worker.presentation import QueueController

    class Api:
        def list_clients(self):
            return [{"id": 7, "name": "Acme & Partners"}]

    class Orchestrator:
        def __init__(self):
            self.store = store
            self.api = Api()
            self.work_dir = tmp_path / "work"
            self.calls = []
            self.preflight_entered = threading.Event()
            self.preflight_release = threading.Event()

        def process_stages(self, item_id, stages, *, cancel=None, on_stage=None, on_progress=None):
            return store.get_item(item_id)

        def preflight(self, item_id, *, cancel=None, on_stage):
            self.calls.append(("preflight", item_id))
            self.preflight_entered.set()
            self.preflight_release.wait(2)
            return store.get_item(item_id)

        def retry_artifact(self, item_id, artifact_name, *, on_stage, on_progress=None):
            self.calls.append((artifact_name, item_id))
            return store.get_item(item_id)

    orchestrator = Orchestrator()
    window = MainWindow(
        QueueController(store, orchestrator.api, timezone="Europe/Bucharest"),
        orchestrator,
    )
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: bool(window.clients))
    video = tmp_path / "2026-07-12 09-30-00 Review.webm"
    video.write_bytes(b"video")
    rejected = tmp_path / "unsupported.mkv"
    rejected.write_bytes(b"mkv")
    window.add_paths([str(video), str(rejected)])
    qtbot.waitUntil(lambda: len(window.cards) == 2)
    added_id = next(item_id for item_id, card in window.cards.items() if card.name.text() == video.name)
    card = window.cards[added_id]
    assert card.client.itemText(1) == "Acme & Partners"
    assert "unsupported video type" in window.notice.text()
    assert orchestrator.preflight_entered.wait(1)
    assert not card.title.isEnabled()
    assert not card.preset.isEnabled()
    assert not card.remove.isEnabled()
    orchestrator.preflight_release.set()
    qtbot.waitUntil(lambda: not window.coordinator.busy)
    window.render_state()
    assert card.title.isEnabled()
    card.title.setText("Manual review")
    card.client.setCurrentIndex(1)
    card.title.editingFinished.emit()
    assert store.get_item(added_id).title == "Manual review"
    assert store.get_item(added_id).client_id == 7
    assert ("preflight", added_id) in orchestrator.calls

    dropped = tmp_path / "Dropped meeting.mp4"
    dropped.write_bytes(b"video")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(dropped))])
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dropEvent(event)
    qtbot.waitUntil(lambda: len(window.cards) == 3)
    assert any(card.name.text() == dropped.name for card in window.cards.values())

    store.reconcile_success(added_id, Stage.PROBE)
    store.reconcile_success(added_id, Stage.SOURCE)
    meeting_item = store.get_item(added_id)
    meeting_item.server_meeting_id = 99
    store.start_stage(added_id, Stage.MEETING)
    store.persist_stage_output(meeting_item, Stage.MEETING)
    store.finish_stage(added_id, Stage.MEETING)
    store.start_stage(added_id, Stage.VIDEO_UPLOAD)
    store.fail_stage(added_id, Stage.VIDEO_UPLOAD, "Upload failed", "safe diagnostic")
    window.render_state()
    assert card.retry_video.isVisibleTo(window.queue_widget)
    assert "Upload failed" in card.error.text()
    assert "safe diagnostic" in card.details.toPlainText()
    card.copy_details.click()
    assert QApplication.clipboard().text() == card.details.toPlainText()
    window.retry_artifact(added_id, "video")
    qtbot.waitUntil(lambda: not window.coordinator.busy)
    assert ("video", added_id) in orchestrator.calls
    window.coordinator.close()
