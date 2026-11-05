"""Encoding adaptation for console output."""

import sys


def setup_output() -> None:
    """Keep the system encoding on a console (GBK on Chinese Windows) and switch to UTF-8 when redirected to a file or a pipe."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
            elif (stream.encoding or "").lower().replace("-", "") != "utf8":
                stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
