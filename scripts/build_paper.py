#!/usr/bin/env python3
"""Build and compile the IEEE paper using local or system LaTeX/tectonic."""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAPER_DIR = PROJECT_ROOT / "paper"
PAPER_OUT_DIR = PROJECT_ROOT / "paper_out"
LOCAL_TECTONIC = PROJECT_ROOT / "tectonic"


def main():
    print("=" * 60)
    print("  GovBench-Clinical: IEEE Paper Compilation Pipeline")
    print("=" * 60)

    PAPER_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Determine compiler executable
    compiler_cmd = None
    if LOCAL_TECTONIC.exists() and LOCAL_TECTONIC.is_file():
        compiler_cmd = [str(LOCAL_TECTONIC), "main.tex"]
    elif shutil.which("tectonic"):
        compiler_cmd = ["tectonic", "main.tex"]
    elif shutil.which("pdflatex"):
        print("Using pdflatex + bibtex fallback...")
        cmds = [
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
            ["bibtex", "main"],
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ]
        for c in cmds:
            res = subprocess.run(c, cwd=str(PAPER_DIR), capture_output=True, text=True)
            if res.returncode != 0:
                print(f"Error executing {c}: {res.stderr}")
                sys.exit(1)
        shutil.copy2(PAPER_DIR / "main.pdf", PAPER_OUT_DIR / "main.pdf")
        print(f"✓ Successfully built: {PAPER_OUT_DIR / 'main.pdf'}")
        return

    if not compiler_cmd:
        print("Error: neither tectonic nor pdflatex was found.")
        sys.exit(1)

    print(f"Compiling with command: {' '.join(compiler_cmd)} in {PAPER_DIR}")
    proc = subprocess.run(compiler_cmd, cwd=str(PAPER_DIR), capture_output=True, text=True)
    if proc.returncode != 0:
        print("Compilation error:")
        print(proc.stderr or proc.stdout)
        sys.exit(proc.returncode)

    built_pdf = PAPER_DIR / "main.pdf"
    if not built_pdf.exists():
        print("Error: main.pdf was not generated.")
        sys.exit(1)

    dest_pdf = PAPER_OUT_DIR / "main.pdf"
    shutil.copy2(built_pdf, dest_pdf)

    # Report page count on macOS
    mdls_proc = subprocess.run(["mdls", "-name", "kMDItemNumberOfPages", str(dest_pdf)], capture_output=True, text=True)
    pages_info = mdls_proc.stdout.strip() if mdls_proc.returncode == 0 else ""

    print(f"\n✓ Compilation Successful!")
    print(f"  Destination: {dest_pdf}")
    print(f"  Size: {dest_pdf.stat().st_size / 1024:.1f} KiB")
    if pages_info:
        print(f"  {pages_info}")
    print("=" * 60)


if __name__ == "__main__":
    main()
