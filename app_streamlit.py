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

# Import simplifié grâce aux __init__.py
from core import PDFProcessor, DataProcessor, FileExporter, Config
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
    return PDFProcessor(), DataProcessor(), FileExporter()

pdf_processor, data_processor, file_exporter = get_processors()
config = Config()

# =============================================================================
# Interface utilisateur
# =============================================================================
st.title("Transformer une facture Relais Local en commande ODOO")
st.markdown("""Cette application permet de convertir une facture relais local au format pdf en un fichier de commande à importer sur ODOO.
            \nLe fichier "product.template.csv"" doit être téléchargé à partir d'ODOO, module Inventaire -> Données de base -> Articles, avec l'export "CGS - Import commandes RL".
            \nLe paramètre "Référence commande" ci-contre doit être renseigné, c'est la référence commande qui sera retenue par ODOO. """)

# Paramètres
st.sidebar.header("Paramètres")
ref_commande = st.sidebar.text_input("Référence commande", value=config.REF_COMMANDE_DEFAULT)
id_fourni = st.sidebar.text_input("ID Fournisseur", value=config.ID_FOURNI_DEFAULT)

# Upload des fichiers
st.header("1. Import des fichiers")
col1, col2 = st.columns(2)

with col1:
    pdf_file = st.file_uploader("Facture au format PDF", type=["pdf"])

with col2:
    csv_file = st.file_uploader('Fichier "product.template.csv"', type=["csv"])

# =============================================================================
# Traitement principal
# =============================================================================
def main_processing(pdf_file, csv_file, ref_commande, id_fourni):
    """Fonction principale de traitement"""
    temp_pdf_path = None
    
    try:
        # Sauvegarde temporaire du PDF
        temp_pdf_path = save_uploaded_file(pdf_file)
        
        # Extraction des tableaux du PDF
        with st.spinner("Extraction des tableaux du PDF..."):
            df_raw = pdf_processor.extract_tables_from_pdf(temp_pdf_path)
        
        # Nettoyage des données
        with st.spinner("Nettoyage des données..."):
            df_clean = data_processor.clean_dataframe(df_raw)
        
        # Fusion avec les articles
        with st.spinner("Fusion avec les articles..."):
            df_processed, df_unlinked = data_processor.merge_with_articles(df_clean, csv_file)
        
        # Préparation du fichier d'import
        with st.spinner("Préparation du fichier d'import..."):
            df_import = data_processor.prepare_import_file(df_processed, ref_commande, id_fourni)
        
        return df_processed, df_unlinked, df_import, pdf_file.name[:-4]
    
    except Exception as e:
        import traceback
        st.error(f"Erreur lors du traitement : {str(e)}")
        st.code(traceback.format_exc())  # Montre les détails de l'erreur
        return None, None, None, None
    
    finally:
        # Nettoyage du fichier temporaire
        if temp_pdf_path:
            cleanup_temp_file(temp_pdf_path)

# Bouton de traitement
if st.button("Traiter les fichiers", type="primary"):
    if pdf_file is not None and csv_file is not None:
        df_processed, df_unlinked, df_import, pdf_name = main_processing(
            pdf_file, csv_file, ref_commande, id_fourni
        )
        
        if df_processed is not None:
            st.success("Traitement terminé avec succès !")
            
            # Affichage des résultats
            st.header("2. Résultats")
            tab1, tab2, tab3 = st.tabs(["Commandes traitées", "Articles non liés", "Fichier à importer"])
            
            with tab1:
                st.subheader("Commandes traitées")
                st.dataframe(df_processed)
                st.write(f"Nombre d'articles traités : {len(df_processed)}")
            
            with tab2:
                st.subheader("Articles non liés")
                if not df_unlinked.empty:
                    st.dataframe(df_unlinked)
                    st.write(f"Nombre d'articles non liés : {len(df_unlinked)}")
                else:
                    st.success("Aucun article non lié !")
            
            with tab3:
                st.subheader("Fichier à importer")
                st.dataframe(df_import)
            
            # Téléchargement des fichiers
            st.header("3. Téléchargement des fichiers")
            
            # Préparer les buffers pour les fichiers
            excel_buffer = file_exporter.export_to_excel(df_processed, df_unlinked)
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
    
    else:
        st.warning("Veuillez importer les deux fichiers (PDF et CSV) avant de lancer le traitement.")

warnings.filterwarnings('always')