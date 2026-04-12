from __future__ import annotations

from media_indexer_backend.core.logging import configure_logging
from media_indexer_worker.services.scanner import ScanWorker


def main() -> None:
    configure_logging()
    ScanWorker().run_forever()


if __name__ == "__main__":
    main()

