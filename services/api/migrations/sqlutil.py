"""Helpers for hand-written SQL migrations.

asyncpg runs every statement as a prepared statement, which cannot hold several commands,
so scripts are split into single statements (dollar-quoted function bodies are kept intact).
"""

from alembic import op


def split_statements(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_dollar = False
    for line in script.splitlines():
        stripped = line.strip()
        if not in_dollar and (not stripped or stripped.startswith("--")):
            continue
        current.append(line)
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        if not in_dollar and stripped.endswith(";"):
            statements.append("\n".join(current).rstrip().rstrip(";"))
            current = []
    if current and "".join(current).strip():
        statements.append("\n".join(current).rstrip().rstrip(";"))
    return statements


def run_script(script: str) -> None:
    for statement in split_statements(script):
        op.execute(statement)
