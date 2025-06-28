"""
EcoOpen LLM-powered Data Availability Extraction
Streamlit app for analyzing scientific papers for data and code availability
"""

import streamlit as st
import sys
import os
import tempfile
import json

# Add the EcoOpen package to path
sys.path.append('/home/domagoj/Dev/EcoOpen/EcoOpenPy')

try:
    from ecoopen import (
        LLM_AVAILABLE, 
        extract_all_information_from_pdf_llm, 
        extract_text_from_pdf, 
        extract_all_information,
        LLMDataExtractor
    )
except ImportError as e:
    st.error(f"Failed to import EcoOpen: {e}")
    st.stop()

# Streamlit app configuration
st.set_page_config(
    page_title="EcoOpen LLM Data Availability Analyzer", 
    page_icon="🔬",
    layout="wide"
)

st.title("🔬 EcoOpen LLM Data Availability Analyzer")
st.markdown("Analyze scientific papers for data and code availability using advanced LLM reasoning.")

# Sidebar for configuration
st.sidebar.header("Configuration")
extraction_method = st.sidebar.selectbox(
    "Extraction Method",
    ["llm", "keyword", "both"],
    index=0 if LLM_AVAILABLE else 1,
    help="Choose the extraction method: LLM (intelligent), keyword (traditional), or both for comparison"
)

if not LLM_AVAILABLE and extraction_method == "llm":
    st.sidebar.warning("LLM extraction not available. Install dependencies with: pip install -r requirements_llm.txt")
    extraction_method = "keyword"

st.sidebar.markdown("### About Methods")
st.sidebar.markdown("""
- **LLM**: Uses Phi4 model for intelligent reasoning about data availability
- **Keyword**: Traditional pattern matching approach
- **Both**: Run both methods for comparison
""")

# Status indicator
status_container = st.container()
with status_container:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("LLM Available", "✅ Yes" if LLM_AVAILABLE else "❌ No")
    with col2:
        st.metric("Selected Method", extraction_method.upper())
    with col3:
        if LLM_AVAILABLE:
            try:
                # Test LLM connection
                extractor = LLMDataExtractor()
                st.metric("LLM Status", "✅ Ready")
            except Exception as e:
                st.metric("LLM Status", "❌ Error")
                st.sidebar.error(f"LLM connection error: {e}")
        else:
            st.metric("LLM Status", "❌ Not Available")

# Main interface
st.markdown("---")

uploaded_file = st.file_uploader(
    "Upload a scientific paper (PDF)", 
    type="pdf",
    help="Upload a scientific paper in PDF format for analysis"
)

if uploaded_file is not None:
    try:
        # Initialize progress tracking
        progress_container = st.container()
        with progress_container:
            progress_bar = st.progress(0, text="Starting analysis...")
            status_text = st.empty()

        # Read PDF content
        pdf_content = uploaded_file.read()
        file_size = len(pdf_content) / (1024 * 1024)  # Size in MB
        
        progress_bar.progress(10, text="PDF loaded...")
        status_text.text(f"PDF loaded ({file_size:.2f} MB)")

        # Run extraction based on selected method
        if extraction_method == "llm" and LLM_AVAILABLE:
            status_text.text("Running LLM analysis...")
            progress_bar.progress(30, text="LLM analysis in progress...")
            
            result = extract_all_information_from_pdf_llm(pdf_content, method="llm")
            progress_bar.progress(100, text="LLM analysis complete!")
            
        elif extraction_method == "keyword":
            status_text.text("Running keyword analysis...")
            progress_bar.progress(30, text="Extracting text...")
            
            text = extract_text_from_pdf(pdf_content)
            progress_bar.progress(60, text="Analyzing text...")
            
            if text:
                result = extract_all_information(text, method="keyword")
                progress_bar.progress(100, text="Keyword analysis complete!")
            else:
                result = {"error": "Failed to extract text from PDF"}
                
        elif extraction_method == "both" and LLM_AVAILABLE:
            status_text.text("Running both analyses...")
            progress_bar.progress(20, text="Starting dual analysis...")
            
            result = extract_all_information_from_pdf_llm(pdf_content, method="both")
            progress_bar.progress(100, text="Dual analysis complete!")
            
        else:
            result = {"error": "Invalid method or LLM not available"}

        status_text.text("Analysis complete!")
        
        # Clear progress indicators
        progress_container.empty()
        
        # Display results
        st.markdown("## 📊 Analysis Results")
        
        if "error" in result:
            st.error(f"Analysis failed: {result['error']}")
        else:
            # Create tabs for different views
            if extraction_method == "both":
                tab1, tab2, tab3, tab4 = st.tabs(["📋 Summary", "🤖 LLM Results", "🔍 Keyword Results", "📊 Comparison"])
                
                with tab1:
                    display_comparison_summary(result)
                    
                with tab2:
                    if "llm_results" in result:
                        display_llm_results(result["llm_results"])
                    else:
                        st.error("LLM results not available")
                        
                with tab3:
                    if "keyword_results" in result:
                        display_keyword_results(result["keyword_results"])
                    else:
                        st.error("Keyword results not available")
                        
                with tab4:
                    display_detailed_comparison(result)
                    
            elif extraction_method == "llm":
                tab1, tab2 = st.tabs(["📋 Summary", "🤖 Detailed Results"])
                
                with tab1:
                    display_llm_summary(result)
                    
                with tab2:
                    display_llm_results(result)
                    
            else:  # keyword method
                tab1, tab2 = st.tabs(["📋 Summary", "🔍 Detailed Results"])
                
                with tab1:
                    display_keyword_summary(result)
                    
                with tab2:
                    display_keyword_results(result)

        # Download results
        st.markdown("---")
        st.markdown("### 💾 Download Results")
        
        result_json = json.dumps(result, indent=2, default=str)
        st.download_button(
            label="Download JSON Results",
            data=result_json,
            file_name=f"ecoopen_analysis_{uploaded_file.name}.json",
            mime="application/json"
        )

    except Exception as e:
        st.error(f"An error occurred during analysis: {str(e)}")
        st.exception(e)

else:
    st.info("👆 Please upload a PDF file to begin analysis.")
    
    # Show example of what the tool can detect
    st.markdown("### 🎯 What this tool detects:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Data Availability:**
        - Open data repositories (Zenodo, Dryad, etc.)
        - Data access conditions
        - Dataset descriptions and links
        - Supplementary material references
        """)
        
    with col2:
        st.markdown("""
        **Code Availability:**
        - GitHub repositories
        - Software and script availability
        - Analysis code descriptions
        - Computational methods
        """)

# Helper functions for displaying results
def display_llm_summary(result):
    """Display summary for LLM results."""
    if not result.get("success"):
        st.error("LLM analysis failed")
        return
    
    availability_info = result.get("availability_info", {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        data_avail = availability_info.get("data_availability", {})
        st.metric(
            "Data Available", 
            "✅ Yes" if data_avail.get("found") else "❌ No",
            delta=data_avail.get("confidence", "unknown")
        )
        
    with col2:
        code_avail = availability_info.get("code_availability", {})
        st.metric(
            "Code Available", 
            "✅ Yes" if code_avail.get("found") else "❌ No",
            delta=code_avail.get("confidence", "unknown")
        )
        
    with col3:
        overall = availability_info.get("overall_assessment", {})
        st.metric(
            "Overall Confidence",
            overall.get("confidence", "unknown").upper()
        )

def display_keyword_summary(result):
    """Display summary for keyword results."""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        data_statements = result.get("data_statements", "")
        st.metric(
            "Data Statements", 
            "✅ Found" if len(data_statements.strip()) > 0 else "❌ None",
            delta=f"{len(data_statements)} chars"
        )
        
    with col2:
        code_statements = result.get("code_statements", "")
        st.metric(
            "Code Statements", 
            "✅ Found" if len(code_statements.strip()) > 0 else "❌ None",
            delta=f"{len(code_statements)} chars"
        )
        
    with col3:
        all_urls = result.get("all_urls", [])
        st.metric(
            "URLs Found",
            len(all_urls),
            delta="total links"
        )

def display_comparison_summary(result):
    """Display comparison summary."""
    comparison = result.get("comparison", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🤖 LLM Analysis")
        llm_success = comparison.get("llm_success", False)
        llm_found_data = comparison.get("llm_found_data", False)
        
        st.metric("Status", "✅ Success" if llm_success else "❌ Failed")
        st.metric("Data Found", "✅ Yes" if llm_found_data else "❌ No")
        
    with col2:
        st.subheader("🔍 Keyword Analysis") 
        keyword_success = comparison.get("keyword_success", False)
        keyword_found_data = comparison.get("keyword_found_data", False)
        
        st.metric("Status", "✅ Success" if keyword_success else "❌ Failed")
        st.metric("Data Found", "✅ Yes" if keyword_found_data else "❌ No")

def display_llm_results(result):
    """Display detailed LLM results."""
    if not result.get("success"):
        st.error("LLM analysis failed")
        if "error" in result:
            st.error(f"Error: {result['error']}")
        return
    
    availability_info = result.get("availability_info", {})
    
    # Data availability
    st.subheader("📊 Data Availability")
    data_avail = availability_info.get("data_availability", {})
    
    if data_avail.get("found"):
        st.success(f"Data availability detected with {data_avail.get('confidence', 'unknown')} confidence")
        st.write(f"**Access Type:** {data_avail.get('access_type', 'unknown')}")
        
        if data_avail.get("statements"):
            st.write("**Statements found:**")
            for i, stmt in enumerate(data_avail["statements"], 1):
                st.write(f"{i}. {stmt}")
                
        if data_avail.get("repositories"):
            st.write(f"**Repositories:** {', '.join(data_avail['repositories'])}")
            
        if data_avail.get("urls"):
            st.write("**URLs:**")
            for url in data_avail["urls"]:
                st.write(f"- {url}")
    else:
        st.warning("No data availability information detected")
    
    # Code availability
    st.subheader("💻 Code Availability")
    code_avail = availability_info.get("code_availability", {})
    
    if code_avail.get("found"):
        st.success(f"Code availability detected with {code_avail.get('confidence', 'unknown')} confidence")
        st.write(f"**Access Type:** {code_avail.get('access_type', 'unknown')}")
        
        if code_avail.get("statements"):
            st.write("**Statements found:**")
            for i, stmt in enumerate(code_avail["statements"], 1):
                st.write(f"{i}. {stmt}")
    else:
        st.warning("No code availability information detected")
    
    # Overall assessment
    overall = availability_info.get("overall_assessment", {})
    if overall:
        st.subheader("📋 Overall Assessment")
        st.write(f"**Summary:** {overall.get('summary', 'No summary available')}")

def display_keyword_results(result):
    """Display detailed keyword results."""
    # Data statements
    st.subheader("📊 Data Statements")
    data_statements = result.get("data_statements", "")
    if data_statements.strip():
        st.text_area("Data-related text found:", data_statements, height=100)
    else:
        st.warning("No data statements detected")
    
    # Code statements  
    st.subheader("💻 Code Statements")
    code_statements = result.get("code_statements", "")
    if code_statements.strip():
        st.text_area("Code-related text found:", code_statements, height=100)
    else:
        st.warning("No code statements detected")
    
    # URLs and other info
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔗 URLs Found")
        all_urls = result.get("all_urls", [])
        if all_urls:
            for url in all_urls:
                st.write(f"- {url}")
        else:
            st.write("No URLs detected")
            
    with col2:
        st.subheader("📝 DOIs Found")
        dois = result.get("dois", [])
        if dois:
            for doi in dois:
                st.write(f"- {doi}")
        else:
            st.write("No DOIs detected")

def display_detailed_comparison(result):
    """Display detailed comparison between methods."""
    st.subheader("📊 Method Comparison")
    
    comparison = result.get("comparison", {})
    
    # Create comparison table
    comparison_data = {
        "Metric": ["Analysis Success", "Data Found", "Method Type"],
        "LLM Results": [
            "✅ Success" if comparison.get("llm_success") else "❌ Failed",
            "✅ Yes" if comparison.get("llm_found_data") else "❌ No", 
            "Intelligent reasoning"
        ],
        "Keyword Results": [
            "✅ Success" if comparison.get("keyword_success") else "❌ Failed",
            "✅ Yes" if comparison.get("keyword_found_data") else "❌ No",
            "Pattern matching"
        ]
    }
    
    st.table(comparison_data)
    
    # Agreement analysis
    llm_found = comparison.get("llm_found_data", False)
    keyword_found = comparison.get("keyword_found_data", False)
    
    if llm_found and keyword_found:
        st.success("🎯 **Agreement:** Both methods detected data availability")
    elif llm_found and not keyword_found:
        st.info("🤖 **LLM detected more:** LLM found data availability that keywords missed")
    elif not llm_found and keyword_found:
        st.info("🔍 **Keywords detected more:** Keywords found patterns that LLM missed")
    else:
        st.warning("❌ **No detection:** Neither method found data availability information")

# Footer
st.markdown("---")
st.markdown("**EcoOpen LLM Analyzer** - Powered by Phi4, LangChain, and ChromaDB | Enhanced data availability detection for scientific literature")
