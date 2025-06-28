#!/usr/bin/env python3
"""
EcoOpen Demo Script
==================

This script demonstrates the enhanced EcoOpen functionality including:
- Format-specific data downloading
- Progress tracking
- Error handling
- CLI integration

Usage:
    python demo.py
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and display results."""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        if result.stdout:
            print("📤 Output:")
            print(result.stdout)
        
        if result.stderr:
            print("⚠️  Errors:")
            print(result.stderr)
            
        if result.returncode == 0:
            print("✅ Command completed successfully!")
        else:
            print(f"❌ Command failed with return code {result.returncode}")
            
    except subprocess.TimeoutExpired:
        print("⏰ Command timed out after 5 minutes")
    except Exception as e:
        print(f"💥 Error running command: {e}")

def main():
    """Main demo function."""
    print("📄 EcoOpen Enhanced Functionality Demo")
    print("=" * 50)
    
    # Change to EcoOpenPy directory
    ecoopen_dir = Path(__file__).parent / "EcoOpenPy"
    if not ecoopen_dir.exists():
        print(f"❌ EcoOpenPy directory not found: {ecoopen_dir}")
        return
    
    os.chdir(ecoopen_dir)
    print(f"📂 Working directory: {os.getcwd()}")
    
    # Check if test PDF exists
    test_pdf = "pdfs/10.5194_bg-15-3521-2018.pdf"
    if not Path(test_pdf).exists():
        print(f"❌ Test PDF not found: {test_pdf}")
        print("Please ensure test PDFs are available in the pdfs/ directory")
        return
    
    # Demo 1: Check system status
    run_command(
        "python ecoopen.py --check-llm",
        "Checking LLM availability"
    )
    
    # Demo 2: List available models
    run_command(
        "python ecoopen.py --list-models",
        "Listing hardware-optimized models"
    )
    
    # Demo 3: Check performance
    run_command(
        "python ecoopen.py --check-performance",
        "Checking Ollama performance"
    )
    
    # Demo 4: Process single PDF with format filtering
    run_command(
        f"python ecoopen.py --pdf {test_pdf} --output demo_tabular.csv --download-data --formats tabular --max-data-files 2",
        "Processing PDF with tabular format filtering"
    )
    
    # Demo 5: Process single PDF with scientific format filtering  
    run_command(
        f"python ecoopen.py --pdf {test_pdf} --output demo_scientific.csv --download-data --formats scientific --max-data-files 2",
        "Processing PDF with scientific format filtering"
    )
    
    # Demo 6: Process single PDF with multiple formats
    run_command(
        f"python ecoopen.py --pdf {test_pdf} --output demo_multi.csv --download-data --formats tabular scientific code --max-data-files 3",
        "Processing PDF with multiple format filtering"
    )
    
    # Demo 7: Show help with new options
    run_command(
        "python ecoopen.py --help",
        "Displaying enhanced CLI help"
    )
    
    print(f"\n{'='*60}")
    print("🎉 Demo completed!")
    print("=" * 60)
    print("📊 Check the following output files:")
    
    output_files = [
        "demo_tabular.csv",
        "demo_scientific.csv", 
        "demo_multi.csv"
    ]
    
    for file in output_files:
        if Path(file).exists():
            size = Path(file).stat().st_size
            print(f"  ✅ {file} ({size:,} bytes)")
        else:
            print(f"  ❌ {file} (not created)")
    
    print("\n🖥️  To try the Streamlit GUI:")
    print("  cd ../EcoOpenGUI")
    print("  pip install -r requirements.txt")
    print("  ./run_gui.sh")
    print("  Open browser to: http://localhost:8501")

if __name__ == "__main__":
    main()
