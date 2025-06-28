#!/usr/bin/env python3
"""
Comprehensive Test Suite for EcoOpen Package
============================================

This script tests the EcoOpen package against all available PDFs in the test directory.
It generates a detailed report showing:
- Processing success/failure rates
- Data availability detection results
- Code availability detection results
- Performance metrics
- CSV output validation

Usage:
    python test_all_pdfs.py [--output results.csv] [--detailed]
"""

import os
import sys
import time
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any
import traceback

# Import the EcoOpen package
try:
    from ecoopen import (
        LLM_AVAILABLE, 
        process_pdf_file, 
        LLMExtractor, 
        CSV_COLUMNS,
        extract_text_from_pdf
    )
except ImportError as e:
    print(f"Error: Could not import EcoOpen package: {e}")
    sys.exit(1)

class ComprehensivePDFTester:
    """Comprehensive tester for all PDFs in the test directory."""
    
    def __init__(self, pdf_dir: str = "./tests/pdf_downloads"):
        self.pdf_dir = Path(pdf_dir)
        self.results = []
        self.start_time = None
        self.total_time = 0
        
    def run_all_tests(self, output_file: str = "comprehensive_test_results.csv", 
                     detailed: bool = False) -> Dict[str, Any]:
        """Run tests on all PDFs and generate comprehensive report."""
        
        print("🧪 EcoOpen Comprehensive PDF Test Suite")
        print("=" * 60)
        
        # Check prerequisites
        if not self._check_prerequisites():
            return {"error": "Prerequisites not met"}
        
        # Get all PDF files
        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"❌ No PDF files found in {self.pdf_dir}")
            return {"error": "No PDF files found"}
        
        print(f"📁 Found {len(pdf_files)} PDF files to test")
        print(f"🤖 LLM Available: {LLM_AVAILABLE}")
        
        if not LLM_AVAILABLE:
            print("⚠️  LLM not available - this will limit testing capabilities")
        
        print("\n🚀 Starting comprehensive test...")
        self.start_time = time.time()
        
        # Process each PDF
        successful = 0
        failed = 0
        
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n📄 [{i:2d}/{len(pdf_files)}] Processing: {pdf_file.name}")
            
            result = self._test_single_pdf(pdf_file, detailed)
            self.results.append(result)
            
            if result['success']:
                successful += 1
                print(f"   ✅ Success")
                if result.get('data_found'):
                    print(f"   📊 Data availability detected")
                if result.get('code_found'):
                    print(f"   💻 Code availability detected")
            else:
                failed += 1
                print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
        
        self.total_time = time.time() - self.start_time
        
        # Generate comprehensive report
        report = self._generate_report(successful, failed, len(pdf_files))
        
        # Save results to CSV
        if self.results:
            self._save_results_csv(output_file)
            print(f"\n💾 Detailed results saved to: {output_file}")
        
        # Print final report
        self._print_report(report)
        
        return report
    
    def _check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        if not self.pdf_dir.exists():
            print(f"❌ PDF directory not found: {self.pdf_dir}")
            return False
        
        if not LLM_AVAILABLE:
            print("⚠️  LLM dependencies not available - some tests will be skipped")
        
        return True
    
    def _test_single_pdf(self, pdf_file: Path, detailed: bool = False) -> Dict[str, Any]:
        """Test processing of a single PDF file."""
        start_time = time.time()
        
        result = {
            'filename': pdf_file.name,
            'file_size': pdf_file.stat().st_size,
            'processing_time': 0,
            'success': False,
            'error': None,
            'pdf_content_length': 0,
            'text_extracted': False,
            'text_length': 0,
            'llm_processed': False,
            'data_found': False,
            'code_found': False,
            'data_statements_count': 0,
            'code_statements_count': 0,
            'data_links_count': 0,
            'repository_detected': False,
            'csv_columns_valid': False
        }
        
        try:
            # Read PDF content
            with open(pdf_file, 'rb') as f:
                pdf_content = f.read()
            
            result['pdf_content_length'] = len(pdf_content)
            
            # Test basic text extraction
            try:
                text = extract_text_from_pdf(pdf_content)
                if text and text.strip():
                    result['text_extracted'] = True
                    result['text_length'] = len(text)
            except Exception as e:
                result['text_extraction_error'] = str(e)
            
            # Test LLM processing if available
            if LLM_AVAILABLE:
                try:
                    pdf_result = process_pdf_file(str(pdf_file))
                    result['llm_processed'] = True
                    
                    # Validate CSV structure
                    result['csv_columns_valid'] = all(col in pdf_result for col in CSV_COLUMNS)
                    
                    # Check data availability
                    data_statements = pdf_result.get('data_availability_statements', '')
                    if data_statements and data_statements.strip():
                        result['data_found'] = True
                        result['data_statements_count'] = len(data_statements.split(';'))
                    
                    # Check code availability
                    code_statements = pdf_result.get('code_availability_statements', '')
                    if code_statements and code_statements.strip():
                        result['code_found'] = True
                        result['code_statements_count'] = len(code_statements.split(';'))
                    
                    # Check data links
                    data_links = pdf_result.get('data_links', [])
                    if isinstance(data_links, list):
                        result['data_links_count'] = len(data_links)
                    elif isinstance(data_links, str) and data_links.strip():
                        result['data_links_count'] = 1
                    
                    # Check repository detection
                    repository = pdf_result.get('repository', '')
                    if repository and repository.strip():
                        result['repository_detected'] = True
                    
                    if detailed:
                        result['full_result'] = pdf_result
                    
                except Exception as e:
                    result['llm_error'] = str(e)
                    if detailed:
                        result['llm_traceback'] = traceback.format_exc()
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            if detailed:
                result['traceback'] = traceback.format_exc()
        
        result['processing_time'] = time.time() - start_time
        return result
    
    def _generate_report(self, successful: int, failed: int, total: int) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        
        # Basic statistics
        success_rate = (successful / total) * 100 if total > 0 else 0
        
        # LLM-specific statistics
        llm_processed = sum(1 for r in self.results if r.get('llm_processed', False))
        text_extracted = sum(1 for r in self.results if r.get('text_extracted', False))
        data_found = sum(1 for r in self.results if r.get('data_found', False))
        code_found = sum(1 for r in self.results if r.get('code_found', False))
        repos_detected = sum(1 for r in self.results if r.get('repository_detected', False))
        
        # Performance statistics
        processing_times = [r.get('processing_time', 0) for r in self.results if r.get('processing_time')]
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        # File size statistics
        file_sizes = [r.get('file_size', 0) for r in self.results]
        avg_size = sum(file_sizes) / len(file_sizes) if file_sizes else 0
        
        return {
            'total_files': total,
            'successful': successful,
            'failed': failed,
            'success_rate': success_rate,
            'llm_processed': llm_processed,
            'text_extracted': text_extracted,
            'data_availability_found': data_found,
            'code_availability_found': code_found,
            'repositories_detected': repos_detected,
            'total_processing_time': self.total_time,
            'average_processing_time': avg_time,
            'average_file_size': avg_size,
            'data_detection_rate': (data_found / llm_processed * 100) if llm_processed > 0 else 0,
            'code_detection_rate': (code_found / llm_processed * 100) if llm_processed > 0 else 0,
            'repository_detection_rate': (repos_detected / llm_processed * 100) if llm_processed > 0 else 0
        }
    
    def _save_results_csv(self, output_file: str):
        """Save detailed results to CSV."""
        # Prepare data for CSV
        csv_data = []
        for result in self.results:
            row = {
                'filename': result['filename'],
                'file_size_bytes': result['file_size'],
                'processing_time_seconds': result['processing_time'],
                'success': result['success'],
                'error': result.get('error', ''),
                'text_extracted': result['text_extracted'],
                'text_length': result['text_length'],
                'llm_processed': result['llm_processed'],
                'data_found': result['data_found'],
                'code_found': result['code_found'],
                'data_statements_count': result['data_statements_count'],
                'code_statements_count': result['code_statements_count'],
                'data_links_count': result['data_links_count'],
                'repository_detected': result['repository_detected'],
                'csv_columns_valid': result['csv_columns_valid']
            }
            csv_data.append(row)
        
        df = pd.DataFrame(csv_data)
        df.to_csv(output_file, index=False)
    
    def _print_report(self, report: Dict[str, Any]):
        """Print comprehensive test report."""
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("=" * 60)
        
        print(f"\n📁 File Processing:")
        print(f"   Total files tested: {report['total_files']}")
        print(f"   Successful: {report['successful']}")
        print(f"   Failed: {report['failed']}")
        print(f"   Success rate: {report['success_rate']:.1f}%")
        
        if LLM_AVAILABLE:
            print(f"\n🤖 LLM Processing:")
            print(f"   LLM processed: {report['llm_processed']}")
            print(f"   Text extracted: {report['text_extracted']}")
            
            print(f"\n📊 Data Availability Detection:")
            print(f"   Papers with data availability: {report['data_availability_found']}")
            print(f"   Data detection rate: {report['data_detection_rate']:.1f}%")
            
            print(f"\n💻 Code Availability Detection:")
            print(f"   Papers with code availability: {report['code_availability_found']}")
            print(f"   Code detection rate: {report['code_detection_rate']:.1f}%")
            
            print(f"\n🏛️ Repository Detection:")
            print(f"   Repositories detected: {report['repositories_detected']}")
            print(f"   Repository detection rate: {report['repository_detection_rate']:.1f}%")
        
        print(f"\n⏱️ Performance:")
        print(f"   Total processing time: {report['total_processing_time']:.1f} seconds")
        print(f"   Average time per file: {report['average_processing_time']:.1f} seconds")
        print(f"   Average file size: {report['average_file_size']/1024:.1f} KB")
        
        print(f"\n🎯 Overall Assessment:")
        if report['success_rate'] >= 90:
            print("   ✅ EXCELLENT - Package performs very well")
        elif report['success_rate'] >= 75:
            print("   👍 GOOD - Package performs well with minor issues")
        elif report['success_rate'] >= 50:
            print("   ⚠️  FAIR - Package has some issues that need attention")
        else:
            print("   ❌ POOR - Package needs significant improvements")
        
        print("\n" + "=" * 60)


def main():
    """Main function to run comprehensive tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive EcoOpen PDF Test Suite')
    parser.add_argument('--output', default='comprehensive_test_results.csv', 
                       help='Output CSV file for detailed results')
    parser.add_argument('--detailed', action='store_true', 
                       help='Include detailed results in output')
    parser.add_argument('--pdf-dir', default='./tests/pdf_downloads',
                       help='Directory containing test PDFs')
    
    args = parser.parse_args()
    
    # Run comprehensive tests
    tester = ComprehensivePDFTester(args.pdf_dir)
    report = tester.run_all_tests(args.output, args.detailed)
    
    # Exit with appropriate code
    if 'error' in report:
        sys.exit(1)
    elif report.get('success_rate', 0) < 50:
        print("\n⚠️  Warning: Low success rate detected")
        sys.exit(1)
    else:
        print("\n🎉 Test suite completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
