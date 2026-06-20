import pretty_midi


def pitch_class(pitch: str) -> str:
    """Return pitch letter name without octave, e.g. D#4 -> D#."""
    return pitch[:-1] if pitch and pitch[-1].isdigit() else pitch


def midi_number_to_pitch(note_number: int) -> str:
    return pretty_midi.note_number_to_name(note_number)


def pitch_to_midi(pitch: str) -> int:
    return pretty_midi.note_name_to_number(pitch)
