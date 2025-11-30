"""
Traitement des fichiers PDF avec Camelot (sans Java)
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
        Extrait les tableaux d'un fichier PDF avec Camelot
        """
        try:
            # Afficher un message de progression
            st.info("🔍 Extraction des tableaux en cours...")
            
            # Extraction des tableaux avec Camelot
            # 'lattice' pour les tableaux avec bordures
            # 'stream' pour les tableaux sans bordures
            tables = camelot.read_pdf(
                pdf_path, 
                pages='all', 
                flavor='lattice',
                suppress_stdout=False
            )
            
            if not tables:
                st.error("❌ Aucun tableau détecté dans le PDF")
                raise ValueError("Aucun tableau trouvé dans le PDF")
            
            # Récupérer le nombre de pages avec PyMuPDF
            pdf_document = fitz.open(pdf_path)
            num_pages = pdf_document.page_count
            pdf_document.close()
            
            st.success(f"📊 {len(tables)} tableaux détectés sur {num_pages} pages")
            
            # Afficher un rapport détaillé
            for i, table in enumerate(tables):
                st.write(f"📋 Tableau {i+1} (page {table.page}) : {table.shape[1]} colonnes × {table.shape[0]} lignes")
            
            # Liste pour stocker les deuxièmes tableaux de chaque page
            df_list = []
            pages_avec_tableaux = []
            
            # Stratégie d'extraction : chercher les 2èmes tableaux par page
            for page_num in range(1, num_pages + 1):
                page_tables = [table for table in tables if table.page == page_num]
                
                if len(page_tables) >= 2:
                    # Prendre le deuxième tableau de la page
                    second_table = page_tables[1]
                    df_list.append(second_table.df)
                    pages_avec_tableaux.append(page_num)
                    st.success(f"✅ Page {page_num}: 2ème tableau extrait ({second_table.shape[1]}×{second_table.shape[0]})")
                elif len(page_tables) == 1:
                    st.warning(f"⚠️ Page {page_num}: 1 seul tableau trouvé")
                else:
                    st.warning(f"ℹ️ Page {page_num}: aucun tableau détecté")
            
            # Si pas assez de deuxièmes tableaux, compléter avec les premiers
            if len(df_list) < num_pages / 2:  # Moins de la moitié des pages ont un 2ème tableau
                st.info("🔄 Complétion avec les premiers tableaux...")
                for page_num in range(1, num_pages + 1):
                    if page_num not in pages_avec_tableaux:  # Page pas encore traitée
                        page_tables = [table for table in tables if table.page == page_num]
                        if page_tables:
                            first_table = page_tables[0]
                            df_list.append(first_table.df)
                            st.info(f"📄 Page {page_num}: 1er tableau utilisé ({first_table.shape[1]}×{first_table.shape[0]})")
            
            if not df_list:
                st.error("❌ Aucun tableau exploitable trouvé")
                raise ValueError("Aucun tableau exploitable trouvé dans le PDF")
            
            # Concaténer tous les DataFrames
            final_df = pd.concat(df_list, ignore_index=True)
            
            # Nettoyer les noms de colonnes (Camelot utilise la première ligne comme header)
            if not final_df.empty:
                # Prendre la première ligne comme nom de colonnes
                final_df.columns = final_df.iloc[0] if len(final_df) > 0 else final_df.columns
                # Supprimer la première ligne si elle était utilisée comme header
                final_df = final_df[1:] if len(final_df) > 1 else final_df
                # Réinitialiser l'index
                final_df = final_df.reset_index(drop=True)
            
            st.success(f"🎉 Extraction terminée : {len(final_df)} lignes, {len(final_df.columns)} colonnes")
            return final_df
            
        except Exception as e:
            st.error(f"❌ Erreur lors de l'extraction avec Camelot: {str(e)}")
            raise