#!/usr/bin/env python3
"""
EcoOpen Command Line Interface
==============================

Command line interface for EcoOpen package.
"""

import sys
import json
import argparse
from pathlib import Path

from .core import (
    LLM_AVAILABLE,
    DATA_FORMATS,
    process_single_pdf_file,
    process_pdf_folder_to_csv,
    check_ollama_performance,
    auto_detect_best_model,
    HARDWARE_OPTIMIZED_MODELS,
    get_gpu_memory,
    get_optimal_model,
    logger
)


def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(description='EcoOpen - PDF Batch Processing for Data Availability Extraction')
    parser.add_argument('--pdf-folder', help='Folder containing PDF files to process')
    parser.add_argument('--pdf', help='Process single PDF file')
    parser.add_argument('--output', default='ecoopen_output.csv', help='Output CSV file')
    parser.add_argument('--download-data', action='store_true', help='Download data files found in papers')
    parser.add_argument('--data-dir', default='./data_downloads', help='Directory to save downloaded data files')
    parser.add_argument('--max-data-files', type=int, default=5, help='Maximum number of data files to download per paper')
    parser.add_argument('--max-file-size', type=int, default=100, help='Maximum file size to download (MB)')
    parser.add_argument('--formats', nargs='*', choices=list(DATA_FORMATS.keys()), 
                       help='Data formats to download (tabular, text, scientific, archives, images, code, documents, other)')
    parser.add_argument('--check-llm', action='store_true', help='Check LLM availability')
    parser.add_argument('--check-performance', action='store_true', help='Check Ollama performance and get optimization suggestions')
    parser.add_argument('--model', default=None, help='LLM model to use (auto-detects phi4 or phi3:mini by default)')
    parser.add_argument('--list-models', action='store_true', help='List recommended models for your hardware')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging to see LLM responses')
    parser.add_argument('--recursive', action='store_true', help='Search for PDFs recursively in subfolders')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')
    
    args = parser.parse_args()
    
    # Store model choice globally for access in other functions
    if args.model is None:
        # Auto-detect optimal phi model
        import ecoopen.core as core
        core._current_model = auto_detect_best_model()
        logger.info(f"🤖 Auto-selected model: {core._current_model}")
    else:
        import ecoopen.core as core
        core._current_model = args.model
        logger.info(f"🤖 Using specified model: {args.model}")
    
    # Enable debug logging if requested
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🐛 Debug logging enabled")
    
    if args.list_models:
        print("=== Hardware-Optimized Model Recommendations ===")
        try:
            vram_gb = get_gpu_memory()
            print(f"🖥️  Detected GPU Memory: {vram_gb:.1f} GB")
            
            optimal_model = get_optimal_model(vram_gb)
            print(f"🎯 Recommended Model: {optimal_model}\n")
            
            print("📋 All Available Models:")
            for model in HARDWARE_OPTIMIZED_MODELS:
                fits = "✅" if model["min_vram"] <= vram_gb else "❌"
                recommended = "⭐" if model["name"] == optimal_model else "  "
                print(f"{fits} {recommended} {model['name']:<15} | {model['size_gb']:>4.1f}GB | {model['quality']:<10} | {model['speed']}")
            
            print(f"\n💡 To use a specific model: --model MODEL_NAME")
            print(f"💡 To auto-detect best model: --model auto (default)")
            
        except Exception as e:
            print(f"❌ Could not detect hardware: {e}")
        sys.exit(0)
    
    if args.check_llm:
        print(f"LLM Available: {LLM_AVAILABLE}")
        if LLM_AVAILABLE:
            try:
                from .core import LLMExtractor
                extractor = LLMExtractor()
                print("✓ LLM extractor initialized successfully")
            except Exception as e:
                print(f"✗ LLM extractor failed: {e}")
        sys.exit(0)
    
    if args.check_performance:
        print("=== Ollama Performance Check ===")
        perf_info = check_ollama_performance()
        if 'error' in perf_info:
            print(f"❌ {perf_info['error']}")
        else:
            print(f"📊 Model: {perf_info['model_name']}")
            print(f"📦 Size: {perf_info['size_gb']} GB")
            print(f"🖥️  CPU: {perf_info['cpu_percent']}% | GPU: {perf_info['gpu_percent']}%")
            
            if perf_info['is_fully_gpu']:
                print("✅ Model is fully running on GPU - optimal performance!")
            elif perf_info['is_mixed']:
                print("⚠️  Model is split between CPU/GPU - this will be slower")
            else:
                print("🐌 Model is mostly on CPU - very slow performance")
            
            if perf_info['recommendations']:
                print("\n🚀 Performance Recommendations:")
                for i, rec in enumerate(perf_info['recommendations'], 1):
                    print(f"   {i}. {rec}")
                    
                print(f"\n💡 Faster model options:")
                for model_info in HARDWARE_OPTIMIZED_MODELS:
                    if model_info["min_vram"] <= 8:  # Show models that fit in most GPUs
                        print(f"   • {model_info['name']}: {model_info['size_gb']}GB - {model_info['quality']} quality, {model_info['speed']} speed")
                    
        sys.exit(0)
    
    if args.pdf:
        # Process single PDF
        if not LLM_AVAILABLE:
            print("Error: LLM dependencies required for PDF processing")
            sys.exit(1)
        
        result = process_single_pdf_file(
            args.pdf,
            download_data=args.download_data,
            data_dir=args.data_dir,
            max_data_files=args.max_data_files,
            allowed_formats=args.formats,
            max_size_mb=args.max_file_size
        )
        
        print(json.dumps(result, indent=2))
        return
    
    # Process PDF folder
    if args.pdf_folder:
        if not LLM_AVAILABLE:
            print("Error: LLM dependencies required for PDF processing")
            sys.exit(1)
        
        df = process_pdf_folder_to_csv(
            args.pdf_folder,
            args.output,
            args.recursive,
            args.download_data,
            args.data_dir,
            args.max_data_files,
            args.formats,
            args.max_file_size
        )
        
        pdf_count = len(df)
        print(f"Processed {pdf_count} PDF files. Results saved to {args.output}")
        
        if args.download_data:
            # Summary of downloaded data
            total_downloaded = sum(1 for _, row in df.iterrows() if row.get('number_of_files', 0) > 0)
            total_files = sum(row.get('number_of_files', 0) for _, row in df.iterrows())
            total_size_mb = sum(row.get('data_size', 0) for _, row in df.iterrows()) / (1024 * 1024)
            print(f"Data download summary:")
            print(f"  - Papers with downloaded data: {total_downloaded}")
            print(f"  - Total files downloaded: {total_files}")
            print(f"  - Total data size: {total_size_mb:.2f} MB")
        
        return
    
    # No input provided
    print("Error: No input provided.")
    print("Use --pdf-folder to process a folder of PDFs")
    print("Use --pdf to process a single PDF file")
    print("Use --help for all options")
    sys.exit(1)


if __name__ == "__main__":
    main()
