# TaskFlow — tarefas no terminal

Gerenciador de tarefas em evolução a partir do `task-cli`: adicionar, editar, listar, concluir e excluir
tarefas, com os dados salvos em um banco SQLite local.

## Como executar

Use Python 3.10 ou superior. Esta etapa utiliza apenas a biblioteca padrão do
Python; não precisa instalar pacotes com `pip`.

No terminal, entre na pasta do projeto e execute:

```bash
python app.py add "Estudar Python"
python app.py add "Revisar currículo"
python app.py list
```

Em um banco novo, a saída da listagem será:

```text
1 [ ] Estudar Python
2 [ ] Revisar currículo
```

Use o ID mostrado na listagem para editar, concluir ou excluir uma tarefa:

```bash
python app.py edit 1 "Estudar Python e SQL"
python app.py done 1
python app.py list --status pending
python app.py list --status done
python app.py delete 2
```

`[ ]` indica uma tarefa pendente e `[x]` uma tarefa concluída. `list` mostra
todas por padrão. A exclusão é permanente e não pede confirmação. Os IDs
excluídos não são reutilizados. Marcar novamente uma tarefa concluída mantém
seu estado. O comando `edit` altera somente o título: o ID e o estado de conclusão
são preservados. Um título vazio ou um ID inexistente gera uma mensagem de erro
e mantém as tarefas existentes.

No Windows, se `python` não for reconhecido, use `py` no lugar de `python`.
Para consultar os comandos: `python app.py --help`.

## Onde os dados ficam

O arquivo `tasks.db` é criado ao lado de `app.py`. Ele mantém as tarefas entre
execuções e está no `.gitignore`, para não publicar dados pessoais no repositório.
Para usar outro arquivo, passe `--db` **antes do comando**:

```bash
python app.py --db estudo.db add "Praticar SQL"
python app.py --db estudo.db list
```

A pasta escolhida precisa existir e permitir escrita. Se o banco não puder ser
aberto ou estiver inválido, o programa informa o erro e encerra; ele não apaga
o arquivo para tentar recuperar os dados.

## Organização e decisões

- `app.py`: interpreta os comandos com `argparse` e apresenta mensagens.
- `taskflow.py`: valida títulos e executa as operações no SQLite.
- `tests/test_cli.py`: testa comandos em processos separados, com bancos temporários.

SQLite permite salvar e consultar tarefas sem configurar um servidor. A
separação em dois módulos permite reaproveitar as operações em uma futura API.
As consultas usam parâmetros (`?`), mantendo os títulos separados do código SQL.
As alterações são feitas em transações: o SQLite confirma a operação ou a desfaz
se ocorrer uma falha.

Títulos vazios são rejeitados; espaços extras e quebras de linha são normalizados.
IDs precisam ser inteiros positivos e identificar uma tarefa existente. Erros
de operação retornam código 1; argumentos inválidos retornam código 2.

## Testes

Na pasta do projeto:

```bash
python -m unittest discover -s tests -v
```

Os 19 testes cobrem persistência, edição, filtros, conclusão, exclusão, IDs, títulos e erros
de acesso ao banco. Eles não usam nem alteram o seu `tasks.db`.

## Próximas etapas

Esta versão é uma ferramenta local para uma pessoa, sem interface web ou API.
O plano é adicionar projetos, depois uma API com FastAPI
e validação com Pydantic. PostgreSQL e Docker ficam para etapas posteriores.
