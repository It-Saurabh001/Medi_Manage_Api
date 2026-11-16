import ast
import os

def extract_detailed():
    entries = []
    for root, dirs, files in os.walk("."):
        if ".venv" in root or ".git" in root or "__pycache__" in root:
            continue
        for file in sorted(files):
            if file.endswith(".py") and file != "scratch_detailed.py":
                fp = os.path.join(root, file)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    src = "".join(lines)
                    tree = ast.parse(src)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            call_name = ""
                            if isinstance(node.func, ast.Attribute):
                                call_name = node.func.attr
                            elif isinstance(node.func, ast.Name):
                                call_name = node.func.id
                            if call_name in ("execute", "executemany", "executescript", "commit", "rollback", "close", "connect", "backup"):
                                lineno = node.lineno
                                line_str = lines[lineno - 1].strip() if lineno <= len(lines) else ""
                                arg0 = ast.unparse(node.args[0]) if node.args else ""
                                arg1 = ast.unparse(node.args[1]) if len(node.args) > 1 else ""
                                # Also find the enclosing function
                                entries.append({
                                    "file": fp.replace("\\", "/"),
                                    "line": lineno,
                                    "call": call_name,
                                    "arg0": arg0,
                                    "arg1": arg1,
                                    "line_str": line_str
                                })
                except Exception as e:
                    pass
    entries.sort(key=lambda x: (x["file"], x["line"]))
    print(f"TOTAL EXTRACTED: {len(entries)}")
    with open("all_db_logics.txt", "w", encoding="utf-8") as out:
        for idx, e in enumerate(entries, 1):
            out.write(f"### Logic #{idx}: {e['file']}:{e['line']} ({e['call']})\n")
            out.write(f"- **Operation:** `{e['call']}`\n")
            out.write(f"- **Statement / Query:**\n```sql\n{e['arg0']}\n```\n")
            if e['arg1']:
                out.write(f"- **Parameters:** `{e['arg1']}`\n")
            out.write(f"- **Source Line:** `{e['line_str']}`\n\n")

extract_detailed()
