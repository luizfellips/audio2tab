from pathlib import Path

from app.core.config import Settings
from app.models.fretboard import MappedNote

STRING_LABELS: dict[int, str] = {
    1: "e",
    2: "B",
    3: "G",
    4: "D",
    5: "A",
    6: "E",
}

DEFAULT_COLUMN_GAP = 4


def _cell_for_string(
    string_number: int,
    active_string: int,
    fret: int,
    width: int,
) -> str:
    if string_number == active_string:
        return str(fret).rjust(width)
    return "-" * width


def _gap_for_delta(
    delta_seconds: float,
    settings: Settings | None,
) -> int:
    if settings is None:
        return DEFAULT_COLUMN_GAP

    gap = int(round(delta_seconds * settings.tab_columns_per_second))
    return max(settings.tab_min_column_gap, min(gap, settings.tab_max_column_gap))


def generate_tab(
    mapped_notes: list[MappedNote],
    settings: Settings | None = None,
) -> str:
    notes = sorted(mapped_notes, key=lambda note: (note.start, note.note))
    lines = _generate_tab_lines(notes, settings=settings)
    return "\n".join(lines) + "\n"


def _generate_tab_lines(
    notes: list[MappedNote],
    settings: Settings | None = None,
) -> list[str]:
    if not notes:
        return [f"{STRING_LABELS[string_number]}|" for string_number in range(1, 7)]

    cell_width = max(len(str(note.position.fret)) for note in notes)
    leading_gap = "-" * _gap_for_delta(0, settings)
    rows: dict[int, list[str]] = {string_number: [] for string_number in range(1, 7)}

    for string_number in range(1, 7):
        rows[string_number].append(leading_gap)

    for index, note in enumerate(notes):
        for string_number in range(1, 7):
            rows[string_number].append(
                _cell_for_string(
                    string_number,
                    note.position.string,
                    note.position.fret,
                    cell_width,
                )
            )

        if index < len(notes) - 1:
            delta = notes[index + 1].start - note.start
            gap = "-" * _gap_for_delta(delta, settings)
            for string_number in range(1, 7):
                rows[string_number].append(gap)

    return [
        f"{STRING_LABELS[string_number]}|{''.join(rows[string_number])}"
        for string_number in range(1, 7)
    ]


def save_tab(
    mapped_notes: list[MappedNote],
    output_path: Path,
    settings: Settings | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_tab(mapped_notes, settings=settings), encoding="utf-8")
    return output_path
