"""Desktop smoke fixture: real Qt/SQLite/FFmpeg, isolated API, no uploads or ASR.

Run from worker root: .venv/bin/python tests/manual/linux_gui.py /tmp/worker-smoke
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from minutory_worker.gui.window import MainWindow
from minutory_worker.media import MediaService, SubprocessRunner
from minutory_worker.orchestrator import Orchestrator
from minutory_worker.presentation import QueueController
from minutory_worker.state import StateStore


class LocalApi:
    def list_clients(self):
        return [{"id": 1, "name": "Linux smoke client"}]


class DisabledAsr:
    def transcribe(self, *args, **kwargs):
        raise RuntimeError("Desktop smoke fixture: ASR and uploads are disabled.")


root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv)
app.setApplicationName("Minutory Worker")
store = StateStore(root / "queue.sqlite3")
api = LocalApi()
orchestrator = Orchestrator(
    store,
    MediaService(Path("ffprobe"), Path("ffmpeg"), SubprocessRunner()),
    DisabledAsr(),
    api,
    root / "work",
    video_codec="libx264",
)
window = MainWindow(
    QueueController(
        store, api, timezone="Europe/Bucharest", work_dir=root / "work", api_base_url="http://localhost:8000"
    ),
    orchestrator,
)
window.setWindowTitle("Minutory Worker — Linux smoke test")
window.show()
app.exec()
store.close()
