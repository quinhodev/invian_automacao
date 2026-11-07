# skills/login_skill.py — Skill: autenticação no Invian (wrapper de login.py)
from playwright.sync_api import Page

from skills import skill


@skill(
    name="login",
    description="Autenticação no sistema Invian usando Playwright.",
    requires_auth=True,
    depends_on=[],
)
def login_skill(pagina: Page, email: str | None = None, senha: str | None = None, **kwargs) -> Page:
    """Executa o login. Sem email/senha, usa INVIAN_EMAIL/INVIAN_SENHA ou pergunta no terminal."""
    from login import fazer_login

    fazer_login(pagina, email, senha)
    return pagina
