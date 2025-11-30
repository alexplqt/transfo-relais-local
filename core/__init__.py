"""
Package core - Fonctionnalités principales de traitement PDF/CSV
"""

from .config import Config
from .pdf_processor import PDFProcessor
from .data_processor import DataProcessor
from .file_exporter import FileExporter

__all__ = [
    'Config',
    'PDFProcessor', 
    'DataProcessor',
    'FileExporter'
]

# Version du package
__version__ = "1.0.0"