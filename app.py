
import argparse
import sqlite3
import sys
from pathlib import Path

from taskflow import (
    add_project, add_task, complete_task, delete_task, edit_task,
    list_projects, list_tasks, move_task, open_database,
)


def positive_id(value):
    try:
        task_id = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("O ID deve ser um inteiro positivo.") from None
    if task_id < 1:
        raise argparse.ArgumentTypeError("O ID deve ser um inteiro positivo.")
    if task_id > 9223372036854775807:
        raise argparse.ArgumentTypeError("O ID informado é grande demais.")
    return task_id


def build_parser():
    parser = argparse.ArgumentParser(description="TaskFlow: tarefas pelo terminal.")
    parser.add_argument(
        "--db", type=Path, default=Path(__file__).resolve().with_name("tasks.db"),
        help="Caminho do banco SQLite (padrão: tasks.db ao lado de app.py).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Adicionar uma tarefa.")
    add.add_argument("title", help="Título entre aspas.")
    add.add_argument("--project", help="Nome de um projeto já criado.")
    edit = commands.add_parser("edit", help="Editar o título de uma tarefa.")
    edit.add_argument("id", type=positive_id)
    edit.add_argument("title", help="Novo título entre aspas.")
    listing = commands.add_parser("list", help="Listar tarefas por ID.")
    listing.add_argument("--status", choices=("all", "pending", "done"), default="all")
    project_filter = listing.add_mutually_exclusive_group()
    project_filter.add_argument("--project", help="Filtrar pelo nome do projeto.")
    project_filter.add_argument("--no-project", action="store_true", help="Somente tarefas sem projeto.")
    move = commands.add_parser("move", help="Mudar o projeto de uma tarefa.")
    move.add_argument("id", type=positive_id)
    destination = move.add_mutually_exclusive_group(required=True)
    destination.add_argument("--project", help="Nome do projeto de destino.")
    destination.add_argument("--no-project", action="store_true", help="Retirar a tarefa do projeto.")
    project = commands.add_parser("project", help="Criar e listar projetos.")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    new_project = project_commands.add_parser("add", help="Criar um projeto.")
    new_project.add_argument("name", help="Nome entre aspas.")
    project_commands.add_parser("list", help="Listar projetos por ID.")
    for name, help_text in (("done", "Concluir uma tarefa."), ("delete", "Excluir uma tarefa.")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("id", type=positive_id)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        with open_database(args.db) as connection:
            if args.command == "add":
                task_id = add_task(connection, args.title, args.project)
                print(f"Tarefa {task_id} adicionada.")
            elif args.command == "edit":
                edit_task(connection, args.id, args.title)
                print(f"Tarefa {args.id} atualizada.")
            elif args.command == "list":
                done = {"all": None, "pending": False, "done": True}[args.status]
                tasks = list_tasks(connection, done, args.project, args.no_project)
                if not tasks:
                    print("Nenhuma tarefa encontrada.")
                for task in tasks:
                    marker = "x" if task["done"] else " "
                    project_label = f" [Projeto: {task['project_name']}]" if task["project_name"] else ""
                    print(f"{task['id']} [{marker}] {task['title']}{project_label}")
            elif args.command == "move":
                move_task(connection, args.id, args.project)
                print(f"Tarefa {args.id} movida.")
            elif args.command == "project":
                if args.project_command == "add":
                    project_id = add_project(connection, args.name)
                    print(f"Projeto {project_id} criado.")
                else:
                    projects = list_projects(connection)
                    if not projects:
                        print("Nenhum projeto encontrado.")
                    for project in projects:
                        print(f"{project['id']} {project['name']}")
            elif args.command == "done":
                complete_task(connection, args.id)
                print(f"Tarefa {args.id} concluída.")
            elif args.command == "delete":
                delete_task(connection, args.id)
                print(f"Tarefa {args.id} excluída.")
    except ValueError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError) as error:
        print(f"Erro ao acessar o banco {args.db}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
