import tkinter as tk
from tkinter import messagebox
from interface.tomasuloGUI import TomasuloGUI

def main():
    root = tk.Tk()
    
    try:
        root.state('zoomed')  # Maximizar no Windows
    except:
        root.attributes('-zoomed', True)  # Maximizar no Linux
    
    app = TomasuloGUI(root)
    
    # Adicionar menu
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    # Menu Arquivo
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Arquivo", menu=file_menu)
    file_menu.add_command(label="Carregar Exemplo", command=app.load_example)
    file_menu.add_separator()
    file_menu.add_command(label="Sair", command=root.quit)
    
    # Menu Simulação
    sim_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Simulação", menu=sim_menu)
    sim_menu.add_command(label="Passo (F5)", command=app.step_simulation)
    sim_menu.add_command(label="Executar (F6)", command=app.run_simulation)
    sim_menu.add_command(label="Reset (F7)", command=app.reset_simulation)
    
    # Menu Ajuda
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Ajuda", menu=help_menu)
    help_menu.add_command(label="Sobre", command=lambda: messagebox.showinfo(
        "Sobre", 
        "Simulador do Algoritmo de Tomasulo\n\n" +
        "Desenvolvido para fins didáticos\n" +
        "Simula arquitetura superescalar com:\n" +
        "• Estações de Reserva\n" +
        "• Buffer de Reordenamento (ROB)\n" +
        "• Especulação de Branches\n" +
        "• Execução Fora de Ordem\n\n" +
        "Instruções suportadas:\n" +
        "ADD, SUB, MUL, DIV, LOAD, STORE, BEQ, BNE\n\n" +
        "Atalhos:\n" +
        "F5 - Passo  F6 - Executar  F7 - Reset"
    ))
    
    # Atalhos de teclado
    root.bind('<F5>', lambda e: app.step_simulation())
    root.bind('<F6>', lambda e: app.run_simulation())
    root.bind('<F7>', lambda e: app.reset_simulation())
    
    # Carregar exemplo inicial
    app.load_example()
    
    root.mainloop()

if __name__ == "__main__":
    main()