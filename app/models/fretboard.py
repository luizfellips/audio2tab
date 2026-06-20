from pydantic import BaseModel, Field


class FretPosition(BaseModel):
    string: int = Field(ge=1, le=6, description="String number (1 = high E)")
    fret: int = Field(ge=0, description="Fret number (0 = open string)")


class MappedNote(BaseModel):
    note: str = Field(description="Note name with octave, e.g. E4")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    position: FretPosition
