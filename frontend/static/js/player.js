/**
 * Plays mapped tab positions using Tone.js (Web Audio).
 * Supports play, pause, stop, and seek.
 */
class TabPlayer {
  constructor() {
    this.positions = [];
    this.synth = null;
    this.endTimer = null;
    this.progressTimer = null;
    this.playbackStartMs = 0;
    this.totalDuration = 0;
    this.currentTime = 0;
    this.playing = false;
    this.scrubbing = false;
    this.wasPlayingBeforeScrub = false;
    this.onProgress = null;
    this.onStateChange = null;
  }

  _createSynth() {
    const synth = new Tone.PolySynth(Tone.Synth, {
      maxPolyphony: 8,
      oscillator: { type: "triangle" },
      envelope: { attack: 0.005, decay: 0.4, sustain: 0.22, release: 0.5 },
    }).toDestination();
    synth.volume.value = -8;
    return synth;
  }

  _destroySynth() {
    if (!this.synth) {
      return;
    }
    try {
      this.synth.releaseAll();
    } catch (_) {
      // Synth may already be disposed.
    }
    this.synth.dispose();
    this.synth = null;
  }

  _clearTimers() {
    if (this.endTimer) {
      clearTimeout(this.endTimer);
      this.endTimer = null;
    }
    if (this.progressTimer) {
      cancelAnimationFrame(this.progressTimer);
      this.progressTimer = null;
    }
  }

  _getElapsed() {
    if (!this.playing) {
      return this.currentTime;
    }
    return this.currentTime + (performance.now() - this.playbackStartMs) / 1000;
  }

  _emitState() {
    if (typeof this.onStateChange === "function") {
      this.onStateChange({
        playing: this.playing,
        currentTime: this._getElapsed(),
        totalDuration: this.totalDuration,
      });
    }
  }

  _emitProgress(elapsedSeconds) {
    if (typeof this.onProgress === "function") {
      this.onProgress(Math.max(0, Math.min(elapsedSeconds, this.totalDuration)));
    }
  }

  _trackProgress() {
    const tick = () => {
      if (!this.playing) {
        return;
      }
      const elapsed = this._getElapsed();
      this._emitProgress(elapsed);
      if (elapsed >= this.totalDuration) {
        this._finish();
        return;
      }
      this.progressTimer = requestAnimationFrame(tick);
    };
    this.progressTimer = requestAnimationFrame(tick);
  }

  _scheduleNotes(fromTime) {
    const contextStart = Tone.now() + 0.08;

    for (const entry of this.positions) {
      if (entry.end <= fromTime) {
        continue;
      }

      let when;
      let duration;
      if (entry.start >= fromTime) {
        duration = Math.max(entry.end - entry.start, 0.06);
        when = contextStart + (entry.start - fromTime);
      } else {
        duration = Math.max(entry.end - fromTime, 0.06);
        when = contextStart;
      }

      this.synth.triggerAttackRelease(entry.note, duration, when);
    }
  }

  _halt(resetPosition = false) {
    this._clearTimers();
    if (this.playing) {
      this.currentTime = this._getElapsed();
    }
    this._destroySynth();
    this.playing = false;
    if (resetPosition) {
      this.currentTime = 0;
    }
  }

  _finish() {
    this._halt(false);
    this.currentTime = this.totalDuration;
    this._emitState();
    this._emitProgress(this.currentTime);
  }

  load(positions) {
    this.stop();
    this.positions = Array.isArray(positions) ? positions : [];
    this.totalDuration =
      this.positions.reduce((max, note) => Math.max(max, note.end), 0) + 0.25;
    return this.positions.length > 0;
  }

  async play() {
    if (!this.positions.length || this.playing) {
      return;
    }

    if (this.currentTime >= this.totalDuration - 0.05) {
      this.currentTime = 0;
    }

    await Tone.start();
    this._clearTimers();
    this._destroySynth();

    this.synth = this._createSynth();
    this.playing = true;
    this.playbackStartMs = performance.now();
    this._scheduleNotes(this.currentTime);
    this._emitState();

    const remainingMs = (this.totalDuration - this.currentTime) * 1000 + 200;
    this.endTimer = window.setTimeout(() => this._finish(), remainingMs);
    this._trackProgress();
  }

  pause() {
    if (!this.playing) {
      return;
    }
    this._halt(false);
    this._emitState();
    this._emitProgress(this.currentTime);
  }

  stop() {
    const hadPosition = this.currentTime > 0 || this.playing;
    this._halt(true);
    if (hadPosition || !this.playing) {
      this._emitState();
      this._emitProgress(0);
    }
  }

  seek(seconds) {
    if (!this.positions.length || this.totalDuration <= 0) {
      return;
    }

    const target = Math.max(0, Math.min(seconds, this.totalDuration));
    const wasPlaying = this.playing;

    if (this.playing) {
      this._halt(false);
    }

    this.currentTime = target;
    this._emitProgress(this.currentTime);

    if (wasPlaying) {
      this.play();
    } else {
      this._emitState();
    }
  }

  beginScrub() {
    this.wasPlayingBeforeScrub = this.playing;
    if (this.playing) {
      this._halt(false);
    }
    this.scrubbing = true;
  }

  scrubTo(seconds) {
    if (!this.positions.length || this.totalDuration <= 0) {
      return;
    }
    this.currentTime = Math.max(0, Math.min(seconds, this.totalDuration));
    this._emitProgress(this.currentTime);
  }

  endScrub() {
    if (!this.scrubbing) {
      return;
    }
    this.scrubbing = false;
    if (this.wasPlayingBeforeScrub) {
      this.play();
    } else {
      this._emitState();
    }
  }

  seekRatio(ratio) {
    this.seek(ratio * this.totalDuration);
  }

  scrubToRatio(ratio) {
    this.scrubTo(ratio * this.totalDuration);
  }
}

window.TabPlayer = TabPlayer;
