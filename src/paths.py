"""Relative paths inside the project, all taken from here. 

Every path is derived from the project root, so no script hard-codes an absolute path; 
the root is inferred from this file's location, so running from any working directory points at the same place. 
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BOARDS = ("disease", "drug", "target")
VARIANTS = (
    "ES1", "ES2", "ES3", "ES4",
    "Europe_PMC", "Europe_PMC2", "Europe_PMC3", "Europe_PMC4",
    "PMC1", "PMC2", "PMC3", "PMC4",
)


def board_data(board: str) -> Path:
    """Data directory of a board: input workbooks, output/ and ALL_result/ live here."""
    return ROOT / board


def board_src(board: str) -> Path:
    """Code directory of a board: src/boards/<board>/."""
    return ROOT / "src" / "boards" / board


def advance_data(board: str) -> Path:
    """Data directory of the advance area: each variant's output/ and input workbooks live here."""
    return ROOT / "advance" / board


def advance_src(board: str) -> Path:
    """Code directory of the advance area: src/advance/<board>/."""
    return ROOT / "src" / "advance" / board


def variant_data(board: str, variant: str) -> Path:
    """Result directory of a variant."""
    return advance_data(board) / variant


def variant_src(board: str, variant: str) -> Path:
    """Code directory of a variant."""
    return advance_src(board) / variant


def add_root_to_path(start: Path) -> str:
    """Add the project root to sys.path and return the path that was added 

    Entry scripts call this once before importing src.*, so the shared layer is found from any directory. 
    """
    import sys

    for folder in start.resolve().parents:
        if (folder / "src" / "__init__.py").exists():
            if str(folder) not in sys.path:
                sys.path.insert(0, str(folder))
            return str(folder)
    raise RuntimeError("project root not found (it should contain src/__init__.py)")
