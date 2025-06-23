from dataclasses import dataclass
from enum import Enum

# instruções possiveis
class InstructionType(Enum):
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    DIV = "DIV"
    LOAD = "LOAD"
    STORE = "STORE"
    BEQ = "BEQ"
    BNE = "BNE"

# status das instruções
class InstructionStatus(Enum):
    WAITING = "Waiting"
    ISSUED = "Issued"
    EXECUTING = "Executing"
    WRITE_BACK = "Write Back"
    COMMITTED = "Committed"
    CANCELLED = "Cancelled"

@dataclass
class Instruction:
    id: int
    type: InstructionType = None
    rd: str = ""
    rs: str = ""
    rt: str = ""
    immediate: int = 0
    address: str = ""
    status: InstructionStatus = InstructionStatus.WAITING
    issue_cycle: int = -1
    exec_start_cycle: int = -1
    exec_end_cycle: int = -1
    write_back_cycle: int = -1
    commit_cycle: int = -1
    rob_entry: int = -1
    reservation_station: int = -1
    original_line: str = ""