import pretty_midi

# Standard tuning: string 1 (high E) through string 6 (low E)
STANDARD_TUNING: dict[int, int] = {
    1: 64,  # E4
    2: 59,  # B3
    3: 55,  # G3
    4: 50,  # D3
    5: 45,  # A2
    6: 40,  # E2
}

DEFAULT_MAX_FRET = 24


class FretboardMappingError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def pitch_to_midi(pitch: str) -> int:
    try:
        return pretty_midi.note_name_to_number(pitch)
    except Exception as exc:
        raise FretboardMappingError(f"Invalid pitch name: {pitch}") from exc


def find_all_positions(
    pitch: str,
    max_fret: int = DEFAULT_MAX_FRET,
    tuning: dict[int, int] | None = None,
) -> list[tuple[int, int]]:
    tuning = tuning or STANDARD_TUNING
    midi_number = pitch_to_midi(pitch)
    positions: list[tuple[int, int]] = []

    for string_number, open_midi in tuning.items():
        fret = midi_number - open_midi
        if 0 <= fret <= max_fret:
            positions.append((string_number, fret))

    if not positions:
        raise FretboardMappingError(
            f"No playable position for {pitch} within {max_fret} frets"
        )

    return positions


def _score_position(
    string_number: int,
    fret: int,
    previous: tuple[int, int] | None,
    preferred_max_fret_string1: int = 12,
) -> int:
    score = 0

    if fret == 0:
        score += 1000

    score -= fret * 10
    score -= (string_number - 1) * 2

    if string_number == 1 and fret > preferred_max_fret_string1:
        score -= (fret - preferred_max_fret_string1) * 15

    if previous is not None:
        prev_string, prev_fret = previous
        fret_distance = abs(fret - prev_fret)
        string_distance = abs(string_number - prev_string)

        score -= fret_distance * 8
        score -= string_distance * 5

        if fret_distance > 4:
            score -= 40

    return score


def select_position(
    pitch: str,
    previous: tuple[int, int] | None = None,
    max_fret: int = DEFAULT_MAX_FRET,
    tuning: dict[int, int] | None = None,
    preferred_max_fret_string1: int = 12,
) -> tuple[int, int]:
    candidates = find_all_positions(pitch, max_fret=max_fret, tuning=tuning)
    return max(
        candidates,
        key=lambda pos: (
            _score_position(
                pos[0],
                pos[1],
                previous,
                preferred_max_fret_string1=preferred_max_fret_string1,
            ),
            -pos[1],
            -pos[0],
        ),
    )
