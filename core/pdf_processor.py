"""
Traitement des fichiers PDF avec Camelot
"""
import fitz  # PyMuPDF
import pandas as pd
import camelot
import streamlit as st
from .config import Config

class PDFProcessor:
    """Classe pour le traitement des fichiers PDF"""
    
    def __init__(self):
        self.config = Config()
    
    def extract_tables_from_pdf(self, pdf_path):
        """
        Extrait les tableaux qui ont 12 colonnes (structure des articles)
        """
        # Extraction de tous les tableaux avec Camelot
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
        
        # Liste pour stocker les tableaux avec 12 colonnes
        df_list = []
        
        # Récupérer le nombre de pages
        pdf_document = fitz.open(pdf_path)
        num_pages = pdf_document.page_count
        pdf_document.close()
        
        st.info(f"📄 PDF de {num_pages} pages - {len(tables)} tableaux détectés")
        
        # Pour chaque tableau, vérifier s'il a 12 colonnes
        for i, table in enumerate(tables):
            nb_colonnes = table.shape[1]  # Nombre de colonnes
            st.write(f"Tableau {i+1} (page {table.page}) : {nb_colonnes} colonnes")
            
            if nb_colonnes == 12:
                df_list.append(table.df)
                st.success(f"✅ Tableau {i+1} sélectionné (12 colonnes)")
            else:
                st.warning(f"❌ Tableau {i+1} ignoré ({nb_colonnes} colonnes)")
        
        if not df_list:
            raise ValueError(f"Aucun tableau avec 12 colonnes trouvé. Tableaux détectés: {[table.shape[1] for table in tables]}")
        
        # Concaténer tous les DataFrames
        final_df = pd.concat(df_list, ignore_index=True)
        st.success(f"🎯 {len(final_df)} lignes extraites de {len(df_list)} tableaux")
        
        return final_df