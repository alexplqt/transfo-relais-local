"""
Connexion et récupération des données depuis Odoo
"""
import odoorpc
import pandas as pd
import streamlit as st
from typing import Optional, Tuple


class OdooConnector:
    """Classe pour gérer la connexion et les requêtes Odoo"""
    
    def __init__(self):
        self.odoo = None
        self.connected = False
    
    def connect(self, url: str, port: int, database: str, username: str, password: str) -> bool:
        """
        Établit la connexion à Odoo
        
        Args:
            url: URL du serveur Odoo
            port: Port (généralement 443 pour SSL)
            database: Nom de la base de données
            username: Nom d'utilisateur
            password: Mot de passe
            
        Returns:
            bool: True si connexion réussie, False sinon
        """
        try:
            self.odoo = odoorpc.ODOO(url, port=port, protocol='jsonrpc+ssl')
            self.odoo.login(database, username, password)
            self.connected = True
            return True
        except Exception as e:
            st.error(f"Erreur de connexion à Odoo : {str(e)}")
            self.connected = False
            return False
    
    def get_product_variants(self) -> Optional[pd.DataFrame]:
        """
        Récupère les variantes d'articles (product.product) depuis Odoo
        
        Returns:
            pd.DataFrame: DataFrame avec les données des variantes ou None si erreur
        """
        if not self.connected:
            st.error("Non connecté à Odoo")
            return None
        
        try:
            # Récupération des variantes d'articles (product.product)
            Product = self.odoo.env['product.product']
            
            articles_data = Product.search_read(
                [('active', '=', True)],  # Uniquement les articles actifs
                [
                    'id',
                    'name',
                    'product_tmpl_id',
                ]
            )
            
            df_articles = pd.DataFrame(articles_data)
            
            if df_articles.empty:
                st.warning("Aucun article trouvé dans Odoo")
                return None
            
            # Récupération des ID externes
            df_articles = self._get_external_ids(df_articles)
            
            # Récupération des informations fournisseurs
            df_articles = self._get_supplier_info(df_articles)
            
            # Récupération des taxes
            df_articles = self._get_tax_info(df_articles)
            
            # Renommage des colonnes pour correspondre au format attendu
            df_articles = self._rename_columns(df_articles)
            
            return df_articles
            
        except Exception as e:
            st.error(f"Erreur lors de la récupération des articles : {str(e)}")
            return None
    
    def _get_external_ids(self, df_articles: pd.DataFrame) -> pd.DataFrame:
        """Récupère les ID externes des articles"""
        try:
            IrModelData = self.odoo.env['ir.model.data']
            external_ids_data = IrModelData.search_read(
                [('model', '=', 'product.product')],
                ['res_id', 'complete_name']
            )
            
            df_external_ids = pd.DataFrame(external_ids_data)
            if not df_external_ids.empty:
                df_external_ids.rename(columns={'complete_name': 'external_id'}, inplace=True)
                df_articles = df_articles.merge(
                    df_external_ids[['res_id', 'external_id']],
                    left_on='id',
                    right_on='res_id',
                    how='left'
                )
        except Exception as e:
            st.warning(f"Impossible de récupérer les ID externes : {str(e)}")
            df_articles['external_id'] = None
        
        return df_articles
    
    def _get_supplier_info(self, df_articles: pd.DataFrame) -> pd.DataFrame:
        """Récupère les informations fournisseurs"""
        try:
            # Extraire les template_id depuis product_tmpl_id
            df_articles['template_id'] = df_articles['product_tmpl_id'].apply(
                lambda x: x[0] if x else None
            )
            
            SupplierInfo = self.odoo.env['product.supplierinfo']
            fournisseurs_data = SupplierInfo.search_read(
                [],
                [
                    'product_tmpl_id',
                    'product_id',
                    'product_uom',
                ]
            )
            
            df_fournisseurs = pd.DataFrame(fournisseurs_data)
            
            if not df_fournisseurs.empty:
                # Traiter les champs relationnels
                df_fournisseurs['template_id'] = df_fournisseurs['product_tmpl_id'].apply(
                    lambda x: x[0] if x else None
                )
                df_fournisseurs['uom_id'] = df_fournisseurs['product_uom'].apply(
                    lambda x: x[0] if x else None
                )
                df_fournisseurs['uom_name'] = df_fournisseurs['product_uom'].apply(
                    lambda x: x[1] if x else None
                )
                
                # Merge avec les articles
                df_articles = df_articles.merge(
                    df_fournisseurs[['template_id', 'uom_name']],
                    on='template_id',
                    how='left'
                )
            else:
                df_articles['uom_name'] = None
                
        except Exception as e:
            st.warning(f"Impossible de récupérer les infos fournisseurs : {str(e)}")
            df_articles['uom_name'] = None
        
        return df_articles
    
    def _get_tax_info(self, df_articles: pd.DataFrame) -> pd.DataFrame:
        """Récupère les informations de taxes via product.template"""
        try:
            # Récupérer les taxes depuis product.template
            ProductTemplate = self.odoo.env['product.template']
            template_ids = df_articles['template_id'].dropna().unique().tolist()
            
            if template_ids:
                templates_data = ProductTemplate.search_read(
                    [('id', 'in', template_ids)],
                    ['id', 'supplier_taxes_id']
                )
                
                df_templates = pd.DataFrame(templates_data)
                df_templates['tax_id'] = df_templates['supplier_taxes_id'].apply(
                    lambda x: x[0] if x and len(x) > 0 else None
                )
                
                # Récupérer les ID externes des taxes
                IrModelData = self.odoo.env['ir.model.data']
                tax_ids = df_templates['tax_id'].dropna().unique().tolist()
                
                if tax_ids:
                    tax_external_ids = IrModelData.search_read(
                        [('model', '=', 'account.tax'), ('res_id', 'in', tax_ids)],
                        ['res_id', 'complete_name']
                    )
                    
                    df_tax_external = pd.DataFrame(tax_external_ids)
                    if not df_tax_external.empty:
                        df_tax_external.rename(columns={'complete_name': 'tax_external_id'}, inplace=True)
                        df_templates = df_templates.merge(
                            df_tax_external[['res_id', 'tax_external_id']],
                            left_on='tax_id',
                            right_on='res_id',
                            how='left'
                        )
                    else:
                        df_templates['tax_external_id'] = None
                else:
                    df_templates['tax_external_id'] = None
                
                # Merge avec les articles
                df_articles = df_articles.merge(
                    df_templates[['id', 'tax_external_id']],
                    left_on='template_id',
                    right_on='id',
                    how='left',
                    suffixes=('', '_template')
                )
            else:
                df_articles['tax_external_id'] = None
                
        except Exception as e:
            st.warning(f"Impossible de récupérer les taxes : {str(e)}")
            df_articles['tax_external_id'] = None
        
        return df_articles
    
    def _rename_columns(self, df_articles: pd.DataFrame) -> pd.DataFrame:
        """Renomme les colonnes pour correspondre au format attendu"""
        column_mapping = {
            'id': 'Article ID Odoo',  # ID interne Odoo (nouveau)
            'external_id': 'Article/ID',  # ID externe
            'name': 'Nom',
            'uom_name': 'Fournisseurs/Unité de mesure/Nom affiché',
            'tax_external_id': 'Taxes fournisseur/ID',
        }
        
        df_articles = df_articles.rename(columns=column_mapping)
        
        # Garder uniquement les colonnes nécessaires
        columns_to_keep = [
            'Article ID Odoo',
            'Article/ID',
            'Nom',
            'Fournisseurs/Unité de mesure/Nom affiché',
            'Taxes fournisseur/ID'
        ]
        
        # S'assurer que toutes les colonnes existent
        for col in columns_to_keep:
            if col not in df_articles.columns:
                df_articles[col] = None
        
        df_articles = df_articles[columns_to_keep]
        
        # DEBUG - Export temporaire
        df_articles.to_csv('debug_articles_odoo.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Articles exportés dans debug_articles_odoo.csv")

        return df_articles
    
    def disconnect(self):
        """Ferme la connexion Odoo"""
        self.odoo = None
        self.connected = False 