
import argparse
import sqlite3
import sys
from pathlib import Path

from taskflow import add_task, complete_task, delete_task, edit_task, list_tasks, open_database


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
    edit = commands.add_parser("edit", help="Editar o título de uma tarefa.")
    edit.add_argument("id", type=positive_id)
    edit.add_argument("title", help="Novo título entre aspas.")
    listing = commands.add_parser("list", help="Listar tarefas por ID.")
    listing.add_argument("--status", choices=("all", "pending", "done"), default="all")
    for name, help_text in (("done", "Concluir uma tarefa."), ("delete", "Excluir uma tarefa.")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("id", type=positive_id)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        with open_database(args.db) as connection:
            if args.command == "add":
                task_id = add_task(connection, args.title)
                print(f"Tarefa {task_id} adicionada.")
            elif args.command == "edit":
                edit_task(connection, args.id, args.title)
                print(f"Tarefa {args.id} atualizada.")
            elif args.command == "list":
                done = {"all": None, "pending": False, "done": True}[args.status]
                tasks = list_tasks(connection, done)
                if not tasks:
                    print("Nenhuma tarefa encontrada.")
                for task in tasks:
                    marker = "x" if task["done"] else " "
                    print(f"{task['id']} [{marker}] {task['title']}")
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
