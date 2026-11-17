import os
import subprocess
from pathlib import Path

output = "/home/navis/BNBroker/BNBroker.txt"
files = subprocess.check_output([
    "git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
    "--", "apps", "core", "templates", "static", "manage.py", "requirements.txt",
])

extensions = {".py", ".html", ".css", ".js", ".ts", ".json", ".txt", ".md", ".po"}
skipped_dirs = {"__pycache__", "node_modules", "media", "staticfiles", "logs", "env", ".venv"}
included = []

for name in sorted(set(files.split(b"\0"))):
    if not name:
        continue
    path = Path(os.fsdecode(name))
    if any(part.startswith(".") or part in skipped_dirs for part in path.parts):
        continue
    if path.is_symlink() or not path.is_file() or path.suffix not in extensions:
        continue
    included.append(path)

with open(output, "w", encoding="utf-8") as snapshot:
    snapshot.write("PROJECT STRUCTURE\n" + "=" * 80 + "\n")
    for path in included:
        snapshot.write(f"    {path}\n")
    for path in included:
        snapshot.write(f"\n{'=' * 80}\n# FILE: {path}\n{'=' * 80}\n")
        snapshot.write(path.read_text(encoding="utf-8", errors="replace"))
        snapshot.write("\n")

print(f"Готово: {output}")
print(f"Файлов в снимке: {len(included)}")
