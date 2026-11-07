# =============================================================================
# horario.py — Lógica de mapeamento e comparação de horários
# =============================================================================
# Responsável por:
#   - Converter o texto da planilha para o nome cadastrado no sistema
#   - Comparar horários para evitar alterações desnecessárias
#   - Gerar termos de busca para o combo de horários
# =============================================================================

import re

from texto import (
    normalizar_horario_texto,
    normalizar_para_comparar,
    normalizar_espacos,
)


# ---------------------------------------------------------------------------
# Mapeamento planilha → sistema
# ---------------------------------------------------------------------------

_RE_SO_INTERVALO = re.compile(r"(\d{2}:\d{2})\s+a\s+(\d{2}:\d{2})")
_DIAS_UTEIS_SAB = "Seg, Ter, Qua, Qui, Sex, Sáb"


def mapear_horario(horario_excel: str) -> str:
    """
    Converte o valor da coluna de horário para o nome cadastrado no Invian.

    Formatos tratados:
      "07:00 - 23:00"                     → "Todos os dias de 07:00 a 23:00"
      "07:00 - 23:00 | Dom 07:00 - 20:00" → "Seg, Ter, Qua, Qui, Sex, Sáb de 07:00 a 23:00 | Dom de 07:00 a 20:00"
      "Segunda a Domingo de 07:00 a 22:00"→ "Todos os dias de 07:00 a 22:00"
      "Fixo"                              → "Fixo"
    Textos já completos (ex.: "Seg, Ter ... de 07:00 a 22:30 | Dom de 07:30 a 20:30")
    são mantidos.
    """
    texto = normalizar_horario_texto(horario_excel)

    if not texto:
        print("[AVISO] Horário vazio na planilha.")
        return ""

    comparavel = normalizar_para_comparar(texto)

    if "fixo" in comparavel:
        return "Fixo"

    # "Segunda a Domingo de HH:MM a HH:MM" → "Todos os dias de HH:MM a HH:MM"
    if "segunda a domingo" in comparavel and "|" not in texto:
        intervalo = _RE_SO_INTERVALO.search(texto)
        if intervalo:
            return f"Todos os dias de {intervalo.group(1)} a {intervalo.group(2)}"

    if "todos os dias" in comparavel and "|" not in texto:
        intervalo = _RE_SO_INTERVALO.search(texto)
        if intervalo:
            return f"Todos os dias de {intervalo.group(1)} a {intervalo.group(2)}"

    # Só um intervalo, sem dias: "07:00 a 23:00"
    so = _RE_SO_INTERVALO.fullmatch(texto)
    if so:
        return f"Todos os dias de {so.group(1)} a {so.group(2)}"

    # Composto: "<intervalo> | Dom [de] <intervalo>"
    partes = [p.strip() for p in re.split(r"\s*\|\s*", texto) if p.strip()]
    if len(partes) > 1:
        novas = []
        for parte in partes:
            if _RE_SO_INTERVALO.fullmatch(parte):          # bloco sem dias = dias úteis + sábado
                parte = f"{_DIAS_UTEIS_SAB} de {parte}"
            else:                                          # "Dom 07:00 a 20:00" → "Dom de 07:00 a 20:00"
                parte = re.sub(r"^([A-Za-zÀ-ú, ]+?)\s+(?=\d{2}:\d{2}\b)(?<!de )", lambda m: m.group(1) + " de ", parte) \
                        if not re.search(r"\bde\s+\d{2}:\d{2}", parte) else parte
            novas.append(parte)
        return " | ".join(novas)

    return texto


# ---------------------------------------------------------------------------
# Comparação de horários
# ---------------------------------------------------------------------------

def partes_horario_para_comparar(horario: str) -> list:
    """Divide o horário composto em partes normalizadas para comparação."""
    texto = normalizar_horario_texto(horario)
    partes = re.split(r"\s*\|\s*", texto)
    return [normalizar_para_comparar(p) for p in partes if p.strip()]


_RE_INTERVALO = re.compile(r"\d{2}:\d{2}\s+a\s+\d{2}:\d{2}")


def horario_corresponde(texto_opcao: str, horario_sistema: str) -> bool:
    """
    Verifica se uma opção exibida no sistema corresponde EXATAMENTE ao horário esperado.

    Aceita:
      - Texto idêntico depois de normalizado
      - Mesmos blocos em ordem diferente (Seg... | Dom... == Dom... | Seg...)
      - Opção com algum texto extra, desde que tenha a mesma quantidade de
        intervalos de hora e contenha todos os blocos esperados

    Antes, a checagem era "um texto contém o outro" nos dois sentidos, o que dava
    falso positivo em dois casos: string vazia (contida em tudo) e horário simples
    ('Dom de 07:00 a 22:00') contido num composto ('Seg... | Dom...'), fazendo o
    robô achar que o horário já estava correto e NÃO salvar.
    """
    opcao_norm = normalizar_para_comparar(texto_opcao)
    esperado_norm = normalizar_para_comparar(horario_sistema)

    if not opcao_norm or not esperado_norm:
        return False

    if opcao_norm == esperado_norm:
        return True

    partes_opcao = set(partes_horario_para_comparar(texto_opcao))
    partes_esperadas = set(partes_horario_para_comparar(horario_sistema))
    if partes_opcao and partes_opcao == partes_esperadas:
        return True

    if len(_RE_INTERVALO.findall(opcao_norm)) != len(_RE_INTERVALO.findall(esperado_norm)):
        return False

    return bool(partes_esperadas) and all(p in opcao_norm for p in partes_esperadas)


# ---------------------------------------------------------------------------
# Geração de termos de busca
# ---------------------------------------------------------------------------

def gerar_termos_busca_horario(horario_sistema: str) -> list:
    """
    Gera uma lista de tentativas de pesquisa para o campo de busca do combo.

    Ordem de tentativa:
        1. Cada bloco do horário composto
        2. Intervalos de hora (ex: "07:00 a 22:30")
        3. Texto completo
        4. Sem filtro (string vazia)
    """
    termos = []
    texto  = normalizar_horario_texto(horario_sistema)

    partes = [p.strip() for p in re.split(r"\s*\|\s*", texto) if p.strip()]
    termos.extend(partes)

    intervalos = re.findall(r"\d{2}:\d{2}\s+a\s+\d{2}:\d{2}", texto)
    termos.extend(intervalos)

    termos.append(texto)
    termos.append("")

    # Remove duplicatas mantendo a ordem
    vistos = []
    for t in termos:
        t = normalizar_espacos(t)
        if t not in vistos:
            vistos.append(t)

    return vistos
