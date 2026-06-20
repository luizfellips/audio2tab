/**
 * Note sequence above the tab — brackets highlight the current note during playback.
 */
class NoteLineView {
  constructor(inputEl) {
    this.inputEl = inputEl;
    this.notes = [];
  }

  sequenceText(highlightIndex = -1) {
    return this.notes
      .map((entry, index) => {
        const name = entry.note || "";
        return index === highlightIndex ? `[${name}]` : name;
      })
      .join("  ");
  }

  load(positions) {
    this.notes = [...positions].sort((a, b) => a.start - b.start || a.note.localeCompare(b.note));
    if (!this.inputEl) {
      return;
    }
    this.inputEl.value = this.notes.length ? this.sequenceText() : "";
    this.inputEl.placeholder = this.notes.length ? "" : "No notes to display";
  }

  noteIndexAtTime(elapsedSeconds) {
    if (!this.notes.length) {
      return -1;
    }
    for (let index = this.notes.length - 1; index >= 0; index -= 1) {
      const note = this.notes[index];
      if (elapsedSeconds >= note.start && elapsedSeconds <= note.end + 0.04) {
        return index;
      }
    }
    return -1;
  }

  updatePlayback(elapsedSeconds) {
    if (!this.inputEl || !this.notes.length) {
      return;
    }
    const index = this.noteIndexAtTime(elapsedSeconds);
    if (index >= 0) {
      this.inputEl.value = this.sequenceText(index);
    } else if (elapsedSeconds <= 0) {
      this.inputEl.value = this.sequenceText();
    }
  }

  resetPlayback() {
    if (!this.inputEl) {
      return;
    }
    this.inputEl.value = this.notes.length ? this.sequenceText() : "";
  }
}

/**
 * Vertical playhead line aligned to tab columns during playback.
 */
class TabPlayhead {
  constructor(wrapEl, tabEl) {
    this.wrapEl = wrapEl;
    this.tabEl = tabEl;
    this.lineEl = document.createElement("div");
    this.lineEl.className = "tab-playhead";
    this.lineEl.setAttribute("aria-hidden", "true");
    if (this.wrapEl) {
      this.wrapEl.appendChild(this.lineEl);
    }

    this.notes = [];
    this.noteCharCenters = [];
    this.cellWidth = 1;
    this.charWidth = 0;
    this.paddingLeft = 0;
    this.labelChars = 2;
    this.activeNoteIndex = -1;

    this.options = {
      columnsPerSecond: 8,
      minColumnGap: 2,
      maxColumnGap: 24,
    };

    if (typeof ResizeObserver !== "undefined" && this.tabEl) {
      this.resizeObserver = new ResizeObserver(() => this.measure());
      this.resizeObserver.observe(this.tabEl);
    }

    if (this.tabEl) {
      this.onScroll = () => {
        if (this.activeNoteIndex >= 0) {
          this.paintLine(this.activeNoteIndex);
        }
      };
      this.tabEl.addEventListener("scroll", this.onScroll);
    }
  }

  gapForDelta(deltaSeconds) {
    const gap = Math.round(deltaSeconds * this.options.columnsPerSecond);
    return Math.max(this.options.minColumnGap, Math.min(gap, this.options.maxColumnGap));
  }

  buildNoteCharCenters(notes) {
    if (!notes.length) {
      return [];
    }

    this.cellWidth = Math.max(1, ...notes.map((entry) => String(entry.position.fret).length));
    let offset = this.gapForDelta(0);
    const centers = [];

    for (let index = 0; index < notes.length; index += 1) {
      centers.push(offset + (this.cellWidth - 1) / 2);
      offset += this.cellWidth;
      if (index < notes.length - 1) {
        offset += this.gapForDelta(notes[index + 1].start - notes[index].start);
      }
    }

    return centers;
  }

  measure() {
    if (!this.tabEl) {
      return;
    }

    const style = getComputedStyle(this.tabEl);
    this.paddingLeft = parseFloat(style.paddingLeft) || 0;

    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    if (context) {
      context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      this.charWidth = context.measureText("0").width;
      return;
    }

    const probe = document.createElement("span");
    probe.textContent = "0";
    probe.style.visibility = "hidden";
    probe.style.position = "absolute";
    probe.style.font = style.font;
    this.tabEl.appendChild(probe);
    this.charWidth = probe.getBoundingClientRect().width || 8;
    probe.remove();
  }

  noteIndexAtTime(elapsedSeconds) {
    if (!this.notes.length) {
      return -1;
    }
    for (let index = this.notes.length - 1; index >= 0; index -= 1) {
      const note = this.notes[index];
      if (elapsedSeconds >= note.start && elapsedSeconds <= note.end + 0.04) {
        return index;
      }
    }
    return -1;
  }

  load(positions) {
    this.notes = [...positions].sort((a, b) => a.start - b.start || a.note.localeCompare(b.note));
    this.noteCharCenters = this.buildNoteCharCenters(this.notes);
    this.measure();
    this.resetPlayback();
  }

  paintLine(noteIndex) {
    if (!this.wrapEl || !this.tabEl || noteIndex < 0 || !this.noteCharCenters.length) {
      this.lineEl.hidden = true;
      return;
    }

    this.measure();
    const charCenter = this.labelChars + this.noteCharCenters[noteIndex];
    const contentLeft = this.paddingLeft + charCenter * this.charWidth;
    const left = contentLeft - this.tabEl.scrollLeft;

    this.lineEl.hidden = false;
    this.lineEl.style.left = `${left}px`;
  }

  setLinePosition(noteIndex) {
    if (!this.wrapEl || !this.tabEl || noteIndex < 0 || !this.noteCharCenters.length) {
      this.activeNoteIndex = -1;
      this.lineEl.hidden = true;
      return;
    }

    this.activeNoteIndex = noteIndex;
    this.measure();
    const charCenter = this.labelChars + this.noteCharCenters[noteIndex];
    const contentLeft = this.paddingLeft + charCenter * this.charWidth;

    const scrollLeft = contentLeft - this.tabEl.clientWidth * 0.4;
    this.tabEl.scrollLeft = Math.max(0, scrollLeft);
    this.paintLine(noteIndex);
  }

  updatePlayback(elapsedSeconds) {
    this.setLinePosition(this.noteIndexAtTime(elapsedSeconds));
  }

  resetPlayback() {
    this.activeNoteIndex = -1;
    this.lineEl.hidden = true;
    if (this.tabEl) {
      this.tabEl.scrollLeft = 0;
    }
  }
}

window.NoteLineView = NoteLineView;
window.TabPlayhead = TabPlayhead;
