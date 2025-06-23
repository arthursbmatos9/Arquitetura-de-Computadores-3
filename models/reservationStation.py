from dataclasses import dataclass
from typing import Optional

from models.instruction import InstructionType

@dataclass
class ReservationStation:
    id: int
    busy: bool = False
    op: Optional[InstructionType] = None
    vj: Optional[float] = None
    vk: Optional[float] = None
    qj: Optional[str] = None
    qk: Optional[str] = None
    dest: Optional[str] = None
    instruction_id: int = -1
    cycles_remaining: int = 0