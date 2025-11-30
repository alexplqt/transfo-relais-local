"""
Traitement des fichiers PDF avec Tabula
"""
import fitz  # PyMuPDF
import pandas as pd
import tabula as tb
from .config import Config

class PDFProcessor:
    """Classe pour le traitement des fichiers PDF"""
    
    def __init__(self):
        self.config = Config()
    
    def extract_tables_from_pdf(self, pdf_path):
        """
        Extrait les tableaux d'un fichier PDF
        """
        # Ouverture du PDF pour connaître le nombre de pages
        pdf_document = fitz.open(pdf_path)
        numPages = pdf_document.page_count
        pdf_document.close()
        
        # Liste pour stocker les DataFrames des deuxièmes tableaux
        df_list = []
        
        # Extraction des tableaux avec tabula
        for page_num in range(numPages):
            # Extraire les tableaux pour chaque page
            tables = tb.read_pdf(pdf_path, pages=page_num + 1, multiple_tables=True, encoding='ISO-8859-1')
            
            # Vérifier si la page contient au moins deux tableaux
            if len(tables) >= 2:
                # Ajouter le deuxième tableau de la page à la liste
                df_list.append(pd.DataFrame(tables[1]))
        
        if not df_list:
            raise ValueError("Aucun deuxième tableau trouvé dans le PDF")
        
        # Concaténer tous les DataFrames de la liste en un seul DataFrame
        return pd.concat(df_list, ignore_index=True)