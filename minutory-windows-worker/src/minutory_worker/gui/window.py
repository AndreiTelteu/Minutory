from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPaintEvent,
    QResizeEvent,
)
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
    QStackedLayout,
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
    pipeline_progress,
)

DARK_STYLE = """
QWidget {
  background: #0f0f10;
  color: #ededec;
  font-family: "Inter", "Segoe UI Variable Text", "Segoe UI";
  font-size: 13px;
}
QMainWindow, QWidget#appShell, QWidget#mainSurface { background: #0f0f10; }
QWidget#pipelineProgress, QWidget#progressCaptions, QWidget#statsOverlay { background: transparent; }
QLabel { background: transparent; color: #ededec; }
QLabel#brandMark {
  background: #4f46e5; color: white; border-radius: 6px;
  font-size: 12px; font-weight: 700;
}
QLabel#brandName { font-size: 14px; font-weight: 650; }
QLabel#pageTitle { font-size: 21px; font-weight: 650; letter-spacing: -0.2px; }
QLabel#sectionTitle { font-size: 13px; font-weight: 600; }
QLabel#cardTitle { font-size: 14px; font-weight: 600; }
QLabel#muted, QLabel#fieldLabel, QLabel#metricLabel { color: #c9c9d1; }
QLabel#fieldLabel { font-size: 12px; }
QLabel#micro { color: #b6b6bf; font-size: 11px; }
QLabel#metricValue { font-size: 16px; font-weight: 650; }
QLabel#overallQueueLabel { color: #c9c9d1; font-size: 15px; font-weight: 600; }
QLabel#error { color: #f87171; }
QLabel#notice {
  background: #171718; border: 1px solid #2a2a2d; border-radius: 6px;
  color: #c9c9d1; padding: 8px 11px;
}
QLabel#noticeError {
  background: rgba(239, 68, 68, 0.08); border: 1px solid #7f1d1d;
  border-radius: 6px; color: #f87171; padding: 8px 11px;
}
QFrame#card { background: #1f1f21; border: 1px solid #2a2a2d; border-radius: 8px; }
QFrame#card:hover { border-color: #3a3a3e; }
QFrame#divider { background: #2a2a2d; border: 0; max-height: 1px; }
QLineEdit, QComboBox, QPlainTextEdit {
  background: #171718; border: 1px solid #3a3a3e; border-radius: 6px;
  padding: 7px 9px; selection-background-color: #4f46e5;
}
QLineEdit:hover, QComboBox:hover { border-color: #52525b; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border: 2px solid #818cf8; padding: 6px 8px; }
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox QAbstractItemView {
  background: #1f1f21; border: 1px solid #3a3a3e; border-radius: 6px;
  selection-background-color: rgba(129, 140, 248, 0.16); selection-color: #ededec;
  padding: 4px; outline: 0;
}
QPushButton, QToolButton {
  background: transparent; border: 1px solid #3a3a3e; border-radius: 6px;
  padding: 7px 12px; font-weight: 500;
}
QPushButton:hover, QToolButton:hover { background: #2a2a2d; border-color: #52525b; }
QPushButton:pressed, QToolButton:pressed { background: #323235; }
QPushButton:focus, QToolButton:focus { border: 2px solid #818cf8; padding: 6px 11px; }
QPushButton#primary { background: #4f46e5; border-color: #4f46e5; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #5b53e9; border-color: #5b53e9; }
QPushButton#ghost { border-color: transparent; color: #c9c9d1; }
QPushButton#ghost:hover { background: #2a2a2d; color: #ffffff; }
QPushButton#dangerGhost { border-color: transparent; color: #c9c9d1; }
QPushButton#dangerGhost:hover { background: rgba(239, 68, 68, 0.10); color: #f87171; }
QPushButton:disabled, QToolButton:disabled { color: #5f5f66; border-color: #2a2a2d; background: transparent; }
QProgressBar {
  background: #171718; border: 0; border-radius: 2px; height: 4px;
  min-height: 4px; max-height: 4px; text-align: center;
}
QProgressBar::chunk { background: #818cf8; border-radius: 2px; }
QProgressBar#stageProgress {
  background: rgba(0, 0, 0, 0.44); height: 6px; min-height: 6px; max-height: 6px;
  border-radius: 1px;
}
QProgressBar#stageProgress::chunk { border-radius: 1px; }
QProgressBar#globalProgress {
  background: rgba(129, 140, 248, 0.04); border-radius: 0;
  min-height: 44px; max-height: 44px;
}
QProgressBar#globalProgress::chunk { background: rgba(129, 140, 248, 0.14); border-radius: 0; }
QFrame#stageDivider { background: #71717a; border: 0; }
QScrollArea { border: 0; background: #0f0f10; }
QScrollArea > QWidget > QWidget { background: #0f0f10; }
QScrollBar#queueScrollbar:vertical {
  background: #171718; border-left: 1px solid #2a2a2d; width: 12px; margin: 0;
}
QScrollBar#queueScrollbar::handle:vertical {
  background: #52525b; border: 2px solid #171718; border-radius: 5px; min-height: 48px;
}
QScrollBar#queueScrollbar::handle:vertical:hover { background: #71717a; }
QScrollBar#queueScrollbar::add-page:vertical, QScrollBar#queueScrollbar::sub-page:vertical {
  background: transparent;
}
QScrollBar#queueScrollbar::add-line:vertical, QScrollBar#queueScrollbar::sub-line:vertical {
  height: 0; background: transparent;
}
QToolTip { background: #27272a; color: #ededec; border: 1px solid #3f3f46; padding: 5px; }
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


class OutlinedLabel(QLabel):
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = painter.fontMetrics()
        baseline = (self.height() + metrics.ascent() - metrics.descent()) / 2
        path = QPainterPath()
        path.addText(0, baseline, self.font(), self.text())
        stroker = QPainterPathStroker()
        stroker.setWidth(5)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.fillPath(stroker.createStroke(path), QColor("#1f1f21"))
        painter.end()
        super().paintEvent(event)


class PipelineProgressWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pipelineProgress")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)
        self._captions = QWidget()
        self._captions.setObjectName("progressCaptions")
        self._captions.setFixedHeight(16)
        root.addWidget(self._captions)
        bars = QHBoxLayout()
        bars.setContentsMargins(0, 0, 0, 0)
        bars.setSpacing(1)
        root.addLayout(bars)
        self._bars_layout = bars
        self._segments: dict[str, tuple[QLabel, QProgressBar]] = {}
        for key in ("audio", "compression", "transcript", "speakerid", "upload"):
            label = OutlinedLabel(self._captions) if key == "audio" else QLabel(self._captions)
            label.setObjectName("micro")
            bar = QProgressBar()
            bar.setObjectName("stageProgress")
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setMinimumWidth(0)
            bar.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            bars.addWidget(bar)
            self._segments[key] = (label, bar)
        self._overall = QLabel(self._captions)
        self._overall.setObjectName("micro")
        self._overall.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._separators = [QFrame(self) for _ in range(4)]
        for separator in self._separators:
            separator.setObjectName("stageDivider")
            separator.setFixedWidth(1)
        self._weights: dict[str, int] = {}
        self.setAccessibleName("Meeting pipeline progress")

    def set_progress(self, view: ItemView, transient: tuple[Stage, int] | None) -> int:
        progress = pipeline_progress(view, transient)
        visible = {stage.key: stage for stage in progress.stages}
        bars = cast(QVBoxLayout, self.layout()).itemAt(1).layout()
        assert isinstance(bars, QHBoxLayout)
        self._weights = {stage.key: stage.weight for stage in progress.stages}
        for index, key in enumerate(("audio", "compression", "transcript", "speakerid", "upload")):
            label, bar = self._segments[key]
            stage = visible.get(key)
            label.setVisible(stage is not None)
            bar.setVisible(stage is not None)
            bars.setStretch(index, stage.weight if stage is not None else 0)
            if stage is None:
                continue
            suffix = f"  {round(stage.fraction * 100)}%" if stage.active and not stage.completed else ""
            label.setText(f"{stage.label}{suffix}")
            label.setStyleSheet("color: #4ade80;" if stage.completed else "color: #b6b6bf;")
            bar.setValue(round(stage.fraction * 100))
            bar.setStyleSheet(
                "QProgressBar::chunk { background: #22c55e; }"
                if stage.completed
                else "QProgressBar::chunk { background: #818cf8; }"
            )
            bar.setAccessibleName(f"{stage.label} progress")
        self._overall.setText(f"Overall {progress.overall_percent}%")
        self._layout_captions()
        return progress.overall_percent

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._layout_captions()

    def _layout_captions(self) -> None:
        if not self._weights:
            return
        self._bars_layout.activate()
        width = self._captions.width()
        self._overall.adjustSize()
        overall_x = max(0, width - self._overall.width())
        self._overall.move(overall_x, 0)
        visible_keys = [
            key
            for key in ("audio", "compression", "transcript", "speakerid", "upload")
            if key in self._weights
        ]
        for key in visible_keys:
            label, bar = self._segments[key]
            label.adjustSize()
            center = bar.geometry().center().x()
            x = 0 if key == "audio" else round(center - label.width() / 2)
            max_x = width - label.width()
            if key == "upload":
                max_x = min(max_x, overall_x - label.width() - 8)
            label.move(max(0, min(x, max_x)), 0)
        for index in range(len(visible_keys) - 1):
            left_key = visible_keys[index]
            right_key = visible_keys[index + 1]
            left_bar = self._segments[left_key][1]
            right_bar = self._segments[right_key][1]
            boundary = (left_bar.geometry().right() + right_bar.geometry().left()) // 2
            separator = self._separators[index]
            separator.setGeometry(boundary, max(0, left_bar.geometry().top() - 20), 1, 20)
            separator.show()
            separator.raise_()
        for separator in self._separators[len(visible_keys) - 1 :]:
            separator.hide()
        self._captions.raise_()


class ItemCard(QFrame):
    def __init__(self, main_window: MainWindow, view: ItemView) -> None:
        super().__init__()
        self._main_window = main_window
        self.item_id = view.item.item_id
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 15)
        root.setSpacing(11)

        heading = QHBoxLayout()
        heading.setSpacing(10)
        self.name = QLabel(Path(view.item.source.path).name)
        self.name.setObjectName("cardTitle")
        self.name.setToolTip(view.item.source.path)
        self.name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.status = QLabel()
        heading.addWidget(self.name, 1)
        heading.addWidget(self.status)
        root.addLayout(heading)

        self.path = QLabel(view.item.source.path)
        self.path.setObjectName("micro")
        self.path.setWordWrap(True)
        root.addWidget(self.path)

        fields = QHBoxLayout()
        fields.setSpacing(10)
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
            ("crf26", "CRF 26 · auto quality"),
            ("crf22", "CRF 22 · auto quality"),
            ("nano", "Nano · 500 kbps"),
            ("micro", "Micro · 1 Mbps"),
            ("compact", "Compact · 2.5 Mbps"),
            ("balanced", "Balanced · 5 Mbps"),
            ("quality", "Quality · 8 Mbps"),
        ):
            self.preset.addItem(label, key)
        self.preset.setCurrentIndex(self.preset.findData(view.item.compression_preset))
        self.language = QComboBox()
        self.language.setAccessibleName("Transcription language")
        for key, label in (("ro", "Romanian"), ("en", "English")):
            self.language.addItem(label, key)
        self.language.setCurrentIndex(self.language.findData(view.item.language))
        for label, control, stretch in (
            ("Client", self.client, 2),
            ("Meeting title", self.title, 4),
            ("Meeting time", self.datetime, 3),
            ("Compression", self.preset, 2),
            ("Language", self.language, 1),
        ):
            field = QVBoxLayout()
            field.setSpacing(5)
            caption = QLabel(label)
            caption.setObjectName("fieldLabel")
            caption.setBuddy(control)
            field.addWidget(caption)
            field.addWidget(control)
            fields.addLayout(field, stretch)
        root.addLayout(fields)

        metrics = QHBoxLayout()
        metrics.setSpacing(8)
        self.probe = QLabel()
        self.probe.setObjectName("micro")
        self.estimate = QLabel()
        self.estimate.setObjectName("micro")
        self.meeting = QLabel()
        self.meeting.setObjectName("micro")
        metrics.addWidget(self.probe)
        metrics.addWidget(self.estimate)
        metrics.addStretch()
        metrics.addWidget(self.meeting)
        root.addLayout(metrics)

        self.progress = PipelineProgressWidget()
        root.addWidget(self.progress)
        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        root.addWidget(self.error)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.start = QPushButton("Start processing")
        self.start.setObjectName("primary")
        self.retry_video = QPushButton("Retry video")
        self.retry_audio = QPushButton("Retry audio")
        self.retry_transcript = QPushButton("Retry transcript")
        self.retry_speakers = QPushButton("Retry SpeakerID")
        retry_actions = QHBoxLayout()
        retry_actions.setSpacing(6)
        self.retry_label = QLabel("Recovery options")
        self.retry_label.setObjectName("micro")
        retry_actions.addWidget(self.retry_label)
        retry_actions.addWidget(self.retry_video)
        retry_actions.addWidget(self.retry_audio)
        retry_actions.addWidget(self.retry_transcript)
        retry_actions.addWidget(self.retry_speakers)
        retry_actions.addStretch()
        root.addLayout(retry_actions)
        self.remove = QPushButton("Remove")
        self.remove.setObjectName("dangerGhost")
        self.open_source = QPushButton("Open source")
        self.open_source.setObjectName("ghost")
        self.open_work = QPushButton("Open work folder")
        self.open_work.setObjectName("ghost")
        self.open_meeting = QPushButton("Open meeting page")
        self.open_meeting.setObjectName("ghost")
        self.details_toggle = QToolButton()
        self.details_toggle.setText("Diagnostics")
        self.details_toggle.setCheckable(True)
        self.copy_details = QPushButton("Copy diagnostics")
        self.copy_details.setObjectName("ghost")
        actions.addWidget(self.start)
        actions.addWidget(self.remove)
        actions.addWidget(self.open_source)
        actions.addWidget(self.open_work)
        actions.addWidget(self.open_meeting)
        actions.addStretch()
        actions.addWidget(self.copy_details)
        actions.addWidget(self.details_toggle)
        root.addLayout(actions)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(170)
        self.details.hide()
        root.addWidget(self.details)

        self.title.editingFinished.connect(self._save_metadata)
        self.datetime.editingFinished.connect(self._save_metadata)
        self.client.currentIndexChanged.connect(self._save_metadata)
        self.preset.currentIndexChanged.connect(self._change_preset)
        self.language.currentIndexChanged.connect(self._change_language)
        self.start.clicked.connect(lambda: self._main_window.start_item(self.item_id))
        self.retry_video.clicked.connect(lambda: self._main_window.retry_artifact(self.item_id, "video"))
        self.retry_audio.clicked.connect(lambda: self._main_window.retry_artifact(self.item_id, "audio"))
        self.retry_transcript.clicked.connect(
            lambda: self._main_window.retry_artifact(self.item_id, "transcript")
        )
        self.retry_speakers.clicked.connect(
            lambda: self._main_window.retry_artifact(self.item_id, "speakers")
        )
        self.remove.clicked.connect(lambda: self._main_window.remove_item(self.item_id))
        self.open_source.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(view.item.source.path))
        )
        self.open_work.clicked.connect(lambda: self._main_window.open_work(self.item_id))
        self.open_meeting.clicked.connect(lambda: self._main_window.open_meeting(self.item_id))
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

    def _change_language(self) -> None:
        self._main_window.change_language(self.item_id, str(self.language.currentData()))

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
        if force_fields or not self.language.hasFocus():
            self.language.blockSignals(True)
            self.language.setCurrentIndex(self.language.findData(view.item.language))
            self.language.blockSignals(False)
        if force_fields or not self.client.hasFocus():
            selected = self.client.findData(view.item.client_id)
            self.client.blockSignals(True)
            self.client.setCurrentIndex(max(0, selected))
            self.client.blockSignals(False)
        rendered_status = "Scheduled" if scheduled and view.active_stage is None else view.status
        status_text = (
            f"Completed · {view.final_size}"
            if rendered_status == "Completed" and view.final_size is not None
            else rendered_status
        )
        status_color, status_background = (
            ("#4ade80", "rgba(34, 197, 94, 0.12)")
            if rendered_status == "Completed"
            else ("#f87171", "rgba(239, 68, 68, 0.12)")
            if rendered_status.startswith("Needs attention")
            else ("#fbbf24", "rgba(245, 158, 11, 0.12)")
            if rendered_status.startswith(("Processing", "Scheduled"))
            else ("#c9c9d1", "rgba(201, 201, 209, 0.10)")
        )
        self.status.setText(f"  •  {status_text}  ")
        self.status.setStyleSheet(
            f"background: {status_background}; color: {status_color}; border-radius: 10px; "
            "font-size: 12px; font-weight: 600; padding: 2px 5px;"
        )
        self.probe.setText(view.probe_summary)
        self.estimate.setText(f"Estimated video · {view.estimated_size}")
        self.meeting.setText(
            f"Meeting #{view.item.server_meeting_id}" if view.item.server_meeting_id else "Not on server"
        )
        self.progress.set_progress(
            view,
            self._main_window.coordinator.item_progress(self.item_id),
        )
        failed = next((stage for stage in view.stages if stage.user_error), None)
        self.error.setText(failed.user_error if failed and failed.user_error else "")
        self.error.setVisible(failed is not None)
        self.details.setPlainText(diagnostic_text(view))
        immutable = view.metadata_locked or scheduled or view.active_stage is not None
        for editable in (self.client, self.title, self.datetime, self.preset, self.language):
            editable.setEnabled(not immutable)
        self.remove.setEnabled(view.removable and not scheduled and view.active_stage is None)
        retry_buttons = {
            "video": self.retry_video,
            "audio": self.retry_audio,
            "transcript": self.retry_transcript,
            "speakers": self.retry_speakers,
        }
        self.retry_label.setVisible(bool(view.retryable_artifacts))
        for name, button in retry_buttons.items():
            button.setVisible(name in view.retryable_artifacts)
            button.setEnabled(not scheduled and view.active_stage is None)
        self.start.setText(
            f"Retry {failed.stage.value.replace('_', ' ')}" if failed is not None else "Start processing"
        )
        self.start.setEnabled(
            not scheduled and view.active_stage is None and view.completed_stages < len(STAGE_ORDER)
        )
        self.open_meeting.setVisible(
            view.item.server_meeting_id is not None and self._main_window.controller.api_base_url is not None
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
        self._settings = QSettings()
        self.setWindowTitle("Minutory Worker")
        self.resize(1320, 820)
        self.setMinimumSize(1080, 680)
        self.setAcceptDrops(True)
        self.setStyleSheet(DARK_STYLE)

        central = QWidget()
        central.setObjectName("appShell")
        app_layout = QHBoxLayout(central)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(0)

        surface = QWidget()
        surface.setObjectName("mainSurface")
        shell = QVBoxLayout(surface)
        shell.setContentsMargins(32, 28, 32, 24)
        shell.setSpacing(16)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_mark = QLabel("M")
        brand_mark.setObjectName("brandMark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(26, 26)
        brand_name = QLabel("Minutory")
        brand_name.setObjectName("brandName")
        brand_row.addWidget(brand_mark)
        brand_row.addWidget(brand_name)
        brand_row.addStretch()
        processor = QLabel("AMD local processor · Online")
        processor.setStyleSheet("color: #4ade80;")
        brand_row.addWidget(processor)
        shell.addLayout(brand_row)

        header_row = QHBoxLayout()
        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("Ingestion queue")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Prepare, transcribe, and upload meetings from this Windows machine.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(subtitle)
        header_row.addLayout(header, 1)

        self.add_button = QPushButton("Add files")
        self.start_batch = QPushButton("Start pending")
        self.start_batch.setObjectName("primary")
        header_row.addWidget(self.add_button)
        header_row.addWidget(self.start_batch)
        shell.addLayout(header_row)

        stats_container = QWidget()
        stats_container.setFixedHeight(44)
        stats_stack = QStackedLayout(stats_container)
        stats_stack.setContentsMargins(0, 0, 0, 0)
        stats_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self.global_progress = QProgressBar()
        self.global_progress.setObjectName("globalProgress")
        self.global_progress.setRange(0, 100)
        self.global_progress.setValue(0)
        self.global_progress.setTextVisible(False)
        self.global_progress.setAccessibleName("Overall queue progress")
        stats_stack.addWidget(self.global_progress)

        stats_overlay = QWidget()
        stats_overlay.setObjectName("statsOverlay")
        stats = QHBoxLayout(stats_overlay)
        stats.setContentsMargins(20, 0, 20, 0)
        stats.setSpacing(28)
        self.total_value = QLabel("0")
        self.ready_value = QLabel("0")
        self.processing_value = QLabel("0")
        self.attention_value = QLabel("0")
        self.processing_value.setStyleSheet("color: #fbbf24;")
        self.attention_value.setStyleSheet("color: #f87171;")
        for value, label in (
            (self.total_value, "queued"),
            (self.ready_value, "ready"),
            (self.processing_value, "processing"),
            (self.attention_value, "needs attention"),
        ):
            value.setObjectName("metricValue")
            metric = QHBoxLayout()
            metric.setSpacing(7)
            metric_label = QLabel(label)
            metric_label.setObjectName("metricLabel")
            metric.addWidget(value)
            metric.addWidget(metric_label)
            stats.addLayout(metric)
        stats.addStretch()
        self.global_progress_label = QLabel()
        self.global_progress_label.setObjectName("overallQueueLabel")
        self.global_progress_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.global_progress_label.setTextFormat(Qt.TextFormat.RichText)
        stats.addWidget(self.global_progress_label)
        stats_stack.addWidget(stats_overlay)
        stats_stack.setCurrentWidget(stats_overlay)
        shell.addWidget(stats_container)

        primary_actions = QHBoxLayout()
        primary_actions.setSpacing(6)
        section_title = QLabel("Meeting files")
        section_title.setObjectName("sectionTitle")
        primary_actions.addWidget(section_title)
        primary_actions.addStretch()
        self.refresh_button = QPushButton("Refresh clients && state")
        self.preflight_button = QPushButton("Preflight unprobed")
        self.cancel_button = QPushButton("Cancel media command")
        self.clear_all_button = QPushButton("Clear all")
        self.refresh_button.setObjectName("ghost")
        self.preflight_button.setObjectName("ghost")
        self.cancel_button.setObjectName("ghost")
        self.clear_all_button.setObjectName("dangerGhost")
        primary_actions.addWidget(self.refresh_button)
        primary_actions.addWidget(self.preflight_button)
        primary_actions.addWidget(self.cancel_button)
        primary_actions.addWidget(self.clear_all_button)
        shell.addLayout(primary_actions)

        self.notice = QLabel("Drop MP4, MOV, AVI, or WebM files anywhere in this window.")
        self.notice.setObjectName("notice")
        self.notice.setAccessibleName("Worker status")
        self.notice.setWordWrap(True)
        shell.addWidget(self.notice)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.queue_widget = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_widget)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(10)
        self.empty = QLabel("No videos queued yet. Drop several recordings here or choose Add files.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setObjectName("muted")
        self.empty.setMinimumHeight(220)
        self.queue_layout.addWidget(self.empty)
        self.queue_layout.addStretch()
        self.scroll_area.setWidget(self.queue_widget)
        queue_scrollbar = self.scroll_area.verticalScrollBar()
        queue_scrollbar.setObjectName("queueScrollbar")
        queue_scrollbar.rangeChanged.connect(self._sync_queue_margin)
        shell.addWidget(self.scroll_area, 1)
        app_layout.addWidget(surface, 1)
        self.setCentralWidget(central)
        self._restore_window_geometry()

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
        self.notice.setObjectName("noticeError" if error else "notice")
        self.style().unpolish(self.notice)
        self.style().polish(self.notice)

    def _sync_queue_margin(self, _minimum: int = 0, _maximum: int = 0) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        right = scrollbar.width() if scrollbar.maximum() > scrollbar.minimum() else 0
        self.queue_layout.setContentsMargins(0, 0, right, 0)

    @staticmethod
    def _screen_fingerprint() -> str:
        resolutions = sorted(
            (screen.geometry().width(), screen.geometry().height())
            for screen in QGuiApplication.screens()
        )
        return json.dumps(resolutions)

    def _restore_window_geometry(self) -> None:
        if self._settings.value("window/screen_fingerprint") != self._screen_fingerprint():
            return
        geometry = self._settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _save_window_geometry(self) -> None:
        self._settings.setValue("window/screen_fingerprint", self._screen_fingerprint())
        self._settings.setValue("window/geometry", self.saveGeometry())

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
        self.total_value.setText(str(len(views)))
        self.ready_value.setText(
            str(
                sum(
                    view.active_stage is None
                    and view.status in {"New", "Completed"}
                    and not self.coordinator.is_scheduled(view.item.item_id)
                    for view in views
                )
            )
        )
        self.processing_value.setText(
            str(
                sum(
                    view.active_stage is not None or self.coordinator.is_scheduled(view.item.item_id)
                    for view in views
                )
            )
        )
        self.attention_value.setText(str(sum(view.status.startswith("Needs attention") for view in views)))
        overall = (
            round(
                sum(
                    pipeline_progress(
                        view,
                        self.coordinator.item_progress(view.item.item_id),
                    ).overall_percent
                    for view in views
                )
                / len(views)
            )
            if views
            else 0
        )
        self._set_global_progress(overall)
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

    def _set_global_progress(self, percent: int) -> None:
        self.global_progress.setValue(percent)
        self.global_progress_label.setText(
            f'Overall queue - <span style="color:#4ade80; font-weight:600">{percent}%</span>'
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

    def change_language(self, item_id: str, language: str) -> None:
        try:
            self.controller.set_language(item_id, language)
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

    def open_meeting(self, item_id: str) -> None:
        item = self.controller.store.get_item(item_id)
        if item.server_meeting_id is None or self.controller.api_base_url is None:
            return
        QDesktopServices.openUrl(QUrl(f"{self.controller.api_base_url}/meetings/{item.server_meeting_id}"))

    def _pipeline_event(self, kind: str, item_id: str, value: object) -> None:
        if kind == "progress":
            card = self.cards.get(item_id)
            if card is not None and isinstance(value, tuple) and len(value) == 2:
                stage, percent = value
                if isinstance(stage, Stage) and isinstance(percent, int):
                    card.progress.set_progress(self.controller.view(item_id), (stage, percent))
                    views = self.controller.views()
                    overall = (
                        round(
                            sum(
                                pipeline_progress(
                                    view,
                                    self.coordinator.item_progress(view.item.item_id),
                                ).overall_percent
                                for view in views
                            )
                            / len(views)
                        )
                        if views
                        else 0
                    )
                    self._set_global_progress(overall)
            return
        self.render_state()
        if kind == "failed":
            self.show_notice(f"Item paused safely: {value}", error=True)
        elif kind == "deferred":
            self.show_notice(str(value))
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
        self._save_window_geometry()
        event.accept()
