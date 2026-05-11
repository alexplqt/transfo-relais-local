"""
Connexion, lecture et ecriture des donnees Odoo.
"""
import datetime
from typing import Optional

import odoorpc
import pandas as pd
import streamlit as st


class OdooConnector:
    """Classe pour gerer la connexion et les requetes Odoo."""

    MARGIN_RATES = {
        "Taux de marque 15%": 17.6471,
        "Taux de marque 21%": 27.1941,
        "Taux de marque 21%-Consigne 0,07": 27.1941,
        "Taux de marque 21%-Consigne 0,15": 27.1941,
        "Taux de marque 25%": 34.1382,
        "Taux de marque 25%-Consigne 0,20": 34.1382,
        "Taux de marque 25%-Consigne 0,35": 34.1382,
        "Taux de marque 25%-Consigne 0,50": 34.1382,
        "Taux de marque 25%-Consigne 1€": 34.1382,
        "Taux de marque 25%-Consigne 2€": 34.1382,
        "Taux de marque 25%-Consigne 2€5": 34.1382,
        "Taux de marque 25%-Consigne 3€": 34.1382,
    }

    def __init__(self):
        self.odoo = None
        self.connected = False

    def connect(self, url: str, port: int, database: str, username: str, password: str) -> bool:
        """Etablit la connexion a Odoo."""
        try:
            self.odoo = odoorpc.ODOO(url, port=port, protocol='jsonrpc+ssl')
            self.odoo.login(database, username, password)
            self.connected = True
            return True
        except Exception as e:
            st.error(f"Erreur de connexion a Odoo : {str(e)}")
            self.connected = False
            return False

    def get_product_variants(self) -> Optional[pd.DataFrame]:
        """Recupere les variantes d'articles (product.product) depuis Odoo."""
        if not self.connected:
            st.error("Non connecte a Odoo")
            return None

        try:
            Product = self.odoo.env['product.product']
            articles_data = Product.search_read(
                [('active', '=', True)],
                ['id', 'name', 'product_tmpl_id', 'uom_po_id']
            )

            df_articles = pd.DataFrame(articles_data)
            if df_articles.empty:
                st.warning("Aucun article trouve dans Odoo")
                return None

            df_articles = self._get_external_ids(df_articles)
            df_articles = self._get_supplier_info(df_articles)
            df_articles = self._get_tax_info(df_articles)
            df_articles = self._rename_columns(df_articles)

            return df_articles

        except Exception as e:
            st.error(f"Erreur lors de la recuperation des articles : {str(e)}")
            return None

    def create_purchase_order(self, df_processed: pd.DataFrame, ref_commande: str, id_fourni: str) -> dict:
        """Cree une demande de prix Odoo depuis les lignes traitees."""
        if not self.connected:
            raise ValueError("Non connecte a Odoo")
        if df_processed.empty:
            raise ValueError("Aucune ligne traitee a envoyer a Odoo")

        partner_id, partner_name = self._resolve_supplier_partner(id_fourni)
        order_line_commands = [
            (0, 0, self._prepare_purchase_order_line(row))
            for _, row in df_processed.iterrows()
        ]

        PurchaseOrder = self.odoo.env['purchase.order']
        order_vals = {
            'partner_id': partner_id,
            'partner_ref': ref_commande,
            'order_line': order_line_commands,
        }
        order_id = PurchaseOrder.create(order_vals)
        order_data = PurchaseOrder.read([order_id], ['name'])[0]

        return {
            'id': order_id,
            'name': order_data.get('name', str(order_id)),
            'partner_id': partner_id,
            'partner_name': partner_name,
            'line_count': len(order_line_commands),
        }

    def build_price_update_preview(
        self,
        df_processed: pd.DataFrame,
        supplier_external_id: str,
        lower_bound: float,
        upper_bound: float,
    ) -> pd.DataFrame:
        """Prepare les lignes de mise a jour de prix depuis la facture traitee."""
        if not self.connected:
            raise ValueError("Non connecte a Odoo")
        if df_processed.empty:
            raise ValueError("Aucune ligne traitee")

        supplier_id, supplier_name = self._resolve_supplier_partner(supplier_external_id)
        product_ids = [
            self._coerce_int(value)
            for value in df_processed.get('Article ID Odoo', pd.Series(dtype='object')).dropna().unique().tolist()
        ]
        product_ids = [product_id for product_id in product_ids if product_id]
        if not product_ids:
            raise ValueError("Aucun ID article Odoo trouve dans les lignes traitees")

        article_details = self._get_price_update_article_details(product_ids, supplier_id)
        invoice_prices = df_processed[['Article ID Odoo', 'REF.', 'DESIGNATION', 'PU Net', 'R.%']].copy()
        invoice_prices['Article ID Odoo'] = invoice_prices['Article ID Odoo'].apply(self._coerce_int)
        invoice_prices = invoice_prices.dropna(subset=['Article ID Odoo'])
        invoice_prices = invoice_prices.drop_duplicates(subset='Article ID Odoo', keep='first')

        preview = invoice_prices.merge(
            article_details,
            how='left',
            left_on='Article ID Odoo',
            right_on='id',
        )
        preview['Fournisseur'] = supplier_name
        preview['Nouveau prix fournisseur'] = preview['PU Net'].astype(float)
        preview['Ratio unite fournisseur'] = preview['Ratio unite fournisseur'].fillna(1).astype(float)
        preview['Nouveau cout'] = (preview['Nouveau prix fournisseur'] * preview['Ratio unite fournisseur']).round(2)
        preview['Nouveau prix de vente'] = preview.apply(
            lambda row: self._compute_sale_price(
                row['Nouveau cout'],
                row.get('Taxe vente montant'),
                row.get('Categorie marge'),
            ),
            axis=1,
        )
        preview['Ecart prix fournisseur'] = (
            preview['Nouveau prix fournisseur'] - preview['Prix fournisseur origine'].fillna(0).astype(float)
        )
        preview['Ecart prix de vente'] = (
            preview['Nouveau prix de vente'] - preview['Prix vente origine'].fillna(0).astype(float)
        )
        preview['Remise temporaire'] = preview['R.%'].apply(self._has_temporary_discount)
        preview['A modifier'] = (
            (preview['Ecart prix de vente'] < lower_bound)
            | (preview['Ecart prix de vente'] > upper_bound)
        )
        preview.loc[
            (preview['Ecart prix de vente'] < lower_bound)
            & (preview['Remise temporaire']),
            'A modifier'
        ] = False
        preview.loc[
            preview[['SupplierInfo ID', 'Nouveau prix de vente']].isna().any(axis=1),
            'A modifier'
        ] = False

        columns = [
            'Article ID Odoo',
            'SupplierInfo ID',
            'REF.',
            'DESIGNATION',
            'Nom',
            'Fournisseur',
            'Prix fournisseur origine',
            'Nouveau prix fournisseur',
            'Cout origine',
            'Nouveau cout',
            'Prix vente origine',
            'Nouveau prix de vente',
            'Ecart prix fournisseur',
            'Ecart prix de vente',
            'Remise temporaire',
            'Categorie marge',
            'Taxe vente montant',
            'Ratio unite fournisseur',
            'A modifier',
        ]
        return preview[columns]

    def update_prices_from_preview(self, preview: pd.DataFrame) -> dict:
        """Met a jour les prix fournisseur, cout et prix de vente dans Odoo."""
        if not self.connected:
            raise ValueError("Non connecte a Odoo")

        to_update = preview[preview['A modifier'] == True].copy()
        if to_update.empty:
            return {'success': 0, 'errors': 0, 'details': []}

        Product = self.odoo.env['product.product']
        SupplierInfo = self.odoo.env['product.supplierinfo']
        details = []
        success = 0
        errors = 0

        for _, row in to_update.iterrows():
            product_id = self._coerce_int(row['Article ID Odoo'])
            supplierinfo_id = self._coerce_int(row['SupplierInfo ID'])
            try:
                SupplierInfo.write(
                    [supplierinfo_id],
                    {'price': float(row['Nouveau prix fournisseur'])}
                )
                Product.write(
                    [product_id],
                    {
                        'standard_price': float(row['Nouveau cout']),
                        'list_price': float(row['Nouveau prix de vente']),
                    }
                )
                success += 1
                details.append({
                    'Article ID Odoo': product_id,
                    'Nom': row.get('Nom'),
                    'Statut': 'OK',
                    'Message': 'Prix mis a jour',
                })
            except Exception as e:
                errors += 1
                details.append({
                    'Article ID Odoo': product_id,
                    'Nom': row.get('Nom'),
                    'Statut': 'Erreur',
                    'Message': str(e),
                })

        return {'success': success, 'errors': errors, 'details': details}

    def _get_external_ids(self, df_articles: pd.DataFrame) -> pd.DataFrame:
        """Recupere les ID externes des articles."""
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
            st.warning(f"Impossible de recuperer les ID externes : {str(e)}")
            df_articles['external_id'] = None

        return df_articles

    def _get_supplier_info(self, df_articles: pd.DataFrame) -> pd.DataFrame:
        """Recupere les informations fournisseurs et l'unite d'achat."""
        df_articles['template_id'] = df_articles['product_tmpl_id'].apply(self._many2one_id)

        try:
            SupplierInfo = self.odoo.env['product.supplierinfo']
            suppliers_data = SupplierInfo.search_read(
                [],
                ['product_tmpl_id', 'product_id', 'product_uom']
            )

            df_suppliers = pd.DataFrame(suppliers_data)
            if not df_suppliers.empty:
                df_suppliers['template_id'] = df_suppliers['product_tmpl_id'].apply(self._many2one_id)
                df_suppliers['uom_id'] = df_suppliers['product_uom'].apply(self._many2one_id)
                df_suppliers['uom_name'] = df_suppliers['product_uom'].apply(self._many2one_name)

                df_articles = df_articles.merge(
                    df_suppliers[['template_id', 'uom_id', 'uom_name']],
                    on='template_id',
                    how='left'
                )
            else:
                df_articles['uom_id'] = None
                df_articles['uom_name'] = None

        except Exception as e:
            st.warning(f"Impossible de recuperer les infos fournisseurs : {str(e)}")
            df_articles['uom_id'] = None
            df_articles['uom_name'] = None

        df_articles['uom_id'] = df_articles.apply(
            lambda row: row['uom_id'] if pd.notna(row.get('uom_id')) else self._many2one_id(row.get('uom_po_id')),
            axis=1
        )
        df_articles['uom_name'] = df_articles.apply(
            lambda row: row['uom_name'] if pd.notna(row.get('uom_name')) else self._many2one_name(row.get('uom_po_id')),
            axis=1
        )

        return df_articles

    def _get_tax_info(self, df_articles: pd.DataFrame) -> pd.DataFrame:
        """Recupere les taxes fournisseurs via product.template."""
        try:
            ProductTemplate = self.odoo.env['product.template']
            template_ids = df_articles['template_id'].dropna().unique().tolist()

            if not template_ids:
                df_articles['tax_id'] = None
                df_articles['tax_external_id'] = None
                return df_articles

            templates_data = ProductTemplate.search_read(
                [('id', 'in', template_ids)],
                ['id', 'supplier_taxes_id']
            )

            df_templates = pd.DataFrame(templates_data)
            df_templates['tax_id'] = df_templates['supplier_taxes_id'].apply(
                lambda value: value[0] if value and len(value) > 0 else None
            )

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

            df_articles = df_articles.merge(
                df_templates[['id', 'tax_id', 'tax_external_id']],
                left_on='template_id',
                right_on='id',
                how='left',
                suffixes=('', '_template')
            )

        except Exception as e:
            st.warning(f"Impossible de recuperer les taxes : {str(e)}")
            df_articles['tax_id'] = None
            df_articles['tax_external_id'] = None

        return df_articles

    def _rename_columns(self, df_articles: pd.DataFrame) -> pd.DataFrame:
        """Renomme les colonnes pour correspondre au format attendu par l'app."""
        column_mapping = {
            'id': 'Article ID Odoo',
            'external_id': 'Article/ID',
            'name': 'Nom',
            'uom_id': 'Fournisseurs/Unité de mesure/ID Odoo',
            'uom_name': 'Fournisseurs/Unité de mesure/Nom affiché',
            'tax_id': 'Taxes fournisseur/ID Odoo',
            'tax_external_id': 'Taxes fournisseur/ID',
        }

        df_articles = df_articles.rename(columns=column_mapping)
        columns_to_keep = [
            'Article ID Odoo',
            'Article/ID',
            'Nom',
            'Fournisseurs/Unité de mesure/ID Odoo',
            'Fournisseurs/Unité de mesure/Nom affiché',
            'Taxes fournisseur/ID Odoo',
            'Taxes fournisseur/ID',
        ]

        for col in columns_to_keep:
            if col not in df_articles.columns:
                df_articles[col] = None

        return df_articles[columns_to_keep]

    def _get_price_update_article_details(self, product_ids: list[int], supplier_id: int) -> pd.DataFrame:
        """Recupere les donnees Odoo necessaires a la mise a jour des prix."""
        Product = self.odoo.env['product.product']
        products = Product.search_read(
            [('id', 'in', product_ids)],
            [
                'id',
                'name',
                'standard_price',
                'list_price',
                'product_tmpl_id',
                'taxes_id',
                'margin_classification_id',
            ],
        )
        df_products = pd.DataFrame(products)
        if df_products.empty:
            return pd.DataFrame()

        df_products['template_id'] = df_products['product_tmpl_id'].apply(self._many2one_id)
        df_products['Categorie marge'] = df_products['margin_classification_id'].apply(self._many2one_name)
        df_products['tax_id'] = df_products['taxes_id'].apply(
            lambda value: value[0] if value and len(value) > 0 else None
        )

        SupplierInfo = self.odoo.env['product.supplierinfo']
        supplier_lines = SupplierInfo.search_read(
            [('product_tmpl_id', 'in', df_products['template_id'].dropna().unique().tolist()), ('name', '=', supplier_id)],
            ['id', 'product_tmpl_id', 'product_id', 'price', 'product_uom'],
        )
        df_suppliers = pd.DataFrame(supplier_lines)
        if df_suppliers.empty:
            df_suppliers = pd.DataFrame(columns=['SupplierInfo ID', 'id', 'template_id', 'Prix fournisseur origine', 'uom_id'])
        else:
            df_suppliers['template_id'] = df_suppliers['product_tmpl_id'].apply(self._many2one_id)
            df_suppliers['supplier_product_id'] = df_suppliers['product_id'].apply(self._many2one_id)
            df_suppliers['uom_id'] = df_suppliers['product_uom'].apply(self._many2one_id)
            df_suppliers = df_suppliers.rename(
                columns={
                    'id': 'SupplierInfo ID',
                    'price': 'Prix fournisseur origine',
                }
            )
            df_suppliers = self._select_supplier_lines_for_products(df_products, df_suppliers)

        Tax = self.odoo.env['account.tax']
        tax_ids = df_products['tax_id'].dropna().unique().tolist()
        if tax_ids:
            tax_data = Tax.search_read([('id', 'in', tax_ids)], ['id', 'amount'])
            df_taxes = pd.DataFrame(tax_data).rename(columns={'amount': 'Taxe vente montant'})
        else:
            df_taxes = pd.DataFrame(columns=['id', 'Taxe vente montant'])

        Uom = self.odoo.env['uom.uom']
        uom_ids = df_suppliers['uom_id'].dropna().unique().tolist()
        if uom_ids:
            uom_data = Uom.search_read([('id', 'in', uom_ids)], ['id', 'factor'])
            df_uom = pd.DataFrame(uom_data).rename(columns={'factor': 'Ratio unite fournisseur'})
        else:
            df_uom = pd.DataFrame(columns=['id', 'Ratio unite fournisseur'])

        details = df_products.merge(
            df_suppliers[['SupplierInfo ID', 'id', 'Prix fournisseur origine', 'uom_id']],
            on='id',
            how='left',
        )
        details = details.merge(
            df_taxes[['id', 'Taxe vente montant']],
            left_on='tax_id',
            right_on='id',
            how='left',
            suffixes=('', '_tax'),
        )
        details = details.merge(
            df_uom[['id', 'Ratio unite fournisseur']],
            left_on='uom_id',
            right_on='id',
            how='left',
            suffixes=('', '_uom'),
        )

        return details.rename(
            columns={
                'name': 'Nom',
                'standard_price': 'Cout origine',
                'list_price': 'Prix vente origine',
            }
        )

    def _select_supplier_lines_for_products(
        self,
        df_products: pd.DataFrame,
        df_suppliers: pd.DataFrame,
    ) -> pd.DataFrame:
        """Choisit une seule ligne fournisseur par variante produit."""
        selected_rows = []

        for _, product in df_products[['id', 'template_id']].iterrows():
            product_id = self._coerce_int(product['id'])
            template_id = self._coerce_int(product['template_id'])
            candidates = df_suppliers[df_suppliers['template_id'] == template_id].copy()

            if candidates.empty:
                selected_rows.append({
                    'id': product_id,
                    'SupplierInfo ID': None,
                    'Prix fournisseur origine': None,
                    'uom_id': None,
                })
                continue

            variant_candidates = candidates[candidates['supplier_product_id'] == product_id]
            generic_candidates = candidates[candidates['supplier_product_id'].isna()]

            if not variant_candidates.empty:
                selected = variant_candidates.sort_values('SupplierInfo ID').iloc[0]
            elif not generic_candidates.empty:
                selected = generic_candidates.sort_values('SupplierInfo ID').iloc[0]
            else:
                selected = candidates.sort_values('SupplierInfo ID').iloc[0]

            selected_rows.append({
                'id': product_id,
                'SupplierInfo ID': selected['SupplierInfo ID'],
                'Prix fournisseur origine': selected['Prix fournisseur origine'],
                'uom_id': selected['uom_id'],
            })

        return pd.DataFrame(selected_rows)

    def _compute_sale_price(self, cost, tax_amount, margin_name):
        """Calcule le prix de vente a partir du cout, de la taxe et de la marge."""
        if pd.isna(cost) or pd.isna(tax_amount) or not margin_name:
            return None
        if margin_name not in self.MARGIN_RATES:
            return None

        margin_rate = self.MARGIN_RATES[margin_name]
        sale_price = float(cost) * (1 + margin_rate / 100) * (1 + float(tax_amount) / 100)

        if "Consigne" in margin_name:
            deposit_text = margin_name.split(" ")[-1].replace("€", ".").replace(",", ".")
            sale_price += float(deposit_text)

        return round(sale_price, 2)

    @staticmethod
    def _has_temporary_discount(value) -> bool:
        if pd.isna(value):
            return False
        try:
            return float(str(value).replace(',', '.').strip() or 0) > 0
        except ValueError:
            return bool(str(value).strip())

    def _prepare_purchase_order_line(self, row: pd.Series) -> dict:
        """Prepare les valeurs d'une ligne de demande de prix."""
        product_id = self._coerce_int(row.get('Article ID Odoo'))
        product_uom = self._coerce_int(row.get('Fournisseurs/Unité de mesure/ID Odoo'))
        tax_id = self._coerce_int(row.get('Taxes fournisseur/ID Odoo'))

        if not product_id:
            raise ValueError(f"Article Odoo introuvable pour la reference {row.get('REF.')}")

        line_vals = {
            'product_id': product_id,
            'name': f"[{row.get('REF.', '')}] {row.get('DESIGNATION', '')}",
            'product_qty': float(row.get('QTE', 0) or 0),
            'price_unit': float(row.get('PU Net', 0) or 0),
            'date_planned': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if product_uom:
            line_vals['product_uom'] = product_uom
        if tax_id:
            line_vals['taxes_id'] = [(6, 0, [tax_id])]

        return line_vals

    def _resolve_record_id(self, value, model: str) -> int:
        """Resout un ID interne Odoo depuis un ID externe ou une valeur numerique."""
        numeric_id = self._coerce_int(value)
        if numeric_id:
            return numeric_id

        external_id = str(value or '').strip()
        if not external_id:
            raise ValueError(f"Identifiant {model} vide")

        matches = self._find_external_id(external_id, model)
        if not matches:
            raise ValueError(f"Impossible de trouver {external_id} dans Odoo ({model})")

        return int(matches[0]['res_id'])

    def _resolve_supplier_partner(self, value) -> tuple[int, str]:
        """Resout le fournisseur vers la societe commerciale, pas un simple contact."""
        partner_id = self._resolve_record_id(value, 'res.partner')
        Partner = self.odoo.env['res.partner']
        partner = Partner.read(
            [partner_id],
            ['display_name', 'commercial_partner_id', 'is_company']
        )[0]

        if not partner.get('is_company') and partner.get('commercial_partner_id'):
            commercial_partner = partner['commercial_partner_id']
            partner_id = int(commercial_partner[0])
            partner_name = commercial_partner[1]
        else:
            partner_name = partner.get('display_name', str(partner_id))

        return partner_id, partner_name

    def _find_external_id(self, external_id: str, model: str) -> list:
        """Cherche un ID externe via module/name, avec fallback sur complete_name."""
        IrModelData = self.odoo.env['ir.model.data']

        if '.' in external_id:
            module, name = external_id.split('.', 1)
            matches = IrModelData.search_read(
                [('model', '=', model), ('module', '=', module), ('name', '=', name)],
                ['res_id'],
                limit=1
            )
            if matches:
                return matches

        return IrModelData.search_read(
            [('model', '=', model), ('complete_name', '=', external_id)],
            ['res_id'],
            limit=1
        )

    @staticmethod
    def _many2one_id(value):
        return value[0] if isinstance(value, (list, tuple)) and value else None

    @staticmethod
    def _many2one_name(value):
        return value[1] if isinstance(value, (list, tuple)) and len(value) > 1 else None

    @staticmethod
    def _coerce_int(value) -> Optional[int]:
        if pd.isna(value):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def disconnect(self):
        """Ferme la connexion Odoo."""
        self.odoo = None
        self.connected = False
