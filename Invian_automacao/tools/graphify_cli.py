#!/usr/bin/env python
# =============================================================================
# tools/graphify_cli.py — CLI do Knowledge Graph (inspirado no Graphify-Labs/graphify)
# =============================================================================
# Permite consultar o grafo de automação via linha de comando.
# Similar ao CLI do Graphify: query, analyze, visualize.
# =============================================================================

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graphify_graph import invian_graph, KnowledgeGraph, NodeType


def query_skills(args):
    """Lista todas as skills registradas."""
    skills = invian_graph.query(NodeType.Skill)
    print(f"\n[SKILLS] Skills registradas ({len(skills)}):")
    for s in skills:
        print(f"  * {s.label} ({s.id})")


def query_screens(args):
    """Lista todas as telas."""
    screens = invian_graph.query(NodeType.Tela)
    print(f"\n[TELAS] Telas do sistema ({len(screens)}):")
    for s in screens:
        print(f"  * {s.label} ({s.id})")


def query_elements(args):
    """Lista elementos de UI (inputs, botões, selects)."""
    for t in [NodeType.Input, NodeType.Botao, NodeType.Select]:
        elements = invian_graph.query(t)
        if elements:
            print(f"\n{t.value.upper()}s ({len(elements)}):")
            for e in elements:
                print(f"  * {e.label} ({e.id})")


def find_path(args):
    """Encontra caminho entre dois nós."""
    path = invian_graph.find_path(args.source, args.target)
    if path:
        print(f"\n[CAMINHO] '{args.source}' -> '{args.target}':")
        for i, node_id in enumerate(path):
            node = invian_graph.get_node(node_id)
            prefix = "  " * i + ("+- " if i > 0 else "")
            print(f"{prefix}{node.label} ({node_id})")
    else:
        print(f"\n[ERRO] Nenhum caminho encontrado de '{args.source}' para '{args.target}'")


def show_graph(args):
    """Mostra o grafo completo."""
    print(f"\n[GRAFO] Grafo completo: {len(invian_graph.nodes)} nós, {sum(len(v) for v in invian_graph.edges.values())} arestas")
    for node_id, node in invian_graph.nodes.items():
        out_edges = node.edges.get("out", [])
        print(f"  [{node.type.value}] {node.label} ({node_id})")
        if out_edges:
            for out in out_edges:
                target = invian_graph.get_node(out)
                print(f"    -> {target.label} ({out})")


def export_graph(args):
    """Exporta o grafo para JSON."""
    invian_graph.save(args.output)
    print(f"\n[OK] Grafo exportado para {args.output}")


def main():
    parser = argparse.ArgumentParser(
        prog="graphify",
        description="Knowledge Graph CLI para Invian_automacao (inspirado no Graphify-Labs/graphify)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # skills
    subparsers.add_parser("skills", help="Lista skills registradas")

    # screens
    subparsers.add_parser("screens", help="Lista telas do sistema")

    # elements
    subparsers.add_parser("elements", help="Lista elementos de UI")

    # path
    path_parser = subparsers.add_parser("path", help="Encontra caminho entre nós")
    path_parser.add_argument("source", help="ID do nó origem")
    path_parser.add_argument("target", help="ID do nó destino")

    # graph
    subparsers.add_parser("graph", help="Mostra grafo completo")

    # export
    export_parser = subparsers.add_parser("export", help="Exporta grafo para JSON")
    export_parser.add_argument("-o", "--output", default="invian_graph.json",
                               help="Arquivo de saída")

    args = parser.parse_args()

    if args.command == "skills":
        query_skills(args)
    elif args.command == "screens":
        query_screens(args)
    elif args.command == "elements":
        query_elements(args)
    elif args.command == "path":
        find_path(args)
    elif args.command == "graph":
        show_graph(args)
    elif args.command == "export":
        export_graph(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()