# narasi.py
"""
AI-generated map captions using Gemini.
Pre-computes percentages from count_points data to minimize token usage.
"""

import json
import time

from .utils import number_to_bulan, dasarian_romawi, dasarian_to_date
from .config import cfg
from .status import update as status_update


# =============================================================================
# RETRY HELPER
# =============================================================================

def _call_with_retry(fn, max_retries=4, initial_delay=2.0):
    """Call *fn()* with exponential-backoff retry on transient API errors."""
    delay = initial_delay
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            # Only retry on server-side (5xx) errors
            err_str = str(e)
            is_server_error = False
            try:
                from google.genai.errors import ServerError
                if isinstance(e, ServerError):
                    is_server_error = True
            except ImportError:
                # Fallback: detect 5xx from error message
                if any(code in err_str for code in ('500', '502', '503', '504', 'UNAVAILABLE')):
                    is_server_error = True
            if not is_server_error:
                raise
            last_exc = e
            if attempt == max_retries:
                break
            status_update(
                f"API unavailable (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay:.0f}s..."
            )
            time.sleep(delay)
            delay = min(delay * 2, 60.0)
    raise last_exc


# =============================================================================
# CATEGORY DEFINITIONS
# =============================================================================

CATEGORY_DEFS = {
    ('Curah Hujan', 'Bulanan'): {"Rendah": "0-100 mm", "Menengah": "100-300 mm", "Tinggi": "300-500 mm", "Sangat Tinggi": ">500 mm"},
    ('Curah Hujan', 'Dasarian'): {"Rendah": "0-50 mm/das", "Menengah": "50-150 mm/das", "Tinggi": "150-300 mm/das", "Sangat Tinggi": ">300 mm/das"},
    ('Sifat Hujan', 'Bulanan'): {"Bawah Normal": "0%-84%", "Normal": "85%-115%", "Atas Normal": ">116%"},
    ('Sifat Hujan', 'Dasarian'): {"Bawah Normal": "0%-84%", "Normal": "85%-115%", "Atas Normal": ">116%"},
    ('Verifikasi', 'Bulanan'): {"Tidak Sesuai": "0", "Sesuai": "1"},
    ('Verifikasi', 'Dasarian'): {"Tidak Sesuai": "0", "Sesuai": "1"},
    ('Bias', 'Bulanan'): "Selisih antara prakiraan dan analisis curah hujan (mm)",
    ('Bias', 'Dasarian'): "Selisih antara prakiraan dan analisis curah hujan (mm)",
    ('Normal', 'Bulanan'): {"Rendah": "0-100 mm", "Menengah": "100-300 mm", "Tinggi": "300-500 mm", "Sangat Tinggi": ">500 mm"},
    ('Probabilistik', 'Bulanan'): "Peluang curah hujan per kategori ambang batas (50mm, 100mm, 150mm)",
    ('HTH', 'Dasarian'): "Jumlah hari tanpa hujan berturut-turut",
}

CATEGORY_PRIORITY = {
    'Sangat Tinggi': 1, 'Rendah': 1, 'Tinggi': 2, 'Menengah': 2,
    'Atas Normal': 1, 'Bawah Normal': 1, 'Normal': 2,
    '>30': 1, '21-30': 1, '11-20': 2, '6-10': 2, '1-5': 2,
    'Sesuai': 1, 'Tidak Sesuai': 1,
}
_HIGH_PRIORITY_THRESHOLD = 5.0


# =============================================================================
# PERCENTAGE COMPUTATION
# =============================================================================

def _counts_to_percentages(counts_dict):
    """Convert count_points output to sorted percentages.

    Input:  {"Rendah": 5, "Menengah": 20, "Tinggi": 18, "Sangat Tinggi": 4, "total": 47}
    Output: [("Menengah", 42.6), ("Tinggi", 38.3), ("Rendah", 10.6), ("Sangat Tinggi", 8.5)]
    """
    total = counts_dict.get('total', 0)
    if total == 0:
        return []
    result = []
    for k, v in counts_dict.items():
        if k == 'total':
            continue
        pct = round(v / total * 100, 1)
        if pct > 0:
            result.append((k, pct))
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def _compute_all_percentages(province_data, kabupaten_data):
    """Convert all province/kabupaten count dicts to percentage summaries."""
    provinsi = {}
    for name, counts in province_data.items():
        provinsi[name] = _counts_to_percentages(counts)

    kabupaten = {}
    for name, counts in kabupaten_data.items():
        if counts.get('total', 0) > 0:
            kabupaten[name] = _counts_to_percentages(counts)

    return {"provinsi": provinsi, "kabupaten": kabupaten}


def _format_kabupaten_by_category(kabupaten_pcts):
    """Group kabupaten by category using priority-based dual logic.

    Priority 1 categories (extreme): include any kabupaten with >= threshold%.
    Priority 2 categories (normal/moderate): include only when dominant.

    Returns formatted string listing kabupaten names under each category.
    """
    groups = {}
    for kab_name, pcts in kabupaten_pcts.items():
        if not pcts:
            continue
        dominant = pcts[0][0]
        # Always add kabupaten to its dominant category
        groups.setdefault(dominant, []).append(kab_name)
        # For priority-1 categories, also add if >= threshold (non-dominant)
        for cat, val in pcts[1:]:
            if CATEGORY_PRIORITY.get(cat, 2) == 1 and val >= _HIGH_PRIORITY_THRESHOLD:
                groups.setdefault(cat, []).append(kab_name)

    lines = []
    for cat, kabs in groups.items():
        lines.append(f"{cat}: {', '.join(kabs)}")
    return "\n".join(lines)


def _format_percentages(pct_data):
    """Format pre-computed percentages into a compact string for the prompt."""
    lines = []

    lines.append("=== PROVINSI ===")
    for name, pcts in pct_data['provinsi'].items():
        if not pcts:
            continue
        dominant = pcts[0][0]
        pct_str = ", ".join([f"{cat}: {val}%" for cat, val in pcts])
        lines.append(f"{name} (dominan: {dominant}): {pct_str}")

    kab_grouped = _format_kabupaten_by_category(pct_data['kabupaten'])
    if kab_grouped:
        lines.append("=== KABUPATEN PER KATEGORI ===")
        lines.append(kab_grouped)

    return "\n".join(lines)


# =============================================================================
# EXAMPLE PAIRS (using pre-computed percentages)
# =============================================================================

EXAMPLE_PAIRS = {
    # ---- 1. Prakiraan + Curah Hujan + Bulanan ----
    ('Prakiraan', 'Curah Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan September 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Tinggi): Tinggi: 50.0%, Menengah: 35.7%, Sangat Tinggi: 10.0%, Rendah: 4.3%\n"
            "Papua Barat Daya (dominan: Menengah): Menengah: 42.6%, Tinggi: 38.3%, Rendah: 10.6%, Sangat Tinggi: 8.5%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Menengah: Sorong, Raja Ampat, Teluk Wondama, Maybrat, Fak Fak\n"
            "Tinggi: Manokwari, Manokwari Selatan, Teluk Bintuni, Kaimana\n"
            "Sangat Tinggi: Pegunungan Arfak, Manokwari\n"
            "Rendah: Sorong Selatan, Fak Fak"
        ),
        "output": (
            "Prakiraan Curah Hujan Bulan September 2024 di Provinsi Papua Barat didominasi curah hujan "
            "Tinggi (300-500 mm) sebesar 50.0%, sementara Papua Barat Daya didominasi Menengah (100-300 mm) "
            "sebesar 42.6%. Curah hujan Sangat Tinggi (>500 mm) diprakirakan terjadi di Kab. Pegunungan Arfak "
            "dan Manokwari, sedangkan curah hujan Rendah (0-100 mm) diprakirakan di Kab. Sorong Selatan dan Fak Fak."
        )
    },

    # ---- 2. Prakiraan + Curah Hujan + Dasarian ----
    ('Prakiraan', 'Curah Hujan', 'Dasarian'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Dasarian I September 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Menengah): Menengah: 46.2%, Tinggi: 30.8%, Rendah: 15.4%, Sangat Tinggi: 7.7%\n"
            "Papua Barat Daya (dominan: Menengah): Menengah: 48.9%, Tinggi: 26.7%, Rendah: 17.8%, Sangat Tinggi: 6.7%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Rendah: Sorong, Sorong Selatan\n"
            "Menengah: Raja Ampat, Teluk Wondama, Maybrat, Fak Fak, Teluk Bintuni\n"
            "Tinggi: Manokwari, Kaimana\n"
            "Sangat Tinggi: Pegunungan Arfak"
        ),
        "output": (
            "Prakiraan Curah Hujan Dasarian I September 2024 (1 - 10 September 2024) di Provinsi "
            "Papua Barat dan Papua Barat Daya umumnya didominasi curah hujan Menengah (50-150 mm/das) "
            "sebesar 46.2% di Papua Barat dan 48.9% di Papua Barat Daya. Curah hujan Rendah (0-50 mm/das) "
            "diprakirakan terjadi di Kab. Sorong dan Sorong Selatan. Sedangkan curah hujan Tinggi "
            "(150-300 mm/das) dan Sangat Tinggi (>300 mm/das) diprakirakan terjadi di Kab. Manokwari, "
            "Kaimana, dan Pegunungan Arfak."
        )
    },

    # ---- 3. Prakiraan + Sifat Hujan + Bulanan ----
    ('Prakiraan', 'Sifat Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan September 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Normal): Normal: 57.1%, Atas Normal: 25.7%, Bawah Normal: 17.1%\n"
            "Papua Barat Daya (dominan: Normal): Normal: 46.8%, Bawah Normal: 31.9%, Atas Normal: 21.3%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Bawah Normal: Teluk Bintuni, Fak Fak\n"
            "Normal: Sorong, Raja Ampat, Teluk Wondama, Maybrat, Kaimana\n"
            "Atas Normal: Manokwari, Pegunungan Arfak"
        ),
        "output": (
            "Prakiraan Sifat Hujan Bulan September 2024 di Provinsi Papua Barat dan Papua Barat Daya "
            "umumnya didominasi sifat hujan Normal (85%-115%) sebesar 57.1% di Papua Barat dan 46.8% "
            "di Papua Barat Daya. Sifat hujan Atas Normal (>116%) diprakirakan terjadi di Kab. Manokwari "
            "dan Pegunungan Arfak, sedangkan sifat hujan Bawah Normal (0%-84%) diprakirakan di Kab. "
            "Teluk Bintuni dan Fak Fak."
        )
    },

    # ---- 4. Prakiraan + Sifat Hujan + Dasarian ----
    ('Prakiraan', 'Sifat Hujan', 'Dasarian'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Dasarian II September 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Normal): Normal: 60.0%, Atas Normal: 25.7%, Bawah Normal: 14.3%\n"
            "Papua Barat Daya (dominan: Normal): Normal: 53.2%, Bawah Normal: 29.8%, Atas Normal: 17.0%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Bawah Normal: Teluk Bintuni, Fak Fak\n"
            "Normal: Sorong, Raja Ampat, Manokwari, Teluk Wondama, Maybrat, Kaimana\n"
            "Atas Normal: Pegunungan Arfak, Manokwari Selatan"
        ),
        "output": (
            "Prakiraan Sifat Hujan Dasarian II September 2024 (11 - 20 September 2024) di Provinsi "
            "Papua Barat dan Papua Barat Daya umumnya didominasi sifat hujan Normal (85%-115%) sebesar "
            "60.0% di Papua Barat dan 53.2% di Papua Barat Daya. Sifat hujan Bawah Normal (0%-84%) "
            "diprakirakan terjadi di Kab. Teluk Bintuni dan Fak Fak, sedangkan sifat hujan Atas Normal "
            "(>116%) diprakirakan di Kab. Pegunungan Arfak dan Manokwari Selatan."
        )
    },

    # ---- 5. Analisis + Curah Hujan + Bulanan ----
    ('Analisis', 'Curah Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan Agustus 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Menengah): Menengah: 42.9%, Tinggi: 40.0%, Sangat Tinggi: 10.0%, Rendah: 7.1%\n"
            "Papua Barat Daya (dominan: Menengah): Menengah: 38.3%, Tinggi: 34.0%, Rendah: 17.0%, Sangat Tinggi: 10.6%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Menengah: Sorong, Raja Ampat, Teluk Wondama, Fak Fak\n"
            "Tinggi: Manokwari, Teluk Bintuni, Kaimana\n"
            "Sangat Tinggi: Pegunungan Arfak, Manokwari Selatan, Manokwari\n"
            "Rendah: Sorong Selatan, Fak Fak"
        ),
        "output": (
            "Analisis Curah Hujan Bulan Agustus 2024 di Provinsi Papua Barat dan Papua Barat Daya "
            "umumnya didominasi curah hujan Menengah (100-300 mm) sebesar 42.9% di Papua Barat dan "
            "38.3% di Papua Barat Daya. Curah hujan Sangat Tinggi (>500 mm) tercatat di Kab. Pegunungan Arfak, "
            "Manokwari Selatan, dan Manokwari, sedangkan curah hujan Rendah (0-100 mm) tercatat di Kab. "
            "Sorong Selatan dan Fak Fak."
        )
    },

    # ---- 6. Analisis + Curah Hujan + Dasarian ----
    ('Analisis', 'Curah Hujan', 'Dasarian'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Dasarian III Agustus 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Menengah): Menengah: 43.1%, Tinggi: 27.7%, Rendah: 23.1%, Sangat Tinggi: 6.2%\n"
            "Papua Barat Daya (dominan: Menengah): Menengah: 44.4%, Rendah: 26.7%, Tinggi: 22.2%, Sangat Tinggi: 6.7%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Rendah: Sorong, Sorong Selatan, Maybrat\n"
            "Menengah: Raja Ampat, Teluk Wondama, Fak Fak, Teluk Bintuni\n"
            "Tinggi: Manokwari, Kaimana\n"
            "Sangat Tinggi: Pegunungan Arfak"
        ),
        "output": (
            "Analisis Curah Hujan Dasarian III Agustus 2024 (21 - 31 Agustus 2024) di Provinsi "
            "Papua Barat dan Papua Barat Daya umumnya didominasi curah hujan Menengah (50-150 mm/das) "
            "sebesar 43.1% di Papua Barat dan 44.4% di Papua Barat Daya. Curah hujan Rendah "
            "(0-50 mm/das) tercatat di Kab. Sorong, Sorong Selatan, dan Maybrat, sedangkan curah hujan "
            "Tinggi (150-300 mm/das) dan Sangat Tinggi (>300 mm/das) tercatat di Kab. Manokwari, "
            "Kaimana, dan Pegunungan Arfak."
        )
    },

    # ---- 7. Analisis + Sifat Hujan + Bulanan ----
    ('Analisis', 'Sifat Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan Agustus 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Normal): Normal: 54.3%, Atas Normal: 25.7%, Bawah Normal: 20.0%\n"
            "Papua Barat Daya (dominan: Normal): Normal: 42.6%, Bawah Normal: 34.0%, Atas Normal: 23.4%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Bawah Normal: Teluk Bintuni, Fak Fak, Maybrat\n"
            "Normal: Sorong, Raja Ampat, Teluk Wondama, Kaimana, Sorong Selatan\n"
            "Atas Normal: Manokwari, Pegunungan Arfak"
        ),
        "output": (
            "Analisis Sifat Hujan Bulan Agustus 2024 di Provinsi Papua Barat dan Papua Barat Daya "
            "umumnya didominasi sifat hujan Normal (85%-115%) sebesar 54.3% di Papua Barat dan 42.6% "
            "di Papua Barat Daya. Sifat hujan Atas Normal (>116%) tercatat di Kab. Manokwari dan "
            "Pegunungan Arfak, sedangkan sifat hujan Bawah Normal (0%-84%) tercatat di Kab. Teluk Bintuni, "
            "Fak Fak, dan Maybrat."
        )
    },

    # ---- 8. Analisis + Sifat Hujan + Dasarian ----
    ('Analisis', 'Sifat Hujan', 'Dasarian'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Dasarian I Agustus 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Normal): Normal: 57.1%, Atas Normal: 25.7%, Bawah Normal: 17.1%\n"
            "Papua Barat Daya (dominan: Normal): Normal: 51.1%, Bawah Normal: 27.7%, Atas Normal: 21.3%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Bawah Normal: Teluk Bintuni, Fak Fak\n"
            "Normal: Sorong, Raja Ampat, Teluk Wondama, Maybrat, Kaimana\n"
            "Atas Normal: Manokwari, Pegunungan Arfak"
        ),
        "output": (
            "Analisis Sifat Hujan Dasarian I Agustus 2024 (1 - 10 Agustus 2024) di Provinsi "
            "Papua Barat dan Papua Barat Daya umumnya didominasi sifat hujan Normal (85%-115%) sebesar "
            "57.1% di Papua Barat dan 51.1% di Papua Barat Daya. Sifat hujan Bawah Normal (0%-84%) "
            "tercatat di Kab. Teluk Bintuni dan Fak Fak, sedangkan sifat hujan Atas Normal (>116%) "
            "tercatat di Kab. Manokwari dan Pegunungan Arfak."
        )
    },

    # ---- 9. Verifikasi + Curah Hujan ----
    ('Verifikasi', 'Curah Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan September 2024\n"
            "Metrik: PC=45.30%, HSS=1.20%, PSS=12.00%\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Tidak Sesuai): Tidak Sesuai: 57.1%, Sesuai: 42.9%\n"
            "Papua Barat Daya (dominan: Tidak Sesuai): Tidak Sesuai: 59.6%, Sesuai: 40.4%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Tidak Sesuai: Manokwari, Pegunungan Arfak, Teluk Bintuni, Kaimana, Fak Fak\n"
            "Sesuai: Sorong, Maybrat, Raja Ampat, Teluk Wondama"
        ),
        "output": (
            "Verifikasi Prakiraan Curah Hujan Bulan September 2024 di Provinsi Papua Barat dan "
            "Papua Barat Daya menunjukkan hasil yang umumnya Tidak Sesuai sebesar 57.1% di Papua Barat "
            "dan 59.6% di Papua Barat Daya. Beberapa wilayah dengan kesesuaian lebih tinggi antara lain "
            "Kab. Sorong, Maybrat, Raja Ampat, dan Teluk Wondama. Akurasi keseluruhan (PC) mencapai "
            "45.30%, HSS sebesar 1.20%, dan PSS sebesar 12.00%."
        )
    },

    # ---- 10. Verifikasi + Sifat Hujan ----
    ('Verifikasi', 'Sifat Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan September 2024\n"
            "Metrik: PC=52.14%, HSS=8.30%, PSS=15.00%\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Sesuai): Sesuai: 57.1%, Tidak Sesuai: 42.9%\n"
            "Papua Barat Daya (dominan: Sesuai): Sesuai: 57.4%, Tidak Sesuai: 42.6%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Tidak Sesuai: Teluk Bintuni, Fak Fak, Kaimana\n"
            "Sesuai: Manokwari, Sorong, Raja Ampat, Pegunungan Arfak, Maybrat"
        ),
        "output": (
            "Verifikasi Prakiraan Sifat Hujan Bulan September 2024 di Provinsi Papua Barat dan "
            "Papua Barat Daya menunjukkan hasil yang umumnya Sesuai sebesar 57.1% di Papua Barat dan "
            "57.4% di Papua Barat Daya. Beberapa wilayah yang menunjukkan ketidaksesuaian antara lain "
            "Kab. Teluk Bintuni, Fak Fak, dan Kaimana. Akurasi keseluruhan (PC) mencapai 52.14%, "
            "HSS sebesar 8.30%, dan PSS sebesar 15.00%."
        )
    },

    # ---- 11. Probabilistik + Curah Hujan ----
    ('Probabilistik', 'Curah Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan Januari 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Tinggi): Tinggi: 50.0%, Sangat Tinggi: 42.9%, Menengah: 7.1%\n"
            "Papua Barat Daya (dominan: Tinggi): Tinggi: 53.2%, Sangat Tinggi: 40.4%, Menengah: 6.4%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Menengah: Sorong, Sorong Selatan\n"
            "Tinggi: Raja Ampat, Teluk Wondama, Fak Fak, Maybrat, Teluk Bintuni\n"
            "Sangat Tinggi: Manokwari, Pegunungan Arfak, Kaimana"
        ),
        "output": (
            "Prakiraan Probabilistik Curah Hujan Bulan Januari 2024 di Provinsi Papua Barat dan "
            "Papua Barat Daya umumnya didominasi curah hujan Tinggi (300-500 mm) sebesar 50.0% di "
            "Papua Barat dan 53.2% di Papua Barat Daya. Curah hujan Sangat Tinggi (>500 mm) "
            "diprakirakan terjadi di Kab. Manokwari, Pegunungan Arfak, dan Kaimana, sedangkan curah "
            "hujan Menengah (100-300 mm) diprakirakan di Kab. Sorong dan Sorong Selatan."
        )
    },

    # ---- 12. Bias + Curah Hujan ----
    ('Bias', 'Curah Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan September 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Menengah): Menengah: 42.9%, Rendah: 28.6%, Tinggi: 21.4%, Sangat Tinggi: 7.1%\n"
            "Papua Barat Daya (dominan: Rendah): Rendah: 38.3%, Menengah: 31.9%, Tinggi: 21.3%, Sangat Tinggi: 8.5%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Rendah: Sorong, Sorong Selatan, Fak Fak\n"
            "Menengah: Raja Ampat, Teluk Wondama, Maybrat, Teluk Bintuni\n"
            "Tinggi: Manokwari, Kaimana\n"
            "Sangat Tinggi: Pegunungan Arfak"
        ),
        "output": (
            "Bias Curah Hujan Bulan September 2024 di Provinsi Papua Barat didominasi kategori "
            "Menengah sebesar 42.9%, sementara Papua Barat Daya didominasi kategori Rendah sebesar "
            "38.3%. Bias yang lebih tinggi tercatat di Kab. Manokwari, Kaimana, dan Pegunungan Arfak, "
            "sedangkan bias Rendah tercatat di Kab. Sorong, Sorong Selatan, dan Fak Fak."
        )
    },

    # ---- 13. Normal + Curah Hujan ----
    ('Normal', 'Curah Hujan', 'Bulanan'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Bulan September (Rata-rata 1991-2020)\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: Menengah): Menengah: 50.0%, Tinggi: 31.4%, Rendah: 11.4%, Sangat Tinggi: 7.1%\n"
            "Papua Barat Daya (dominan: Menengah): Menengah: 42.6%, Tinggi: 27.7%, Rendah: 21.3%, Sangat Tinggi: 8.5%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "Rendah: Sorong Selatan\n"
            "Menengah: Sorong, Raja Ampat, Teluk Wondama, Maybrat, Fak Fak, Teluk Bintuni\n"
            "Tinggi: Manokwari, Kaimana\n"
            "Sangat Tinggi: Pegunungan Arfak"
        ),
        "output": (
            "Normal Curah Hujan Bulan September berdasarkan rata-rata periode 1991-2020 di Provinsi "
            "Papua Barat dan Papua Barat Daya umumnya pada kategori Menengah (100-300 mm) sebesar "
            "50.0% di Papua Barat dan 42.6% di Papua Barat Daya. Curah hujan normal Tinggi (300-500 mm) "
            "dan Sangat Tinggi (>500 mm) tercatat di Kab. Manokwari, Kaimana, dan Pegunungan Arfak, "
            "sedangkan curah hujan normal Rendah (0-100 mm) di Kab. Sorong Selatan."
        )
    },

    # ---- 14. HTH ----
    ('HTH', None, 'Dasarian'): {
        "input": (
            "Wilayah: Papua Barat dan Papua Barat Daya\n"
            "Periode: Update Dasarian I September 2024\n"
            "=== PROVINSI ===\n"
            "Papua Barat (dominan: 1-5): 1-5: 42.6%, 6-10: 31.9%, 11-20: 17.0%, 21-30: 6.4%, >30: 2.1%\n"
            "Papua Barat Daya (dominan: 1-5): 1-5: 42.9%, 6-10: 34.3%, 11-20: 17.1%, 21-30: 5.7%\n"
            "=== KABUPATEN PER KATEGORI ===\n"
            "1-5: Manokwari, Raja Ampat, Teluk Wondama, Fak Fak\n"
            "6-10: Pegunungan Arfak, Maybrat, Teluk Bintuni, Kaimana\n"
            "11-20: Manokwari Selatan\n"
            "21-30: Sorong\n"
            ">30: Sorong Selatan"
        ),
        "output": (
            "Monitoring Hari Tanpa Hujan Berturut-turut Update Dasarian I September 2024 di Provinsi "
            "Papua Barat dan Papua Barat Daya umumnya pada kategori 1-5 hari sebesar 42.6% di Papua "
            "Barat dan 42.9% di Papua Barat Daya. Hari tanpa hujan yang lebih panjang (21-30 hari dan "
            ">30 hari) perlu mendapat perhatian di Kab. Sorong dan Sorong Selatan."
        )
    },
}


# =============================================================================
# PROMPT HELPERS
# =============================================================================

def _build_periode(map_data):
    """Build human-readable period string from map_data."""
    peta = map_data['peta']
    skala = map_data.get('skala', '')
    month = map_data['month']
    year = map_data['year']
    bulan = number_to_bulan(month)

    if peta == 'HTH':
        return (
            f"Update Dasarian {dasarian_romawi(map_data['dasarian_ver'])} "
            f"{number_to_bulan(map_data['month_ver'])} {map_data['year_ver']}"
        )
    if skala == 'Dasarian':
        return f"Dasarian {dasarian_romawi(map_data['dasarian'])} {bulan} {year}"
    if peta == 'Normal':
        return f"Bulan {bulan} (Rata-rata 1991-2020)"
    return f"Bulan {bulan} {year}"


def _resolve_example_key(peta, tipe, skala):
    """Map (peta, tipe, skala) to the correct EXAMPLE_PAIRS key."""
    if peta == 'HTH':
        return ('HTH', None, 'Dasarian')
    if peta == 'Verifikasi':
        return (peta, tipe, 'Bulanan')
    return (peta, tipe, skala)


def _resolve_cat_defs(peta, tipe, skala):
    """Resolve category definitions for the prompt."""
    if peta == 'HTH':
        return CATEGORY_DEFS.get(('HTH', 'Dasarian'), "")
    if peta == 'Verifikasi':
        return CATEGORY_DEFS.get(('Verifikasi', skala), {})
    if peta in ('Bias', 'Probabilistik', 'Normal'):
        return CATEGORY_DEFS.get((peta, skala), "")
    return CATEGORY_DEFS.get((tipe, skala), {})


def _build_input_text(nama_wilayah, periode, pct_text, metrik_str=""):
    """Assemble the input block for the prompt."""
    lines = [
        f"Wilayah: {nama_wilayah}",
        f"Periode: {periode}",
    ]
    if metrik_str:
        lines.append(metrik_str)
    lines.append(pct_text)
    return "\n".join(lines)


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def get_analysis(map_data):
    """Generate AI narration for a BMKG map.

    Args:
        map_data: dict returned by execute() or overlay_image(), must contain
                  'province_data', 'kabupaten_data', and map metadata.

    Returns:
        str: Generated narration paragraph in Bahasa Indonesia.
    """
    try:
        from google import genai
    except ImportError:
        import subprocess
        status_update("Installing google-genai...")
        subprocess.check_call(['pip', 'install', 'google-genai', '-q'])
        from google import genai
    api_key = cfg.gemini_api_key
    if not api_key:
        raise ValueError("Gemini API key not configured.")
    client = genai.Client(api_key=api_key)
    status_update("Generating AI narration")

    peta = map_data['peta']
    tipe = map_data['tipe']
    skala = map_data['skala']
    nama_wilayah = map_data['nama_wilayah']

    # --- Guard: Probabilistik has no count data ---
    if peta == 'Probabilistik':
        if map_data.get('province_data') is None:
            return "Narasi otomatis tidak tersedia untuk peta Probabilistik."

    # --- Guard: missing data ---
    if map_data.get('province_data') is None or map_data.get('kabupaten_data') is None:
        return "Narasi otomatis tidak tersedia: data provinsi/kabupaten tidak ditemukan."

    # --- Pre-compute percentages ---
    pct_data = _compute_all_percentages(
        map_data['province_data'],
        map_data['kabupaten_data']
    )
    pct_text = _format_percentages(pct_data)

    # --- Metrics for verifikasi ---
    metrik_str = ""
    if peta == 'Verifikasi':
        metrik_str = (
            f"Metrik: PC={map_data['accuracy']:.2%}, "
            f"HSS={map_data['hss']:.2%}, "
            f"PSS={map_data['pss']:.2%}"
        )

    # --- Build current input text ---
    periode = _build_periode(map_data)
    current_input = _build_input_text(nama_wilayah, periode, pct_text, metrik_str)

    # --- Resolve example ---
    example_key = _resolve_example_key(peta, tipe, skala)
    example = EXAMPLE_PAIRS.get(example_key)
    if example is None:
        example = EXAMPLE_PAIRS.get((peta, tipe, 'Bulanan'))
    if example is None:
        return f"Narasi otomatis tidak tersedia: tidak ada contoh untuk {peta}, {tipe}, {skala}."

    # --- Resolve category defs ---
    cat_defs = _resolve_cat_defs(peta, tipe, skala)
    cat_str = json.dumps(cat_defs, ensure_ascii=False) if isinstance(cat_defs, dict) else cat_defs

    # --- Build prompt ---
    prompt = (
        "Kamu penulis narasi peta BMKG. "
        "Tulis narasi SINGKAT (2-3 kalimat) dengan STRUKTUR dan GAYA yang IDENTIK dengan contoh.\n"
        "ATURAN:\n"
        "- Kalimat pertama: sebutkan dominan kategori per provinsi dengan RENTANG NILAI dan PERSENTASE.\n"
        "- Kalimat berikutnya: sebutkan nama kabupaten untuk kategori non-dominan, TANPA persentase.\n"
        "- Sebutkan SEMUA kategori yang ada di data kabupaten, terutama kategori ekstrem.\n"
        "- Gunakan angka persentase PERSIS dari data, jangan hitung ulang.\n"
        "- Tulis teks polos tanpa formatting (tanpa bold, italic, bullet, heading).\n\n"
        f"Definisi kategori: {cat_str}\n\n"
        f"=== CONTOH ===\nInput:\n{example['input']}\n\nOutput:\n{example['output']}\n=== AKHIR CONTOH ===\n\n"
        f"=== DATA BARU ===\nInput:\n{current_input}\n\nOutput:"
    )

    # --- Generate ---
    def _generate():
        return client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=prompt
        )
    response = _call_with_retry(_generate)
    status_update("AI narration complete")
    return response.text


def get_visual_interpretation(map_data, analysis_text=None):
    """Generate a freeform visual interpretation of a BMKG map image using Gemini.

    Args:
        map_data: dict returned by execute() or overlay_image(), must contain
                  'image' (PIL Image).

    Returns:
        str: Freeform analytical interpretation in Bahasa Indonesia.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        import subprocess
        status_update("Installing google-genai...")
        subprocess.check_call(['pip', 'install', 'google-genai', '-q'])
        from google import genai
        from google.genai import types
    api_key = cfg.gemini_api_key
    if not api_key:
        raise ValueError("Gemini API key not configured.")
    client = genai.Client(api_key=api_key)

    # --- Guard: missing image ---
    if map_data.get('image') is None:
        return "Interpretasi visual tidak tersedia: gambar peta tidak ditemukan."

    status_update("Generating visual interpretation")

    # Convert PIL Image to PNG bytes
    import io
    buf = io.BytesIO()
    map_data['image'].save(buf, format='PNG')
    image_bytes = buf.getvalue()

    # Build grounding data from count_points to reduce hallucination
    grounding = ""
    if map_data.get('province_data') and map_data.get('kabupaten_data'):
        pct_data = _compute_all_percentages(
            map_data['province_data'],
            map_data['kabupaten_data']
        )
        grounding = (
            "\n\nBerikut data statistik aktual sebagai referensi (GUNAKAN angka ini, "
            "JANGAN mengarang angka sendiri):\n"
            + _format_percentages(pct_data)
        )

    # Include prior analysis text so Gemini avoids repeating it
    prior_context = ""
    if analysis_text:
        prior_context = (
            "\n\nBerikut adalah narasi analisis yang SUDAH ditulis sebelumnya. "
            "JANGAN ulangi informasi yang sudah disebutkan di narasi ini. "
            "Tulislah kalimat yang MELENGKAPI narasi berikut, fokus pada pola spasial "
            "yang BELUM disebutkan:\n"
            f'"""{analysis_text}"""'
        )

    prompt = (
        "Kamu adalah analis cuaca BMKG. "
        "Perhatikan gambar peta berikut dan berikan interpretasi visual SINGKAT dalam Bahasa Indonesia. "
        "HANYA 1-2 kalimat saja yang menjelaskan pola spasial utama yang terlihat di peta. "
        "Kalimat harus bisa langsung menyambung narasi sebelumnya tanpa pengulangan periode atau judul. "
        "JANGAN mengarang angka atau persentase yang tidak ada dalam data referensi. "
        "JANGAN ulangi kategori, persentase, atau nama wilayah yang sudah disebutkan di narasi sebelumnya. "
        "JANGAN gunakan formatting apapun (tanpa bold, italic, bullet, heading, asterisk). "
        "Tulis dalam teks polos, singkat, dan padat."
        + grounding
        + prior_context
    )

    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    def _generate():
        return client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=[prompt, image_part]
        )
    response = _call_with_retry(_generate)
    status_update("Visual interpretation complete")
    return response.text


def get_full_narration(map_data):
    """Generate complete narration for a BMKG map.

    Combines structured AI analysis with freeform visual interpretation
    of the map image.

    Args:
        map_data: dict returned by execute() or overlay_image().

    Returns:
        str: Combined narration paragraph (analysis + visual interpretation).
    """
    analysis = get_analysis(map_data)
    visual = get_visual_interpretation(map_data, analysis_text=analysis)

    if visual and not visual.startswith("Interpretasi visual tidak tersedia"):
        return f"{analysis} {visual}"
    return analysis


# =============================================================================
# TABLE DATA GENERATION
# =============================================================================

def build_table_data(map_data):
    """Build table data for the Word document report.

    For standard maps (CH, SH, Verifikasi, etc.): produces a KRITERIA vs DAERAH
    table where each row is a category and its associated kabupaten list.

    For HTH maps: produces a station-level table with Provinsi, Kabupaten,
    optional Kecamatan/Pos, and the HTH classification name.

    Skips table for Probabilistik maps and kabupaten-level wilayah.

    Args:
        map_data: dict returned by overlay_image().

    Returns:
        dict with 'columns' (list[str]) and 'rows' (list[list[str]]),
        or None if no table should be generated.
    """
    peta = map_data.get('peta')

    # Skip for Probabilistik
    if peta == 'Probabilistik':
        return None

    # Skip if wilayah is kabupaten-level (no meaningful sub-breakdown)
    nama_wilayah = map_data.get('nama_wilayah', '')
    if 'Provinsi' not in nama_wilayah:
        return None

    if peta == 'HTH':
        return _build_hth_table(map_data)
    return _build_kriteria_table(map_data)


def _kriteria_column_name(peta, tipe):
    """Determine the KRITERIA column header based on map/data type."""
    if peta == 'Verifikasi':
        return 'Verifikasi'
    if tipe == 'Curah Hujan':
        return 'Curah Hujan (mm)'
    if tipe == 'Sifat Hujan':
        return 'Sifat Hujan (%)'
    return tipe or 'Kriteria'


def _build_kriteria_table(map_data):
    """Build KRITERIA vs DAERAH table for standard (non-HTH) maps.

    Each kabupaten is assigned to its *dominant* category (the category with the
    highest station count).  Rows follow the original category order from
    count_points so that the table reads from low → high severity.
    """
    kabupaten_data = map_data.get('kabupaten_data')
    if not kabupaten_data:
        return None

    peta = map_data.get('peta')
    tipe = map_data.get('tipe')
    col_name = _kriteria_column_name(peta, tipe)

    # Classify each kabupaten by dominant category
    category_to_kabs = {}
    for kab_name, counts in kabupaten_data.items():
        if counts.get('total', 0) == 0:
            continue
        dominant = max(
            ((cat, cnt) for cat, cnt in counts.items() if cat != 'total'),
            key=lambda x: x[1],
        )[0]
        category_to_kabs.setdefault(dominant, []).append(kab_name)

    if not category_to_kabs:
        return None

    # Preserve original category order from the first kabupaten's count dict
    first_counts = next(iter(kabupaten_data.values()))
    cat_order = [k for k in first_counts if k != 'total']

    rows = []
    for cat in cat_order:
        kabs = category_to_kabs.get(cat)
        if kabs:
            rows.append([cat, ', '.join(sorted(kabs))])

    # Include any extra categories not present in the original order
    for cat, kabs in category_to_kabs.items():
        if cat not in cat_order:
            rows.append([cat, ', '.join(sorted(kabs))])

    if not rows:
        return None

    return {
        'columns': [col_name, 'Daerah'],
        'rows': rows,
    }


def _build_hth_table(map_data):
    """Return pre-computed HTH table data (built in map_creation.py)."""
    return map_data.get('hth_table_data')
