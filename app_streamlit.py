# Pour lancer le script en local, il faut lancer dans la console anaconda : streamlit run app_streamlit.py


# =============================================================================
# # Liste des commandes pour mettre à jour sur github les modifications : 
# =============================================================================
# git status          # Voir ce qui est modifié (facultatif)
# git add .           # Ajouter tous les fichiers modifiés
# git commit -m "message"  # Sauvegarder en local
# git push origin main      # Envoyer sur GitHub

# =============================================================================
# Pour récupérer les modifs qui ont été faites sur github
# =============================================================================
# git pull origin main      # Récupérer les modifs de GitHub


import streamlit as st
import warnings
import pandas as pd

# Import simplifié grâce aux __init__.py
from core import PDFProcessor, DataProcessor, FileExporter, OdooConnector, Config
from utils import save_uploaded_file, cleanup_temp_file

warnings.filterwarnings('ignore')

# =============================================================================
# Configuration de la page Streamlit
# =============================================================================
st.set_page_config(
    page_title="Transformation facture Relais Local en commande",
    page_icon="📄",
    layout="centered"
)

# =============================================================================
# Initialisation des classes
# =============================================================================
@st.cache_resource
def get_processors():
    """Initialise et cache les processeurs"""
    return PDFProcessor(), DataProcessor(), FileExporter(), OdooConnector()

pdf_processor, data_processor, file_exporter, odoo_connector = get_processors()
config = Config()

# =============================================================================
# Gestion de la connexion Odoo et cache des données
# =============================================================================
@st.cache_data(ttl=3600)  # Cache pendant 1 heure
def get_odoo_articles(_odoo_connector, url, port, database, username, password):
    """Récupère et cache les articles depuis Odoo"""
    if _odoo_connector.connect(url, port, database, username, password):
        return _odoo_connector.get_product_variants()
    return None

# =============================================================================
# Interface utilisateur
# =============================================================================
st.title("Transformer une facture Relais Local en commande ODOO")
st.markdown("""Cette application permet de convertir une facture relais local au format pdf en un fichier de commande à importer sur ODOO.
            \nLe fichier "Correspondance.xlsx" doit contenir la correspondance entre les références RL et les noms d'articles ODOO.
            \nLe paramètre "Référence commande" ci-contre doit être renseigné, c'est la référence commande qui sera retenue par ODOO. """)

# Paramètres
st.sidebar.header("Paramètres")
ref_commande = st.sidebar.text_input("Référence commande", value=config.REF_COMMANDE_DEFAULT)
id_fourni = st.sidebar.text_input("ID Fournisseur", value=config.ID_FOURNI_DEFAULT)

# =============================================================================
# Section : Choix de la source des articles
# =============================================================================
st.header("1. Source des articles ODOO")

source_mode = st.radio(
    "Choisissez votre méthode :",
    ["Connexion Odoo", "Upload fichier CSV"],
    horizontal=True
)

df_articles = None

if source_mode == "Connexion Odoo":
    st.subheader("🔐 Connexion à Odoo")
    
    # Vérifier si on a des secrets configurés
    try:
        odoo_url = st.secrets.get("odoo", {}).get("url", "odoo.demainsupermarche.org")
        odoo_port = st.secrets.get("odoo", {}).get("port", 443)
        odoo_database = st.secrets.get("odoo", {}).get("database", "demain")
        odoo_username = st.secrets.get("odoo", {}).get("username", "")
        odoo_password = st.secrets.get("odoo", {}).get("password", "")
        use_secrets = True
    except:
        # Valeurs par défaut si pas de secrets configurés
        odoo_url = "odoo.demainsupermarche.org"
        odoo_port = 443
        odoo_database = "demain"
        odoo_username = ""
        odoo_password = ""
        use_secrets = False
    
    # Afficher les champs de connexion
    col1, col2 = st.columns(2)
    with col1:
        odoo_url = st.text_input("URL Odoo", value=odoo_url)
        odoo_database = st.text_input("Base de données", value=odoo_database)
        odoo_username = st.text_input("Nom d'utilisateur", value=odoo_username)
    with col2:
        odoo_port = st.number_input("Port", value=odoo_port, min_value=1, max_value=65535)
        odoo_password = st.text_input("Mot de passe", type="password", value=odoo_password)
    
    if st.button("🔌 Se connecter et récupérer les articles", type="primary"):
        with st.spinner("Connexion à Odoo et récupération des articles..."):
            df_articles = get_odoo_articles(
                odoo_connector,
                odoo_url,
                odoo_port,
                odoo_database,
                odoo_username,
                odoo_password
            )
            
            if df_articles is not None:
                st.success(f"✅ {len(df_articles)} articles récupérés depuis Odoo")
                st.session_state['df_articles'] = df_articles
                st.session_state['articles_source'] = 'odoo'
            else:
                st.error("❌ Échec de la récupération des articles")
    
    # Afficher les articles si déjà récupérés
    if 'df_articles' in st.session_state and st.session_state.get('articles_source') == 'odoo':
        df_articles = st.session_state['df_articles']
        with st.expander("📊 Aperçu des articles récupérés"):
            st.dataframe(df_articles.head(10))
            st.info(f"Total : {len(df_articles)} articles")

else:  # Upload fichier CSV
    st.subheader("📁 Upload du fichier product.product.csv")
    st.info('Le fichier "product.product.csv" doit être téléchargé à partir d\'ODOO, module Inventaire -> Données de base -> Variantes d\'articles.')
    
    csv_file = st.file_uploader('Fichier "product.product.csv"', type=["csv"])
    
    if csv_file is not None:
        try:
            df_articles = pd.read_csv(csv_file)
            st.success(f"✅ {len(df_articles)} articles chargés depuis le CSV")
            st.session_state['df_articles'] = df_articles
            st.session_state['articles_source'] = 'csv'
            
            with st.expander("📊 Aperçu du fichier CSV"):
                st.dataframe(df_articles.head(10))
        except Exception as e:
            st.error(f"❌ Erreur lors de la lecture du CSV : {str(e)}")

# =============================================================================
# Upload des autres fichiers
# =============================================================================
st.header("2. Import des autres fichiers")
col1, col2 = st.columns(2)

with col1:
    pdf_file = st.file_uploader("Facture au format PDF", type=["pdf"])

with col2:
    excel_file = st.file_uploader('Fichier "Correspondance.xlsx"', type=["xlsx"])

# =============================================================================
# Traitement principal
# =============================================================================
def main_processing(pdf_file, df_articles, excel_file, ref_commande, id_fourni):
    """Fonction principale de traitement"""
    temp_pdf_path = None
    
    try:
        # Sauvegarde temporaire du PDF
        temp_pdf_path = save_uploaded_file(pdf_file)
        
        # Extraction des tableaux du PDF
        with st.spinner("Extraction des tableaux du PDF..."):
            try:
                df_raw = pdf_processor.extract_tables_from_pdf(temp_pdf_path)
                st.success("✅ Extraction PDF terminée")
            except Exception as e:
                st.error(f"❌ Échec de l'extraction PDF: {str(e)}")
                return None, None, None, None, None
                
        # Nettoyage des données
        with st.spinner("Nettoyage des données..."):
            df_clean = data_processor.clean_dataframe(df_raw)
        
        # Fusion avec les articles
        with st.spinner("Fusion avec les articles..."):
            df_processed, df_unlinked_rl, df_unlinked_od = data_processor.merge_with_articles(
                df_clean, df_articles, excel_file
            )
        
        # Préparation du fichier d'import
        with st.spinner("Préparation du fichier d'import..."):
            df_import = data_processor.prepare_import_file(df_processed, ref_commande, id_fourni)
        
        return df_processed, df_unlinked_rl, df_unlinked_od, df_import, pdf_file.name[:-4]
    
    except Exception as e:
        import traceback
        st.error(f"Erreur lors du traitement : {str(e)}")
        st.code(traceback.format_exc())
        return None, None, None, None, None
    
    finally:
        # Nettoyage du fichier temporaire
        if temp_pdf_path:
            cleanup_temp_file(temp_pdf_path)

# Bouton de traitement
if st.button("Traiter les fichiers", type="primary"):
    # Vérifier que les articles sont disponibles
    if 'df_articles' not in st.session_state or st.session_state['df_articles'] is None:
        st.error("❌ Veuillez d'abord récupérer les articles (via Odoo ou CSV)")
    elif pdf_file is None or excel_file is None:
        st.warning("⚠️ Veuillez uploader le PDF et le fichier de correspondance")
    else:
        df_processed, df_unlinked_rl, df_unlinked_od, df_import, pdf_name = main_processing(
            pdf_file, st.session_state['df_articles'], excel_file, ref_commande, id_fourni
        )
        
        if df_processed is not None:
            st.success("Traitement terminé avec succès !")
            
            # Affichage des résultats
            st.header("3. Résultats")
            tab1, tab2, tab3, tab4 = st.tabs(["Commandes traitées", "Articles non liés (RL)", "Articles non liés (ODOO)", "Fichier à importer"])
            
            with tab1:
                st.subheader("Commandes traitées")
                st.dataframe(df_processed)
                st.write(f"Nombre d'articles traités : {len(df_processed)}")
            
            with tab2:
                st.subheader("Articles non liés (RL)")
                if not df_unlinked_rl.empty:
                    st.dataframe(df_unlinked_rl)
                    st.write(f"Nombre d'articles non liés RL : {len(df_unlinked_rl)}")
                else:
                    st.success("Aucun article non lié RL !")
            
            with tab3:
                st.subheader("Articles non liés (ODOO)")
                if not df_unlinked_od.empty:
                    st.dataframe(df_unlinked_od)
                    st.write(f"Nombre d'articles non liés ODOO : {len(df_unlinked_od)}")
                else:
                    st.success("Aucun article non lié ODOO !")
            
            with tab4:
                st.subheader("Fichier à importer")
                st.dataframe(df_import)
            
            # Téléchargement des fichiers
            st.header("4. Téléchargement des fichiers")
            
            # Préparer les buffers pour les fichiers
            excel_buffer = file_exporter.export_to_excel(df_processed, df_unlinked_rl, df_unlinked_od)
            csv_buffer = file_exporter.export_to_csv(df_import)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.download_button(
                    label="📥 Télécharger le fichier Excel",
                    data=excel_buffer,
                    file_name=f"commandes_traitee_{pdf_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col2:
                st.download_button(
                    label="📥 Télécharger le fichier CSV",
                    data=csv_buffer,
                    file_name=f"a_importer_{pdf_name}.csv",
                    mime="text/csv"
                )
            
            with col3:
                # Créer un fichier ZIP contenant les deux fichiers
                import zipfile
                from io import BytesIO
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    # Ajouter le fichier Excel
                    excel_buffer.seek(0)
                    zip_file.writestr(f"commandes_traitee_{pdf_name}.xlsx", excel_buffer.read())
                    
                    # Ajouter le fichier CSV
                    csv_buffer.seek(0)
                    zip_file.writestr(f"a_importer_{pdf_name}.csv", csv_buffer.read())
                
                zip_buffer.seek(0)
                
                st.download_button(
                    label="📦 Télécharger les deux fichiers (ZIP)",
                    data=zip_buffer,
                    file_name=f"export_complet_{pdf_name}.zip",
                    mime="application/zip"
                )

warnings.filterwarnings('always')