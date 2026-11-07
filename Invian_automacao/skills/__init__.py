# =============================================================================
# skills/__init__.py — Registro de Habilidades (Superpowers Framework)
# =============================================================================
# Aplica o padrão de skills composáveis do obra/superpowers.
# Cada automação é uma "skill" que pode ser descoberta, registrada e composta.
# =============================================================================

from typing import Callable, Any, Dict, List
from pathlib import Path
import importlib


class SkillMetadata:
    """Metadados de uma skill — segue o padrão Superpowes de descoberta."""

    def __init__(
        self,
        name: str,
        description: str,
        module_path: str,
        handler: Callable,
        requires_auth: bool = True,
        depends_on: List[str] | None = None,
    ):
        self.name = name
        self.description = description
        self.module_path = module_path
        self.handler = handler
        self.requires_auth = requires_auth
        self.depends_on = depends_on or []
        self.executed = False
        self.evidence: List[str] = []


class SkillRegistry:
    """Registro central de skills — permite descoberta dinâmica e composição."""

    def __init__(self):
        self._skills: Dict[str, SkillMetadata] = {}
        self._execution_order: List[str] = []

    def register(
        self,
        name: str,
        description: str,
        handler: Callable,
        module_path: str,
        requires_auth: bool = True,
        depends_on: List[str] | None = None,
    ) -> None:
        existente = self._skills.get(name)
        if existente is not None and existente.module_path != module_path:
            raise ValueError(
                f"Skill '{name}' já está registrada por '{existente.module_path}'."
            )
        # mesmo módulo registrando de novo (reload) → apenas substitui
        self._skills[name] = SkillMetadata(
            name=name,
            description=description,
            module_path=module_path,
            handler=handler,
            requires_auth=requires_auth,
            depends_on=depends_on,
        )

    def get(self, name: str) -> SkillMetadata | None:
        return self._skills.get(name)

    def list_skills(self) -> List[SkillMetadata]:
        return list(self._skills.values())

    def resolve_execution_order(self) -> List[str]:
        """Ordena habilidades por dependências (topológico simples)."""
        ordered: List[str] = []
        visited: set[str] = set()

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)
            skill = self._skills[name]
            for dep in skill.depends_on:
                visit(dep)
            ordered.append(name)

        for name in self._skills:
            visit(name)
        self._execution_order = ordered
        return ordered

    def execute_skill(
        self, name: str, pagina=None, contexto=None, row=None, **kwargs
    ) -> Dict[str, Any]:
        """
        Executa uma skill coletando evidências (evidence over claims).

        Retorna {"skill", "success", "evidence", "error", "value"}, onde `value` é o que
        o handler retornou. Antes o retorno do handler era DESCARTADO, então
        `pagina = registry.execute_skill("login", ...)` devolvia um dict em vez da
        página e o pipeline do agente quebrava. Use `call()` se só quiser o valor.
        """
        skill = self._skills[name]
        result: Dict[str, Any] = {
            "skill": name,
            "success": False,
            "evidence": [],
            "error": None,
            "value": None,
        }

        handler_kwargs = {
            k: v
            for k, v in (("pagina", pagina), ("contexto", contexto), ("row", row))
            if v is not None
        }
        handler_kwargs.update(kwargs)

        try:
            result["value"] = skill.handler(**handler_kwargs)
            skill.executed = True
            result["success"] = True
            result["evidence"].append(f"Skill '{name}' executada com sucesso")
        except Exception as e:
            result["error"] = str(e)
            result["evidence"].append(f"Skill '{name}' falhou: {e}")
            skill.evidence.extend(result["evidence"])
            raise

        skill.evidence.extend(result["evidence"])
        return result

    def call(self, name: str, **kwargs) -> Any:
        """Executa a skill e devolve diretamente o valor retornado pelo handler."""
        return self.execute_skill(name, **kwargs)["value"]


# Instância global do registro
registry = SkillRegistry()


def skill(
    name: str,
    description: str = "",
    requires_auth: bool = True,
    depends_on: List[str] | None = None,
):
    """Decorador para registrar funções como skills no framework."""

    def decorator(func):
        registry.register(
            name=name,
            description=description or func.__doc__ or name,
            handler=func,
            module_path=func.__module__,
            requires_auth=requires_auth,
            depends_on=depends_on,
        )
        return func

    return decorator


def discover_skills(base_dir: Path | None = None) -> None:
    """Descobre automaticamente skills na pasta skills/."""
    if base_dir is None:
        base_dir = Path(__file__).parent

    for py_file in sorted(base_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        module_name = f"skills.{py_file.stem}"
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            print(f"[AVISO] Não foi possível importar skill '{module_name}': {exc}")