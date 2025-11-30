# Transformer une facture Relais Local en commande ODOO

Application Streamlit pour convertir une facture Relais Local (PDF) en fichier de commande prêt à importer sur ODOO.

## 📋 Fonctionnalités

- Import d'une facture Relais Local au format PDF
- Import du fichier `product.template.csv` depuis ODOO
- Génération d'un fichier Excel avec les commandes traitées et articles non liés
- Génération d'un fichier CSV prêt à importer dans ODOO
- Export groupé des deux fichiers en format ZIP

## 🚀 Installation et utilisation

### 1. Installation
```bash
# Cloner le repository
git clone https://github.com/votre-username/transformation-relais-local.git

# Aller dans le dossier
cd transformation-relais-local

# Installer les dépendances
pip install -r requirements.txt