# unused.py
"""
Functions moved here for archival. Not actively used in the pipeline.
"""

import numpy as np
import pandas as pd


# =============================================================================
# ARSIP: kategorisasi lama (tidak dipanggil di mana pun dalam paket)
# =============================================================================
# Diarsipkan, bukan dihapus. Versi vektor yang dipakai arrange_table() ada di
# utils.py: categorize_ch_vec() / categorize_index_vec().
# Fallback nilai hilang tetap kategori 1 (terendah) -- lihat CLAUDE.md.

def categorize_ch(value):
    fallback_strategy = 'lowest'
    ranges = {
        1: (0, 100),
        2: (101, 300),
        3: (301, 500),
        4: (501, float('inf'))
    }

    if pd.isna(value) or value is None:
        if fallback_strategy == 'lowest':
            return 1
        elif fallback_strategy == 'highest':
            return 4
        elif fallback_strategy == 'middle':
            return 2
        elif fallback_strategy == 'zero_as_lowest':
            return 1

    try:
        if np.isnan(value):
            if fallback_strategy == 'lowest':
                return 1
            elif fallback_strategy == 'highest':
                return 4
            elif fallback_strategy == 'middle':
                return 2
            elif fallback_strategy == 'zero_as_lowest':
                return 1
    except (TypeError, ValueError):
        pass

    if not isinstance(value, (int, float, np.integer, np.floating)):
        if fallback_strategy == 'lowest':
            return 1
        elif fallback_strategy == 'highest':
            return 4
        elif fallback_strategy == 'middle':
            return 2
        elif fallback_strategy == 'zero_as_lowest':
            return 1

    if value < 0:
        return 1

    for category, (min_val, max_val) in ranges.items():
        if min_val <= value <= max_val:
            return category

    return 4


def categorize_index(value):
    fallback_strategy = 'lowest'
    ranges = {
        1: (0, 20),
        2: (21, 50),
        3: (51, 100),
        4: (101, 150),
        5: (151, 200),
        6: (201, 300),
        7: (301, 400),
        8: (401, 500),
        9: (501, float('inf'))
    }

    if pd.isna(value) or value is None:
        if fallback_strategy == 'lowest':
            return 1
        elif fallback_strategy == 'highest':
            return 9
        elif fallback_strategy == 'middle':
            return 5
        elif fallback_strategy == 'zero_as_lowest':
            return 1

    try:
        if np.isnan(value):
            if fallback_strategy == 'lowest':
                return 1
            elif fallback_strategy == 'highest':
                return 9
            elif fallback_strategy == 'middle':
                return 5
            elif fallback_strategy == 'zero_as_lowest':
                return 1
    except (TypeError, ValueError):
        pass

    if not isinstance(value, (int, float, np.integer, np.floating)):
        if fallback_strategy == 'lowest':
            return 1
        elif fallback_strategy == 'highest':
            return 9
        elif fallback_strategy == 'middle':
            return 5
        elif fallback_strategy == 'zero_as_lowest':
            return 1

    if value < 0:
        return 1

    for category, (min_val, max_val) in ranges.items():
        if min_val <= value <= max_val:
            return category

    return 9
