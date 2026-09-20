import os
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "logs" / "directory-tree.txt"


def is_reparse_point(path):
    try:
        attributes = os.stat(path, follow_symlinks=False).st_file_attributes
        return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, OSError):
        return False


def extended_path(path):
    value = os.path.abspath(os.fspath(path))
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        return "\\\\?\\" + value
    return value


def tree_lines(directory, prefix=""):
    try:
        entries = sorted(
            os.scandir(extended_path(directory)),
            key=lambda entry: entry.name.lower(),
        )
    except OSError as exc:
        yield f"{prefix}[ERROR: {exc}]"
        return

    items = []
    for entry in entries:
        items.append(entry)

    for index, entry in enumerate(items):
        last = index == len(items) - 1
        connector = "`-- " if last else "|-- "
        yield f"{prefix}{connector}{entry.name}"

        if not entry.is_dir(follow_symlinks=False):
            continue

        if is_reparse_point(entry.path):
            try:
                target = os.readlink(entry.path)
            except OSError:
                target = "unknown"
            yield f"{prefix}{'    ' if last else '|   '}    [junction -> {target}]"
            continue

        next_prefix = prefix + ("    " if last else "|   ")
        yield from tree_lines(entry.path, next_prefix)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.touch(exist_ok=True)
    lines = [str(ROOT)] + list(tree_lines(ROOT))
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} lines to {OUTPUT}")


if __name__ == "__main__":
    main()
