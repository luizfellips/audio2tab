from pathlib import Path

import librosa
import numpy as np

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.services.harmonic_correction import (
    align_cadence_octaves,
    apply_harmonic_corrections,
    apply_semitone_flat_bias,
    fold_harmonic_ghosts,
    fold_unpaired_octave_errors,
)
from app.utils.pitch import pitch_class, pitch_to_midi


def _note_strength(note: NoteEvent) -> float:
    energy = note.amplitude if note.amplitude > 0 else note.velocity / 127.0
    return energy * max(note.duration, 0.01)


def _overlaps(a: NoteEvent, b: NoteEvent) -> bool:
    return a.start < b.end and b.start < a.end


def _in_guitar_range(note: NoteEvent, settings: Settings) -> bool:
    try:
        midi_number = pitch_to_midi(note.pitch)
    except Exception:
        return False
    return settings.guitar_min_midi <= midi_number <= settings.guitar_max_midi


def _passes_basic_filters(note: NoteEvent, settings: Settings) -> bool:
    energy = note.amplitude if note.amplitude > 0 else note.velocity / 127.0
    in_range = _in_guitar_range(note, settings) if settings.apply_guitar_range_filter else True
    return (
        in_range
        and note.velocity >= settings.min_note_velocity
        and energy >= settings.min_note_amplitude
        and note.duration >= settings.min_note_duration_sec
    )


def _gate_by_audio_energy(
    notes: list[NoteEvent],
    audio_path: Path,
    settings: Settings,
) -> list[NoteEvent]:
    """Drop notes that fall in low-energy (likely silent) audio regions."""
    try:
        audio, sample_rate = librosa.load(str(audio_path), sr=22050, mono=True)
    except Exception:
        return notes

    hop_length = 512
    rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]
    frame_times = librosa.frames_to_time(
        np.arange(len(rms)),
        sr=sample_rate,
        hop_length=hop_length,
    )

    gated: list[NoteEvent] = []
    for note in notes:
        mask = (frame_times >= note.start) & (frame_times <= note.end)
        if not np.any(mask):
            gated.append(note)
            continue

        segment_rms = float(np.mean(rms[mask]))
        if segment_rms >= settings.audio_rms_threshold:
            gated.append(note)

    return gated


def _merge_same_pitch_runs(notes: list[NoteEvent], max_gap_sec: float) -> list[NoteEvent]:
    if not notes:
        return []

    merged: list[NoteEvent] = [notes[0].model_copy()]
    for note in notes[1:]:
        previous = merged[-1]
        if note.pitch == previous.pitch and note.start - previous.end <= max_gap_sec:
            merged[-1] = previous.model_copy(
                update={
                    "end": max(previous.end, note.end),
                    "velocity": max(previous.velocity, note.velocity),
                    "amplitude": max(previous.amplitude, note.amplitude),
                }
            )
            continue
        merged.append(note.model_copy())
    return merged


def _enforce_monophonic(notes: list[NoteEvent]) -> list[NoteEvent]:
    """Legacy overlap handler: replaces at most one overlapping note per insert."""
    ordered = sorted(notes, key=lambda note: (note.start, -_note_strength(note)))
    kept: list[NoteEvent] = []

    for note in ordered:
        replaced = False
        for index, existing in enumerate(kept):
            if not _overlaps(note, existing):
                continue
            if _note_strength(note) > _note_strength(existing):
                kept[index] = note.model_copy()
            replaced = True
            break
        if not replaced:
            kept.append(note.model_copy())

    return sorted(kept, key=lambda note: (note.start, note.pitch))


def _extract_primary_melody(notes: list[NoteEvent]) -> list[NoteEvent]:
    """Keep the strongest note in each overlapping group (better for dense mixes)."""
    if not notes:
        return []

    ordered = sorted(notes, key=lambda note: (note.start, -_note_strength(note)))
    kept: list[NoteEvent] = []

    for note in ordered:
        overlap_indices = [
            index for index, existing in enumerate(kept) if _overlaps(note, existing)
        ]
        if not overlap_indices:
            kept.append(note.model_copy())
            continue

        if any(_note_strength(kept[index]) >= _note_strength(note) for index in overlap_indices):
            continue

        for index in sorted(overlap_indices, reverse=True):
            del kept[index]
        kept.append(note.model_copy())

    return sorted(kept, key=lambda note: (note.start, note.pitch))


def _drop_weak_overlapped(notes: list[NoteEvent], amplitude_cap: float) -> list[NoteEvent]:
    """Remove quiet detections masked by a stronger simultaneous note (octave ghosts)."""
    if amplitude_cap <= 0 or not notes:
        return notes

    kept: list[NoteEvent] = []
    for note in notes:
        energy = note.amplitude if note.amplitude > 0 else note.velocity / 127.0
        if energy >= amplitude_cap:
            kept.append(note)
            continue

        masked = False
        for other in notes:
            if other is note or not _overlaps(note, other):
                continue
            if _note_strength(other) >= _note_strength(note) * 1.4:
                masked = True
                break
        if not masked:
            kept.append(note)

    return kept


def _note_amplitude(note: NoteEvent) -> float:
    return note.amplitude if note.amplitude > 0 else note.velocity / 127.0


def _pick_onset_cluster_note(
    cluster: list[NoteEvent],
    previous_pitch_class: str | None = None,
) -> NoteEvent:
    """Pick cluster winner: prefer lower octave partner, then alternate pitch vs previous."""
    best = max(cluster, key=_note_amplitude)
    best_amp = _note_amplitude(best)

    try:
        best_midi = pitch_to_midi(best.pitch)
    except Exception:
        best_midi = None

    if best_midi is not None:
        for note in cluster:
            try:
                midi = pitch_to_midi(note.pitch)
            except Exception:
                continue
            if midi >= best_midi or best_midi - midi != 12:
                continue
            lower_amp = _note_amplitude(note)
            # Prefer lower octave only when it is nearly as strong (not a weak ghost).
            if lower_amp >= best_amp * 0.85:
                best = note
                best_amp = lower_amp
                best_midi = midi

    if previous_pitch_class:
        ranked = sorted(cluster, key=_note_amplitude, reverse=True)
        top_amp = _note_amplitude(ranked[0])
        for note in ranked:
            if pitch_class(note.pitch) == previous_pitch_class:
                continue
            if _note_amplitude(note) >= top_amp * 0.85:
                return note

    return best


def _collapse_same_pitch_repeats(
    notes: list[NoteEvent],
    min_gap_sec: float,
) -> list[NoteEvent]:
    """Merge rapid same-pitch re-attacks (common Basic Pitch shimmer on AI guitar)."""
    if min_gap_sec <= 0 or len(notes) < 2:
        return notes

    kept: list[NoteEvent] = [notes[0]]
    for note in notes[1:]:
        previous = kept[-1]
        if (
            pitch_class(note.pitch) == pitch_class(previous.pitch)
            and note.start - previous.start < min_gap_sec
        ):
            winner = note if _note_amplitude(note) > _note_amplitude(previous) else previous
            kept[-1] = winner.model_copy(
                update={
                    "start": min(previous.start, note.start),
                    "end": max(previous.end, note.end),
                    "velocity": max(previous.velocity, note.velocity),
                    "amplitude": max(previous.amplitude, note.amplitude),
                }
            )
            continue
        kept.append(note.model_copy())

    return kept


def _merge_consecutive_same_pitch_runs(
    notes: list[NoteEvent],
    max_start_gap_sec: float,
) -> list[NoteEvent]:
    """Merge back-to-back same pitch-class notes when their starts are close together."""
    if max_start_gap_sec <= 0 or len(notes) < 2:
        return notes

    kept: list[NoteEvent] = [notes[0].model_copy()]
    for note in notes[1:]:
        previous = kept[-1]
        if (
            pitch_class(note.pitch) == pitch_class(previous.pitch)
            and note.start - previous.start <= max_start_gap_sec
        ):
            winner = note if _note_amplitude(note) > _note_amplitude(previous) else previous
            kept[-1] = winner.model_copy(
                update={
                    "start": min(previous.start, note.start),
                    "end": max(previous.end, note.end),
                    "velocity": max(previous.velocity, note.velocity),
                    "amplitude": max(previous.amplitude, note.amplitude),
                }
            )
            continue
        kept.append(note.model_copy())

    return kept


def _extract_onset_melody(
    notes: list[NoteEvent],
    cluster_sec: float,
    cluster_split_min_amplitude: float = 0.0,
) -> list[NoteEvent]:
    """Pick one pitch per attack cluster with octave/alternate-pitch heuristics."""
    if not notes:
        return []

    ordered = sorted(notes, key=lambda note: note.start)
    clusters: list[list[NoteEvent]] = [[ordered[0]]]

    for note in ordered[1:]:
        cluster = clusters[-1]
        within_window = note.start - cluster[0].start <= cluster_sec
        if not within_window:
            clusters.append([note])
            continue

        if cluster_split_min_amplitude > 0:
            note_pc = pitch_class(note.pitch)
            cluster_pcs = {pitch_class(existing.pitch) for existing in cluster}
            if (
                note_pc not in cluster_pcs
                and _note_amplitude(note) >= cluster_split_min_amplitude
            ):
                clusters.append([note])
                continue

        cluster.append(note)

    melody: list[NoteEvent] = []
    previous_pitch_class: str | None = None
    for cluster in clusters:
        picked = _pick_onset_cluster_note(cluster, previous_pitch_class)
        melody.append(picked)
        previous_pitch_class = pitch_class(picked.pitch)

    return sorted(melody, key=lambda note: (note.start, note.pitch))


def _apply_melody_extraction(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    mode = settings.melody_extraction_mode.lower()
    if mode == "none":
        return notes
    if mode == "onset":
        return _extract_onset_melody(
            notes,
            cluster_sec=settings.onset_cluster_sec,
            cluster_split_min_amplitude=settings.onset_cluster_split_min_amplitude,
        )
    if settings.enforce_monophonic:
        return _apply_monophonic_mode(notes, settings)
    return notes


def _apply_monophonic_mode(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    if not settings.enforce_monophonic:
        return notes

    mode = settings.monophonic_mode.lower()
    if mode == "none":
        return notes
    if mode == "melody":
        return _extract_primary_melody(notes)
    return _enforce_monophonic(notes)


def _remove_melodic_outliers(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    """Remove short notes that jump unrealistically far from neighbors."""
    if len(notes) < 2:
        return notes

    ordered = sorted(notes, key=lambda note: note.start)
    kept: list[NoteEvent] = [ordered[0]]

    for note in ordered[1:]:
        previous = kept[-1]
        try:
            interval = abs(pitch_to_midi(note.pitch) - pitch_to_midi(previous.pitch))
        except Exception:
            kept.append(note)
            continue

        gap = max(0.0, note.start - previous.end)
        large_jump = interval > settings.max_melodic_jump_semitones
        short_note = note.duration < settings.short_note_max_duration_sec
        tight_gap = gap < settings.tight_gap_sec

        if large_jump and short_note and tight_gap:
            continue

        kept.append(note)

    return kept


def _remove_isolated_spikes(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    """Remove brief notes stranded far from other activity."""
    if len(notes) < 3:
        return notes

    ordered = sorted(notes, key=lambda note: note.start)
    kept: list[NoteEvent] = []

    for index, note in enumerate(ordered):
        if note.duration > settings.isolated_note_max_duration_sec:
            kept.append(note)
            continue

        gap_before = note.start - ordered[index - 1].end if index > 0 else float("inf")
        gap_after = (
            ordered[index + 1].start - note.end if index < len(ordered) - 1 else float("inf")
        )

        if gap_before >= settings.isolated_note_min_gap_sec and gap_after >= settings.isolated_note_min_gap_sec:
            continue

        kept.append(note)

    return kept


def _apply_note_durations(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    """Extend or cap note lengths after pitch cleanup (legato toward next onset)."""
    if settings.note_duration_mode.lower() != "legato" or not notes:
        return notes

    ordered = sorted(notes, key=lambda note: note.start)
    gap = max(0.0, settings.note_legato_gap_sec)
    max_duration = max(0.05, settings.note_max_duration_sec)
    extended: list[NoteEvent] = []

    for index, note in enumerate(ordered):
        end = max(note.end, note.start + settings.min_note_duration_sec)
        if index + 1 < len(ordered):
            legato_end = ordered[index + 1].start - gap
            if legato_end > note.start:
                end = max(end, legato_end)
            end = min(end, note.start + max_duration)
        extended.append(note.model_copy(update={"end": round(end, 2)}))

    return extended


def _collapse_simultaneous_onsets(
    notes: list[NoteEvent],
    window_sec: float,
) -> list[NoteEvent]:
    """When several notes share nearly the same start, keep the loudest one."""
    if window_sec <= 0 or len(notes) < 2:
        return notes

    ordered = sorted(notes, key=lambda note: note.start)
    kept: list[NoteEvent] = [ordered[0].model_copy()]

    for note in ordered[1:]:
        previous = kept[-1]
        if note.start - previous.start <= window_sec:
            if _note_amplitude(note) > _note_amplitude(previous):
                kept[-1] = note.model_copy()
            continue
        kept.append(note.model_copy())

    return kept


def _trim_leading_silence(notes: list[NoteEvent], enabled: bool) -> list[NoteEvent]:
    """Align the first attack to t=0 so playback and tab match the riff start."""
    if not enabled or not notes:
        return notes

    offset = min(note.start for note in notes)
    if offset <= 0.05:
        return notes

    trimmed: list[NoteEvent] = []
    for note in notes:
        start = round(note.start - offset, 2)
        end = round(max(note.end - offset, start + 0.01), 2)
        trimmed.append(note.model_copy(update={"start": start, "end": end}))
    return trimmed


def _normalize_note_timing(notes: list[NoteEvent], settings: Settings) -> list[NoteEvent]:
    """Fix overlapping start/end in the note list (written to notes.json / positions.json)."""
    gap = settings.note_onset_spacing_sec
    min_inter_onset = settings.note_min_inter_onset_sec
    min_duration = max(0.0, settings.min_note_duration_sec)

    if len(notes) < 2 or (gap <= 0 and min_inter_onset <= 0):
        return notes

    ordered = sorted(notes, key=lambda note: note.start)
    normalized: list[NoteEvent] = [ordered[0].model_copy()]

    for note in ordered[1:]:
        current = note.model_copy()
        previous = normalized[-1]

        if gap > 0 and previous.end > current.start - gap:
            trimmed_end = max(previous.start + min_duration, current.start - gap)
            previous = previous.model_copy(update={"end": round(trimmed_end, 2)})
            normalized[-1] = previous

        if gap > 0 and current.start < previous.end + gap:
            shift = (previous.end + gap) - current.start
            current = current.model_copy(
                update={
                    "start": round(current.start + shift, 2),
                    "end": round(current.end + shift, 2),
                }
            )

        if min_inter_onset > 0 and current.start - previous.start < min_inter_onset:
            shift = min_inter_onset - (current.start - previous.start)
            current = current.model_copy(
                update={
                    "start": round(current.start + shift, 2),
                    "end": round(current.end + shift, 2),
                }
            )

        normalized.append(current)

    return normalized


def clean_notes(
    notes: list[NoteEvent],
    settings: Settings,
    audio_path: Path | None = None,
) -> tuple[list[NoteEvent], int]:
    """Return guitar-focused note list and count of removed events."""
    raw_count = len(notes)

    filtered = [note for note in notes if _passes_basic_filters(note, settings)]

    if audio_path is not None:
        filtered = _gate_by_audio_energy(filtered, audio_path, settings)

    if settings.melody_extraction_mode.lower() == "onset":
        prepared = fold_harmonic_ghosts(filtered, settings)
        prepared = _drop_weak_overlapped(prepared, settings.weak_note_amplitude_cap)
        melodic_line = _extract_onset_melody(
            prepared,
            cluster_sec=settings.onset_cluster_sec,
            cluster_split_min_amplitude=settings.onset_cluster_split_min_amplitude,
        )
        if settings.harmonic_fold_enabled:
            melodic_line = fold_unpaired_octave_errors(melodic_line, settings)
        deduped = _collapse_same_pitch_repeats(
            melodic_line,
            min_gap_sec=settings.same_pitch_repeat_gap_sec,
        )
        deduped = apply_semitone_flat_bias(deduped, settings)
        if settings.harmonic_fold_enabled:
            deduped = align_cadence_octaves(deduped, settings)
    else:
        merged = (
            _merge_same_pitch_runs(filtered, max_gap_sec=settings.merge_same_pitch_max_gap_sec)
            if settings.merge_same_pitch_max_gap_sec > 0
            else filtered
        )
        corrected = apply_harmonic_corrections(merged, settings)
        weakened = _drop_weak_overlapped(corrected, settings.weak_note_amplitude_cap)
        monophonic = _apply_melody_extraction(weakened, settings)
        melodic = _remove_melodic_outliers(monophonic, settings)
        deduped = _remove_isolated_spikes(melodic, settings)

    deduped = _merge_consecutive_same_pitch_runs(
        deduped,
        max_start_gap_sec=settings.merge_consecutive_same_pitch_max_gap_sec,
    )
    deduped = _collapse_simultaneous_onsets(
        deduped,
        window_sec=settings.simultaneous_onset_window_sec,
    )
    deduped = _normalize_note_timing(deduped, settings)
    deduped = _apply_note_durations(deduped, settings)
    deduped = _trim_leading_silence(deduped, settings.trim_leading_silence)

    cleaned: list[NoteEvent] = []
    for note in deduped:
        cleaned.append(
            NoteEvent(
                pitch=note.pitch,
                start=round(note.start, 2),
                end=round(max(note.end, note.start + settings.min_note_duration_sec), 2),
                velocity=note.velocity,
                amplitude=note.amplitude,
            )
        )

    return cleaned, raw_count - len(cleaned)
