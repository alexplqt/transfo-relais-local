"""
Traitement et transformation des données
"""
import pandas as pd
import datetime
from .config import Config

class DataProcessor:
    """Classe pour le traitement des données"""
    
    def __init__(self):
        self.config = Config()
    
    def clean_dataframe(self, df):
        """
        Nettoie et transforme le DataFrame extrait du PDF
        
        Args:
            df (pd.DataFrame): DataFrame brut extrait du PDF
            
        Returns:
            pd.DataFrame: DataFrame nettoyé
        """
        # Vérification des colonnes nécessaires
        missing_columns = [col for col in self.config.PDF_COLUMNS if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Colonnes manquantes dans le PDF: {missing_columns}")
        
        # Retirer les lignes sans référence produit
        df_clean = df[~df['REF.'].isna()].copy()
        
        # Conserver uniquement les colonnes intéressantes
        df_clean = df_clean[self.config.PDF_COLUMNS]
        
        # Conversion des types de données
        df_clean = self._convert_data_types(df_clean)
        
        # Recalcul de la quantité
        df_clean = self._recalculate_quantity(df_clean)
        
        return df_clean
    
    def _convert_data_types(self, df):
        """Convertit les types de données des colonnes"""
        # Colonnes float
        for col in self.config.FLOAT_COLUMNS:
            df[col] = (
                df[col]
                .astype('string')
                .str.replace(',', '.')
                .astype('float64')
            )
        
        # Traitement spécifique pour la quantité
        df['QTE'] = (
            df['QTE']
            .astype('string')
            .str.replace('K', '')
            .str.replace('G virgule', '')
            .str.replace(',', '.')
            .astype('float64')
        )
        
        # Traitement de la référence
        df['REF.'] = df['REF.'].astype('string').str.replace('.0', '')
        
        return df
    
    def _recalculate_quantity(self, df):
        """Recalcule la quantité si nécessaire"""
        df['QTE 2'] = df['Montant HT'] / df['PU Net']
        df.loc[df['QTE'] != df['QTE 2'], 'QTE'] = df['QTE 2']
        return df.drop('QTE 2', axis=1)
    
    def merge_with_articles(self, df, articles_csv):
        """
        Fusionne les données avec le fichier des articles
        
        Args:
            df (pd.DataFrame): DataFrame des commandes
            articles_csv: Fichier CSV des articles (file object ou path)
            
        Returns:
            tuple: (df_merged, df_unlinked) - Données fusionnées et articles non liés
        """
        # Import du fichier articles
        art = pd.read_csv(articles_csv)
        
        # Nettoyage des articles
        art.loc[art['Article/ID'].isna(),'Article/ID'] = art['ID Externe']
        art = art[~art['Article/ID'].isna()]
        art = art[~art['Fournisseurs/Référence Fournisseur'].isna()]
        art = art.drop_duplicates(subset='Fournisseurs/Référence Fournisseur', keep='first')
        
        # Colonnes à conserver pour le merge
        art_columns = [
            'Article/ID', 'Fournisseurs/Référence Fournisseur',
            'Fournisseurs/Unité de mesure/Nom affiché', 'Taxes fournisseur/ID'
        ]
        
        # Merge avec les articles
        df_merged = df.merge(
            art[art_columns],
            how='left',
            left_on='REF.',
            right_on='Fournisseurs/Référence Fournisseur',
        )
        
        # Articles non liés
        df_unlinked = df_merged[df_merged['Article/ID'].isna()]
        df_merged = df_merged[~df_merged['Article/ID'].isna()]
        
        return df_merged, df_unlinked
    
    def prepare_import_file(self, df, ref_commande, id_fourni):
        """
        Prépare le fichier pour l'import
        
        Args:
            df (pd.DataFrame): DataFrame des commandes fusionnées
            ref_commande (str): Référence de commande
            id_fourni (str): ID du fournisseur
            
        Returns:
            pd.DataFrame: DataFrame formaté pour l'import
        """
        df_import = pd.DataFrame(columns=self.config.EXPORT_COLUMNS, index=df.index)
        
        # Alimentation des colonnes
        df_import['Lignes de la commande/Description'] = "[" + df['REF.'] + "] " + df['DESIGNATION']
        df_import['Lignes de la commande/Article/ID'] = df['Article/ID']
        df_import["Lignes de la commande/Unité de mesure d'article"] = df["Fournisseurs/Unité de mesure/Nom affiché"]
        df_import['Lignes de la commande/Quantité'] = df['QTE']
        df_import['Lignes de la commande/Prix unitaire'] = df["PU Net"]
        df_import['Lignes de la commande/Taxes/ID'] = df['Taxes fournisseur/ID']
        df_import["Lignes de la commande/Date prévue"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Colonnes avec seulement la première ligne renseignée
        df_import.loc[df_import.index[0], 'Référence commande'] = ref_commande
        df_import.loc[df_import.index[0], 'Fournisseur/ID'] = id_fourni
        
        return df_import