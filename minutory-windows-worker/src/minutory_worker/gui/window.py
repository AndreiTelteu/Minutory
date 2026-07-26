from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..domain import STAGE_ORDER, Stage
from ..orchestrator import Orchestrator
from ..presentation import (
    ClientChoice,
    ItemView,
    ProcessingCoordinator,
    QueueController,
    diagnostic_text,
    offset_iso_to_local,
)

DARK_STYLE = """
QWidget { background: #0f0f10; color: #ededec; font-family: "Segoe UI"; font-size: 13px; }
QMainWindow { background: #0f0f10; }
QFrame#card { background: #171718; border: 1px solid #2a2a2d; border-radius: 8px; }
QLabel#title { font-size: 20px; font-weight: 600; }
QLabel#cardTitle { font-size: 14px; font-weight: 600; }
QLabel#muted { color: #a1a1aa; }
QLabel#error { color: #f87171; }
QLineEdit, QComboBox, QPlainTextEdit {
  background: #1f1f21; border: 1px solid #3a3a3e; border-radius: 6px; padding: 7px;
  selection-background-color: #4f46e5;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border: 2px solid #818cf8; }
QPushButton, QToolButton {
  background: transparent; border: 1px solid #3a3a3e; border-radius: 6px; padding: 7px 12px;
}
QPushButton:hover, QToolButton:hover { background: #1f1f21; border-color: #52525b; }
QPushButton:focus, QToolButton:focus { border: 2px solid #818cf8; }
QPushButton#primary { background: #4f46e5; border-color: #4f46e5; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #5b53e9; }
QPushButton:disabled, QToolButton:disabled { color: #71717a; border-color: #2a2a2d; }
QProgressBar { background: #1f1f21; border: 0; border-radius: 3px; height: 6px; text-align: center; }
QProgressBar::chunk { background: #818cf8; border-radius: 3px; }
QScrollArea { border: 0; }
"""


class TaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, function: Callable[[], object]) -> None:
        super().__init__()
        self.function = function
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.function())
        except Exception as exception:
            self.signals.failed.emit(str(exception))


class EventBridge(QObject):
    pipeline_event = Signal(str, str, object)


class ItemCard(QFrame):
    def __init__(self, main_window: MainWindow, view: ItemView) -> None:
        super().__init__()
        self._main_window = main_window
        self.item_id = view.item.item_id
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        heading = QHBoxLayout()
        self.name = QLabel(Path(view.item.source.path).name)
        self.name.setObjectName("cardTitle")
        self.name.setToolTip(view.item.source.path)
        self.name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.status = QLabel()
        self.status.setObjectName("muted")
        heading.addWidget(self.name, 1)
        heading.addWidget(self.status)
        root.addLayout(heading)

        self.path = QLabel(view.item.source.path)
        self.path.setObjectName("muted")
        self.path.setWordWrap(True)
        root.addWidget(self.path)

        fields = QHBoxLayout()
        self.client = QComboBox()
        self.client.setAccessibleName("Client")
        self.client.addItem("Select client…", None)
        self.title = QLineEdit(view.item.title)
        self.title.setAccessibleName("Meeting title")
        self.title.setPlaceholderText("Meeting title")
        self.datetime = QLineEdit(offset_iso_to_local(view.item.meeting_at, main_window.controller.timezone))
        self.datetime.setAccessibleName("Meeting date and time")
        self.datetime.setPlaceholderText("YYYY-MM-DDTHH:MM:SS (optional)")
        self.preset = QComboBox()
        self.preset.setAccessibleName("Compression preset")
        for key, label in (
            ("none", "None · original"),
            ("compact", "Compact · 2.5 Mbps"),
            ("balanced", "Balanced · 5 Mbps"),
            ("quality", "Quality · 8 Mbps"),
        ):
            self.preset.addItem(label, key)
        self.preset.setCurrentIndex(self.preset.findData(view.item.compression_preset))
        for label, control, stretch in (
            ("Client", self.client, 2),
            ("Meeting title", self.title, 4),
            ("Meeting time", self.datetime, 3),
            ("Compression", self.preset, 2),
        ):
            field = QVBoxLayout()
            caption = QLabel(label)
            caption.setObjectName("muted")
            field.addWidget(caption)
            field.addWidget(control)
            fields.addLayout(field, stretch)
        root.addLayout(fields)

        metrics = QHBoxLayout()
        self.probe = QLabel()
        self.probe.setObjectName("muted")
        self.estimate = QLabel()
        self.estimate.setObjectName("muted")
        self.meeting = QLabel()
        self.meeting.setObjectName("muted")
        metrics.addWidget(self.probe)
        metrics.addWidget(self.estimate)
        metrics.addStretch()
        metrics.addWidget(self.meeting)
        root.addLayout(metrics)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, len(STAGE_ORDER))
        self.progress.setAccessibleName("Pipeline stage progress")
        root.addWidget(self.progress)
        self.stage_summary = QLabel()
        self.stage_summary.setObjectName("muted")
        self.stage_summary.setWordWrap(True)
        root.addWidget(self.stage_summary)
        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        root.addWidget(self.error)

        actions = QHBoxLayout()
        self.start = QPushButton("Start / resume")
        self.start.setObjectName("primary")
        self.retry_video = QPushButton("Retry video")
        self.retry_audio = QPushButton("Retry audio")
        self.retry_transcript = QPushButton("Retry transcript")
        retry_actions = QHBoxLayout()
        self.retry_label = QLabel("Artifact recovery")
        self.retry_label.setObjectName("muted")
        retry_actions.addWidget(self.retry_label)
        retry_actions.addWidget(self.retry_video)
        retry_actions.addWidget(self.retry_audio)
        retry_actions.addWidget(self.retry_transcript)
        retry_actions.addStretch()
        root.addLayout(retry_actions)
        self.remove = QPushButton("Remove")
        self.open_source = QPushButton("Open source")
        self.open_work = QPushButton("Open work folder")
        self.details_toggle = QToolButton()
        self.details_toggle.setText("Diagnostics")
        self.details_toggle.setCheckable(True)
        self.copy_details = QPushButton("Copy diagnostics")
        actions.addWidget(self.start)
        actions.addWidget(self.remove)
        actions.addWidget(self.open_source)
        actions.addWidget(self.open_work)
        actions.addStretch()
        actions.addWidget(self.copy_details)
        actions.addWidget(self.details_toggle)
        root.addLayout(actions)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(180)
        self.details.hide()
        root.addWidget(self.details)

        self.title.editingFinished.connect(self._save_metadata)
        self.datetime.editingFinished.connect(self._save_metadata)
        self.client.currentIndexChanged.connect(self._save_metadata)
        self.preset.currentIndexChanged.connect(self._change_preset)
        self.start.clicked.connect(lambda: self._main_window.start_item(self.item_id))
        self.retry_video.clicked.connect(lambda: self._main_window.retry_artifact(self.item_id, "video"))
        self.retry_audio.clicked.connect(lambda: self._main_window.retry_artifact(self.item_id, "audio"))
        self.retry_transcript.clicked.connect(
            lambda: self._main_window.retry_artifact(self.item_id, "transcript")
        )
        self.remove.clicked.connect(lambda: self._main_window.remove_item(self.item_id))
        self.open_source.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(view.item.source.path))
        )
        self.open_work.clicked.connect(lambda: self._main_window.open_work(self.item_id))
        self.details_toggle.toggled.connect(self.details.setVisible)
        self.copy_details.clicked.connect(
            lambda: QApplication.clipboard().setText(self.details.toPlainText())
        )
        self.apply_view(view, scheduled=main_window.coordinator.is_scheduled(self.item_id))

    def set_clients(self, clients: tuple[ClientChoice, ...], selected: int | None) -> None:
        self.client.blockSignals(True)
        self.client.clear()
        self.client.addItem("Select client…", None)
        for client in clients:
            self.client.addItem(client.name, client.id)
        index = self.client.findData(selected)
        self.client.setCurrentIndex(max(0, index))
        self.client.blockSignals(False)

    def _save_metadata(self) -> None:
        if not self.title.hasAcceptableInput():
            return
        self._main_window.save_metadata(
            self.item_id,
            self.title.text(),
            self.datetime.text(),
            self.client.currentData(),
        )

    def _change_preset(self) -> None:
        self._main_window.change_preset(self.item_id, str(self.preset.currentData()))

    def apply_view(
        self,
        view: ItemView,
        *,
        scheduled: bool = False,
        force_fields: bool = False,
    ) -> None:
        local_datetime = offset_iso_to_local(
            view.item.meeting_at,
            self._main_window.controller.timezone,
        )
        for control, value in (
            (self.title, view.item.title),
            (self.datetime, local_datetime),
        ):
            if force_fields or not control.hasFocus():
                control.blockSignals(True)
                control.setText(value)
                control.blockSignals(False)
        if force_fields or not self.preset.hasFocus():
            self.preset.blockSignals(True)
            self.preset.setCurrentIndex(self.preset.findData(view.item.compression_preset))
            self.preset.blockSignals(False)
        if force_fields or not self.client.hasFocus():
            selected = self.client.findData(view.item.client_id)
            self.client.blockSignals(True)
            self.client.setCurrentIndex(max(0, selected))
            self.client.blockSignals(False)
        rendered_status = "Scheduled" if scheduled and view.active_stage is None else view.status
        self.status.setText(rendered_status)
        status_color = (
            "#4ade80"
            if rendered_status == "Completed"
            else "#f87171"
            if rendered_status.startswith("Needs attention")
            else "#fbbf24"
            if rendered_status.startswith(("Processing", "Scheduled"))
            else "#a1a1aa"
        )
        self.status.setStyleSheet(f"color: {status_color}; font-weight: 600;")
        self.probe.setText(view.probe_summary)
        self.estimate.setText(f"Estimated video · {view.estimated_size}")
        self.meeting.setText(
            f"Meeting #{view.item.server_meeting_id}" if view.item.server_meeting_id else "Not on server"
        )
        self.progress.setValue(view.completed_stages)
        self.stage_summary.setText(
            " · ".join(
                f"{stage.stage.value.replace('_', ' ')}: {stage.status.value}"
                + (f" ({stage.attempts} attempts)" if stage.attempts else "")
                for stage in view.stages
            )
        )
        failed = next((stage for stage in view.stages if stage.user_error), None)
        self.error.setText(failed.user_error if failed and failed.user_error else "")
        self.error.setVisible(failed is not None)
        self.details.setPlainText(diagnostic_text(view))
        immutable = view.metadata_locked or scheduled or view.active_stage is not None
        for editable in (self.client, self.title, self.datetime, self.preset):
            editable.setEnabled(not immutable)
        self.remove.setEnabled(
            view.removable and not scheduled and view.active_stage is None
        )
        retry_buttons = {
            "video": self.retry_video,
            "audio": self.retry_audio,
            "transcript": self.retry_transcript,
        }
        self.retry_label.setVisible(bool(view.retryable_artifacts))
        for name, button in retry_buttons.items():
            button.setVisible(name in view.retryable_artifacts)
            button.setEnabled(not scheduled and view.active_stage is None)
        self.start.setText(
            f"Retry {failed.stage.value.replace('_', ' ')}" if failed is not None else "Start / resume"
        )
        self.start.setEnabled(
            not scheduled and view.active_stage is None and view.completed_stages < len(STAGE_ORDER)
        )


class MainWindow(QMainWindow):
    def __init__(self, controller: QueueController, orchestrator: Orchestrator) -> None:
        super().__init__()
        self.controller = controller
        self.orchestrator = orchestrator
        self.cards: dict[str, ItemCard] = {}
        self.clients: tuple[ClientChoice, ...] = ()
        self.pool = QThreadPool.globalInstance()
        self.bridge = EventBridge()
        self.bridge.pipeline_event.connect(self._pipeline_event)
        self.coordinator = ProcessingCoordinator(orchestrator, self.bridge.pipeline_event.emit)
        self.setWindowTitle("Minutory Worker")
        self.resize(1180, 780)
        self.setMinimumSize(1180, 650)
        self.setAcceptDrops(True)
        self.setStyleSheet(DARK_STYLE)

        central = QWidget()
        shell = QVBoxLayout(central)
        shell.setContentsMargins(24, 20, 24, 20)
        shell.setSpacing(14)
        header = QVBoxLayout()
        title = QLabel("Windows ingestion queue")
        title.setObjectName("title")
        subtitle = QLabel("Local AMD transcription · artifacts upload only after local processing")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(subtitle)
        shell.addLayout(header)

        primary_actions = QHBoxLayout()
        primary_actions.addStretch()
        self.refresh_button = QPushButton("Refresh clients && state")
        self.preflight_button = QPushButton("Preflight unprobed")
        self.add_button = QPushButton("Add files")
        self.start_batch = QPushButton("Start pending")
        self.start_batch.setObjectName("primary")
        self.cancel_button = QPushButton("Cancel media command")
        self.clear_all_button = QPushButton("Clear all")
        primary_actions.addWidget(self.refresh_button)
        primary_actions.addWidget(self.preflight_button)
        primary_actions.addWidget(self.add_button)
        primary_actions.addWidget(self.start_batch)
        shell.addLayout(primary_actions)

        secondary_actions = QHBoxLayout()
        secondary_actions.addStretch()
        secondary_actions.addWidget(self.clear_all_button)
        secondary_actions.addWidget(self.cancel_button)
        shell.addLayout(secondary_actions)

        self.notice = QLabel("Drop MP4, MOV, AVI, or WebM files anywhere in this window.")
        self.notice.setObjectName("muted")
        self.notice.setWordWrap(True)
        shell.addWidget(self.notice)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.queue_widget = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_widget)
        self.queue_layout.setContentsMargins(0, 0, 8, 0)
        self.queue_layout.setSpacing(10)
        self.empty = QLabel("No videos queued yet. Drop several recordings here or choose Add files.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setObjectName("muted")
        self.empty.setMinimumHeight(220)
        self.queue_layout.addWidget(self.empty)
        self.queue_layout.addStretch()
        self.scroll_area.setWidget(self.queue_widget)
        shell.addWidget(self.scroll_area, 1)
        self.setCentralWidget(central)

        self.add_button.clicked.connect(self.choose_files)
        self.start_batch.clicked.connect(self.start_pending)
        self.preflight_button.clicked.connect(self.preflight_unprobed)
        self.cancel_button.clicked.connect(self.cancel_media)
        self.clear_all_button.clicked.connect(self.clear_all)
        self.refresh_button.clicked.connect(self.refresh_all)
        self.render_state()
        self.refresh_clients()

    def show_notice(self, message: str, *, error: bool = False) -> None:
        self.notice.setText(message)
        self.notice.setObjectName("error" if error else "muted")
        self.style().unpolish(self.notice)
        self.style().polish(self.notice)

    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add meeting videos",
            "",
            "Video files (*.mp4 *.mov *.avi *.webm)",
        )
        self.add_paths(paths)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def add_paths(self, paths: list[str]) -> None:
        result = self.controller.add_paths(paths)
        for item_id in result.added:
            self.coordinator.preflight(item_id)
        messages = []
        if result.added:
            messages.append(f"Added {len(result.added)} video(s).")
        if result.existing:
            messages.append(f"Skipped {len(result.existing)} duplicate(s).")
        messages.extend(result.errors)
        self.show_notice(" ".join(messages) or "No files were added.", error=bool(result.errors))
        self.render_state()

    def refresh_clients(self) -> None:
        self.refresh_button.setEnabled(False)
        self.show_notice("Loading clients…")
        task = Task(self.controller.load_clients)
        task.signals.succeeded.connect(self._clients_loaded)
        task.signals.failed.connect(self._clients_failed)
        self.pool.start(task)

    def _clients_loaded(self, clients: object) -> None:
        self.clients = cast(tuple[ClientChoice, ...], clients)
        self.refresh_button.setEnabled(True)
        self.show_notice(f"Connected · {len(self.clients)} client(s) available.")
        for view in self.controller.views():
            self.cards[view.item.item_id].set_clients(self.clients, view.item.client_id)

    def _clients_failed(self, message: str) -> None:
        self.refresh_button.setEnabled(True)
        self.show_notice(f"Clients unavailable: {message}", error=True)

    def refresh_all(self) -> None:
        self.render_state()
        self.refresh_clients()

    def render_state(self) -> None:
        views = self.controller.views()
        existing = {view.item.item_id for view in views}
        for item_id in set(self.cards) - existing:
            card = self.cards.pop(item_id)
            self.queue_layout.removeWidget(card)
            card.deleteLater()
        for view in views:
            existing_card = self.cards.get(view.item.item_id)
            if existing_card is None:
                new_card = ItemCard(self, view)
                self.cards[view.item.item_id] = new_card
                self.queue_layout.insertWidget(self.queue_layout.count() - 1, new_card)
                new_card.set_clients(self.clients, view.item.client_id)
            else:
                existing_card.apply_view(
                    view,
                    scheduled=self.coordinator.is_scheduled(view.item.item_id),
                )
        self.empty.setVisible(not views)

    def save_metadata(self, item_id: str, title: str, local_datetime: str, client_id: int | None) -> None:
        try:
            self.controller.update_metadata(
                item_id,
                title=title,
                local_datetime=local_datetime or None,
                client_id=client_id,
            )
            self.show_notice("Metadata saved.")
        except Exception as exception:
            self.show_notice(str(exception), error=True)
            self.cards[item_id].apply_view(
                self.controller.view(item_id),
                scheduled=self.coordinator.is_scheduled(item_id),
                force_fields=True,
            )

    def change_preset(self, item_id: str, preset: str) -> None:
        try:
            self.controller.set_preset(item_id, preset)
            self.render_state()
        except Exception as exception:
            self.show_notice(str(exception), error=True)
            self.cards[item_id].apply_view(
                self.controller.view(item_id),
                scheduled=self.coordinator.is_scheduled(item_id),
                force_fields=True,
            )

    def start_item(self, item_id: str) -> None:
        view = self.controller.view(item_id)
        if view.item.client_id is None:
            self.show_notice("Select a client before starting this item.", error=True)
            return
        if self.coordinator.start(item_id):
            self.show_notice("Item scheduled.")
            self.render_state()
        else:
            self.show_notice("That item is already scheduled.")

    def start_pending(self) -> None:
        missing = [view for view in self.controller.views() if view.item.client_id is None]
        if missing:
            self.show_notice(
                "Select a client for every pending item before starting the batch.",
                error=True,
            )
            return
        count = self.coordinator.start_pending()
        self.show_notice(f"Scheduled {count} item(s).")
        self.render_state()

    def preflight_unprobed(self) -> None:
        count = self.coordinator.preflight_unprobed()
        self.show_notice(f"Scheduled {count} media preflight(s).")
        self.render_state()

    def retry_artifact(self, item_id: str, artifact_name: str) -> None:
        if self.coordinator.retry_artifact(item_id, artifact_name):
            self.show_notice(f"{artifact_name.title()} retry scheduled.")
            self.render_state()
        else:
            self.show_notice("That item is already scheduled.")

    def cancel_media(self) -> None:
        self.show_notice(
            "Cancellation requested; the current stage will remain retryable."
            if self.coordinator.cancel_current_media()
            else "Only active compression or audio extraction can be cancelled safely.",
        )

    def clear_all(self) -> None:
        views = self.controller.views()
        if not views:
            self.show_notice("The queue is already empty.")
            return
        removable = [
            view
            for view in views
            if view.removable
            and view.active_stage is None
            and not self.coordinator.is_scheduled(view.item.item_id)
        ]
        skipped = len(views) - len(removable)
        if not removable:
            self.show_notice(
                "Nothing can be cleared; every item is scheduled, processing, or locked.",
                error=True,
            )
            return
        answer = QMessageBox.question(
            self,
            "Clear all items?",
            f"Remove {len(removable)} item(s) from the queue?"
            + (f" {skipped} scheduled/processing item(s) will be kept." if skipped else ""),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        errors = 0
        for view in removable:
            try:
                self.controller.remove(view.item.item_id)
            except Exception:
                errors += 1
        message = f"Removed {len(removable) - errors} item(s)."
        if skipped:
            message += f" Kept {skipped} scheduled/processing item(s)."
        if errors:
            message += f" {errors} item(s) could not be removed."
        self.show_notice(message, error=bool(errors))
        self.render_state()

    def remove_item(self, item_id: str) -> None:
        try:
            if self.coordinator.is_scheduled(item_id):
                raise RuntimeError("A scheduled item cannot be removed.")
            self.controller.remove(item_id)
            self.render_state()
        except Exception as exception:
            self.show_notice(str(exception), error=True)

    def open_work(self, item_id: str) -> None:
        item = self.controller.store.get_item(item_id)
        path = self.orchestrator.work_dir / item.item_id
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _pipeline_event(self, kind: str, item_id: str, value: object) -> None:
        if kind == "progress":
            card = self.cards.get(item_id)
            if card is not None and isinstance(value, int):
                card.status.setText(f"Processing · transcribe {value}%")
            return
        self.render_state()
        if kind == "failed":
            self.show_notice(f"Item paused safely: {value}", error=True)
        elif kind == "completed":
            self.show_notice("Item completed and reconciled with the server.")
        elif kind == "preflight_completed":
            self.show_notice("Preflight complete. Review metadata and estimated output size.")
        elif kind == "artifact_completed":
            self.show_notice("Requested artifact retry completed.")
        elif kind == "stage":
            if not isinstance(value, tuple) or len(value) != 2:
                return
            stage, status = value
            if isinstance(stage, Stage) and hasattr(status, "value"):
                self.show_notice(f"{stage.value.replace('_', ' ').title()} · {status.value}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.coordinator.transcription_active:
            self.show_notice(
                "Transcription is active. Minutory Worker will stay open to keep the GPU model stable."
            )
            QMessageBox.information(
                self,
                "Transcription is still active",
                "Wait for transcription to finish before closing. This avoids an upstream "
                "CTranslate2/HIP teardown deadlock.",
            )
            event.ignore()
            return
        if self.coordinator.busy:
            if self.coordinator.current_stage not in {Stage.SOURCE, Stage.WAV}:
                self.show_notice(
                    "The current stage cannot be interrupted safely. Close again after it finishes."
                )
                event.ignore()
                return
            answer = QMessageBox.question(
                self,
                "Stop processing and close?",
                "The active media command will be cancelled safely and can be resumed next time.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if not self.coordinator.close():
            event.ignore()
            return
        event.accept()
