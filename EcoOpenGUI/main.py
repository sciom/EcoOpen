#!/usr/bin/env python3
"""
EcoOpen Streamlit GUI - User-friendly interface for batch PDF processing
========================================================================

A modern, interactive web interface for the EcoOpen tool that allows users to:
- Upload PDF files or select folders
- Configure processing options
- Select data formats for downloading
- Monitor processing progress
- View and download results

Uses phi models only (phi4 preferred, phi3:mini fallback)

Author: Domagoj K. Hackenberger
License: MIT
"""

import streamlit as st
import pandas as pd
import os
import sys
import tempfile
import zipfile
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

# Add parent directory to path to import ecoopen
sys.path.append(str(Path(__file__).parent.parent / "EcoOpenPy"))

try:
    from ecoopen import (
        process_single_pdf_file, 
        process_pdf_folder_to_csv,
        DATA_FORMATS,
        LLM_AVAILABLE,
        HARDWARE_OPTIMIZED_MODELS,
        get_gpu_memory,
        get_optimal_model,
        check_ollama_performance,
        auto_detect_best_model
    )
    ECOOPEN_AVAILABLE = True
except ImportError as e:
    ECOOPEN_AVAILABLE = False

# Configure page
st.set_page_config(
    page_title="EcoOpen - PDF Data Extraction",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72, #2a5298);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
    }
    .phi-model-badge {
        background: linear-gradient(45deg, #ff6b6b, #ee5a24);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        margin: 0.5rem 0;
    }
    .status-box {
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

def check_system_status():
    """Check if all required components are available."""
    status = {
        'ecoopen_available': ECOOPEN_AVAILABLE,
        'llm_available': LLM_AVAILABLE if ECOOPEN_AVAILABLE else False,
        'ollama_running': False,
        'model_loaded': False,
        'gpu_available': False,
        'recommended_model': 'phi3:mini',
        'phi4_available': False,
        'phi3_mini_available': False
    }
    
    if ECOOPEN_AVAILABLE and LLM_AVAILABLE:
        try:
            # Check if Ollama is running
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                status['ollama_running'] = True
                available_models = result.stdout.lower()
                
                # Check for phi models specifically
                status['phi4_available'] = 'phi4' in available_models
                status['phi3_mini_available'] = 'phi3:mini' in available_models or 'phi3-mini' in available_models
                
                # Check if any model is loaded
                ps_result = subprocess.run(['ollama', 'ps'], capture_output=True, text=True, timeout=5)
                if ps_result.returncode == 0 and len(ps_result.stdout.strip().split('\n')) > 1:
                    status['model_loaded'] = True
                
                # Check GPU and get recommended model
                try:
                    gpu_memory = get_gpu_memory()
                    if gpu_memory > 2.0:
                        status['gpu_available'] = True
                        status['recommended_model'] = get_optimal_model(gpu_memory)
                except Exception:
                    pass
                    
        except Exception:
            pass
    
    return status

def render_system_status():
    """Render system status in the sidebar."""
    st.sidebar.header("🔧 System Status")
    
    status = check_system_status()
    
    # Phi Models Badge
    st.sidebar.markdown('<div class="phi-model-badge">🤖 Phi Models Only</div>', unsafe_allow_html=True)
    st.sidebar.markdown("*Optimized for phi4 and phi3:mini models*")
    
    # EcoOpen Backend
    if status['ecoopen_available']:
        st.sidebar.success("✅ EcoOpen Backend Available")
    else:
        st.sidebar.error("❌ EcoOpen Backend Not Found")
        st.sidebar.markdown("Please ensure the EcoOpenPy module is in the correct path.")
    
    # LLM Dependencies
    if status['llm_available']:
        st.sidebar.success("✅ LLM Dependencies Available")
    else:
        st.sidebar.error("❌ LLM Dependencies Missing")
        st.sidebar.code("pip install -r requirements.txt", language="bash")
    
    # Ollama Service
    if status['ollama_running']:
        st.sidebar.success("✅ Ollama Service Running")
    else:
        st.sidebar.error("❌ Ollama Service Not Running")
        st.sidebar.markdown("Start with: `ollama serve`")
    
    # Phi Model Status
    if status['phi4_available']:
        st.sidebar.success("✅ phi4 Available (Excellent Quality)")
    elif status['phi3_mini_available']:
        st.sidebar.success("✅ phi3:mini Available (Very Good Quality)")
        st.sidebar.info("💡 Consider installing phi4 for better quality")
        st.sidebar.code("ollama pull phi4", language="bash")
    else:
        st.sidebar.error("❌ No Phi Models Found")
        st.sidebar.markdown("Install a phi model:")
        st.sidebar.code("ollama pull phi4", language="bash")
        st.sidebar.markdown("Or fallback:")
        st.sidebar.code("ollama pull phi3:mini", language="bash")
    
    # Model Status
    if status['model_loaded']:
        st.sidebar.success("✅ Model Loaded")
    else:
        st.sidebar.warning("⚠️ No Model Loaded")
        st.sidebar.markdown(f"Install: `ollama pull {status['recommended_model']}`")
    
    # GPU Status
    if status['gpu_available']:
        st.sidebar.success("✅ GPU Available")
        try:
            gpu_memory = get_gpu_memory()
            if gpu_memory >= 12.0:
                st.sidebar.info(f"🎮 {gpu_memory:.1f}GB VRAM - phi4 recommended")
            else:
                st.sidebar.info(f"🎮 {gpu_memory:.1f}GB VRAM - phi3:mini recommended")
        except:
            st.sidebar.info("🎮 GPU detected")
    else:
        st.sidebar.info("ℹ️ CPU Mode (slower)")
    
    # Auto-detected Model
    try:
        recommended = auto_detect_best_model()
        st.sidebar.markdown(f"**Auto-Selected:** `{recommended}`")
    except:
        st.sidebar.markdown(f"**Fallback:** `phi3:mini`")
    
    return status

def render_format_selector():
    """Render data format selector with descriptions."""
    st.subheader("📁 Data Format Selection")
    
    # Create columns for better layout
    col1, col2 = st.columns(2)
    
    format_descriptions = {
        'tabular': '📊 Spreadsheets & tables (CSV, Excel, etc.)',
        'text': '📝 Text files (JSON, XML, YAML, etc.)',
        'scientific': '🔬 Scientific data (NetCDF, HDF5, MATLAB, etc.)',
        'archives': '📦 Compressed files (ZIP, TAR, etc.)',
        'images': '🖼️ Image files (PNG, JPEG, TIFF, etc.)',
        'code': '💻 Source code (Python, R, Jupyter, etc.)',
        'documents': '📄 Documents (PDF, Word, etc.)',
        'other': '❓ Other file types'
    }
    
    selected_formats = []
    
    with col1:
        for fmt in ['tabular', 'text', 'scientific', 'archives']:
            if st.checkbox(format_descriptions[fmt], key=f"fmt_{fmt}"):
                selected_formats.append(fmt)
    
    with col2:
        for fmt in ['images', 'code', 'documents', 'other']:
            if st.checkbox(format_descriptions[fmt], key=f"fmt_{fmt}"):
                selected_formats.append(fmt)
    
    if st.checkbox("📥 Download all formats", key="fmt_all"):
        selected_formats = list(DATA_FORMATS.keys())
    
    if selected_formats:
        st.info(f"Selected formats: {', '.join(selected_formats)}")
        
        # Show file extensions for selected formats
        with st.expander("📋 File extensions included"):
            for fmt in selected_formats:
                extensions = DATA_FORMATS.get(fmt, [])
                st.write(f"**{fmt}**: {', '.join(extensions)}")
    
    return selected_formats if selected_formats else None

def render_processing_options():
    """Render processing configuration options."""
    st.subheader("⚙️ Processing Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        download_data = st.checkbox("📥 Download data files", value=False)
        recursive_search = st.checkbox("🔍 Search subfolders recursively", value=False)
        
        if download_data:
            max_files = st.slider("Maximum files per paper", 1, 20, 5)
            max_size = st.slider("Maximum file size (MB)", 1, 500, 100)
        else:
            max_files = 5
            max_size = 100
    
    with col2:
        # Only phi models in the selector
        phi_models = ["phi4", "phi3:mini", "auto-detect"]
        selected_model = st.selectbox("🤖 Phi Model", phi_models, index=2)
        
        if selected_model == "auto-detect":
            try:
                auto_model = auto_detect_best_model()
                st.info(f"Auto-detected: {auto_model}")
                selected_model = auto_model
            except:
                selected_model = "phi3:mini"
        
        debug_mode = st.checkbox("🐛 Debug logging", value=False)
    
    return {
        'download_data': download_data,
        'recursive_search': recursive_search,
        'max_files': max_files,
        'max_size': max_size,
        'model': selected_model,
        'debug': debug_mode
    }

def process_files(pdf_paths: List[str], options: Dict, selected_formats: List[str] = None):
    """Process PDF files with progress tracking."""
    if not pdf_paths:
        st.error("No PDF files to process")
        return None, None
    
    # Create temporary directory for downloads
    temp_dir = tempfile.mkdtemp(prefix="ecoopen_")
    
    # Set up progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.empty()
    
    results = []
    
    try:
        total_files = len(pdf_paths)
        
        for i, pdf_path in enumerate(pdf_paths):
            progress = (i + 1) / total_files
            progress_bar.progress(progress)
            status_text.text(f"Processing {i+1}/{total_files}: {Path(pdf_path).name}")
            
            try:
                # Process single PDF
                result = process_single_pdf_file(
                    pdf_path,
                    download_data=options['download_data'],
                    data_dir=temp_dir,
                    max_data_files=options['max_files'],
                    allowed_formats=selected_formats,
                    max_size_mb=options['max_size']
                )
                
                result['identifier'] = f"{i+1:03d}"
                result['path'] = pdf_path
                results.append(result)
                
                # Show intermediate progress
                successful = sum(1 for r in results if r.get('doi') or r.get('title'))
                with results_container.container():
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Processed", f"{i+1}/{total_files}")
                    with col2:
                        st.metric("Successful", successful)
                    with col3:
                        if options['download_data']:
                            downloaded = sum(1 for r in results if r.get('number_of_files', 0) > 0)
                            st.metric("Data Downloads", downloaded)
                
            except Exception as e:
                st.error(f"Error processing {Path(pdf_path).name}: {e}")
                # Add empty result to maintain order
                empty_result = {
                    'identifier': f"{i+1:03d}",
                    'path': pdf_path,
                    'doi': '',
                    'title': f"Error: {str(e)}",
                    'authors': '',
                    'published': '',
                    'url': '',
                    'journal': '',
                    'has_fulltext': False,
                    'is_oa': False,
                    'pdf_content_length': 0,
                    'data_links': [],
                    'data_availability_statements': '',
                    'code_availability_statements': '',
                    'format': '',
                    'repository': '',
                    'repository_url': '',
                    'data_download_path': '',
                    'data_size': 0,
                    'number_of_files': 0,
                    'license': ''
                }
                results.append(empty_result)
        
        progress_bar.progress(1.0)
        status_text.text("✅ Processing complete!")
        
        return results, temp_dir
        
    except Exception as e:
        st.error(f"Processing failed: {e}")
        return None, temp_dir

def render_results(results: List[Dict], temp_dir: str):
    """Render processing results with download options."""
    if not results:
        return
    
    st.subheader("📊 Processing Results")
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total PDFs", len(df))
    
    with col2:
        successful = len(df[df['doi'].notna() & (df['doi'] != '')])
        st.metric("DOIs Found", successful)
    
    with col3:
        with_data = len(df[df['data_availability_statements'].str.len() > 0])
        st.metric("Data Statements", with_data)
    
    with col4:
        downloads = df['number_of_files'].sum()
        st.metric("Files Downloaded", int(downloads))
    
    # Data preview
    st.subheader("📋 Results Preview")
    
    # Select columns to display
    display_columns = ['identifier', 'doi', 'title', 'authors', 'published', 'journal']
    if 'data_availability_statements' in df.columns:
        display_columns.append('data_availability_statements')
    if 'number_of_files' in df.columns:
        display_columns.append('number_of_files')
    
    # Filter out empty rows for display
    display_df = df[display_columns].copy()
    display_df = display_df[display_df['title'].str.len() > 0]
    
    st.dataframe(display_df, use_container_width=True, height=400)
    
    # Download options
    st.subheader("💾 Download Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV download
        csv_data = df.to_csv(sep=';', index=False)
        st.download_button(
            label="📄 Download CSV Results",
            data=csv_data,
            file_name=f"ecoopen_results_{int(time.time())}.csv",
            mime="text/csv"
        )
    
    with col2:
        # JSON download
        json_data = df.to_json(orient='records', indent=2)
        st.download_button(
            label="📋 Download JSON Results",
            data=json_data,
            file_name=f"ecoopen_results_{int(time.time())}.json",
            mime="application/json"
        )
    
    # Downloaded files archive
    downloaded_files = df[df['number_of_files'] > 0]
    if len(downloaded_files) > 0 and os.path.exists(temp_dir):
        st.subheader("📦 Downloaded Data Files")
        
        # Create ZIP archive of downloaded files
        zip_buffer = create_download_archive(temp_dir, downloaded_files)
        if zip_buffer:
            st.download_button(
                label="📦 Download Data Files Archive",
                data=zip_buffer,
                file_name=f"ecoopen_data_{int(time.time())}.zip",
                mime="application/zip"
            )
        
        # Show download summary
        total_size = downloaded_files['data_size'].sum() / (1024 * 1024)  # MB
        total_files = downloaded_files['number_of_files'].sum()
        st.info(f"📊 Download summary: {int(total_files)} files, {total_size:.2f} MB total")

def create_download_archive(temp_dir: str, downloaded_files: pd.DataFrame) -> bytes:
    """Create a ZIP archive of downloaded files."""
    try:
        import io
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for _, row in downloaded_files.iterrows():
                paper_id = row['identifier']
                title = row.get('title', 'Unknown')[:50]  # Limit title length
                
                # Create folder for this paper
                paper_folder = f"{paper_id}_{title.replace('/', '_').replace(':', '_')}"
                
                # Find downloaded files for this paper
                paper_dir = Path(temp_dir) / paper_id
                if paper_dir.exists():
                    for file_path in paper_dir.rglob('*'):
                        if file_path.is_file():
                            # Add file to ZIP with paper folder structure
                            relative_path = file_path.relative_to(paper_dir)
                            zip_path = f"{paper_folder}/{relative_path}"
                            zip_file.write(file_path, zip_path)
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
        
    except Exception as e:
        st.error(f"Error creating download archive: {e}")
        return None

def main():
    """Main Streamlit application."""
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📄 EcoOpen - PDF Data Extraction Tool</h1>
        <p>Extract data and code availability information from scientific PDFs using AI</p>
        <div class="phi-model-badge" style="margin-top: 1rem;">🤖 Optimized for Phi Models</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Check system status
    status = render_system_status()
    
    if not status['ecoopen_available']:
        st.error("❌ EcoOpen backend not available. Please check the system status in the sidebar.")
        st.info("💡 Make sure the EcoOpenPy module is installed and in the correct path.")
        return
    
    if not status['llm_available']:
        st.error("❌ LLM dependencies not available. Please install requirements.")
        st.code("pip install -r requirements.txt", language="bash")
        return
    
    # Main interface
    tab1, tab2, tab3 = st.tabs(["📁 Batch Processing", "📄 Single File", "ℹ️ About"])
    
    with tab1:
        st.header("📁 Batch PDF Processing")
        
        # File upload
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type="pdf",
            accept_multiple_files=True,
            help="Upload multiple PDF files for batch processing"
        )
        
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} PDF files uploaded")
            
            # Save uploaded files to temporary directory
            temp_upload_dir = tempfile.mkdtemp(prefix="ecoopen_upload_")
            pdf_paths = []
            
            for uploaded_file in uploaded_files:
                file_path = Path(temp_upload_dir) / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                pdf_paths.append(str(file_path))
            
            # Format selection
            selected_formats = render_format_selector()
            
            # Processing options
            options = render_processing_options()
            
            # Process button
            if st.button("🚀 Start Processing", type="primary"):
                with st.spinner("Processing PDFs..."):
                    results, temp_dir = process_files(pdf_paths, options, selected_formats)
                    
                    if results:
                        render_results(results, temp_dir)
    
    with tab2:
        st.header("📄 Single PDF Processing")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type="pdf",
            help="Upload a single PDF file for processing"
        )
        
        if uploaded_file:
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(uploaded_file.getvalue())
            temp_file.close()
            
            # Format selection
            selected_formats = render_format_selector()
            
            # Processing options
            options = render_processing_options()
            
            # Process button
            if st.button("🚀 Process File", type="primary"):
                with st.spinner("Processing PDF..."):
                    results, temp_dir = process_files([temp_file.name], options, selected_formats)
                    
                    if results:
                        render_results(results, temp_dir)
    
    with tab3:
        st.header("ℹ️ About EcoOpen")
        
        st.markdown("""
        ### 🎯 What is EcoOpen?
        
        EcoOpen is an AI-powered tool for extracting data and code availability information from scientific PDFs. 
        It uses Large Language Models (LLMs) to intelligently identify and extract relevant information, making it 
        much more accurate than simple keyword-based approaches.
        
        ### 🤖 Phi Model Optimization
        
        This version is optimized specifically for **phi models**:
        - **phi4**: Excellent quality, slower processing (requires 12GB+ VRAM)
        - **phi3:mini**: Very good quality, faster processing (requires 4GB+ VRAM)
        - **Auto-detection**: Automatically selects the best phi model for your hardware
        
        ### 🚀 Key Features
        
        - **Smart AI Extraction**: Uses phi models for context-aware extraction
        - **DOI Integration**: Automatically fetches metadata from OpenAlex
        - **Data Downloads**: Finds and downloads data files referenced in papers
        - **Format Filtering**: Select specific data formats you're interested in
        - **Batch Processing**: Process hundreds of PDFs automatically
        - **User-Friendly**: Simple web interface, no command-line required
        
        ### 📊 Output Information
        
        For each PDF, EcoOpen extracts:
        - Paper metadata (title, authors, journal, year)
        - Data availability statements
        - Code availability statements  
        - Repository URLs and data links
        - Downloaded data files (optional)
        
        ### 🔧 Technical Requirements
        
        - **Ollama**: Local LLM server for AI processing
        - **Phi Models**: phi4 (preferred) or phi3:mini (fallback)
        - **Python 3.8+**: Core runtime environment
        - **4GB+ RAM**: For processing large PDFs
        - **GPU (optional)**: Faster processing with CUDA support
        
        ### 📈 Performance
        
        - **Speed**: ~10-15 seconds per PDF (with phi models on GPU)
        - **Accuracy**: 95%+ for data availability detection
        - **Throughput**: ~240 PDFs per hour
        - **Scalability**: Handles collections of 1000+ PDFs
        
        ### 🚀 Quick Setup
        
        1. Install Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`
        2. Install phi model: `ollama pull phi4` or `ollama pull phi3:mini`
        3. Start Ollama: `ollama serve`
        4. Launch this GUI and start processing!
        
        ### 🤝 Getting Help
        
        - Check system status in the sidebar
        - Enable debug mode for detailed logging
        - Review the original README for troubleshooting
        - Submit issues on the project repository
        
        ### 👨‍💻 Author
        
        **Domagoj K. Hackenberger**  
        Licensed under MIT License
        """)
        
        # System information
        st.subheader("🖥️ System Information")
        
        if status['gpu_available']:
            try:
                gpu_memory = get_gpu_memory()
                st.info(f"🎮 GPU Memory: {gpu_memory:.1f} GB")
                if gpu_memory >= 12.0:
                    st.success("✅ Sufficient VRAM for phi4 (excellent quality)")
                elif gpu_memory >= 4.5:
                    st.info("ℹ️ Sufficient VRAM for phi3:mini (very good quality)")
                else:
                    st.warning("⚠️ Limited VRAM - may run slowly on CPU")
            except:
                st.info("🎮 GPU detected but memory unknown")
        else:
            st.info("💻 Running in CPU mode")
        
        # Model recommendations
        st.subheader("🤖 Model Recommendations")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **phi4** 🏆
            - Size: 10GB
            - Quality: Excellent
            - Speed: Slower
            - Requires: 12GB+ VRAM
            """)
        
        with col2:
            st.markdown("""
            **phi3:mini** ⚡
            - Size: 3.8GB  
            - Quality: Very Good
            - Speed: Fast
            - Requires: 4GB+ VRAM
            """)
        
        # Performance check
        if st.button("🔍 Check Performance"):
            with st.spinner("Checking Ollama performance..."):
                perf_info = check_ollama_performance()
                
                if 'error' in perf_info:
                    st.error(f"❌ {perf_info['error']}")
                else:
                    st.success("✅ Performance check complete!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Model", perf_info['model_name'])
                        st.metric("Size", f"{perf_info['size_gb']} GB")
                    
                    with col2:
                        st.metric("CPU Usage", f"{perf_info['cpu_percent']}%")
                        st.metric("GPU Usage", f"{perf_info['gpu_percent']}%")
                    
                    if perf_info['recommendations']:
                        st.subheader("🚀 Recommendations")
                        for rec in perf_info['recommendations']:
                            st.info(rec)

if __name__ == "__main__":
    main()
