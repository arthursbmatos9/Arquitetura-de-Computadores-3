from dataclasses import dataclass
from typing import Optional

from models.instruction import InstructionType

@dataclass
class ROBEntry:
    id: int
    instruction_id: int = -1
    type: Optional[InstructionType] = None
    destination: str = ""
    value: Optional[float] = None
    ready: bool = False
    speculative: bool = False