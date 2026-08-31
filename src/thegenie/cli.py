from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thegenie", description="Local academic retrieval and citation verification"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging from thegenie and its dependencies"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Index PDFs from a file or directory")
    ingest.add_argument("path", type=Path)
    ingest.add_argument("--prune", action="store_true", help="Remove indexed PDFs missing beneath PATH")

    search = commands.add_parser("search", help="Search indexed academic passages")
    search.add_argument("query")
    search.add_argument("--top-k", type=_positive_int)
    search.add_argument("--document-filter", help="Exact document ID, filename, or title")

    reference = commands.add_parser("reference", help="Show one stored passage and its provenance")
    reference.add_argument("citation_id")

    verify = commands.add_parser("verify", help="Verify citations and claims with local NLI")
    verify.add_argument("document", type=Path)
    verify.add_argument("--strict", action="store_true", help="Fail unsupported or unverifiable literature claims")

    revise = commands.add_parser("revise", help="Write a revision plan without editing the document")
    revise.add_argument("document", type=Path)

    citations = commands.add_parser("citations", help="Resolve citation markers into bibliography entries")
    citations.add_argument("document", type=Path)

    commands.add_parser("health", help="Check Qdrant, local models, documents, and index counts")

    models = commands.add_parser("models", help="Manage local models")
    model_commands = models.add_subparsers(dest="models_command", required=True)
    model_commands.add_parser("download", help="Download embedding, reranker, and NLI models")

    commands.add_parser("mcp", help="Run the read-only FastMCP stdio server")
    return parser


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _document(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _run(args: argparse.Namespace) -> int:
    import logging

    from thegenie.app import Application, json_text

    app = Application()
    logging.basicConfig(
        level="DEBUG" if args.verbose else "WARNING",
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logging.getLogger("thegenie").setLevel("DEBUG" if args.verbose else app.settings.log_level)
    if args.command == "ingest":
        from tqdm import tqdm

        bar: Any = None

        def _progress(done: int, total: int, item: Any) -> None:
            nonlocal bar
            if bar is None:
                bar = tqdm(total=total, desc="Ingesting", unit="doc", dynamic_ncols=True)
            bar.set_postfix_str(str(item.source_path), refresh=False)
            bar.update(1)

        report = app.ingest(args.path, prune=args.prune, on_progress=_progress)
        if bar is not None:
            bar.close()
        for item in report.items:
            detail = f" ({item.chunk_count} chunks)" if item.chunk_count else ""
            if item.error:
                detail = f": {item.error}"
            print(f"{item.status}: {item.source_path}{detail}")
        print(f"found {report.found}; updated {report.updated_chunks} chunks")
        return 1 if any(item.status == "failed" for item in report.items) else 0

    if args.command == "search":
        from thegenie.retrieval import format_human

        results = app.search(args.query, top_k=args.top_k, document_filter=args.document_filter)
        print(format_human(results) if results else "No references found.")
        return 0

    if args.command == "reference":
        reference = app.get_reference(args.citation_id)
        if reference is None:
            print("error: reference not found", file=sys.stderr)
            return 1
        print(json_text(reference))
        return 0

    if args.command == "verify":
        report, path = app.verify(_document(args.document), strict=args.strict)
        counts: dict[str, int] = {}
        for result in report.claims:
            counts[result.verdict] = counts.get(result.verdict, 0) + 1
        print("claims: " + (", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"))
        for result in report.structural:
            for issue in result.issues:
                print(f"{issue.failure}: {issue.message}")
        for result in report.claims:
            if result.verdict != "SUPPORTED" and result.claim.claim_type == "LITERATURE_CLAIM":
                print(f"{result.verdict}: {'; '.join(result.reasons)} — {result.claim.text}")
        print(f"report: {path}")
        return 1 if report.failed else 0

    if args.command == "revise":
        plan, json_path, markdown_path = app.revise(_document(args.document))
        print(f"revision items: {len(plan.items)}")
        print(f"plan: {json_path}\nreadable plan: {markdown_path}")
        return 0

    if args.command == "citations":
        entries, results = app.citations(_document(args.document))
        for entry in entries:
            print(entry)
        for result in results:
            for issue in result.issues:
                print(f"{issue.failure}: {issue.message}", file=sys.stderr)
        return 1 if any(not result.valid for result in results) else 0

    if args.command == "health":
        report = app.health()
        print(json_text(report))
        return 0 if report["status"] == "ok" else 1

    if args.command == "models":
        for model in app.download_models():
            print(f"downloaded: {model}")
        return 0

    if args.command == "mcp":
        from thegenie.mcp.server import run

        run(app)
        return 0

    raise RuntimeError(f"unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return _run(build_parser().parse_args(argv))
    except (KeyboardInterrupt, BrokenPipeError):
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
