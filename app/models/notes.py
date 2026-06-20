from pydantic import BaseModel, Field


class NoteEvent(BaseModel):
    pitch: str = Field(description="Note name with octave, e.g. E4")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    velocity: int = Field(default=80, ge=0, le=127, description="MIDI velocity")
    amplitude: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Basic Pitch frame energy (0-1)",
    )

    @property
    def duration(self) -> float:
        return self.end - self.start
