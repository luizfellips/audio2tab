"""Correct pitch errors common in synthetic / compressed guitar audio."""

from __future__ import annotations

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.utils.pitch import midi_number_to_pitch, pitch_to_midi

# Octave (+12) only by default; wider intervals are more aggressive.
HARMONIC_INTERVALS = (12,)


def _note_amplitude(note: NoteEvent) -> float:
    return note.amplitude if note.amplitude > 0 else note.velocity / 127.0


def _note_strength(note: NoteEvent) -> float:
    energy = note.amplitude if note.amplitude > 0 else note.velocity / 127.0
    return energy * max(note.duration, 0.01)


def _overlaps(a: NoteEvent, b: NoteEvent) -> bool:
    return a.start < b.end and b.start < a.end


def _time_overlap_ratio(a: NoteEvent, b: NoteEvent) -> float:
    start = max(a.start, b.start)
    end = min(a.end, b.end)
    if end <= start:
        return 0.0
    overlap = end - start
    shorter = min(a.duration, b.duration)
    return overlap / shorter if shorter > 0 else 0.0


def fold_harmonic_ghosts(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    """Drop higher detections when a overlapping lower harmonic partner exists."""
    if not settings.harmonic_fold_enabled or len(notes) < 2:
        return notes

    ordered = sorted(notes, key=lambda note: (note.start, pitch_to_midi(note.pitch)))
    drop: set[int] = set()

    for high_index, high in enumerate(ordered):
        if high_index in drop:
            continue
        try:
            high_midi = pitch_to_midi(high.pitch)
        except Exception:
            continue

        for interval in HARMONIC_INTERVALS:
            low_midi = high_midi - interval
            if low_midi < settings.guitar_min_midi or low_midi > settings.guitar_max_midi:
                continue
            low_pitch = midi_number_to_pitch(low_midi)

            for low_index, low in enumerate(ordered):
                if low_index == high_index or low_index in drop:
                    continue
                if low.pitch != low_pitch:
                    continue
                if _time_overlap_ratio(high, low) < 0.40:
                    continue
                # Drop the upper octave only when the lower partner is nearly as loud.
                if _note_amplitude(low) >= _note_amplitude(high) * 0.85:
                    drop.add(high_index)
                    break
            if high_index in drop:
                break

    return [note for index, note in enumerate(ordered) if index not in drop]


def fold_unpaired_octave_errors(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    """Fold lone high notes down an octave when no fundamental partner was detected."""
    if not settings.harmonic_fold_enabled or not settings.harmonic_fold_unpaired_octaves:
        return notes

    ordered = sorted(notes, key=lambda note: note.start)
    corrected: list[NoteEvent] = []
    fold_threshold_midi = settings.guitar_min_midi + 24  # above ~E4 region

    for index, note in enumerate(ordered):
        try:
            midi_number = pitch_to_midi(note.pitch)
        except Exception:
            corrected.append(note.model_copy())
            continue

        if midi_number < fold_threshold_midi:
            corrected.append(note.model_copy())
            continue

        lower_midi = midi_number - 12
        if lower_midi < settings.guitar_min_midi:
            corrected.append(note.model_copy())
            continue

        has_partner = any(
            pitch_to_midi(other.pitch) == lower_midi and _overlaps(note, other)
            for other in ordered
            if other is not note
        )
        if has_partner:
            corrected.append(note.model_copy())
            continue

        previous = corrected[-1] if corrected else None
        if previous is None:
            corrected.append(note.model_copy())
            continue

        try:
            prev_midi = pitch_to_midi(previous.pitch)
        except Exception:
            corrected.append(note.model_copy())
            continue

        current_jump = abs(midi_number - prev_midi)
        folded_jump = abs(lower_midi - prev_midi)
        gap = max(0.0, note.start - previous.end)

        if folded_jump + 2 < current_jump and gap < 0.35:
            corrected.append(
                note.model_copy(update={"pitch": midi_number_to_pitch(lower_midi)})
            )
            continue

        corrected.append(note.model_copy())

    return corrected


def collapse_semitone_shimmer(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    """Merge rapid ±1 semitone alternation (common with synthetic partials)."""
    if not settings.semitone_shimmer_collapse or len(notes) < 2:
        return notes

    ordered = sorted(notes, key=lambda note: note.start)
    groups: list[list[NoteEvent]] = [[ordered[0]]]
    window = settings.semitone_shimmer_window_sec

    for note in ordered[1:]:
        previous = groups[-1][-1]
        try:
            interval = abs(pitch_to_midi(note.pitch) - pitch_to_midi(previous.pitch))
        except Exception:
            interval = 99

        if note.start - previous.start <= window and interval <= 1:
            groups[-1].append(note)
        else:
            groups.append([note])

    collapsed: list[NoteEvent] = []
    for group in groups:
        if len(group) == 1:
            collapsed.append(group[0].model_copy())
            continue
        best = max(group, key=_note_strength)
        merged = best.model_copy(
            update={
                "start": min(note.start for note in group),
                "end": max(note.end for note in group),
                "velocity": max(note.velocity for note in group),
                "amplitude": max(note.amplitude for note in group),
            }
        )
        collapsed.append(merged)

    return sorted(collapsed, key=lambda note: (note.start, note.pitch))


def apply_harmonic_corrections(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    notes = collapse_semitone_shimmer(notes, settings)
    notes = fold_harmonic_ghosts(notes, settings)
    return fold_unpaired_octave_errors(notes, settings)
