import os
from pathlib import Path
import shutil
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


if __name__ == "__main__":
    unittest.main()
