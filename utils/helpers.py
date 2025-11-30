"""
Fonctions utilitaires
"""
import os
import tempfile

def save_uploaded_file(uploaded_file):
    """
    Sauvegarde un fichier uploadé temporairement
    
    Args:
        uploaded_file: Fichier uploadé via Streamlit
        
    Returns:
        str: Chemin vers le fichier temporaire
    """
    try:
        # Créer un fichier temporaire
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getbuffer())
            return tmp_file.name
    except Exception as e:
        raise Exception(f"Erreur lors de la sauvegarde du fichier: {str(e)}")

def cleanup_temp_file(file_path):
    """
    Supprime un fichier temporaire
    
    Args:
        file_path (str): Chemin vers le fichier à supprimer
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Erreur lors de la suppression du fichier temporaire: {str(e)}")