# narasi.py
"""
AI-generated map captions using Gemini.
Pre-computes percentages from count_points data to minimize token usage.
"""

import json

from .utils import number_to_bulan, dasarian_romawi, dasarian_to_date
from .config import cfg
from .status import update as status_update


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
    """Group kabupaten by their dominant category.

    Returns formatted string listing kabupaten names under each category.
    """
    groups = {}
    for kab_name, pcts in kabupaten_pcts.items():
        if not pcts:
            continue
        dominant = pcts[0][0]
        groups.setdefault(dominant, []).append(kab_name)

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
            "Rendah: Sorong Selatan\n"
            "Menengah: Sorong, Raja Ampat, Teluk Wondama, Maybrat, Fak Fak\n"
            "Tinggi: Manokwari, Manokwari Selatan, Teluk Bintuni, Kaimana\n"
            "Sangat Tinggi: Pegunungan Arfak"
        ),
        "output": (
            "Prakiraan Curah Hujan Bulan September 2024 di Provinsi Papua Barat didominasi curah hujan "
            "Tinggi (300-500 mm) sebesar 50.0%, sementara Papua Barat Daya didominasi Menengah (100-300 mm) "
            "sebesar 42.6%. Curah hujan Sangat Tinggi (>500 mm) diprakirakan terjadi di Kab. Pegunungan Arfak, "
            "sedangkan curah hujan Rendah (0-100 mm) diprakirakan di Kab. Sorong Selatan."
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
            "Rendah: Sorong Selatan\n"
            "Menengah: Sorong, Raja Ampat, Teluk Wondama, Fak Fak\n"
            "Tinggi: Manokwari, Teluk Bintuni, Kaimana\n"
            "Sangat Tinggi: Pegunungan Arfak, Manokwari Selatan"
        ),
        "output": (
            "Analisis Curah Hujan Bulan Agustus 2024 di Provinsi Papua Barat dan Papua Barat Daya "
            "umumnya didominasi curah hujan Menengah (100-300 mm) sebesar 42.9% di Papua Barat dan "
            "38.3% di Papua Barat Daya. Curah hujan Tinggi (300-500 mm) dan Sangat Tinggi (>500 mm) "
            "tercatat di Kab. Manokwari, Pegunungan Arfak, dan Manokwari Selatan, sedangkan curah hujan "
            "Rendah (0-100 mm) tercatat di Kab. Sorong Selatan."
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
        import google.generativeai as genai
    except ImportError:
        import subprocess
        status_update("Installing google-generativeai...")
        subprocess.check_call(['pip', 'install', 'google-generativeai', '-q'])
        import google.generativeai as genai
    from google.colab import userdata
    genai.configure(api_key=userdata.get('GEMINI_API_KEY'))
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
        "- Gunakan angka persentase PERSIS dari data, jangan hitung ulang.\n"
        "- Tulis teks polos tanpa formatting (tanpa bold, italic, bullet, heading).\n\n"
        f"Definisi kategori: {cat_str}\n\n"
        f"=== CONTOH ===\nInput:\n{example['input']}\n\nOutput:\n{example['output']}\n=== AKHIR CONTOH ===\n\n"
        f"=== DATA BARU ===\nInput:\n{current_input}\n\nOutput:"
    )

    # --- Generate ---
    model = genai.GenerativeModel('gemini-3-flash-preview')
    response = model.generate_content(prompt)
    status_update("AI narration complete")
    return response.text


def get_full_narration(map_data):
    """Generate narration for a BMKG map.

    Args:
        map_data: dict returned by execute() or overlay_image().

    Returns:
        str: Narration paragraph.
    """
    return get_analysis(map_data)
