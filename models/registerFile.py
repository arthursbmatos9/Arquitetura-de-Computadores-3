from typing import Optional, Tuple

class RegisterFile:
    def __init__(self):
        self.registers = {f"R{i}": 0.0 for i in range(32)}
        self.qi = {f"R{i}": None for i in range(32)}
    
    def read(self, reg: str) -> Tuple[Optional[float], Optional[str]]:
        return self.registers.get(reg, 0.0), self.qi.get(reg)
    
    def write(self, reg: str, value: float, rob_tag: str = None):
        self.registers[reg] = value
        if rob_tag and self.qi[reg] == rob_tag:
            self.qi[reg] = None
    
    def set_pending(self, reg: str, rob_tag: str):
        self.qi[reg] = rob_tag