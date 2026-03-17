import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.theme import Theme

THEME = Theme({
    "pass": "bold green",
    "fail": "bold red",
    "skip": "bold yellow",
    "info": "dim cyan",
    "header": "bold cyan",
})

console = Console(theme=THEME, stderr=False)

_file_handler: logging.FileHandler | None = None


class _CheckErrorCapture(logging.Handler):
    """Captures WARNING/ERROR messages during check execution for brief display."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []
        self.capturing = False

    def emit(self, record: logging.Record) -> None:
        if self.capturing:
            self.messages.append(record.getMessage())

    def start(self) -> None:
        self.messages.clear()
        self.capturing = True

    def stop(self) -> list[str]:
        self.capturing = False
        msgs = list(self.messages)
        self.messages.clear()
        return msgs


error_capture = _CheckErrorCapture()


def setup_logging(log_path: Path | None = None, verbose: bool = False) -> None:
    """Configure root logger.

    Console gets NO automatic log output (we print manually via console.print).
    File handler gets everything at DEBUG level.
    In verbose mode, a stream handler at DEBUG is added for troubleshooting.
    """
    global _file_handler

    logging.root.setLevel(logging.DEBUG)
    logging.root.handlers.clear()

    logging.root.addHandler(error_capture)

    if verbose:
        stream = logging.StreamHandler(sys.stdout)
        stream.setLevel(logging.DEBUG)
        stream.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        logging.root.addHandler(stream)

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _file_handler = logging.FileHandler(filename=log_path, encoding="utf-8")
        _file_handler.setLevel(logging.DEBUG)
        _file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logging.root.addHandler(_file_handler)
