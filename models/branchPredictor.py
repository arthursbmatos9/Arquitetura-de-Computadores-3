class BranchPredictor:
    def __init__(self):
        self.prediction_table = {}
    
    def predict(self, pc: int) -> bool:
        return self.prediction_table.get(pc, False)
    
    def update(self, pc: int, taken: bool):
        self.prediction_table[pc] = taken