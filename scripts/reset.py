"""Naye account par switch karne se pehle purana data saaf karo.

Chalao:  python scripts/reset.py

Account badalne par reset zaruri hai, warna:
  - purane account ke followers "seeded" hain, naye account ka follow-back tootega
  - purane account ka discovered cap naye par lag jayega
  - day counter galat hoga, warmup skip ho jayega
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> int:
    if not DATA.exists():
        print("data/ folder hai hi nahi. Kuch reset karne ko nahi.")
        return 0

    files = [p for p in DATA.iterdir() if p.is_file()]
    if not files:
        print("data/ khali hai. Kuch reset karne ko nahi.")
        return 0

    print("Ye files hain:")
    for p in files:
        print("  ", p.name)

    answer = input("\nSab backup karke reset kar dun? (haan/nahi): ").strip().lower()
    if answer not in ("haan", "y", "yes", "ha"):
        print("Rehne diya.")
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    backup = ROOT / f"data-backup-{stamp}"
    backup.mkdir()
    for p in files:
        shutil.copy2(p, backup / p.name)
        p.unlink()

    print(f"\nHo gaya. Backup yahan hai: {backup.name}")
    print("Ab .env me naye account ki details daalo aur bot chalao.")
    print("Pehla din phir se Day 1 hoga, warmup dobara chalega. Yahi sahi hai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
