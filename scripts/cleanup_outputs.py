import argparse
import os
from pathlib import Path


def human_size(n):
    for unit in ['B','KB','MB','GB','TB']:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def collect_files(root: Path, patterns=("*.mp4", "*.mp3", "*.wav", "*.mov")):
    files = []
    for pat in patterns:
        files.extend(root.rglob(pat))
    # de-dup
    seen = set()
    unique = []
    for p in files:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def main():
    ap = argparse.ArgumentParser(description="Clean large outputs in out/ and web/out")
    ap.add_argument("--out-dirs", nargs="*", default=["out", "web/out"], help="Directories to clean")
    ap.add_argument("--keep-n", type=int, default=10, help="Keep N most recent files per dir")
    ap.add_argument("--min-mb", type=int, default=50, help="Only delete files larger than this size (MB)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    args = ap.parse_args()

    total_deleted = 0
    total_bytes = 0

    for d in args.out_dirs:
        root = Path(d)
        if not root.exists():
            print(f"[SKIP] {root} not found")
            continue
        files = collect_files(root)
        files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

        # Keep newest N, evaluate deletions beyond keep
        candidates = files[args.keep_n:]
        candidates = [p for p in candidates if p.stat().st_size >= args.min_mb * 1024 * 1024]

        if not candidates:
            print(f"[OK] Nothing to delete in {root}")
            continue

        print(f"[CLEAN] {root} -> {len(candidates)} files > {args.min_mb}MB (keeping {args.keep_n})")
        for p in candidates:
            size = p.stat().st_size
            print(f" - {p} ({human_size(size)})")
            if not args.dry_run:
                try:
                    p.unlink()
                    total_deleted += 1
                    total_bytes += size
                except Exception as e:
                    print(f"   [WARN] Failed to delete {p}: {e}")

    print(f"\n[SUMMARY] Deleted {total_deleted} files, freed {human_size(total_bytes)}")


if __name__ == "__main__":
    main()
