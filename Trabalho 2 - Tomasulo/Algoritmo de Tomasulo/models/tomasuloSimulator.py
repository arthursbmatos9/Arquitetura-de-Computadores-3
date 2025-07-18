from typing import List, Dict, Optional, Tuple
import re
from models.branchPredictor import BranchPredictor

from models.instruction import Instruction, InstructionStatus, InstructionType
from models.registerFile import RegisterFile
from models.reservationStation import ReservationStation
from models.robEntry import ROBEntry

class InvalidInstructionError(Exception):
    """Exceção lançada quando uma instrução inválida é encontrada"""
    def __init__(self, line_number: int, instruction: str, message: str = ""):
        self.line_number = line_number
        self.instruction = instruction
        self.message = message
        super().__init__(f"Linha {line_number}: Instrução inválida '{instruction}'" + 
                        (f" - {message}" if message else ""))

class TomasuloSimulator:
    def __init__(self):
        self.instructions: List[Instruction] = []
        self.reservation_stations: List[ReservationStation] = []
        self.rob: List[ROBEntry] = []
        self.register_file = RegisterFile()
        self.branch_predictor = BranchPredictor()
        
        # Armazena erros de parsing para serem reportados
        self.parsing_errors: List[str] = []
        
        self.num_add_stations = 3
        self.num_mul_stations = 2
        self.num_load_stations = 2
        self.rob_size = 16
        
        self.latencies = {
            InstructionType.ADD: 1,
            InstructionType.SUB: 1,
            InstructionType.MUL: 3,
            InstructionType.DIV: 6,
            InstructionType.LOAD: 2,
            InstructionType.STORE: 1,
            InstructionType.BEQ: 1,
            InstructionType.BNE: 1
        }
        
        self.cycle = 0
        self.pc = 0
        self.total_instructions = 0
        self.committed_instructions = 0
        self.bubble_cycles = 0
        self.mispredicted_branches = 0
        self.speculation_depth = 0
        
        self.reset()
    
    def reset(self):
        self.cycle = 0
        self.pc = 0
        self.committed_instructions = 0
        self.bubble_cycles = 0
        self.mispredicted_branches = 0
        self.speculation_depth = 0
        self.parsing_errors = []
        
        for instr in self.instructions:
            instr.status = InstructionStatus.WAITING
            instr.issue_cycle = -1
            instr.exec_start_cycle = -1
            instr.exec_end_cycle = -1
            instr.write_back_cycle = -1
            instr.commit_cycle = -1
            instr.rob_entry = -1
            instr.reservation_station = -1
        
        
        self.reservation_stations = []
        station_id = 0
        
        
        for i in range(self.num_add_stations):
            self.reservation_stations.append(ReservationStation(station_id))
            station_id += 1
        
        
        for i in range(self.num_mul_stations):
            self.reservation_stations.append(ReservationStation(station_id))
            station_id += 1
        
        
        for i in range(self.num_load_stations):
            self.reservation_stations.append(ReservationStation(station_id))
            station_id += 1
        
        
        self.rob = [ROBEntry(i) for i in range(self.rob_size)]
        
        
        self.register_file = RegisterFile()
               
        self.register_file.registers["R1"] = 10.0
        self.register_file.registers["R2"] = 20.0
        self.register_file.registers["R3"] = 5.0
        self.register_file.registers["R4"] = 15.0
    
    def is_valid_register(self, reg: str) -> bool:
        """Verifica se o registrador é válido (R0-R31)"""
        if not reg.startswith('R'):
            return False
        try:
            reg_num = int(reg[1:])
            return 0 <= reg_num <= 31
        except ValueError:
            return False
    
    def parse_instruction(self, line: str, instruction_id: int, line_number: int) -> Optional[Instruction]:
        original_line = line.strip()
        line = original_line.upper()
        
        # Ignorar linhas vazias e comentários
        if not line or line.startswith('#'):
            return None
        
        # Remover comentários inline
        if '#' in line:
            line = line[:line.index('#')].strip()
        
        if not line:  # Se linha ficou vazia após remover comentário
            return None
        
        parts = re.split(r'[,\s]+', line)
        if len(parts) < 2:
            raise InvalidInstructionError(line_number, original_line, 
                                        "Formato inválido - muito poucos argumentos")
        
        instr = Instruction(id=instruction_id, type=InstructionType.ADD, original_line=original_line)
        
        try:
            # Verificar se é uma instrução conhecida
            if parts[0] not in ['ADD', 'SUB', 'MUL', 'DIV', 'LOAD', 'STORE', 'BEQ', 'BNE']:
                raise InvalidInstructionError(line_number, original_line, 
                                            f"Operação '{parts[0]}' não reconhecida")
            
            if parts[0] in ['ADD', 'SUB']:
                if len(parts) != 4:
                    raise InvalidInstructionError(line_number, original_line, 
                                                f"{parts[0]} requer exatamente 3 registradores")
                
                instr.type = InstructionType(parts[0])
                instr.rd = parts[1]
                instr.rs = parts[2]
                instr.rt = parts[3]
                
                # Validar registradores
                for reg in [instr.rd, instr.rs, instr.rt]:
                    if not self.is_valid_register(reg):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Registrador inválido: {reg}")
            
            elif parts[0] in ['MUL', 'DIV']:
                if len(parts) != 4:
                    raise InvalidInstructionError(line_number, original_line, 
                                                f"{parts[0]} requer exatamente 3 registradores")
                
                instr.type = InstructionType(parts[0])
                instr.rd = parts[1]
                instr.rs = parts[2]
                instr.rt = parts[3]
                
                # Validar registradores
                for reg in [instr.rd, instr.rs, instr.rt]:
                    if not self.is_valid_register(reg):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Registrador inválido: {reg}")
            
            elif parts[0] == 'LOAD':
                if len(parts) != 3:
                    raise InvalidInstructionError(line_number, original_line, 
                                                "LOAD requer registrador destino e endereço")
                
                instr.type = InstructionType.LOAD
                instr.rd = parts[1]
                
                if not self.is_valid_register(instr.rd):
                    raise InvalidInstructionError(line_number, original_line, 
                                                f"Registrador destino inválido: {instr.rd}")
                
                # Processar endereço
                if '(' in parts[2]:
                    addr_parts = parts[2].split('(')
                    if len(addr_parts) != 2 or not addr_parts[1].endswith(')'):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    "Formato de endereço inválido para LOAD")
                    
                    try:
                        instr.immediate = int(addr_parts[0]) if addr_parts[0] else 0
                    except ValueError:
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Valor imediato inválido: {addr_parts[0]}")
                    
                    instr.rs = addr_parts[1].rstrip(')')
                    if not self.is_valid_register(instr.rs):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Registrador base inválido: {instr.rs}")
                else:
                    instr.rs = parts[2]
                    if not self.is_valid_register(instr.rs):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Registrador base inválido: {instr.rs}")
            
            elif parts[0] == 'STORE':
                if len(parts) != 3:
                    raise InvalidInstructionError(line_number, original_line, 
                                                "STORE requer registrador fonte e endereço")
                
                instr.type = InstructionType.STORE
                instr.rs = parts[1]  # registrador fonte
                
                if not self.is_valid_register(instr.rs):
                    raise InvalidInstructionError(line_number, original_line, 
                                                f"Registrador fonte inválido: {instr.rs}")
                
                # Processar endereço
                if '(' in parts[2]:
                    addr_parts = parts[2].split('(')
                    if len(addr_parts) != 2 or not addr_parts[1].endswith(')'):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    "Formato de endereço inválido para STORE")
                    
                    try:
                        instr.immediate = int(addr_parts[0]) if addr_parts[0] else 0
                    except ValueError:
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Valor imediato inválido: {addr_parts[0]}")
                    
                    instr.rt = addr_parts[1].rstrip(')')
                    if not self.is_valid_register(instr.rt):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Registrador base inválido: {instr.rt}")
                else:
                    instr.rt = parts[2]
                    if not self.is_valid_register(instr.rt):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Registrador base inválido: {instr.rt}")
            
            elif parts[0] in ['BEQ', 'BNE']:
                if len(parts) != 4:
                    raise InvalidInstructionError(line_number, original_line, 
                                                f"{parts[0]} requer 2 registradores e offset")
                
                instr.type = InstructionType(parts[0])
                instr.rs = parts[1]
                instr.rt = parts[2]
                
                # Validar registradores
                for reg in [instr.rs, instr.rt]:
                    if not self.is_valid_register(reg):
                        raise InvalidInstructionError(line_number, original_line, 
                                                    f"Registrador inválido: {reg}")
                
                # Validar offset
                try:
                    instr.immediate = int(parts[3])
                except ValueError:
                    raise InvalidInstructionError(line_number, original_line, 
                                                f"Offset inválido: {parts[3]}")
            
            return instr
            
        except (IndexError, ValueError) as e:
            raise InvalidInstructionError(line_number, original_line, 
                                        f"Erro de parsing: {str(e)}")
    
    def load_program(self, code: str):
        self.instructions = []
        self.parsing_errors = []
        lines = code.strip().split('\n')
        instruction_id = 0
        
        valid_instructions = []
        invalid_instructions = []
        
        for line_number, line in enumerate(lines, 1):
            try:
                instr = self.parse_instruction(line, instruction_id, line_number)
                if instr:
                    valid_instructions.append(instr)
                    instruction_id += 1
            except InvalidInstructionError as e:
                invalid_instructions.append(str(e))
        
        # Armazenar erros para relatório
        self.parsing_errors = invalid_instructions
        
        # Usar apenas as instruções válidas
        self.instructions = valid_instructions
        self.total_instructions = len(self.instructions)
        
        # Se não há instruções válidas, ainda assim permitir execução (resultará em execução vazia)
        if self.total_instructions == 0 and len(invalid_instructions) > 0:
            # Programa só tinha instruções inválidas
            pass
        elif self.total_instructions == 0 and len(invalid_instructions) == 0:
            # Programa estava completamente vazio
            pass
    
    def get_parsing_errors(self) -> List[str]:
        """Retorna a lista de erros de parsing encontrados"""
        return self.parsing_errors
    
    def has_parsing_errors(self) -> bool:
        """Verifica se houve erros de parsing"""
        return len(self.parsing_errors) > 0
    
    def get_parsing_error_summary(self) -> str:
        """Retorna um resumo dos erros de parsing"""
        if not self.parsing_errors:
            return ""
        
        summary = f"⚠️  Foram encontrados {len(self.parsing_errors)} erro(s) no código:\n\n"
        for error in self.parsing_errors:
            summary += f"• {error}\n"
        
        summary += f"\n✅ {self.total_instructions} instrução(ões) válida(s) será(ão) executada(s)."
        
        if self.total_instructions == 0:
            summary += "\n\n⚠️  Nenhuma instrução válida encontrada. A simulação será executada com programa vazio."
        
        return summary
    
    def can_issue(self, instr: Instruction) -> Tuple[bool, Optional[int], Optional[int]]:
        
        station_type = self.get_station_type(instr.type)
        available_station = None
        
        for i, station in enumerate(self.reservation_stations):
            if not station.busy and self.is_compatible_station(station, station_type, i):
                available_station = i
                break
        
        if available_station is None:
            return False, None, None
             
        available_rob = None
        for i, rob_entry in enumerate(self.rob):
            if rob_entry.instruction_id == -1:
                available_rob = i
                break
        
        if available_rob is None:
            return False, None, None

        return True, available_station, available_rob
    
    def get_station_type(self, instr_type: InstructionType) -> str:
        if instr_type in [InstructionType.ADD, InstructionType.SUB]:
            return "ADD"
        elif instr_type in [InstructionType.MUL, InstructionType.DIV]:
            return "MUL"
        else:
            return "LOAD"
    
    def is_compatible_station(self, station: ReservationStation, station_type: str, station_idx: int) -> bool:
        if station_type == "ADD":
            return station_idx < self.num_add_stations
        elif station_type == "MUL":
            return self.num_add_stations <= station_idx < self.num_add_stations + self.num_mul_stations
        else:  
            return station_idx >= self.num_add_stations + self.num_mul_stations
    
    def issue_instruction(self, instr: Instruction, station_idx: int, rob_idx: int):
        station = self.reservation_stations[station_idx]
        rob_entry = self.rob[rob_idx]

        # Preencher a estação de reserva
        station.busy = True
        station.op = instr.type
        station.instruction_id = instr.id
        station.cycles_remaining = self.latencies[instr.type]

        # Preencher a ROB
        rob_entry.instruction_id = instr.id
        rob_entry.type = instr.type
        rob_entry.destination = instr.rd if instr.rd else ""

        # Renomear o registrador de destino ANTES de ler os registradores fonte
        if instr.rd and instr.type not in [InstructionType.STORE, InstructionType.BEQ, InstructionType.BNE]:
            self.register_file.set_pending(instr.rd, f"ROB{rob_idx}")

        # Ler rs
        if instr.rs:
            val, qi = self.register_file.read(instr.rs)
            if qi:
                station.vj = None
                station.qj = qi
            else:
                station.vj = val
                station.qj = None

        # Ler rt
        if instr.rt:
            val, qi = self.register_file.read(instr.rt)
            if qi:
                station.vk = None
                station.qk = qi
            else:
                station.vk = val
                station.qk = None

        # Marcar branch como especulativo
        if instr.type in [InstructionType.BEQ, InstructionType.BNE]:
            rob_entry.speculative = True
            self.speculation_depth += 1

        # Atualizar status da instrução
        instr.status = InstructionStatus.ISSUED
        instr.issue_cycle = self.cycle
        instr.reservation_station = station_idx
        instr.rob_entry = rob_idx

    def execute_instructions(self):
        for station in self.reservation_stations:
            if station.busy and station.cycles_remaining > 0:
                
                if (station.qj is None or self.is_value_ready(station.qj)) and \
                   (station.qk is None or self.is_value_ready(station.qk)):
                         
                    if station.qj:
                        station.vj = self.get_rob_value(station.qj)
                        station.qj = None
                    if station.qk:
                        station.vk = self.get_rob_value(station.qk)
                        station.qk = None
                     
                    station.cycles_remaining -= 1
                    
                    instr = next(i for i in self.instructions if i.id == station.instruction_id)
                    if instr.exec_start_cycle == -1:
                        instr.exec_start_cycle = self.cycle
                        instr.status = InstructionStatus.EXECUTING
    
    def write_back(self):
        completed_stations = []
        
        for i, station in enumerate(self.reservation_stations):
            if station.busy and station.cycles_remaining == 0:
                instr = next(inst for inst in self.instructions if inst.id == station.instruction_id)
                rob_entry = self.rob[instr.rob_entry]
                
                result = self.calculate_result(station, instr)
                
                rob_entry.value = result
                rob_entry.ready = True
                
                instr.status = InstructionStatus.WRITE_BACK
                instr.exec_end_cycle = self.cycle
                instr.write_back_cycle = self.cycle
                
                self.broadcast_result(f"ROB{instr.rob_entry}", result)
                
                completed_stations.append(i)

                rob_entry.ready = True
                rob_entry.ready_cycle = self.cycle + 1
  
        for i in completed_stations:
            self.reservation_stations[i].busy = False
            self.reservation_stations[i].op = None
            self.reservation_stations[i].instruction_id = -1
    
    def calculate_result(self, station: ReservationStation, instr: Instruction) -> float:
        if station.op == InstructionType.ADD:
            return (station.vj or 0) + (station.vk or 0)
        elif station.op == InstructionType.SUB:
            return (station.vj or 0) - (station.vk or 0)
        elif station.op == InstructionType.MUL:
            return (station.vj or 0) * (station.vk or 0)
        elif station.op == InstructionType.DIV:
            return (station.vj or 0) / max(station.vk or 1, 0.001)  
        elif station.op == InstructionType.LOAD:
            
            addr = (station.vj or 0) + instr.immediate
            return addr % 100
        # CORREÇÃO 2: Implementar cálculo correto para branches
        elif station.op in [InstructionType.BEQ, InstructionType.BNE]:
            val1 = station.vj or 0
            val2 = station.vk or 0
            
            if station.op == InstructionType.BEQ:
                branch_taken = (val1 == val2)
            else:  # BNE
                branch_taken = (val1 != val2)
            
            # Retorna 1 se branch é tomado, 0 se não é tomado
            return 1.0 if branch_taken else 0.0
        else:
            return station.vj or 0
    
    def broadcast_result(self, tag: str, value: float):
        for station in self.reservation_stations:
            if station.qj == tag:
                station.vj = value
                station.qj = None
            if station.qk == tag:
                station.vk = value
                station.qk = None
    
    def is_value_ready(self, tag: str) -> bool:
        if not tag or not tag.startswith("ROB"):
            return True
    
        rob_idx = int(tag[3:])
        rob_entry = self.rob[rob_idx]
        return rob_entry.ready and (rob_entry.ready_cycle <= self.cycle)
    
    def get_rob_value(self, tag: str) -> float:
        if not tag or not tag.startswith("ROB"):
            return 0.0
        
        rob_idx = int(tag[3:])
        return self.rob[rob_idx].value or 0.0
    
    def commit_instructions(self):
        
        committed_this_cycle = 0
        
        for i in range(self.rob_size):
            rob_entry = self.rob[i]
            
            if rob_entry.instruction_id == -1:
                continue
            
            if not rob_entry.ready:
                break  
            
            instr = next(inst for inst in self.instructions if inst.id == rob_entry.instruction_id)
            
            if rob_entry.destination and rob_entry.type not in [InstructionType.STORE, InstructionType.BEQ, InstructionType.BNE]:
                self.register_file.write(rob_entry.destination, rob_entry.value, f"ROB{i}")
            
            if rob_entry.type in [InstructionType.BEQ, InstructionType.BNE]:
                self.handle_branch_commit(instr, rob_entry)
            
            instr.status = InstructionStatus.COMMITTED
            instr.commit_cycle = self.cycle
            self.committed_instructions += 1
            
            rob_entry.instruction_id = -1
            rob_entry.type = None
            rob_entry.destination = ""
            rob_entry.value = None
            rob_entry.ready = False
            rob_entry.speculative = False
            
            committed_this_cycle += 1
            
            if committed_this_cycle >= 2:
                break
    
    def handle_branch_commit(self, instr: Instruction, rob_entry: ROBEntry):
        """Handle branch commit TOTALMENTE CORRIGIDO"""
        
        print(f"\n=== COMMIT BRANCH {instr.id} ===")
        
        self.speculation_depth = max(0, self.speculation_depth - 1)
        branch_taken = rob_entry.value == 1.0
        predicted_taken = self.branch_predictor.predict(instr.id)

        print(f"Branch taken: {branch_taken}, Predicted: {predicted_taken}")

        # Calcular target PC
        if branch_taken:
            target_pc = instr.id + 1 + instr.immediate
            print(f"Target PC: {instr.id} + 1 + {instr.immediate} = {target_pc}")
            
            # Validar target
            if target_pc < 0:
                target_pc = 0
            elif target_pc >= len(self.instructions):
                target_pc = len(self.instructions)
            print(f"Target final: {target_pc}")
        else:
            target_pc = instr.id + 1
            print(f"Branch não tomado, target = {target_pc}")

        # Determinar o próximo PC esperado (onde o pipeline estava indo)
        expected_next_pc = instr.id + 1

        # Verificar misprediction
        mispredicted = False
        
        if branch_taken and not predicted_taken:
            # Branch tomado mas preditor disse que não seria
            mispredicted = True
            print("MISPREDICTION: Branch tomado mas preditor disse que não")
        elif not branch_taken and predicted_taken:
            # Branch não tomado mas preditor disse que seria
            mispredicted = True
            print("MISPREDICTION: Branch não tomado mas preditor disse que seria")
        elif branch_taken and predicted_taken:
            # Ambos verdadeiros - verificar se o target está correto
            if self.pc != target_pc:
                mispredicted = True
                print(f"MISPREDICTION: Target incorreto. PC={self.pc}, Target={target_pc}")

        if mispredicted:
            print(f"MISPREDICTION DETECTADA! Executando flush...")
            self.mispredicted_branches += 1
            self.bubble_cycles += 3
            
            # Flush com target correto
            self.flush_pipeline_after_branch(instr.id, target_pc)
            
        else:
            print("Predição correta")
            # Mesmo com predição correta, garantir que PC está correto
            if branch_taken and self.pc != target_pc:
                print(f"Ajustando PC de {self.pc} para {target_pc}")
                self.pc = target_pc

        # Atualizar preditor
        self.branch_predictor.update(instr.id, branch_taken)
        print("=== FIM COMMIT BRANCH ===\n")

    def discard_instruction(self, inst: Instruction):
        """Descarte de instrução com limpeza completa"""
        
        print(f"  DESCARTANDO: ID={inst.id}, Status={inst.status}")
        print(f"    RS={inst.reservation_station}, ROB={inst.rob_entry}")
        
        # 1. Marcar como cancelada
        inst.status = InstructionStatus.CANCELLED
        
        # 2. Limpar timings
        inst.issue_cycle = -1
        inst.exec_start_cycle = -1
        inst.exec_end_cycle = -1
        inst.write_back_cycle = -1
        inst.commit_cycle = -1

        # 3. Liberar estação de reserva
        if inst.reservation_station != -1:
            station = self.reservation_stations[inst.reservation_station]
            print(f"    Liberando estação {inst.reservation_station}")
            
            # Zerar completamente a estação
            station.busy = False
            station.op = None
            station.instruction_id = -1
            station.vj = None
            station.vk = None
            station.qj = None
            station.qk = None
            station.cycles_remaining = 0
            
            inst.reservation_station = -1

        # 4. Limpar ROB e resolver dependências
        if inst.rob_entry != -1:
            rob = self.rob[inst.rob_entry]
            rob_tag = f"ROB{inst.rob_entry}"
            
            print(f"    Liberando ROB {inst.rob_entry}, destino='{rob.destination}'")
            
            # Se tinha um registrador de destino, resolver dependências
            if rob.destination:
                # Reverter renomeamento no register file
                if (rob.destination in self.register_file.qi and 
                    self.register_file.qi[rob.destination] == rob_tag):
                    print(f"    Revertendo renomeamento de {rob.destination}")
                    self.register_file.qi[rob.destination] = None
                
                # Resolver dependências em outras estações
                self.resolve_cancelled_dependencies(rob_tag, rob.destination)
            
            # Limpar completamente a ROB
            rob.instruction_id = -1
            rob.type = None
            rob.destination = ""
            rob.value = None
            rob.ready = False
            rob.speculative = False
            if hasattr(rob, 'ready_cycle'):
                rob.ready_cycle = -1
            
            inst.rob_entry = -1
        
        print(f"    Instrução {inst.id} descartada com sucesso")

    def resolve_cancelled_dependencies(self, cancelled_rob_tag: str, cancelled_register: str):
        """Resolve dependências de instruções que estavam esperando por uma instrução cancelada"""
        
        print(f"    Resolvendo dependências para {cancelled_rob_tag} ({cancelled_register})")
        
        # Buscar o valor atual do registrador
        current_value = self.register_file.registers.get(cancelled_register, 0.0)
        
        # Procurar nas estações de reserva
        for i, station in enumerate(self.reservation_stations):
            if not station.busy:
                continue
            
            # Se estava esperando pelo valor cancelado em qj
            if station.qj == cancelled_rob_tag:
                print(f"      Estação {i}: qj {cancelled_rob_tag} -> valor {current_value}")
                station.vj = current_value
                station.qj = None
                
            # Se estava esperando pelo valor cancelado em qk
            if station.qk == cancelled_rob_tag:
                print(f"      Estação {i}: qk {cancelled_rob_tag} -> valor {current_value}")
                station.vk = current_value
                station.qk = None

    def flush_pipeline_after_branch(self, branch_instruction_id: int, target_pc: int):
        """Limpa o pipeline após um branch mispredicted - VERSÃO FINAL CORRIGIDA"""
        
        print(f"\n=== FLUSH PIPELINE ===")
        print(f"Branch ID: {branch_instruction_id}, Target PC: {target_pc}")
        
        # 1. Identificar instruções que devem ser canceladas vs mantidas
        instructions_to_cancel = []
        instructions_to_keep = []
        
        for inst in self.instructions:
            # Se a instrução é posterior ao branch E foi emitida
            if (inst.id > branch_instruction_id and 
                inst.status in [InstructionStatus.ISSUED, InstructionStatus.EXECUTING, InstructionStatus.WRITE_BACK]):
                
                # Se o target_pc está dentro do range de instruções válidas
                if target_pc < len(self.instructions):
                    # Cancelar apenas se a instrução não está no caminho correto
                    if inst.id < target_pc:
                        instructions_to_cancel.append(inst)
                        print(f"  Cancelando: ID={inst.id} (entre branch e target)")
                    else:
                        # Instrução está no target path - deve ser mantida mas pode precisar ser reprocessada
                        instructions_to_keep.append(inst)
                        print(f"  Mantendo: ID={inst.id} (no target path)")
                else:
                    # Se target_pc está fora do range, cancelar todas as posteriores
                    instructions_to_cancel.append(inst)
                    print(f"  Cancelando: ID={inst.id} (target fora do range)")
        
        # 2. Cancelar as instruções identificadas
        for inst in instructions_to_cancel:
            print(f">>> Cancelando instrução {inst.id}: {inst.original_line}")
            self.discard_instruction(inst)
        
        # 3. NOVA CORREÇÃO: Verificar instruções do target path que podem estar "presas"
        for inst in instructions_to_keep:
            if inst.status == InstructionStatus.ISSUED:
                # Verificar se a instrução está presa (estação de reserva não está progredindo)
                if inst.reservation_station != -1:
                    station = self.reservation_stations[inst.reservation_station]
                    
                    # Se a estação tem dependências não resolvidas, pode estar presa
                    if station.qj or station.qk:
                        print(f"  ATENÇÃO: Instrução {inst.id} pode estar presa com dependências:")
                        print(f"    qj={station.qj}, qk={station.qk}")
                        
                        # Tentar resolver dependências órfãs
                        self.resolve_orphaned_dependencies(station, inst)
        
        # 4. Resetar status das instruções no target path que ainda não foram processadas
        for inst in self.instructions:
            if inst.id >= target_pc and inst.status == InstructionStatus.WAITING:
                print(f"  Garantindo que instrução {inst.id} está WAITING")
                inst.status = InstructionStatus.WAITING
        
        # 5. Resetar PC para o target correto
        old_pc = self.pc
        self.pc = target_pc
        print(f"PC: {old_pc} -> {self.pc}")
        print("=== FIM FLUSH ===\n")

    def check_stuck_instructions(self):
        """Detecta e corrige instruções que podem estar presas"""
        
        for inst in self.instructions:
            if inst.status == InstructionStatus.ISSUED and inst.reservation_station != -1:
                station = self.reservation_stations[inst.reservation_station]
                
                # Verificar se está presa há muito tempo
                cycles_since_issue = self.cycle - inst.issue_cycle
                if cycles_since_issue > 10:  # Threshold arbitrário
                    print(f"  INSTRUÇÃO PRESA DETECTADA: ID={inst.id}, {cycles_since_issue} ciclos desde emissão")
                    
                    # Tentar resolver dependências
                    if station.qj or station.qk:
                        print(f"    Tentando resolver dependências: qj={station.qj}, qk={station.qk}")
                        self.resolve_orphaned_dependencies(station, inst)
                    
                    # Se ainda não consegue executar, pode ser um problema mais sério
                    if station.qj or station.qk:
                        print(f"    ATENÇÃO: Instrução {inst.id} ainda tem dependências não resolvidas")
                        print(f"    Forçando resolução com valores padrão...")
                        
                        # Forçar resolução de dependências órfãs
                        if station.qj:
                            station.vj = 0.0
                            station.qj = None
                            print(f"      Forçou qj -> 0.0")
                        
                        if station.qk:
                            station.vk = 0.0  
                            station.qk = None
                            print(f"      Forçou qk -> 0.0")

    def resolve_orphaned_dependencies(self, station: ReservationStation, inst: Instruction):
        """Resolve dependências órfãs que podem ter sido criadas pelo flush"""
        
        print(f"    Resolvendo dependências órfãs para instrução {inst.id}")
        
        # Resolver qj se estiver esperando por uma ROB que não existe mais
        if station.qj:
            if station.qj.startswith("ROB"):
                rob_idx = int(station.qj[3:])
                rob_entry = self.rob[rob_idx]
                
                # Se a ROB entry está vazia (foi limpa), resolver com valor padrão
                if rob_entry.instruction_id == -1:
                    print(f"      qj {station.qj} órfão - usando valor do registrador")
                    if inst.rs:
                        station.vj = self.register_file.registers.get(inst.rs, 0.0)
                    else:
                        station.vj = 0.0
                    station.qj = None
                # Se a ROB entry está pronta, usar seu valor
                elif rob_entry.ready:
                    print(f"      qj {station.qj} pronto - usando valor {rob_entry.value}")
                    station.vj = rob_entry.value
                    station.qj = None
        
        # Resolver qk se estiver esperando por uma ROB que não existe mais  
        if station.qk:
            if station.qk.startswith("ROB"):
                rob_idx = int(station.qk[3:])
                rob_entry = self.rob[rob_idx]
                
                # Se a ROB entry está vazia (foi limpa), resolver com valor padrão
                if rob_entry.instruction_id == -1:
                    print(f"      qk {station.qk} órfão - usando valor do registrador")
                    if inst.rt:
                        station.vk = self.register_file.registers.get(inst.rt, 0.0)
                    else:
                        station.vk = 0.0
                    station.qk = None
                # Se a ROB entry está pronta, usar seu valor
                elif rob_entry.ready:
                    print(f"      qk {station.qk} pronto - usando valor {rob_entry.value}")
                    station.vk = rob_entry.value
                    station.qk = None

    def step(self):
        """Step com controle melhorado para instruções em estados inconsistentes"""
        self.cycle += 1
        print(f"\n--- CICLO {self.cycle} ---")
        
        # 1. Commit
        print("1. COMMIT")
        self.commit_instructions()
        
        # 2. Write back
        print("2. WRITE BACK")
        self.write_back()
        
        # 3. Execute
        print("3. EXECUTE")
        self.execute_instructions()
        
        # 4. NOVA VERIFICAÇÃO: Detectar instruções "presas" em ISSUED
        print("4. VERIFICAÇÃO DE INSTRUÇÕES PRESAS")
        self.check_stuck_instructions()
        
        # 5. Issue
        print("5. ISSUE")
        issued_count = 0
        max_issue_per_cycle = 2
        
        print(f"PC atual: {self.pc}, Total instruções: {len(self.instructions)}")
        
        # Verificar se PC está dentro do range válido
        if self.pc >= len(self.instructions):
            print("  PC fora do range de instruções")
            return
        
        while self.pc < len(self.instructions) and issued_count < max_issue_per_cycle:
            instr = self.instructions[self.pc]
            
            print(f"  Verificando instrução {instr.id}: {instr.original_line.strip()} (Status: {instr.status})")
            
            # Pular instruções canceladas
            if instr.status == InstructionStatus.CANCELLED:
                print(f"  -> Pulando instrução cancelada {instr.id}")
                self.pc += 1
                continue
            
            # Pular instruções já processadas
            if instr.status in [InstructionStatus.ISSUED, InstructionStatus.EXECUTING, 
                            InstructionStatus.WRITE_BACK, InstructionStatus.COMMITTED]:
                print(f"  -> Pulando instrução já processada {instr.id}")
                self.pc += 1
                continue
            
            # Tentar emitir
            if instr.status == InstructionStatus.WAITING:
                can_issue, station_idx, rob_idx = self.can_issue(instr)
                if can_issue:
                    print(f"  -> Emitindo instrução {instr.id} (RS={station_idx}, ROB={rob_idx})")
                    self.issue_instruction(instr, station_idx, rob_idx)
                    self.pc += 1
                    issued_count += 1
                else:
                    print(f"  -> Não pode emitir instrução {instr.id} (recursos indisponíveis)")
                    self.bubble_cycles += 1
                    break
            else:
                print(f"  -> Status inesperado para instrução {instr.id}: {instr.status}")
                self.pc += 1
        
        print(f"PC final: {self.pc}, Emitidas: {issued_count}")
    
    def is_finished(self) -> bool:
        """Verificação melhorada para fim da simulação"""
        # Contar apenas instruções não canceladas
        valid_instructions = [inst for inst in self.instructions 
                            if inst.status != InstructionStatus.CANCELLED]
        
        if not valid_instructions:
            return True
        
        # Verificar se todas as instruções válidas foram commitadas
        all_committed = all(inst.status == InstructionStatus.COMMITTED 
                        for inst in valid_instructions)
        
        # Debug: mostrar instruções que ainda não foram commitadas
        if not all_committed:
            pending = [inst for inst in valid_instructions 
                    if inst.status != InstructionStatus.COMMITTED]
            print(f"  Instruções pendentes: {len(pending)}")
            for inst in pending:
                print(f"    ID={inst.id}: {inst.status.name} - {inst.original_line.strip()}")
        
        return all_committed
    
    def get_ipc(self) -> float:
        return self.committed_instructions / max(self.cycle, 1)
    
    def get_metrics(self) -> Dict[str, float]:
        return {
            "IPC": self.get_ipc(),
            "Ciclos": self.cycle,
            "Instruções Commitadas": self.committed_instructions,
            "Total de Instruções": self.total_instructions,
            "Branches Incorretos": self.mispredicted_branches,
            "Profundidade Especulativa": self.speculation_depth
        }