"""
Traitement des fichiers PDF.

Les factures Relais Local sont des PDF texte avec une mise en page stable.
On reconstruit donc les lignes depuis les coordonnees des mots plutot que via
une detection automatique de tableau, trop sensible aux colonnes fusionnees.
"""
import re

import fitz  # PyMuPDF
import pandas as pd

from .config import Config


class PDFProcessor:
    """Classe pour le traitement des fichiers PDF."""

    PRODUCT_REF_PATTERN = re.compile(r"^\d{6}$")

    # Bornes horizontales observees sur les factures Relais Local.
    # Les colonnes non utilisees plus tard sont conservees pour faciliter le debug.
    COLUMN_BOUNDS = {
        'REF.': (0, 55),
        'DESIGNATION': (55, 220),
        'Nature': (220, 255),
        'Marque': (255, 315),
        'NB Colis': (315, 350),
        'QTE': (350, 375),
        'UV': (375, 395),
        'PU Brut': (395, 435),
        'R.%': (435, 460),
        'PU Net': (460, 500),
        'Montant HT': (500, 545),
        'Tva': (545, 580),
    }

    def __init__(self):
        self.config = Config()

    def extract_tables_from_pdf(self, pdf_path):
        """
        Extrait les lignes d'articles du PDF et retourne une liste de DataFrames.

        L'ancienne extraction Tabula dependait du "deuxieme tableau" de chaque
        page. Elle produisait parfois des colonnes fusionnees selon le contenu.
        Ici, chaque ligne est reconstruite depuis les mots du PDF :
        - la reference produit a gauche sert d'ancre de ligne ;
        - la ligne s'etend jusqu'a la reference suivante ;
        - les valeurs sont affectees aux colonnes par zones horizontales.
        """
        df_list = []

        with fitz.open(pdf_path) as pdf_document:
            for page_num, page in enumerate(pdf_document, start=1):
                page_df = self._extract_invoice_lines_from_page(page, page_num)
                if not page_df.empty:
                    df_list.append(page_df)

        if not df_list:
            raise ValueError("Aucune ligne article trouvee dans le PDF")

        return df_list

    def _extract_invoice_lines_from_page(self, page, page_num):
        """Reconstruit les lignes d'articles d'une page depuis les mots positionnes."""
        words = page.get_text("words")
        line_anchors = self._find_line_anchors(words)
        footer_y = self._find_footer_y(words, page.rect.height)
        rows = []

        for index, (line_y, ref) in enumerate(line_anchors):
            next_line_y = (
                line_anchors[index + 1][0]
                if index + 1 < len(line_anchors)
                else min(footer_y, line_y + 45)
            )
            band_words = [
                word for word in words
                if line_y - 2 <= word[1] < next_line_y - 1
            ]
            row = self._words_to_row(band_words)
            row['REF.'] = ref
            row['Page'] = page_num
            rows.append(row)

        return pd.DataFrame(rows)

    def _find_line_anchors(self, words):
        """Trouve les references articles qui ancrent les lignes du tableau."""
        anchors = []

        for word in words:
            x0, y0, _, _, text, *_ = word
            if (
                y0 > 230
                and x0 < self.COLUMN_BOUNDS['REF.'][1]
                and self.PRODUCT_REF_PATTERN.match(text)
            ):
                anchors.append((y0, text))

        return sorted(anchors, key=lambda item: item[0])

    def _find_footer_y(self, words, page_height):
        """Trouve le debut du pied de facture pour eviter de polluer la derniere ligne."""
        footer_markers = []

        for word in words:
            _, y0, _, _, text, *_ = word
            if y0 > 230 and text in {'IBAN:', 'CONDITIONS', 'Clauses'}:
                footer_markers.append(y0)

        return min(footer_markers) if footer_markers else page_height

    def _words_to_row(self, words):
        """Affecte les mots d'une bande de ligne aux colonnes attendues."""
        row = {}

        for column, (left, right) in self.COLUMN_BOUNDS.items():
            column_words = [
                word for word in words
                if left <= word[0] < right
            ]
            column_words = sorted(column_words, key=lambda word: (word[1], word[0]))
            row[column] = " ".join(word[4] for word in column_words).strip()

        return row
