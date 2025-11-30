"""
Traitement des fichiers PDF
"""
import fitz  # PyMuPDF
import pandas as pd
import subprocess
import os
from .config import Config

class PDFProcessor:
    """Classe pour le traitement des fichiers PDF"""
    
    def __init__(self):
        self.config = Config()
    
    def extract_tables_from_pdf(self, pdf_path):
        """
        Extrait les tableaux d'un fichier PDF avec une méthode alternative
        """
        try:
            # Essayer d'abord avec tabula - IMPORT ICI !
            import tabula as tb
            return self._extract_with_tabula(pdf_path, tb)
        except Exception as e:
            # Fallback : méthode manuelle avec PyMuPDF
            st.error(f"Tabula a échoué, utilisation de la méthode de secours: {str(e)}")
            return self._extract_with_pymupdf(pdf_path)
    
    def _extract_with_tabula(self, pdf_path, tb):
        """Méthode avec tabula (si Java disponible)"""
        # Récupérer le nombre de pages
        pdf_document = fitz.open(pdf_path)
        num_pages = pdf_document.page_count
        pdf_document.close()
        
        df_list = []
        
        for page_num in range(num_pages):
            tables = tb.read_pdf(pdf_path, pages=page_num + 1, multiple_tables=True, encoding='ISO-8859-1')
            
            if len(tables) >= 2:
                df_list.append(pd.DataFrame(tables[1]))
        
        if not df_list:
            raise ValueError("Aucun tableau trouvé dans le PDF")
        
        return pd.concat(df_list, ignore_index=True)
    
    def _extract_with_pymupdf(self, pdf_path):
        """Méthode fallback avec PyMuPDF seulement"""
        # Pour l'instant, on lève une exception pour voir l'erreur
        raise Exception("Méthode de secours non implémentée - Tabula a échoué")