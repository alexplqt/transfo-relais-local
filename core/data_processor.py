# -*- coding: utf-8 -*-
"""
Traitement et transformation des données
"""
import pandas as pd
import datetime
import streamlit as st
import re
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
        # Retirer les lignes sans référence produit
        df_clean = df[~df['REF.'].isna()].copy()

        # Si les colonnes PU Brut et R.% ont fusionné, on les sépare
        if 'PU Brut R.%' in df_clean.columns:
            df_clean['PU Brut'] = df_clean['PU Brut R.%'].str[:4]
            df_clean['R.%'] = df_clean['PU Brut R.%'].str[4:]

        # Même problème pour DESIGNATION et Nature
        if 'DESIGNATION Nature' in df_clean.columns:
            # Liste des mots avec lequel on va split (on doit passer par là car ici la longueur des variables n'est pas fixe)
            mot_split = ['BIO', 'NATURE & PNROUGSR ELSE SAVONS (38)']
            pattern = '|'.join(map(re.escape, mot_split))
            df_clean[['DESIGNATION', 'Nature']] = df_clean['DESIGNATION Nature'].str.split(pattern, n=1, expand=True)
            df_clean['DESIGNATION'] = df_clean['DESIGNATION'].str.strip()
            df_clean['Nature'] = df_clean['Nature'].str.strip()
        
        # Vérification des colonnes nécessaires (après le traitement des colonnes fusionnées)
        missing_columns = [col for col in self.config.PDF_COLUMNS if col not in df_clean.columns]
        if missing_columns:
            raise ValueError(f"Colonnes manquantes dans le PDF: {missing_columns}")
        
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
                .replace('', '0')
                .astype('float64')
            )
        
        # Traitement spécifique pour la quantité
        df['QTE'] = (
            df['QTE']
            .astype('string')
            .str.replace('K', '')
            .str.replace('G virgule', '')
            .str.replace(',', '.')
            .replace('', '0')
            .astype('float64')
        )
        
        # Traitement de la référence
        df['REF.'] = df['REF.'].astype('string').str.replace('.0', '')

        # DEBUG - Export temporaire
        df.to_csv('debug_facture.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Facture exportée dans debug_facture.csv")
        
        return df
    
    def _recalculate_quantity(self, df):
        """Recalcule la quantité si nécessaire"""
        df['QTE 2'] = df['Montant HT'] / df['PU Net']
        df.loc[df['QTE'] != df['QTE 2'], 'QTE'] = df['QTE 2']
        return df.drop('QTE 2', axis=1)
    
    def merge_with_articles(self, df, articles_data, correspondance_excel):
        """
        Fusionne les données avec les articles et la correspondance
        
        Args:
            df (pd.DataFrame): DataFrame des commandes
            articles_data: DataFrame ou fichier CSV des articles
            correspondance_excel: Fichier Excel de correspondance (file object ou path)
            
        Returns:
            tuple: (df_merged, df_unlinked_rl, df_unlinked_od) - Données fusionnées et articles non liés
        """
        # Gestion des articles : soit un DataFrame (venant d'Odoo), soit un CSV
        if isinstance(articles_data, pd.DataFrame):
            art = articles_data.copy()
        else:
            art = pd.read_csv(articles_data)
        
        # Import du fichier de correspondance
        crpd = pd.read_excel(correspondance_excel)
        
        # Nettoyage des données articles
        # Pour les données venant d'Odoo, on utilise déjà l'ID externe
        if 'Article/ID' not in art.columns and 'ID Externe' in art.columns:
            art['Article/ID'] = art['ID Externe']
        elif 'Article/ID' not in art.columns:
            # Si aucune des deux colonnes n'existe, on essaie de la créer
            art['Article/ID'] = None
        
        # Remplir les valeurs manquantes d'Article/ID avec ID Externe si disponible
        if 'ID Externe' in art.columns:
            art.loc[art['Article/ID'].isna(), 'Article/ID'] = art['ID Externe']
        
        art = art[~art['Article/ID'].isna()]
        
        # Nettoyage de la correspondance
        crpd = crpd.drop_duplicates(subset='Référence', keep='first')
        crpd['Référence'] = crpd['Référence'].astype('string')
        
        st.info(f"📊 Fichier correspondance : {len(crpd)} références")
        st.info(f"📊 Articles disponibles : {len(art)} articles")
        
        # Premier merge avec la correspondance
        df_merged = df.merge(
            crpd[['Référence', 'Nom ODOO']],
            how='left',
            left_on='REF.',
            right_on='Référence',
        )
        
        # Deuxième merge avec les articles ODOO
        df_merged = df_merged.merge(
            art[['Article/ID', 'Nom', 'Fournisseurs/Unité de mesure/Nom affiché', 'Taxes fournisseur/ID']],
            how='left',
            left_on='Nom ODOO',
            right_on='Nom',
        )
        
        # Articles non liés
        art_non_liés_rl = df_merged[df_merged['Nom ODOO'].isna()]  # Non trouvés dans Correspondance
        art_non_liés_od = df_merged[(df_merged['Article/ID'].isna()) & (~df_merged['Nom ODOO'].isna())]  # Trouvés dans correspondance mais pas dans ODOO
        df_processed = df_merged[~df_merged['Article/ID'].isna()]  # Uniquement ceux complètement traités
        
        st.success(f"✅ Articles traités : {len(df_processed)}")
        if not art_non_liés_rl.empty:
            st.warning(f"⚠️ Articles non liés RL : {len(art_non_liés_rl)}")
        if not art_non_liés_od.empty:
            st.warning(f"⚠️ Articles non liés ODOO : {len(art_non_liés_od)}")
        
        return df_processed, art_non_liés_rl, art_non_liés_od
    
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