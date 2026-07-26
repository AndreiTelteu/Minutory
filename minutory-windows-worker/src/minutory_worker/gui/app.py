from __future__ import annotations

import os
import sys
from pathlib import Path

from ..config import load_config
from ..presentation import QueueController
from ..runtime import build_orchestrator


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print("PySide6 is not installed. Run bootstrap.ps1 before starting Minutory Worker.")
        return 2

    app = QApplication(sys.argv)
    app.setApplicationName("Minutory Worker")
    app.setOrganizationName("Minutory")
    env_file = Path(os.environ.get("MINUTORY_ENV_FILE", ".env"))
    try:
        config = load_config(env_file)
        orchestrator = build_orchestrator(config)
    except Exception as exception:
        QMessageBox.critical(None, "Minutory Worker cannot start", str(exception))
        return 2

    from .window import MainWindow

    controller = QueueController(
        orchestrator.store,
        orchestrator.api,
        timezone=config.timezone,
        default_preset=config.compression_preset,
        default_language=config.language,
        work_dir=orchestrator.work_dir,
    )
    window = MainWindow(controller, orchestrator)
    window.show()
    result = app.exec()
    if not window.coordinator.busy:
        orchestrator.store.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
