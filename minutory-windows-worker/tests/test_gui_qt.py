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

        def preflight(self, item_id, *, cancel=None, on_stage, on_progress=None):
            self.calls.append(("preflight", item_id))
            return store.get_item(item_id)

        def retry_artifact(self, item_id, artifact_name, *, on_stage, on_progress=None):
            self.calls.append((artifact_name, item_id))
            return store.get_item(item_id)

    orchestrator = Orchestrator()
    window = MainWindow(
        QueueController(
            store,
            orchestrator.api,
            timezone="Europe/Bucharest",
            api_base_url="https://minutory.test",
        ),
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
            self.pipeline_entered = threading.Event()
            self.pipeline_release = threading.Event()

        def process_stages(self, item_id, stages, *, cancel=None, on_stage=None, on_progress=None):
            self.calls.append(("pipeline", item_id))
            self.pipeline_entered.set()
            self.pipeline_release.wait(2)
            return store.get_item(item_id)

        def preflight(self, item_id, *, cancel=None, on_stage, on_progress=None):
            self.calls.append(("preflight", item_id))
            return store.get_item(item_id)

        def retry_artifact(self, item_id, artifact_name, *, on_stage, on_progress=None):
            self.calls.append((artifact_name, item_id))
            return store.get_item(item_id)

    orchestrator = Orchestrator()
    window = MainWindow(
        QueueController(
            store,
            orchestrator.api,
            timezone="Europe/Bucharest",
            api_base_url="https://minutory.test",
        ),
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
    assert not orchestrator.pipeline_entered.wait(0.1)
    assert card.status.text().strip() == "•  New"
    assert card.title.isEnabled()
    assert card.preset.isEnabled()
    assert card.remove.isEnabled()
    card.client.setCurrentIndex(1)
    card.start.click()
    assert orchestrator.pipeline_entered.wait(1)
    assert not card.title.isEnabled()
    assert not card.preset.isEnabled()
    assert not card.remove.isEnabled()

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
    dropped_card = next(card for card in window.cards.values() if card.name.text() == dropped.name)
    assert dropped_card.status.text().strip() == "•  New"
    assert dropped_card.title.isEnabled()
    assert dropped_card.preset.isEnabled()
    assert dropped_card.remove.isEnabled()

    orchestrator.pipeline_release.set()
    qtbot.waitUntil(lambda: not window.coordinator.busy)
    window.render_state()
    assert card.title.isEnabled()
    compression_bar = card.progress._segments["compression"][1]
    assert not compression_bar.isHidden()
    card.preset.setCurrentIndex(card.preset.findData("none"))
    assert compression_bar.isHidden()
    card.preset.setCurrentIndex(card.preset.findData("crf22"))
    window.coordinator._progress[added_id] = (Stage.TRANSCRIBE, 50)
    window._pipeline_event("progress", added_id, (Stage.TRANSCRIBE, 50))
    assert card.progress._segments["transcript"][1].value() == 50
    assert window.global_progress.value() > 0
    assert window.global_progress.maximumWidth() > 1000
    assert "color:#4ade80" in window.global_progress_label.text()
    assert window.global_progress_label.objectName() == "overallQueueLabel"
    assert window.scroll_area.verticalScrollBar().objectName() == "queueScrollbar"
    assert window.queue_layout.contentsMargins().right() == 0
    window.scroll_area.verticalScrollBar().setRange(0, 100)
    assert window.queue_layout.contentsMargins().right() == window.scroll_area.verticalScrollBar().width()
    window.scroll_area.verticalScrollBar().setRange(0, 0)
    assert window.queue_layout.contentsMargins().right() == 0
    assert card.progress.objectName() == "pipelineProgress"
    assert card.progress._captions.objectName() == "progressCaptions"
    assert card.progress._segments["audio"][0].__class__.__name__ == "OutlinedLabel"
    assert card.progress._segments["compression"][0].__class__.__name__ == "QLabel"
    assert card.progress._segments["audio"][0].text() == "Audio convert"
    card.progress.resize(1000, card.progress.sizeHint().height())
    card.progress._layout_captions()
    assert all(not separator.isHidden() for separator in card.progress._separators)
    assert all(separator.height() == 20 for separator in card.progress._separators)
    visible_bars = [
        card.progress._segments[key][1]
        for key in ("audio", "compression", "transcript", "upload")
    ]
    for index, separator in enumerate(card.progress._separators):
        left_bar = visible_bars[index]
        right_bar = visible_bars[index + 1]
        assert separator.x() == (left_bar.geometry().right() + right_bar.geometry().left()) // 2
    assert visible_bars[0].width() / sum(bar.width() for bar in visible_bars) == pytest.approx(
        0.05,
        abs=0.01,
    )
    card.title.setText("Manual review")
    card.client.setCurrentIndex(1)
    card.title.editingFinished.emit()
    assert store.get_item(added_id).title == "Manual review"
    assert store.get_item(added_id).client_id == 7
    assert ("pipeline", added_id) in orchestrator.calls

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
    assert card.open_meeting.isVisibleTo(window.queue_widget)
    card.copy_details.click()
    assert QApplication.clipboard().text() == card.details.toPlainText()
    window.retry_artifact(added_id, "video")
    qtbot.waitUntil(lambda: not window.coordinator.busy)
    assert ("video", added_id) in orchestrator.calls
    window.coordinator.close()
