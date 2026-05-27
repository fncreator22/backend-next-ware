import os

def search():
    keywords = ["export", "import", "backup", "restore", "csv", "excel", "pdf", "json"]
    src_dir = "c:\\Users\\sr2ma\\OneDrive\\Documents\\GitHub\\backend-warehouse\\src"
    results = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                for idx, line in enumerate(lines):
                    for kw in keywords:
                        if kw in line.lower():
                            results.append((path, idx + 1, kw, line.strip()))
                            break
    print(f"Found {len(results)} matches for import/export keywords:")
    for path, line_no, kw, content in results[:50]:
        print(f" - {os.path.basename(path)}:{line_no} [{kw}]: {content[:80]}")

if __name__ == "__main__":
    search()
