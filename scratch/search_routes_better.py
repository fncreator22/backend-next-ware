import os
import re

def search():
    src_dir = "c:\\Users\\sr2ma\\OneDrive\\Documents\\GitHub\\backend-warehouse\\src"
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith("router.py") or file.endswith("service.py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                # Find occurrences of pdf, csv, excel, export, import, print
                matches = re.finditer(r"(def\s+\w+|@router\.\w+\([^)]+\))", content)
                for m in matches:
                    text = m.group(0)
                    if any(kw in text.lower() for kw in ["pdf", "csv", "excel", "export", "import", "print"]):
                        print(f" - {os.path.basename(path)}: {text.strip()}")

if __name__ == "__main__":
    search()
