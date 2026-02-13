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
    ('Curah Hujan', 'Dasarian'): {"Rendah": "0-50 mm", "Menengah": "50-150 mm", "Tinggi": "150-300 mm", "Sangat Tinggi": ">300 mm"},
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


def _find_outlier_kabupaten(province_pcts, kabupaten_pcts, max_outliers=3, min_deviation=15.0):
    """Identify kabupaten whose distribution deviates significantly from province pattern.

    Returns list of (kab_name, percentages) for at most max_outliers kabupaten,
    prioritized by: (1) different dominant category from any province, then
    (2) largest deviation in dominant % from the province's dominant %.
    """
    prov_dominants = {}
    for prov_name, pcts in province_pcts.items():
        if pcts:
            prov_dominants[pcts[0][0]] = max(
                prov_dominants.get(pcts[0][0], 0), pcts[0][1]
            )

    outliers = []
    for kab_name, pcts in kabupaten_pcts.items():
        if not pcts:
            continue
        kab_dominant = pcts[0][0]
        kab_pct = pcts[0][1]

        if kab_dominant not in prov_dominants:
            outliers.append((kab_name, pcts, 100.0))
        else:
            deviation = abs(kab_pct - prov_dominants[kab_dominant])
            if deviation >= min_deviation:
                outliers.append((kab_name, pcts, deviation))

    outliers.sort(key=lambda x: -x[2])
    return [(name, pcts) for name, pcts, _ in outliers[:max_outliers]]


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

    outliers = _find_outlier_kabupaten(pct_data['provinsi'], pct_data['kabupaten'])
    if outliers:
        lines.append("=== KABUPATEN MENONJOL ===")
        for kab_name, pcts in outliers:
            pct_str = ", ".join([f"{cat}: {val}%" for cat, val in pcts])
            lines.append(f"{kab_name} (dominan: {pcts[0][0]}): {pct_str}")

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
            "=== KABUPATEN MENONJOL ===\n"
            "Pegunungan Arfak (dominan: Tinggi): Tinggi: 50.0%, Sangat Tinggi: 40.0%, Menengah: 10.0%\n"
            "Sorong (dominan: Menengah): Menengah: 53.3%, Tinggi: 33.3%, Rendah: 13.3%"
        ),
        "output": (
            "Pada bulan September 2024, umumnya prakiraan curah hujan di Papua Barat pada kategori "
            "Tinggi yaitu sejumlah 50.0%, dan sisanya mengalami curah hujan kategori Menengah yaitu "
            "sejumlah 35.7%, kategori Sangat Tinggi sejumlah 10.0%, dan kategori Rendah sejumlah 4.3%. "
            "Sementara itu, di Papua Barat Daya umumnya pada kategori Menengah yaitu sejumlah 42.6%, "
            "kategori Tinggi sejumlah 38.3%, kategori Rendah sejumlah 10.6%, dan kategori Sangat Tinggi "
            "sejumlah 8.5%. Secara khusus, Kab. Pegunungan Arfak diprakirakan mengalami curah hujan "
            "dengan kategori Sangat Tinggi mencapai 40.0%. Kab. Sorong diprakirakan didominasi curah "
            "hujan kategori Menengah sejumlah 53.3%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Menengah): Menengah: 44.4%, Tinggi: 38.9%, Sangat Tinggi: 11.1%, Rendah: 5.6%"
        ),
        "output": (
            "Pada dasarian I September 2024, umumnya prakiraan curah hujan di Papua Barat pada kategori "
            "Menengah yaitu sejumlah 46.2%, dan sisanya mengalami curah hujan kategori Tinggi yaitu "
            "sejumlah 30.8%, kategori Rendah sejumlah 15.4%, dan kategori Sangat Tinggi sejumlah 7.7%. "
            "Sementara itu, di Papua Barat Daya umumnya pada kategori Menengah yaitu sejumlah 48.9%, "
            "kategori Tinggi sejumlah 26.7%, kategori Rendah sejumlah 17.8%, dan kategori Sangat Tinggi "
            "sejumlah 6.7%. Secara khusus, Kab. Manokwari diprakirakan memiliki curah hujan yang lebih "
            "tinggi dibandingkan wilayah lain dengan kategori Tinggi mencapai 38.9%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Atas Normal): Atas Normal: 55.6%, Normal: 44.4%\n"
            "Teluk Bintuni (dominan: Bawah Normal): Bawah Normal: 57.1%, Normal: 28.6%, Atas Normal: 14.3%"
        ),
        "output": (
            "Pada bulan September 2024, prakiraan sifat hujan di Papua Barat umumnya didominasi "
            "kategori Normal yaitu sejumlah 57.1%, dan sisanya kategori Atas Normal sejumlah 25.7%, "
            "dan kategori Bawah Normal sejumlah 17.1%. Sementara itu, di Papua Barat Daya umumnya "
            "pada kategori Normal yaitu sejumlah 46.8%, kategori Bawah Normal sejumlah 31.9%, dan "
            "kategori Atas Normal sejumlah 21.3%. Secara khusus, Kab. Manokwari diprakirakan memiliki "
            "sifat hujan Atas Normal yang dominan sejumlah 55.6%. Kab. Teluk Bintuni diprakirakan "
            "memiliki sifat hujan Bawah Normal yang dominan sejumlah 57.1%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Teluk Bintuni (dominan: Bawah Normal): Bawah Normal: 50.0%, Normal: 35.7%, Atas Normal: 14.3%"
        ),
        "output": (
            "Pada dasarian II September 2024, prakiraan sifat hujan di Papua Barat umumnya didominasi "
            "kategori Normal yaitu sejumlah 60.0%, dan sisanya kategori Atas Normal sejumlah 25.7%, "
            "dan kategori Bawah Normal sejumlah 14.3%. Sementara itu, di Papua Barat Daya umumnya "
            "pada kategori Normal yaitu sejumlah 53.2%, kategori Bawah Normal sejumlah 29.8%, dan "
            "kategori Atas Normal sejumlah 17.0%. Secara khusus, Kab. Teluk Bintuni diprakirakan "
            "memiliki sifat hujan Bawah Normal yang dominan sejumlah 50.0%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Tinggi): Tinggi: 55.6%, Sangat Tinggi: 22.2%, Menengah: 22.2%\n"
            "Sorong (dominan: Menengah): Menengah: 53.3%, Tinggi: 20.0%, Rendah: 20.0%, Sangat Tinggi: 6.7%"
        ),
        "output": (
            "Pada bulan Agustus 2024, umumnya analisis curah hujan di Papua Barat tercatat pada kategori "
            "Menengah yaitu sejumlah 42.9%, dan sisanya mengalami curah hujan kategori Tinggi yaitu "
            "sejumlah 40.0%, kategori Sangat Tinggi sejumlah 10.0%, dan kategori Rendah sejumlah 7.1%. "
            "Sementara itu, di Papua Barat Daya umumnya pada kategori Menengah yaitu sejumlah 38.3%, "
            "kategori Tinggi sejumlah 34.0%, kategori Rendah sejumlah 17.0%, dan kategori Sangat Tinggi "
            "sejumlah 10.6%. Secara khusus, Kab. Manokwari tercatat mengalami curah hujan yang lebih "
            "tinggi dengan kategori Tinggi mencapai 55.6% dan Sangat Tinggi mencapai 22.2%. Kab. Sorong "
            "tercatat didominasi curah hujan kategori Menengah sejumlah 53.3%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Menengah): Menengah: 38.9%, Tinggi: 33.3%, Sangat Tinggi: 16.7%, Rendah: 11.1%"
        ),
        "output": (
            "Pada dasarian III Agustus 2024, umumnya analisis curah hujan di Papua Barat tercatat pada "
            "kategori Menengah yaitu sejumlah 43.1%, dan sisanya mengalami curah hujan kategori Tinggi "
            "yaitu sejumlah 27.7%, kategori Rendah sejumlah 23.1%, dan kategori Sangat Tinggi sejumlah "
            "6.2%. Sementara itu, di Papua Barat Daya umumnya pada kategori Menengah yaitu sejumlah "
            "44.4%, kategori Rendah sejumlah 26.7%, kategori Tinggi sejumlah 22.2%, dan kategori Sangat "
            "Tinggi sejumlah 6.7%. Secara khusus, Kab. Manokwari tercatat mengalami curah hujan yang "
            "lebih tinggi dengan kategori Tinggi mencapai 33.3% dan Sangat Tinggi mencapai 16.7%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Atas Normal): Atas Normal: 55.6%, Normal: 38.9%, Bawah Normal: 5.6%\n"
            "Teluk Bintuni (dominan: Bawah Normal): Bawah Normal: 64.3%, Normal: 21.4%, Atas Normal: 14.3%"
        ),
        "output": (
            "Pada bulan Agustus 2024, analisis sifat hujan di Papua Barat umumnya didominasi kategori "
            "Normal yaitu sejumlah 54.3%, dan sisanya kategori Atas Normal sejumlah 25.7%, dan kategori "
            "Bawah Normal sejumlah 20.0%. Sementara itu, di Papua Barat Daya umumnya pada kategori "
            "Normal yaitu sejumlah 42.6%, kategori Bawah Normal sejumlah 34.0%, dan kategori Atas Normal "
            "sejumlah 23.4%. Secara khusus, Kab. Manokwari tercatat memiliki sifat hujan Atas Normal "
            "yang dominan sejumlah 55.6%. Kab. Teluk Bintuni tercatat memiliki sifat hujan Bawah Normal "
            "yang dominan sejumlah 64.3%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Normal): Normal: 50.0%, Atas Normal: 50.0%\n"
            "Teluk Bintuni (dominan: Bawah Normal): Bawah Normal: 57.1%, Normal: 28.6%, Atas Normal: 14.3%"
        ),
        "output": (
            "Pada dasarian I Agustus 2024, analisis sifat hujan di Papua Barat umumnya didominasi "
            "kategori Normal yaitu sejumlah 57.1%, dan sisanya kategori Atas Normal sejumlah 25.7%, "
            "dan kategori Bawah Normal sejumlah 17.1%. Sementara itu, di Papua Barat Daya umumnya "
            "pada kategori Normal yaitu sejumlah 51.1%, kategori Bawah Normal sejumlah 27.7%, dan "
            "kategori Atas Normal sejumlah 21.3%. Secara khusus, Kab. Manokwari tercatat memiliki "
            "sifat hujan Normal dan Atas Normal masing-masing sejumlah 50.0%. Kab. Teluk Bintuni "
            "tercatat memiliki sifat hujan Bawah Normal yang dominan sejumlah 57.1%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Sorong (dominan: Sesuai): Sesuai: 66.7%, Tidak Sesuai: 33.3%\n"
            "Maybrat (dominan: Sesuai): Sesuai: 66.7%, Tidak Sesuai: 33.3%\n"
            "Manokwari (dominan: Tidak Sesuai): Tidak Sesuai: 66.7%, Sesuai: 33.3%"
        ),
        "output": (
            "Pada bulan September 2024, hasil verifikasi prakiraan curah hujan di Papua Barat "
            "menunjukkan kategori Tidak Sesuai sejumlah 57.1% dan Sesuai sejumlah 42.9%. "
            "Sementara itu, di Papua Barat Daya kategori Tidak Sesuai sejumlah 59.6% dan "
            "Sesuai sejumlah 40.4%. Beberapa wilayah yang menunjukkan kesesuaian lebih tinggi "
            "antara lain Kab. Sorong dan Kab. Maybrat dengan kategori Sesuai masing-masing "
            "sejumlah 66.7%. Sebaliknya, Kab. Manokwari menunjukkan ketidaksesuaian yang lebih "
            "tinggi dengan kategori Tidak Sesuai sejumlah 66.7%. Akurasi keseluruhan (Percent "
            "Correct) mencapai 45.30%, Heidke Skill Score (HSS) sebesar 1.20%, dan Peirce Skill "
            "Score (PSS) sebesar 12.00%, mengindikasikan bahwa model memiliki kemampuan yang hanya "
            "sedikit lebih baik dibandingkan prakiraan acak."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Sesuai): Sesuai: 66.7%, Tidak Sesuai: 33.3%\n"
            "Teluk Bintuni (dominan: Tidak Sesuai): Tidak Sesuai: 64.3%, Sesuai: 35.7%"
        ),
        "output": (
            "Pada bulan September 2024, hasil verifikasi prakiraan sifat hujan di Papua Barat "
            "menunjukkan kategori Sesuai sejumlah 57.1% dan Tidak Sesuai sejumlah 42.9%. "
            "Sementara itu, di Papua Barat Daya kategori Sesuai sejumlah 57.4% dan Tidak Sesuai "
            "sejumlah 42.6%. Secara khusus, Kab. Manokwari menunjukkan kesesuaian yang lebih tinggi "
            "dengan kategori Sesuai sejumlah 66.7%. Sebaliknya, Kab. Teluk Bintuni menunjukkan "
            "ketidaksesuaian yang lebih tinggi dengan kategori Tidak Sesuai sejumlah 64.3%. "
            "Akurasi keseluruhan (Percent Correct) mencapai 52.14%, Heidke Skill Score (HSS) "
            "sebesar 8.30%, dan Peirce Skill Score (PSS) sebesar 15.00%, mengindikasikan bahwa "
            "model memiliki kemampuan yang sedikit lebih baik dibandingkan prakiraan acak."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Sangat Tinggi): Sangat Tinggi: 55.6%, Tinggi: 44.4%\n"
            "Pegunungan Arfak (dominan: Tinggi): Tinggi: 40.0%, Sangat Tinggi: 40.0%, Menengah: 20.0%"
        ),
        "output": (
            "Pada bulan Januari 2024, prakiraan probabilistik curah hujan di Papua Barat umumnya "
            "pada kategori Tinggi yaitu sejumlah 50.0%, dan sisanya kategori Sangat Tinggi sejumlah "
            "42.9%, dan kategori Menengah sejumlah 7.1%. Sementara itu, di Papua Barat Daya umumnya "
            "pada kategori Tinggi yaitu sejumlah 53.2%, kategori Sangat Tinggi sejumlah 40.4%, dan "
            "kategori Menengah sejumlah 6.4%. Secara khusus, Kab. Manokwari memiliki peluang tertinggi "
            "dengan kategori Sangat Tinggi mencapai 55.6%. Kab. Pegunungan Arfak menunjukkan variasi "
            "yang lebih luas dengan kategori Menengah mencapai 20.0%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Sorong (dominan: Rendah): Rendah: 46.7%, Menengah: 33.3%, Tinggi: 13.3%, Sangat Tinggi: 6.7%"
        ),
        "output": (
            "Pada bulan September 2024, bias curah hujan di Papua Barat umumnya pada kategori "
            "Menengah yaitu sejumlah 42.9%, dan sisanya kategori Rendah sejumlah 28.6%, kategori "
            "Tinggi sejumlah 21.4%, dan kategori Sangat Tinggi sejumlah 7.1%. Sementara itu, "
            "di Papua Barat Daya umumnya pada kategori Rendah yaitu sejumlah 38.3%, kategori "
            "Menengah sejumlah 31.9%, kategori Tinggi sejumlah 21.3%, dan kategori Sangat Tinggi "
            "sejumlah 8.5%. Secara khusus, Kab. Sorong menunjukkan bias yang lebih rendah dengan "
            "kategori Rendah sejumlah 46.7%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Manokwari (dominan: Tinggi): Tinggi: 50.0%, Menengah: 33.3%, Sangat Tinggi: 16.7%"
        ),
        "output": (
            "Berdasarkan rata-rata periode 1991-2020, normal curah hujan bulan September di Papua Barat "
            "umumnya pada kategori Menengah yaitu sejumlah 50.0%, dan sisanya kategori Tinggi sejumlah "
            "31.4%, kategori Rendah sejumlah 11.4%, dan kategori Sangat Tinggi sejumlah 7.1%. "
            "Sementara itu, di Papua Barat Daya umumnya pada kategori Menengah yaitu sejumlah 42.6%, "
            "kategori Tinggi sejumlah 27.7%, kategori Rendah sejumlah 21.3%, dan kategori Sangat Tinggi "
            "sejumlah 8.5%. Secara khusus, Kab. Manokwari memiliki curah hujan normal yang lebih tinggi "
            "dengan kategori Tinggi mencapai 50.0% dan Sangat Tinggi mencapai 16.7%."
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
            "=== KABUPATEN MENONJOL ===\n"
            "Sorong (dominan: 6-10): 6-10: 30.8%, 1-5: 23.1%, 11-20: 23.1%, 21-30: 15.4%, >30: 7.7%"
        ),
        "output": (
            "Pada update dasarian I September 2024, monitoring hari tanpa hujan berturut-turut di "
            "Papua Barat menunjukkan kategori 1-5 hari yaitu sejumlah 42.6%, dan sisanya kategori "
            "6-10 hari sejumlah 31.9%, kategori 11-20 hari sejumlah 17.0%, kategori 21-30 hari "
            "sejumlah 6.4%, dan kategori >30 hari sejumlah 2.1%. Sementara itu, di Papua Barat Daya "
            "umumnya pada kategori 1-5 hari yaitu sejumlah 42.9%, kategori 6-10 hari sejumlah 34.3%, "
            "kategori 11-20 hari sejumlah 17.1%, dan kategori 21-30 hari sejumlah 5.7%. Secara khusus, "
            "Kab. Sorong perlu mendapat perhatian dengan hari tanpa hujan berturut-turut yang lebih "
            "panjang, termasuk kategori 21-30 hari sejumlah 15.4% dan >30 hari sejumlah 7.7%."
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
        "Tulis narasi untuk data baru dengan STRUKTUR KALIMAT, GAYA, dan ALUR yang IDENTIK dengan contoh. "
        "Hanya ganti data, wilayah, dan periode sesuai data baru. "
        "Gunakan semua angka persentase persis seperti yang diberikan, jangan hitung ulang.\n\n"
        f"Definisi kategori: {cat_str}\n\n"
        f"=== CONTOH ===\nInput:\n{example['input']}\n\nOutput:\n{example['output']}\n=== AKHIR CONTOH ===\n\n"
        f"=== DATA BARU ===\nInput:\n{current_input}\n\nOutput:"
    )

    # --- Generate ---
    model = genai.GenerativeModel('gemini-3-flash-preview')
    response = model.generate_content(prompt)
    status_update("AI narration complete")
    return response.text


def get_visual_interpretation(map_data):
    """Generate a freeform visual interpretation of a BMKG map image using Gemini.

    Args:
        map_data: dict returned by execute() or overlay_image(), must contain
                  'image' (PIL Image).

    Returns:
        str: Freeform analytical interpretation in Bahasa Indonesia.
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

    prompt = (
        "Kamu adalah analis cuaca BMKG. "
        "Perhatikan gambar peta berikut dan berikan interpretasi visual SINGKAT dalam Bahasa Indonesia. "
        "HANYA 1-2 kalimat saja yang menjelaskan pola spasial utama yang terlihat di peta. "
        "Kalimat harus bisa langsung menyambung narasi sebelumnya tanpa pengulangan periode atau judul. "
        "JANGAN mengarang angka atau persentase yang tidak ada dalam data referensi. "
        "JANGAN gunakan formatting apapun (tanpa bold, italic, bullet, heading, asterisk). "
        "Tulis dalam teks polos, singkat, dan padat."
        + grounding
    )

    model = genai.GenerativeModel('gemini-3-flash-preview')
    response = model.generate_content([prompt, {"mime_type": "image/png", "data": image_bytes}])
    status_update("Visual interpretation complete")
    return response.text


def get_full_narration(map_data):
    """Generate narration for a BMKG map.

    Args:
        map_data: dict returned by execute() or overlay_image().

    Returns:
        str: Narration paragraph.
    """
    return get_analysis(map_data)
