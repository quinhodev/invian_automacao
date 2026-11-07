# main.py — Ponto de entrada (CLI e GUI). A lógica vive em core.py.
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import executar_automacao  # noqa: E402


def rodar_automacao_cli(modo="unidades", arquivo=None, aba=None, linha_inicial=None, linha_cabecalho=1,
                        headless=None, coluna=None, coluna_horario=None, valor_anunciantes=None) -> int:
    """Roda no terminal. Retorna 0 se tudo ok, 1 se houve erro em alguma linha."""
    resumo = executar_automacao(
        modo=modo, arquivo=arquivo, aba=aba, linha_inicial=linha_inicial,
        headless=headless, coluna=coluna, coluna_horario=coluna_horario,
        linha_cabecalho=linha_cabecalho, valor_anunciantes=valor_anunciantes,
        log=print,
    )
    houve_erro = resumo["contagem"].get("erro", 0) > 0 or resumo["navegador_fechou"] or resumo["interrompido"]
    return 1 if houve_erro else 0


def rodar_gui() -> int:
    import tkinter as tk
    from tkinter import messagebox

    from gui import abrir_configuracao, run_automation_with_gui

    config = abrir_configuracao()
    if config is None:
        print("Configuração cancelada pelo usuário.")
        return 0

    root = tk.Tk()
    root.title("Invian Automation - Execução")
    root.geometry("700x500")

    log_frame = tk.Frame(root)
    log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    log_text = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 9))
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll = tk.Scrollbar(log_frame, command=log_text.yview)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.config(yscrollcommand=scroll.set, state=tk.DISABLED)

    btn_frame = tk.Frame(root)
    btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
    # O botão Parar antes nascia DESABILITADO e nunca era habilitado.
    stop_btn = tk.Button(btn_frame, text="Parar")
    stop_btn.pack(side=tk.RIGHT)
    close_btn = tk.Button(btn_frame, text="Fechar", command=root.destroy, state=tk.DISABLED)
    close_btn.pack(side=tk.RIGHT, padx=(0, 10))

    # Estes callbacks rodam na thread principal do Tk (o runner enfileira os eventos).
    def log_callback(msg):
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, msg + "\n")
        log_text.see(tk.END)
        log_text.config(state=tk.DISABLED)

    def finished_callback(success, message):
        stop_btn.config(state=tk.DISABLED)
        close_btn.config(state=tk.NORMAL)
        log_callback(f"\n{message}")
        (messagebox.showinfo if success else messagebox.showwarning)(
            "Concluído" if success else "Atenção", message
        )

    def on_stop():
        runner.stop()
        stop_btn.config(state=tk.DISABLED)
        log_callback("Parando após a linha atual...")

    def on_close():
        if runner.is_running() and not messagebox.askyesno("Sair", "A automação está rodando. Parar e sair?"):
            return
        runner.stop()
        root.destroy()

    stop_btn.config(command=on_stop)
    root.protocol("WM_DELETE_WINDOW", on_close)

    runner = run_automation_with_gui(config, log_callback, finished_callback, tk_root=root)
    root.mainloop()
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Invian Automation - Automação de Unidades e Faces",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exemplos:
  python main.py                           # Abre interface gráfica
  python main.py --cli                     # Modo CLI (Unidades/Horários)
  python main.py --cli --modo faces        # Modo CLI (Faces/Anunciantes)
  python main.py --cli --modo ambos        # Executa os dois em sequência
  python main.py --cli --arquivo dados.xlsx --aba Planilha1 --linha 2
  python main.py --cli --headless          # Navegador invisível""",
    )
    parser.add_argument("--cli", action="store_true", help="Executa sem GUI")
    parser.add_argument("--modo", choices=["unidades", "faces", "ambos", "panvel"], default="unidades")
    parser.add_argument("--arquivo", type=str, help="Caminho do arquivo Excel")
    parser.add_argument("--aba", type=str, help="Nome da aba da planilha")
    parser.add_argument("--linha", type=int, help="Linha inicial do Excel (1 = cabeçalho)")
    parser.add_argument("--coluna", type=str, help="Coluna com o nome do player/face (padrão: config.py)")
    parser.add_argument("--coluna-horario", type=str, help="Coluna com o horário (padrão: config.py)")
    parser.add_argument("--cabecalho", type=int, default=1, help="Linha do cabeçalho na planilha (padrão: 1)")
    parser.add_argument("--anunciantes", type=int, help="Quantidade de anunciantes por dia (modo faces/ambos, padrão: config.py)")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--headless", action="store_true", help="Navegador invisível")
    grupo.add_argument("--visible", action="store_true", help="Navegador visível (padrão do config.py)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.cli:
        headless = True if args.headless else (False if args.visible else None)
        sys.exit(rodar_automacao_cli(
            modo=args.modo, arquivo=args.arquivo, aba=args.aba,
            linha_inicial=args.linha, headless=headless, coluna=args.coluna,
            coluna_horario=args.coluna_horario, linha_cabecalho=args.cabecalho,
            valor_anunciantes=args.anunciantes,
        ))
    sys.exit(rodar_gui())
