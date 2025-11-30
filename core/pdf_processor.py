"""
Traitement des fichiers PDF
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
        
        Args:
            pdf_path (str): Chemin vers le fichier PDF
            
        Returns:
            pd.DataFrame: DataFrame contenant les données extraites
        """
        # Ouverture du PDF pour vérification
        pdf_document = fitz.open(pdf_path)
        num_pages = pdf_document.page_count
        pdf_document.close()
        
        # Liste pour stocker les DataFrames des deuxièmes tableaux
        df_list = []
        
        # Extraction des tableaux avec tabula
        for page_num in range(num_pages):
            tables = tb.read_pdf(
                pdf_path, 
                pages=page_num + 1, 
                multiple_tables=True, 
                encoding=self.config.ENCODING
            )
            
            # Vérifier si la page contient au moins deux tableaux
            if len(tables) >= 2:
                df_list.append(pd.DataFrame(tables[1]))
        
        if not df_list:
            raise ValueError("Aucun tableau trouvé dans le PDF")
        
        # Concaténer tous les DataFrames
        return pd.concat(df_list, ignore_index=True)