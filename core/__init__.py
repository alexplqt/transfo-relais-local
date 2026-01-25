"""
Package core - Fonctionnalités principales de traitement PDF/CSV et connexion Odoo
"""
from .config import Config
from .pdf_processor import PDFProcessor
from .data_processor import DataProcessor
from .file_exporter import FileExporter
from .odoo_connector import OdooConnector

__all__ = [
    'Config',
    'PDFProcessor', 
    'DataProcessor',
    'FileExporter',
    'OdooConnector'
]

# Version du package
__version__ = "2.0.0"