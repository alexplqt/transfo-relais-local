"""
Traitement des fichiers PDF avec Camelot
"""
import fitz  # PyMuPDF
import pandas as pd
import camelot
from .config import Config

class PDFProcessor:
    """Classe pour le traitement des fichiers PDF"""
    
    def __init__(self):
        self.config = Config()
    
    def extract_tables_from_pdf(self, pdf_path):
        """
        Extrait le DEUXIÈME tableau de chaque page du PDF
        """
        # Extraction de tous les tableaux avec Camelot
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
        
        # Liste pour stocker les deuxièmes tableaux
        df_list = []
        
        # Récupérer le nombre de pages
        pdf_document = fitz.open(pdf_path)
        num_pages = pdf_document.page_count
        pdf_document.close()
        
        # Pour chaque page, prendre le 2ème tableau
        for page_num in range(1, num_pages + 1):
            # Filtrer les tableaux de cette page
            page_tables = [table for table in tables if table.page == page_num]
            
            # Si la page a au moins 2 tableaux, prendre le 2ème
            if len(page_tables) >= 2:
                df_list.append(page_tables[1].df)
        
        if not df_list:
            raise ValueError("Aucun deuxième tableau trouvé dans le PDF")
        
        # Concaténer tous les DataFrames
        return pd.concat(df_list, ignore_index=True)