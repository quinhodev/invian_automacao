# =============================================================================
# gui/__init__.py — Interface Gráfica para Invian Automation
# =============================================================================
# Fornece uma GUI amigável para configurar e executar as automações.
# =============================================================================

from .config_dialog import abrir_configuracao
from .automation_runner import run_automation_with_gui

__all__ = ["abrir_configuracao", "run_automation_with_gui"]