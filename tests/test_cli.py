from __future__ import annotations

import io
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from underwright.cli import build_parser, run_command

REQUEST_ID = UUID("80000000-0000-0000-0000-000000000001")

class CliUnitTests(unittest.TestCase):
    def test_build_parser_parses_run_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--quote-request-id",
                str(REQUEST_ID),
                "--template-code",
                "PAD_STANDARD_RO",
            ]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.quote_request_id, REQUEST_ID)
        self.assertEqual(args.template_code, "PAD_STANDARD_RO")

    @patch("underwright.cli.build_quote_workflow")
    def test_run_command_prints_generated_document_id(
        self,
        mock_build_workflow: MagicMock,
    ) -> None:
        class DocumentWithId:
            id = 123
            rendered_text = "rendered content"

        mock_result = MagicMock()
        mock_result.quote_document = DocumentWithId()
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = mock_result
        mock_build_workflow.return_value = mock_workflow

        with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            result = run_command(
                quote_request_id=REQUEST_ID,
                template_code="PAD_STANDARD_RO",
            )

        self.assertEqual(result, 0)
        mock_workflow.run.assert_called_once_with(
            request_id=REQUEST_ID,
            template_code="PAD_STANDARD_RO",
        )
        self.assertIn("QuoteDocument id=123", fake_stdout.getvalue())

    @patch("underwright.cli.build_quote_workflow")
    def test_run_command_prints_success_without_document_id(
        self,
        mock_build_workflow: MagicMock,
    ) -> None:
        class DocumentWithoutId:
            pass

        mock_result = MagicMock()
        mock_result.quote_document = DocumentWithoutId()
        mock_result.status = "underwriter_review"
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = mock_result
        mock_build_workflow.return_value = mock_workflow

        with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            result = run_command(
                quote_request_id=REQUEST_ID,
                template_code="PAD_STANDARD_RO",
            )

        self.assertEqual(result, 0)
        self.assertIn(
            "Quote generation flow completed with status=underwriter_review.",
            fake_stdout.getvalue(),
        )
        self.assertNotIn("QuoteDocument id=", fake_stdout.getvalue())
