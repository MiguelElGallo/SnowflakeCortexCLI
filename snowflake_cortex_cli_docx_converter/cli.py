from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert DOCX files under docs/ to Markdown using MarkItDown."
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Directory that contains .docx files. Defaults to ./docs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Optional output directory for .md files. If omitted, each Markdown file is "
            "written next to its source .docx file."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Markdown files.",
    )
    return parser.parse_args()


def find_docx_files(docs_dir: Path) -> list[Path]:
    return sorted(path for path in docs_dir.rglob("*.docx") if path.is_file())


def target_path(docx_path: Path, docs_dir: Path, output_dir: Path | None) -> Path:
    if output_dir is None:
        return docx_path.with_suffix(".md")

    relative_docx = docx_path.relative_to(docs_dir)
    return output_dir / relative_docx.with_suffix(".md")


def convert_docs(docs_dir: Path, output_dir: Path | None, force: bool) -> int:
    if not docs_dir.exists() or not docs_dir.is_dir():
        print(f"Docs directory does not exist or is not a directory: {docs_dir}")
        return 1

    docx_files = find_docx_files(docs_dir)
    if not docx_files:
        print(f"No .docx files found under {docs_dir}")
        return 1

    from markitdown import MarkItDown

    converter = MarkItDown(enable_plugins=False)
    converted = 0
    skipped = 0
    failed = 0

    for docx_path in docx_files:
        output_path = target_path(docx_path, docs_dir, output_dir)

        if output_path.exists() and not force:
            print(f"Skipping existing file: {output_path}")
            skipped += 1
            continue

        try:
            result = converter.convert(str(docx_path))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.text_content, encoding="utf-8")
            print(f"Converted {docx_path} -> {output_path}")
            converted += 1
        except Exception as exc:  # pragma: no cover - depends on external converter/runtime
            print(f"Failed to convert {docx_path}: {exc}")
            failed += 1

    print(f"Finished. converted={converted} skipped={skipped} failed={failed}")
    return 1 if failed else 0


def main() -> int:
    args = parse_args()
    docs_dir = args.docs_dir.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else None
    return convert_docs(docs_dir=docs_dir, output_dir=output_dir, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
