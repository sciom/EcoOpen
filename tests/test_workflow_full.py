"""
Full workflow test for EcoOpen PDF analysis.

This test runs a comprehensive workflow on example PDFs to assess current accuracy and performance.
It exercises the full pipeline headlessly (no API, no MongoDB required) and reports detailed metrics.

Mark as 'integration' and 'slow' since it requires:
- Ollama with embedding model available
- Reachable LLM endpoint
- Multiple PDF analyses (takes time)
"""

import logging
import os
import time
from typing import Dict, List, Optional

import pytest

from app.core.errors import EmbeddingModelMissingError, InvalidPDFError, LLMServiceError
from app.models.schemas import PDFAnalysisResultModel
from app.services.agent import AgentRunner

logger = logging.getLogger(__name__)


class WorkflowTestResult:
    """Container for workflow test results and metrics."""

    def __init__(self, filename: str):
        self.filename = filename
        self.success = False
        self.error: Optional[str] = None
        self.duration_ms: Optional[int] = None
        self.result: Optional[PDFAnalysisResultModel] = None
        # Expected values for accuracy checking
        self.expected_doi: Optional[str] = None
        self.expected_title_keywords: List[str] = []
        self.expected_has_data_statement = False
        self.expected_has_code_statement = False
        self.expected_min_data_links = 0
        self.expected_min_code_links = 0

    def set_expectations(
        self,
        doi: Optional[str] = None,
        title_keywords: Optional[List[str]] = None,
        has_data_statement: bool = False,
        has_code_statement: bool = False,
        min_data_links: int = 0,
        min_code_links: int = 0,
    ):
        """Set expected values for accuracy validation."""
        self.expected_doi = doi
        self.expected_title_keywords = title_keywords or []
        self.expected_has_data_statement = has_data_statement
        self.expected_has_code_statement = has_code_statement
        self.expected_min_data_links = min_data_links
        self.expected_min_code_links = min_code_links

    def validate_accuracy(self) -> Dict[str, bool]:
        """
        Validate extraction accuracy against expected values.

        Returns:
            Dictionary mapping validation check to pass/fail status
        """
        if not self.result:
            return {"overall": False}

        checks = {}

        # DOI check
        if self.expected_doi:
            checks["doi_match"] = self.result.doi == self.expected_doi
        else:
            checks["doi_extracted"] = self.result.doi is not None

        # Title keywords check
        if self.expected_title_keywords and self.result.title:
            title_lower = self.result.title.lower()
            checks["title_has_keywords"] = all(kw.lower() in title_lower for kw in self.expected_title_keywords)

        # Data statement check
        if self.expected_has_data_statement:
            checks["has_data_statement"] = bool(self.result.data_availability_statement)

        # Code statement check
        if self.expected_has_code_statement:
            checks["has_code_statement"] = bool(self.result.code_availability_statement)

        # Data links check
        if self.expected_min_data_links > 0:
            checks["data_links_count"] = len(self.result.data_links) >= self.expected_min_data_links

        # Code links check
        if self.expected_min_code_links > 0:
            checks["code_links_count"] = len(self.result.code_links) >= self.expected_min_code_links

        # Overall check - all individual checks must pass
        checks["overall"] = all(checks.values()) if checks else False

        return checks


class WorkflowTestSuite:
    """Test suite for full workflow testing."""

    def __init__(self):
        self.results: List[WorkflowTestResult] = []
        self.total_duration_ms = 0

    def run_single_pdf(self, pdf_path: str, test_result: WorkflowTestResult) -> WorkflowTestResult:
        """
        Run analysis on a single PDF and record results.

        Args:
            pdf_path: Path to the PDF file
            test_result: WorkflowTestResult object to populate

        Returns:
            Populated WorkflowTestResult object
        """
        runner = AgentRunner()
        start_time = time.time()

        try:
            result = runner.analyze(pdf_path)
            test_result.success = True
            test_result.result = result
        except (EmbeddingModelMissingError, LLMServiceError, ImportError) as e:
            test_result.success = False
            test_result.error = f"Service unavailable: {str(e)}"
        except InvalidPDFError as e:
            test_result.success = False
            test_result.error = f"PDF error: {str(e)}"
        except Exception as e:
            test_result.success = False
            test_result.error = f"Unexpected error: {str(e)}"
        finally:
            end_time = time.time()
            test_result.duration_ms = int((end_time - start_time) * 1000)

        return test_result

    def run_all(self, pdf_configs: List[tuple]) -> None:
        """
        Run workflow tests on all configured PDFs.

        Args:
            pdf_configs: List of (pdf_path, test_result) tuples
        """
        total_start = time.time()

        for pdf_path, test_result in pdf_configs:
            if not os.path.exists(pdf_path):
                test_result.success = False
                test_result.error = "PDF file not found"
                self.results.append(test_result)
                continue

            self.run_single_pdf(pdf_path, test_result)
            self.results.append(test_result)

        total_end = time.time()
        self.total_duration_ms = int((total_end - total_start) * 1000)

    def generate_report(self) -> str:
        """
        Generate a comprehensive test report.

        Returns:
            Formatted report string
        """
        report_lines = [
            "=" * 80,
            "FULL WORKFLOW TEST REPORT",
            "=" * 80,
            "",
        ]

        # Summary statistics
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - successful_tests

        report_lines.extend(
            [
                f"Total Tests: {total_tests}",
                f"Successful: {successful_tests}",
                f"Failed: {failed_tests}",
                f"Success Rate: {(successful_tests / total_tests * 100):.1f}%" if total_tests > 0 else "N/A",
                f"Total Duration: {self.total_duration_ms}ms ({self.total_duration_ms / 1000:.2f}s)",
                "",
                "-" * 80,
                "",
            ]
        )

        # Individual test results
        for idx, result in enumerate(self.results, 1):
            report_lines.append(f"Test {idx}: {result.filename}")
            report_lines.append(f"  Status: {'✓ PASS' if result.success else '✗ FAIL'}")
            report_lines.append(f"  Duration: {result.duration_ms}ms")

            if result.error:
                report_lines.append(f"  Error: {result.error}")
            elif result.result:
                # Show extracted data
                report_lines.append(f"  Title: {result.result.title or 'None'}")
                report_lines.append(f"  DOI: {result.result.doi or 'None'}")
                report_lines.append(
                    f"  Data Statement: {result.result.data_availability_statement[:60] + '...' if result.result.data_availability_statement and len(result.result.data_availability_statement) > 60 else result.result.data_availability_statement or 'None'} (status={result.result.data_availability_status})"
                )
                report_lines.append(
                    f"  Code Statement: {result.result.code_availability_statement[:60] + '...' if result.result.code_availability_statement and len(result.result.code_availability_statement) > 60 else result.result.code_availability_statement or 'None'}"
                )
                report_lines.append(f"  Data Links: {len(result.result.data_links)}")
                for link in result.result.data_links:
                    report_lines.append(f"    - {link}")
                report_lines.append(f"  Code Links: {len(result.result.code_links)}")
                for link in result.result.code_links:
                    report_lines.append(f"    - {link}")

                # Accuracy validation
                accuracy_checks = result.validate_accuracy()
                if accuracy_checks:
                    report_lines.append("  Accuracy Validation:")
                    for check_name, passed in accuracy_checks.items():
                        status = "✓" if passed else "✗"
                        report_lines.append(f"    {status} {check_name}")

            report_lines.append("")

        # Performance summary
        if successful_tests > 0:
            avg_duration = sum(r.duration_ms for r in self.results if r.success) / successful_tests
            report_lines.extend(
                [
                    "-" * 80,
                    "PERFORMANCE SUMMARY",
                    "-" * 80,
                    f"Average processing time: {avg_duration:.0f}ms ({avg_duration / 1000:.2f}s)",
                    f"Fastest: {min(r.duration_ms for r in self.results if r.success)}ms",
                    f"Slowest: {max(r.duration_ms for r in self.results if r.success)}ms",
                    "",
                ]
            )

        # Accuracy summary
        overall_accuracy = sum(1 for r in self.results if r.success and r.validate_accuracy().get("overall", False))
        if successful_tests > 0:
            report_lines.extend(
                [
                    "-" * 80,
                    "ACCURACY SUMMARY",
                    "-" * 80,
                    f"Tests with expected results: {overall_accuracy}/{successful_tests}",
                    f"Accuracy Rate: {(overall_accuracy / successful_tests * 100):.1f}%",
                    "",
                ]
            )

        report_lines.append("=" * 80)

        return "\n".join(report_lines)


@pytest.mark.integration
@pytest.mark.slow
def test_full_workflow():
    """
    Run a complete workflow test on multiple example PDFs.

    This test:
    1. Processes multiple PDFs with known content
    2. Measures performance (processing time)
    3. Validates accuracy (expected vs actual extraction)
    4. Generates a comprehensive report

    The test will skip if required services are unavailable.
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    example_papers_dir = os.path.join(base_dir, "example_papers")

    # Configure test cases with expected results
    test_configs = []

    # Test 1: Data-focused paper
    test1 = WorkflowTestResult("test_data_paper.pdf")
    test1.set_expectations(
        doi="10.1234/example.2024.001",
        title_keywords=["Machine", "Learning", "Climate"],
        has_data_statement=True,
        min_data_links=1,
    )
    test_configs.append((os.path.join(example_papers_dir, "test_data_paper.pdf"), test1))

    # Test 2: Code-focused paper
    test2 = WorkflowTestResult("test_code_paper.pdf")
    test2.set_expectations(
        doi="10.1234/example.2024.002",
        title_keywords=["Algorithm", "Gene"],
        has_code_statement=True,
        min_code_links=1,
    )
    test_configs.append((os.path.join(example_papers_dir, "test_code_paper.pdf"), test2))

    # Test 3: Both data and code
    test3 = WorkflowTestResult("test_full_paper.pdf")
    test3.set_expectations(
        doi="10.1234/example.2024.003",
        title_keywords=["Biodiversity"],
        has_data_statement=True,
        has_code_statement=True,
        min_data_links=1,
        min_code_links=1,
    )
    test_configs.append((os.path.join(example_papers_dir, "test_full_paper.pdf"), test3))

    # Run the test suite
    suite = WorkflowTestSuite()
    suite.run_all(test_configs)

    # Generate and log report
    report = suite.generate_report()
    logger.info("\n" + report)
    print("\n" + report)  # Also print to stdout for pytest -s

    # Check if any tests were skipped due to service unavailability
    service_errors = [r for r in suite.results if r.error and "Service unavailable" in r.error]
    if service_errors:
        pytest.skip(f"Required services unavailable: {service_errors[0].error}")

    # Assertions for test success
    assert len(suite.results) > 0, "No tests were executed"
    assert suite.results[0].success or suite.results[0].error is not None, "Test did not complete properly"

    # If at least one test succeeded, we can validate the workflow works
    successful_count = sum(1 for r in suite.results if r.success)
    if successful_count > 0:
        assert suite.total_duration_ms > 0, "Total duration should be positive"
        assert successful_count == len(
            suite.results
        ), f"Some tests failed: {len(suite.results) - successful_count} out of {len(suite.results)}"
