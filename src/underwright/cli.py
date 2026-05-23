from __future__ import annotations

import argparse
from typing import Sequence
from uuid import UUID

from underwright.composition import build_quote_workflow

# Underwright CLI example:
# python -m underwright.cli run --quote-request-id 80000000-0000-0000-0000-000000000001 --template-code PAD_STANDARD_RO


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="underwright",
        description="Underwright PAD contract generation CLI",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Run the Underwright quote generation flow for one quote request",
    )
    run_parser.add_argument(
        "--quote-request-id",
        type=UUID,
        required=True,
        help="Quote request UUID to generate",
    )
    run_parser.add_argument(
        "--template-code",
        type=str,
        required=True,
        help="Template code to use for rendering",
    )

    return parser


def run_command(quote_request_id: UUID, template_code: str) -> int:
    workflow = build_quote_workflow()
    result = workflow.run(request_id=quote_request_id, template_code=template_code)

    if result.status == "failed":
        print("Quote generation flow failed.")
        if result.module_results:
            last_result = result.module_results[-1]
            print(f"Failure module: {last_result.module_name}")
            print(f"Reason: {last_result.summary}")
        return 1

    document = result.quote_document

    document_id = getattr(document, "id", None)

    if document_id is not None:
        print(
            f"Quote generation flow completed successfully. "
            f"QuoteDocument id={document_id}"
        )
        print("\n--- Generated quote ---\n")
        print(document.rendered_text)
    else:
        print(f"Quote generation flow completed with status={result.status}.")

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return run_command(
            quote_request_id=args.quote_request_id,
            template_code=args.template_code,
        )

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
