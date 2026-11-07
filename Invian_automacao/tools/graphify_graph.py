# =============================================================================
# tools/graphify_graph.py — Knowledge Graph inspired by Graphify-Labs/graphify
# =============================================================================
# Aplica a abordagem do Graphify: transforma o código/automação em um grafo
# queryável, onde cada nó representa um elemento (tela, botão, dado) e as arestas
# representam as relações (navegação, fluxo, dependência).
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import json


class NodeType(Enum):
    Tela = "tela"
    Botao = "botao"
    Input = "input"
    Select = "select"
    Row = "row"
    Skill = "skill"
    Documento = "documento"


@dataclass
class Node:
    id: str
    type: NodeType
    label: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=lambda: {"out": [], "in": []})

    def add_edge(self, direction: str, target_id: str) -> None:
        if direction not in self.edges:
            self.edges[direction] = []
        if target_id not in self.edges[direction]:
            self.edges[direction].append(target_id)


@dataclass
class KnowledgeGraph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: Dict[str, List[tuple]] = field(default_factory=lambda: {})

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str, label: str = "") -> None:
        if from_id not in self.nodes or to_id not in self.nodes:
            raise ValueError("Ambos os nós devem existir no grafo.")
        self.nodes[from_id].add_edge("out", to_id)
        self.nodes[to_id].add_edge("in", from_id)
        if from_id not in self.edges:
            self.edges[from_id] = []
        if (to_id, label) not in self.edges[from_id]:
            self.edges[from_id].append((to_id, label))

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def find_path(self, start_id: str, end_id: str) -> Optional[List[str]]:
        if start_id not in self.nodes or end_id not in self.nodes:
            return None
        visited: Set[str] = {start_id}
        queue: List[tuple] = [(start_id, [start_id])]
        while queue:
            current, path = queue.pop(0)
            if current == end_id:
                return path
            for neighbor in self.nodes[current].edges["out"]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None

    def query(self, node_type: NodeType, label_substring: str = "") -> List[Node]:
        results = []
        for node in self.nodes.values():
            if node.type == node_type and (label_substring.lower() in node.label.lower()):
                results.append(node)
        return results

    def to_json(self) -> Dict[str, Any]:
        return {
            "nodes": [
                {"id": n.id, "type": n.type.value, "label": n.label,
                 "metadata": n.metadata, "edges": n.edges}
                for n in self.nodes.values()
            ],
            "edges": {k: v for k, v in self.edges.items()},
        }

    def save(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(filepath: str) -> "KnowledgeGraph":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        kg = KnowledgeGraph()
        for n in data.get("nodes", []):
            kg.add_node(Node(id=n["id"], type=NodeType(n["type"]),
                             label=n["label"], metadata=n.get("metadata", {})))
        for from_id, targets in data.get("edges", {}).items():
            for to_id, label in targets:
                kg.add_edge(from_id, to_id, label)  # [to, label] vindo do JSON
        return kg


def build_invian_automation_graph() -> KnowledgeGraph:
    kg = KnowledgeGraph()

    kg.add_node(Node(id="skill_login", type=NodeType.Skill, label="Login no Invian"))
    kg.add_node(Node(id="skill_navegador", type=NodeType.Skill, label="Criar navegador"))
    kg.add_node(Node(id="skill_unidades", type=NodeType.Skill, label="Abrir tela de Unidades"))
    kg.add_node(Node(id="skill_processar", type=NodeType.Skill, label="Processar linha da planilha"))
    # Novas skills de Faces
    kg.add_node(Node(id="skill_abrir_faces", type=NodeType.Skill, label="Abrir tela de Faces"))
    kg.add_node(Node(id="skill_processar_face", type=NodeType.Skill, label="Processar Face (Preços/Anunciantes)"))

    kg.add_node(Node(id="tela_home", type=NodeType.Tela, label="Tela Home Invian"))
    kg.add_node(Node(id="tela_unidades", type=NodeType.Tela, label="Tela de Unidades"))
    kg.add_node(Node(id="tela_player", type=NodeType.Tela, label="Cadastro do Player"))
    # Novas telas de Faces
    kg.add_node(Node(id="tela_faces", type=NodeType.Tela, label="Tela de Faces"))
    kg.add_node(Node(id="modal_precos", type=NodeType.Tela, label="Modal Preços"))

    kg.add_node(Node(id="input_pesquisa", type=NodeType.Input, label="Campo de pesquisa"))
    kg.add_node(Node(id="botao_salvar", type=NodeType.Botao, label="Botao Salvar"))
    kg.add_node(Node(id="combo_horarios", type=NodeType.Select, label="Combo Horarios"))
    # Novos elementos de Faces
    kg.add_node(Node(id="menu_tres_pontinhos", type=NodeType.Botao, label="Menu 3 pontinhos (ações)"))
    kg.add_node(Node(id="opcao_precos", type=NodeType.Botao, label="Opção Preços no menu"))
    kg.add_node(Node(id="input_anunciantes_dia", type=NodeType.Input, label="Campo Anunciantes por dia"))
    kg.add_node(Node(id="botao_salvar_precos", type=NodeType.Botao, label="Botão Salvar na modal Preços"))

    kg.add_node(Node(id="planilha_dados", type=NodeType.Documento, label="Planilha bancodeDados.xlsx"))

    kg.add_edge("skill_login", "tela_home", "navega_ate_home")
    kg.add_edge("skill_navegador", "tela_home", "inicia_navegador")
    kg.add_edge("tela_home", "tela_unidades", "navega_para_unidades")
    kg.add_edge("tela_unidades", "input_pesquisa", "pesquisa_player")
    kg.add_edge("input_pesquisa", "tela_player", "abre_cadastro_player")
    kg.add_edge("tela_player", "combo_horarios", "seleciona_horario")
    kg.add_edge("combo_horarios", "botao_salvar", "apresenta_botao_salvar")
    kg.add_edge("botao_salvar", "skill_processar", "salva_alteracoes")
    kg.add_edge("planilha_dados", "skill_processar", "fornece_dados")
    
    # Arestas do fluxo de Faces
    kg.add_edge("tela_home", "tela_faces", "navega_para_faces")
    kg.add_edge("skill_abrir_faces", "tela_faces", "abre_tela_faces")
    kg.add_edge("tela_faces", "menu_tres_pontinhos", "localiza_menu_acao")
    kg.add_edge("menu_tres_pontinhos", "opcao_precos", "abre_menu_precos")
    kg.add_edge("opcao_precos", "modal_precos", "abre_modal_precos")
    kg.add_edge("modal_precos", "input_anunciantes_dia", "exibe_campo_anunciantes")
    kg.add_edge("input_anunciantes_dia", "botao_salvar_precos", "valida_e_salva")
    kg.add_edge("botao_salvar_precos", "skill_processar_face", "confirma_alteracao")
    kg.add_edge("planilha_dados", "skill_processar_face", "fornece_dados_face")

    return kg


invian_graph = build_invian_automation_graph()


if __name__ == "__main__":
    path = invian_graph.find_path("skill_login", "botao_salvar")
    print("Caminho do login ao salvar:", path)

    skills = invian_graph.query(NodeType.Skill)
    print("\nSkills registradas:", [s.label for s in skills])

    path2 = invian_graph.find_path("skill_login", "skill_processar")
    print("Caminho do login ao processar:", path2)

    invian_graph.save("invian_graph.json")
    print("\nGrafo salvo em invian_graph.json")