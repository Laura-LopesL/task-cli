"""Operações de tarefas e persistência em SQLite."""

import sqlite3
from contextlib import contextmanager


@contextmanager
def open_database(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                    done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1))
                )"""
            )
        yield connection
    finally:
        connection.close()


def clean_title(title):
    title = " ".join(title.split())
    if not title:
        raise ValueError("O título da tarefa não pode ficar vazio.")
    return title


def add_task(connection, title):
    title = clean_title(title)
    with connection:
        cursor = connection.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
    return cursor.lastrowid


def edit_task(connection, task_id, title):
    title = clean_title(title)
    with connection:
        cursor = connection.execute(
            "UPDATE tasks SET title = ? WHERE id = ?", (title, task_id)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Tarefa {task_id} não encontrada.")


def list_tasks(connection, done=None):
    if done is None:
        return connection.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    return connection.execute(
        "SELECT * FROM tasks WHERE done = ? ORDER BY id", (int(done),)
    ).fetchall()


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
