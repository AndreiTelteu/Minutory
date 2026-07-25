from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import ConfigError, load_config
from .state import StateStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Minutory worker headless diagnostics")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate-config")
    subcommands.add_parser("list-state")
    arguments = parser.parse_args()

    try:
        config = load_config(arguments.env_file)
    except ConfigError as exception:
        parser.error(str(exception))

    if arguments.command == "validate-config":
        print(json.dumps(config.safe_dict(), default=str, indent=2))
        return 0

    store = StateStore(config.state_db)
    try:
        print(json.dumps([item.item_id for item in store.list_items()], indent=2))
    finally:
        store.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
