"""
Export des fichiers
"""
import pandas as pd
from io import BytesIO
from .config import Config

class FileExporter:
    """Classe pour l'export des fichiers"""
    
    def __init__(self):
        self.config = Config()
    
    def export_to_excel(self, df_processed, df_unlinked_rl, df_unlinked_od):
        """
        Exporte les données vers un fichier Excel en mémoire avec 3 onglets
        
        Args:
            df_processed (pd.DataFrame): Commandes traitées
            df_unlinked_rl (pd.DataFrame): Articles non liés RL
            df_unlinked_od (pd.DataFrame): Articles non liés ODOO
            
        Returns:
            BytesIO: Buffer contenant le fichier Excel
        """
        excel_buffer = BytesIO()
        
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_processed.to_excel(writer, sheet_name='commandes traitée', index=False)
            df_unlinked_rl.to_excel(writer, sheet_name='articles non liés (RL)', index=False)
            df_unlinked_od.to_excel(writer, sheet_name='articles non liés (ODOO)', index=False)
        
        excel_buffer.seek(0)
        return excel_buffer
    
    def export_to_csv(self, df_import):
        """
        Exporte les données vers un fichier CSV en mémoire
        
        Args:
            df_import (pd.DataFrame): Données à importer
            
        Returns:
            BytesIO: Buffer contenant le fichier CSV
        """
        csv_buffer = BytesIO()
        df_import.to_csv(csv_buffer, index=False, encoding=self.config.ENCODING)
        csv_buffer.seek(0)
        return csv_buffer