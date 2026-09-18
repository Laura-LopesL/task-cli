import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class TaskFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.database = self.directory / "tasks.db"

    def cli(self, *args, expected=0):
        result = subprocess.run(
            [sys.executable, str(PROJECT / "app.py"), "--db", str(self.database), *args],
            capture_output=True, text=True, encoding="utf-8", cwd=self.directory,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_empty_list(self):
        self.assertIn("Nenhuma tarefa", self.cli("list").stdout)

    def test_add_persists_between_processes_and_normalizes_title(self):
        self.cli("add", "  Estudar   Python  ")
        self.assertEqual(self.cli("list").stdout.strip(), "1 [ ] Estudar Python")

    def test_complete_and_filter(self):
        self.cli("add", "Ler")
        self.cli("add", "Praticar")
        self.cli("done", "1")
        self.assertEqual(self.cli("list", "--status", "done").stdout.strip(), "1 [x] Ler")
        self.assertEqual(self.cli("list", "--status", "pending").stdout.strip(), "2 [ ] Praticar")

    def test_edit_persists_with_same_id_and_only_changes_selected_task(self):
        self.cli("add", "Estudar")
        self.cli("add", "Outra tarefa")
        self.assertIn("Tarefa 1 atualizada.", self.cli("edit", "1", "  Estudar   SQL  ").stdout)
        self.assertEqual(
            self.cli("list").stdout.strip(),
            "1 [ ] Estudar SQL\n2 [ ] Outra tarefa",
        )

    def test_edit_completed_task_keeps_completed_status(self):
        self.cli("add", "Ler")
        self.cli("done", "1")
        self.cli("edit", "1", "Ler documentação")
        self.assertEqual(
            self.cli("list", "--status", "done").stdout.strip(), "1 [x] Ler documentação"
        )

    def test_edit_rejects_blank_title_and_preserves_old_title(self):
        self.cli("add", "Manter título")
        for title in ("", " \t\n "):
            with self.subTest(title=title):
                error = self.cli("edit", "1", title, expected=1).stderr
                self.assertIn("não pode ficar vazio", error)
        self.assertEqual(self.cli("list").stdout.strip(), "1 [ ] Manter título")

    def test_edit_missing_task_does_not_create_or_change_tasks(self):
        self.cli("add", "Manter")
        self.assertIn("não encontrada", self.cli("edit", "99", "Novo", expected=1).stderr)
        self.assertEqual(self.cli("list").stdout.strip(), "1 [ ] Manter")

    def test_edit_sql_like_title_stays_text(self):
        self.cli("add", "Inicial")
        self.cli("add", "Outra")
        title = "Estudar 'SQL'); DROP TABLE tasks; --"
        self.cli("edit", "1", title)
        self.assertEqual(self.cli("list").stdout.strip(), f"1 [ ] {title}\n2 [ ] Outra")

    def test_edit_rejects_invalid_ids(self):
        for task_id in ("0", "-1", "abc", "1.5", "9223372036854775808"):
            with self.subTest(task_id=task_id):
                self.cli("edit", task_id, "Novo", expected=2)

    def test_completing_twice_keeps_one_completed_task(self):
        self.cli("add", "Ler")
        self.cli("done", "1")
        self.cli("done", "1")
        self.assertEqual(self.cli("list").stdout.strip(), "1 [x] Ler")

    def test_delete_does_not_reuse_id(self):
        self.cli("add", "Primeira")
        self.cli("delete", "1")
        self.assertIn("Nenhuma tarefa", self.cli("list").stdout)
        self.cli("add", "Segunda")
        self.assertEqual(self.cli("list").stdout.strip(), "2 [ ] Segunda")

    def test_empty_title_rejected_without_losing_existing_task(self):
        self.cli("add", "Manter")
        for title in ("", " \t\n "):
            with self.subTest(title=title):
                self.assertIn("não pode ficar vazio", self.cli("add", title, expected=1).stderr)
        self.assertEqual(self.cli("list").stdout.strip(), "1 [ ] Manter")

    def test_missing_task_rejected(self):
        for command in ("done", "delete"):
            with self.subTest(command=command):
                self.assertIn("não encontrada", self.cli(command, "99", expected=1).stderr)

    def test_invalid_ids_rejected(self):
        for task_id in ("0", "-1", "abc", "1.5"):
            with self.subTest(task_id=task_id):
                self.assertIn("inteiro positivo", self.cli("done", task_id, expected=2).stderr)

    def test_id_outside_sqlite_range_rejected(self):
        self.assertIn("grande demais", self.cli("done", "9223372036854775808", expected=2).stderr)

    def test_sql_like_title_stays_text(self):
        title = "Ler 'SQL'); DROP TABLE tasks; --"
        self.cli("add", title)
        self.cli("add", "Outra")
        output = self.cli("list").stdout
        self.assertIn(title, output)
        self.assertIn("2 [ ] Outra", output)

    def test_corrupt_database_is_reported_and_preserved(self):
        original = b"isto nao e um banco SQLite"
        self.database.write_bytes(original)
        self.assertIn("Erro ao acessar o banco", self.cli("list", expected=1).stderr)
        self.assertEqual(self.database.read_bytes(), original)

    def test_missing_database_directory_reported(self):
        self.database = self.directory / "missing" / "tasks.db"
        self.assertIn("Erro ao acessar o banco", self.cli("list", expected=1).stderr)

    def test_default_database_location_does_not_depend_on_working_directory(self):
        copied = self.directory / "project"
        copied.mkdir()
        for filename in ("app.py", "taskflow.py"):
            shutil.copyfile(PROJECT / filename, copied / filename)
        for working_directory in (self.directory, copied):
            result = subprocess.run(
                [sys.executable, str(copied / "app.py"), "list"],
                cwd=working_directory, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((copied / "tasks.db").exists())
        self.assertFalse((self.directory / "tasks.db").exists())

    def test_projects_persist_and_normalize_names(self):
        self.assertIn("Nenhum projeto", self.cli("project", "list").stdout)
        self.cli("project", "add", "  Meu   portfólio  ")
        self.cli("project", "add", "Estudos")
        self.assertEqual(
            self.cli("project", "list").stdout.strip(), "1 Meu portfólio\n2 Estudos"
        )

    def test_blank_and_duplicate_project_names_are_rejected(self):
        self.cli("project", "add", "Estudos")
        for name in ("", " \t\n "):
            with self.subTest(name=name):
                self.assertIn("não pode ficar vazio", self.cli("project", "add", name, expected=1).stderr)
        self.assertIn("já existe", self.cli("project", "add", "  Estudos  ", expected=1).stderr)
        self.assertEqual(self.cli("project", "list").stdout.strip(), "1 Estudos")

    def test_project_and_status_filters_combine_without_hiding_unassigned_tasks(self):
        self.cli("project", "add", "Estudos")
        self.cli("project", "add", "Trabalho")
        self.cli("add", "Ler", "--project", " Estudos ")
        self.cli("add", "Praticar", "--project", "Estudos")
        self.cli("add", "Reunião", "--project", "Trabalho")
        self.cli("add", "Comprar pão")
        self.cli("done", "1")
        self.assertEqual(
            self.cli("list", "--project", "Estudos", "--status", "done").stdout.strip(),
            "1 [x] Ler [Projeto: Estudos]",
        )
        self.assertEqual(
            self.cli("list", "--project", "Estudos", "--status", "pending").stdout.strip(),
            "2 [ ] Praticar [Projeto: Estudos]",
        )
        self.assertEqual(self.cli("list", "--no-project").stdout.strip(), "4 [ ] Comprar pão")
        self.assertIn("Nenhuma tarefa", self.cli("list", "--no-project", "--status", "done").stdout)
        self.assertEqual(len(self.cli("list").stdout.splitlines()), 4)

    def test_unknown_project_does_not_create_or_move_tasks(self):
        self.cli("add", "Manter")
        for command in (("add", "Nova"), ("move", "1"), ("list",)):
            with self.subTest(command=command):
                self.assertIn(
                    "não encontrado", self.cli(*command, "--project", "Ausente", expected=1).stderr
                )
        self.assertEqual(self.cli("list").stdout.strip(), "1 [ ] Manter")
        self.assertIn("Nenhum projeto", self.cli("project", "list").stdout)

    def test_moving_and_unassigning_keeps_task_id_title_and_status(self):
        self.cli("project", "add", "Estudos")
        self.cli("project", "add", "Trabalho")
        self.cli("add", "Ler", "--project", "Estudos")
        self.cli("add", "Outra")
        self.cli("done", "1")
        self.cli("move", "1", "--project", "Trabalho")
        self.assertEqual(
            self.cli("list").stdout.strip(), "1 [x] Ler [Projeto: Trabalho]\n2 [ ] Outra"
        )
        self.assertIn("Nenhuma tarefa", self.cli("list", "--project", "Estudos").stdout)
        self.cli("move", "1", "--no-project")
        self.assertEqual(self.cli("list").stdout.strip(), "1 [x] Ler\n2 [ ] Outra")
        self.assertIn("não encontrada", self.cli("move", "99", "--project", "Estudos", expected=1).stderr)
        self.assertEqual(self.cli("list").stdout.strip(), "1 [x] Ler\n2 [ ] Outra")

    def test_project_arguments_reject_ambiguous_filters_and_invalid_task_ids(self):
        for task_id in ("0", "-1", "abc", "9223372036854775808"):
            with self.subTest(task_id=task_id):
                self.cli("move", task_id, "--no-project", expected=2)
        for command in (("list",), ("move", "1")):
            with self.subTest(command=command):
                self.cli(*command, "--project", "Estudos", "--no-project", expected=2)
        self.cli("move", "1", expected=2)
        self.cli("project", expected=2)

    def test_sql_like_project_name_stays_text(self):
        name = "Ler 'SQL'); DROP TABLE tasks; --"
        self.cli("project", "add", name)
        self.cli("add", "Praticar", "--project", name)
        self.cli("project", "add", "Outro")
        self.assertEqual(
            self.cli("list", "--project", name).stdout.strip(), f"1 [ ] Praticar [Projeto: {name}]"
        )
        self.assertEqual(self.cli("project", "list").stdout.strip(), f"1 {name}\n2 Outro")

    def test_old_database_migrates_without_losing_tasks_or_reusing_deleted_ids(self):
        connection = sqlite3.connect(self.database)
        try:
            with connection:
                connection.execute("""CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                    done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1))
                )""")
                connection.executemany(
                    "INSERT INTO tasks (id, title, done) VALUES (?, ?, ?)",
                    [(3, "Concluída", 1), (5, "Pendente", 0), (9, "Excluída", 0)],
                )
                connection.execute("DELETE FROM tasks WHERE id = 9")
        finally:
            connection.close()
        for _ in range(2):
            self.assertEqual(self.cli("list").stdout.strip(), "3 [x] Concluída\n5 [ ] Pendente")
        self.cli("project", "add", "Estudos")
        self.cli("move", "3", "--project", "Estudos")
        self.assertIn("Tarefa 10 adicionada", self.cli("add", "Nova", "--project", "Estudos").stdout)
        self.assertEqual(
            self.cli("list").stdout.strip(),
            "3 [x] Concluída [Projeto: Estudos]\n5 [ ] Pendente\n10 [ ] Nova [Projeto: Estudos]",
        )

    def test_edit_and_delete_keep_project_and_other_tasks(self):
        self.cli("project", "add", "Estudos")
        self.cli("add", "Ler", "--project", "Estudos")
        self.cli("add", "Praticar", "--project", "Estudos")
        self.cli("edit", "1", "Ler SQL")
        self.assertEqual(
            self.cli("list", "--project", "Estudos").stdout.strip(),
            "1 [ ] Ler SQL [Projeto: Estudos]\n2 [ ] Praticar [Projeto: Estudos]",
        )
        self.cli("delete", "1")
        self.assertEqual(
            self.cli("list", "--project", "Estudos").stdout.strip(), "2 [ ] Praticar [Projeto: Estudos]"
        )
        self.assertEqual(self.cli("project", "list").stdout.strip(), "1 Estudos")


if __name__ == "__main__":
    unittest.main()
