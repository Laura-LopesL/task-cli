"""Operações de tarefas e persistência em SQLite."""

import sqlite3
from contextlib import contextmanager


@contextmanager
def open_database(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            # A verificação e a atualização do esquema precisam ser atômicas.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                    done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1))
                )"""
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "project_id" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN project_id INTEGER REFERENCES projects(id)"
                )
        yield connection
    finally:
        connection.close()


def clean_title(title):
    title = " ".join(title.split())
    if not title:
        raise ValueError("O título da tarefa não pode ficar vazio.")
    return title


def clean_project_name(name):
    name = " ".join(name.split())
    if not name:
        raise ValueError("O nome do projeto não pode ficar vazio.")
    return name


def add_project(connection, name):
    name = clean_project_name(name)
    with connection:
        cursor = connection.execute(
            "INSERT INTO projects (name) VALUES (?) ON CONFLICT(name) DO NOTHING", (name,)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Projeto '{name}' já existe.")
    return cursor.lastrowid


def list_projects(connection):
    return connection.execute("SELECT id, name FROM projects ORDER BY id").fetchall()


def find_project_id(connection, name):
    name = clean_project_name(name)
    project = connection.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
    if project is None:
        raise ValueError(f"Projeto '{name}' não encontrado. Crie-o com project add.")
    return project["id"]


def add_task(connection, title, project=None):
    title = clean_title(title)
    project_id = find_project_id(connection, project) if project is not None else None
    with connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, project_id) VALUES (?, ?)", (title, project_id)
        )
    return cursor.lastrowid


def edit_task(connection, task_id, title):
    title = clean_title(title)
    with connection:
        cursor = connection.execute(
            "UPDATE tasks SET title = ? WHERE id = ?", (title, task_id)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Tarefa {task_id} não encontrada.")


def move_task(connection, task_id, project=None):
    project_id = find_project_id(connection, project) if project is not None else None
    with connection:
        cursor = connection.execute(
            "UPDATE tasks SET project_id = ? WHERE id = ?", (project_id, task_id)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Tarefa {task_id} não encontrada.")


def list_tasks(connection, done=None, project=None, no_project=False):
    if project is not None and no_project:
        raise ValueError("Escolha um projeto ou tarefas sem projeto.")
    query = """SELECT tasks.*, projects.name AS project_name FROM tasks
               LEFT JOIN projects ON tasks.project_id = projects.id"""
    conditions = []
    values = []
    if done is not None:
        conditions.append("tasks.done = ?")
        values.append(int(done))
    if project is not None:
        conditions.append("tasks.project_id = ?")
        values.append(find_project_id(connection, project))
    elif no_project:
        conditions.append("tasks.project_id IS NULL")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    return connection.execute(query + " ORDER BY tasks.id", values).fetchall()


def complete_task(connection, task_id):
    with connection:
        cursor = connection.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            raise ValueError(f"Tarefa {task_id} não encontrada.")


def delete_task(connection, task_id):
    with connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            raise ValueError(f"Tarefa {task_id} não encontrada.")
