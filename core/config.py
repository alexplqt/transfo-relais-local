"""
Configuration de l'application
"""

class Config:
    """Paramètres de configuration par défaut"""
    REF_COMMANDE_DEFAULT = "A définir"
    ID_FOURNI_DEFAULT = "__export__.res_partner_244_9deb6d8b"
    ENCODING = 'ISO-8859-1'
    
    # Colonnes attendues dans le PDF
    PDF_COLUMNS = ['REF.', 'DESIGNATION', 'QTE', 'UV', 'PU Brut', 'R.%', 'PU Net', 'Montant HT']
    FLOAT_COLUMNS = ['PU Brut', 'R.%', 'PU Net', 'Montant HT']
    
    # Colonnes pour l'export
    EXPORT_COLUMNS = [
        'ID Externe', 'Référence commande', 'Fournisseur/ID',
        'Lignes de la commande/Description', 'Lignes de la commande/Article/ID',
        "Lignes de la commande/Unité de mesure d'article", 'Lignes de la commande/Quantité',
        'Lignes de la commande/Prix unitaire', 'Lignes de la commande/Taxes/ID',
        'Lignes de la commande/Date prévue'
    ]