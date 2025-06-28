#!/bin/bash
"""
EcoOpen GUI Launcher
===================

This script launches the Streamlit GUI for EcoOpen.
Make sure you have installed the requirements and Ollama is running.

Usage:
    ./run_gui.sh

Or manually:
    streamlit run main.py
"""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit not found. Please install requirements:"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Check if Ollama is running
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama not found. Please install Ollama first:"
    echo "   curl -fsSL https://ollama.ai/install.sh | sh"
    echo ""
fi

# Check if Ollama service is running
if ! ollama list &> /dev/null; then
    echo "⚠️  Ollama service not running. Please start it:"
    echo "   ollama serve"
    echo ""
fi

echo "🚀 Starting EcoOpen GUI..."
echo "   Open your browser to: http://localhost:8501"
echo ""

# Launch Streamlit
cd "$(dirname "$0")"
streamlit run main.py --server.headless true --server.port 8501
