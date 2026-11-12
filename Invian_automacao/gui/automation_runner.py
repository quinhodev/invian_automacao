# gui/automation_runner.py — Executa core.executar_automacao numa thread
#
# Tkinter NÃO é thread-safe: os callbacks de log/fim precisam rodar na thread
# principal. A thread de trabalho só coloca eventos numa fila; `_drenar` (agendado
# com root.after) entrega os eventos aos callbacks na thread do Tk.
import queue
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class AutomationRunner:
    def __init__(self, log_callback, finished_callback, tk_root=None):
        self.log_callback = log_callback
        self.finished_callback = finished_callback
        self.tk_root = tk_root
        self._eventos = queue.Queue()
        self._parar = threading.Event()
        self._thread = None

    # -- controle ---------------------------------------------------------
    def start(self, config):
        if self.is_running():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._run, args=(config,), daemon=True)
        self._thread.start()
        if self.tk_root is not None:
            self.tk_root.after(100, self._drenar)

    def stop(self):
        self._parar.set()

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    # -- comunicação thread -> GUI ---------------------------------------
    def _emitir(self, evento):
        if self.tk_root is None:  # uso sem Tk: chama direto
            self._entregar(evento)
        else:
            self._eventos.put(evento)

    def _entregar(self, evento):
        if evento[0] == "log":
            self.log_callback(evento[1])
        else:
            self.finished_callback(evento[1], evento[2])

    def _drenar(self):
        try:
            while True:
                self._entregar(self._eventos.get_nowait())
        except queue.Empty:
            pass
        if self.is_running() or not self._eventos.empty():
            self.tk_root.after(100, self._drenar)

    # -- trabalho ----------------------------------------------------------
    def _run(self, config):
        log = lambda msg: self._emitir(("log", msg))  # noqa: E731
        try:
            from core import executar_automacao

            log("Iniciando automação...")
            log(f"Modo: {config['tipo']} | Arquivo: {Path(config['arquivo']).name} | "
                f"Aba: {config['aba']} | Linha inicial: {config['linha_inicial']} | "
                f"Headless: {config['headless']}")

            resumo = executar_automacao(
                modo=config["tipo"],
                arquivo=config["arquivo"],
                aba=config["aba"],
                linha_inicial=config["linha_inicial"],
                headless=config["headless"],
                coluna=config.get("coluna"),
                coluna_horario=config.get("coluna_horario"),
                email=config.get("email"),
                senha=config.get("senha"),
                linha_cabecalho=config.get("linha_cabecalho", 1),
                valor_anunciantes=config.get("valor_anunciantes"),
                log=log,
                parar=self._parar,
                dry_run=config.get("dry_run", False),
            )

            erros = resumo["contagem"].get("erro", 0)
            if resumo["interrompido"]:
                self._emitir(("fim", False, "Interrompido pelo usuário"))
            elif resumo["navegador_fechou"]:
                self._emitir(("fim", False, "O navegador foi fechado antes do fim"))
            elif erros:
                self._emitir(("fim", False, f"Concluído com {erros} linha(s) com erro — veja o log/relatório"))
            else:
                self._emitir(("fim", True, "Automação finalizada com sucesso"))
        except Exception as e:
            log(f"Erro: {e}\n{traceback.format_exc()}")
            self._emitir(("fim", False, f"Erro: {e}"))


def run_automation_with_gui(config, log_callback, finished_callback, tk_root=None):
    runner = AutomationRunner(log_callback, finished_callback, tk_root)
    runner.start(config)
    return runner
