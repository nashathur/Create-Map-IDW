# narasi.py
"""
Map narration and Word table data.

The narration is hybrid: the opening sentence (period, dominant category and
its percentage per province) and the verification metrics are built in code,
so numbers are always exact. Gemini only writes the sentences naming
kabupaten per category; its output is checked and replaced by a template
sentence when it is missing, malformed or drops a kabupaten.

Narration and table use the same grouping (group_kabupaten) and the same
category scheme as count_points (utils.CATEGORY_SCHEMES), so they agree.
"""

import calendar
import re
import time

from .utils import number_to_bulan, dasarian_romawi, category_scheme
from .config import cfg
from .status import update as status_update


# =============================================================================
# MODEL FALLBACK CHAINS — tried in order on 429 RESOURCE_EXHAUSTED
# =============================================================================

ANALYSIS_MODELS = [
    'gemini-3-flash-preview',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
]

VISUAL_MODELS = [
    'gemini-3-flash-preview',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
]


# =============================================================================
# RETRY HELPER
# =============================================================================

def _is_rate_limited(e):
    """Check if exception is a 429 rate-limit / RESOURCE_EXHAUSTED error."""
    try:
        from google.genai.errors import ClientError
        if isinstance(e, ClientError) and '429' in str(e):
            return True
    except ImportError:
        pass
    err_str = str(e)
    return any(s in err_str for s in ('429', 'RESOURCE_EXHAUSTED'))


def _call_with_model_fallback(fn, models, max_retries=3, initial_delay=2.0):
    """Try fn(model) across a list of models, falling back on rate limits.

    - 5xx errors: retry with backoff within the same model
    - 429/RESOURCE_EXHAUSTED: move to next model immediately
    - Other errors: raise immediately

    Returns response on success, None if all models exhausted.
    """
    for model_idx, model in enumerate(models):
        delay = initial_delay
        for attempt in range(max_retries + 1):
            try:
                return fn(model)
            except Exception as e:
                if _is_rate_limited(e):
                    if model_idx < len(models) - 1:
                        status_update(
                            f"Rate limited on {model}, trying next model..."
                        )
                    else:
                        status_update(
                            f"Rate limited on {model} (last model)."
                        )
                    break  # Move to next model

                # Check for 5xx server error → retry with backoff
                is_server = False
                try:
                    from google.genai.errors import ServerError
                    if isinstance(e, ServerError):
                        is_server = True
                except ImportError:
                    err_str = str(e)
                    if any(c in err_str for c in ('500', '502', '503', '504', 'UNAVAILABLE')):
                        is_server = True

                if not is_server:
                    raise  # Client errors other than 429 → raise

                if attempt == max_retries:
                    # Exhausted retries for this model, try next
                    if model_idx < len(models) - 1:
                        status_update(f"Server errors on {model}, trying next model...")
                    break

                status_update(
                    f"API error on {model} (attempt {attempt + 1}/{max_retries + 1}), "
                    f"retrying in {delay:.0f}s..."
                )
                time.sleep(delay)
                delay = min(delay * 2, 60.0)

    return None  # All models exhausted


def _gemini_client():
    """Return (genai, types, client), installing google-genai if needed."""
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
    return genai, types, genai.Client(api_key=api_key)


# =============================================================================
# CATEGORIES AND GROUPING (shared by narration and table)
# =============================================================================

_NEAR_TIE_PP = 10.0      # also list a kabupaten under categories this close to its dominant one
_EXTREME_MIN_PCT = 5.0   # ... and under any extreme category holding at least this share


def _categories(map_data):
    """[(label, range_text, extreme), ...] in low → high order for this map."""
    scheme = category_scheme(map_data.get('peta'), map_data.get('tipe'), map_data.get('skala'))
    if scheme is not None:
        return scheme[1]
    counts = map_data.get('kabupaten_data') or map_data.get('province_data') or {}
    first = next(iter(counts.values()), {})
    return [(k, '', False) for k in first if k != 'total']


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


def _nice(name):
    """'Kabupaten SORONG DAN MAYBRAT' -> 'Kabupaten Sorong dan Maybrat'.

    Only all-caps words change, so already mixed-case words are kept.
    """
    words = [w.title() if w.isupper() else w for w in str(name).split()]
    return ' '.join('dan' if w == 'Dan' else w for w in words)


def group_kabupaten(kabupaten_data, categories):
    """Map each category label to the kabupaten listed under it.

    A kabupaten goes under its dominant category, under any category within
    _NEAR_TIE_PP percentage points of it, and under any extreme category
    holding at least _EXTREME_MIN_PCT of its points. Names are display-cased
    and sorted; every category of the scheme is a key, in scheme order.
    """
    extreme = {c[0] for c in categories if c[2]}
    groups = {c[0]: [] for c in categories}
    for kab in sorted(kabupaten_data, key=_nice):
        pcts = _counts_to_percentages(kabupaten_data[kab])
        if not pcts:
            continue
        top = pcts[0][1]
        for cat, pct in pcts:
            if top - pct <= _NEAR_TIE_PP or (cat in extreme and pct >= _EXTREME_MIN_PCT):
                groups.setdefault(cat, []).append(_nice(kab))
    return groups


# =============================================================================
# WORDING
# =============================================================================

def _map_title(peta, tipe):
    if peta == 'Verifikasi':
        return f"Verifikasi Prakiraan {tipe}"
    if peta == 'Normal':
        return "Normal Curah Hujan"
    if peta == 'Bias':
        return "Bias Curah Hujan"
    if peta == 'HTH':
        return "Monitoring Hari Tanpa Hujan Berturut-turut"
    if peta == 'Probabilistik':
        return "Prakiraan Probabilistik Curah Hujan"
    if tipe == 'SPI':
        return f"{peta} Indeks Presipitasi Terstandarisasi (SPI)"
    return f"{peta} {tipe}"


def _kind(peta, tipe):
    """Noun put before a category label: 'curah hujan Tinggi', 'kategori Netral'."""
    if peta in ('Prakiraan', 'Analisis', 'Normal', 'Probabilistik'):
        if tipe == 'Curah Hujan':
            return 'curah hujan'
        if tipe == 'Sifat Hujan':
            return 'sifat hujan'
    return 'kategori'


_VERBS = {
    'Prakiraan': 'diprakirakan terjadi',
    'Probabilistik': 'diprakirakan terjadi',
    'Analisis': 'tercatat',
    'Normal': 'tercatat',
    'Bias': 'tercatat',
    'HTH': 'terpantau',
    'Verifikasi': 'terdapat',
}


def _phrase(kind, label, rng):
    return f"{kind} {label} ({rng})" if rng else f"{kind} {label}"


def _join_id(items):
    """Indonesian list: 'A', 'A dan B', 'A, B, dan C'."""
    items = list(items)
    if len(items) <= 1:
        return ''.join(items)
    if len(items) == 2:
        return f"{items[0]} dan {items[1]}"
    return ', '.join(items[:-1]) + f", dan {items[-1]}"


def _kab_list(names):
    """'Kab. Sorong, Maybrat, dan Kota Sorong' — one 'Kab.' for the kabupaten."""
    kab = [n for n in names if not n.lower().startswith(('kota ', 'kab'))]
    other = [n for n in names if n not in kab]
    items = ([f"Kab. {kab[0]}"] + kab[1:] if kab else []) + other
    return _join_id(items)


def _capitalize(s):
    return s[:1].upper() + s[1:]


def _build_periode(map_data, with_dates=False):
    """Human-readable period; with_dates adds '(1 - 10 September 2024)' for dasarian."""
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
        das = map_data['dasarian']
        text = f"Dasarian {dasarian_romawi(das)} {bulan} {year}"
        if with_dates:
            start = {1: 1, 2: 11, 3: 21}[das]
            end = {1: 10, 2: 20, 3: calendar.monthrange(year, month)[1]}[das]
            text += f" ({start} - {end} {bulan} {year})"
        return text
    if peta == 'Normal':
        return f"Bulan {bulan} (Rata-rata 1991-2020)"
    return f"Bulan {bulan} {year}"


# =============================================================================
# NARRATION PIECES
# =============================================================================

def _per_province(map_data):
    return str(map_data.get('nama_wilayah', '')).startswith('Provinsi')


def _sum_counts(count_dicts):
    total = {}
    for counts in count_dicts:
        for k, v in counts.items():
            total[k] = total.get(k, 0) + v
    return total


def _dominants(map_data):
    """[(place, label, pct), ...]: one per province, or one for a kabupaten-level wilayah."""
    if _per_province(map_data):
        out = []
        for prov, counts in map_data['province_data'].items():
            pcts = _counts_to_percentages(counts)
            if pcts:
                out.append((_nice(prov), pcts[0][0], pcts[0][1]))
        return out
    pcts = _counts_to_percentages(_sum_counts(map_data['province_data'].values()))
    return [(_nice(map_data['nama_wilayah']), pcts[0][0], pcts[0][1])] if pcts else []


def _lead_sentence(map_data, categories, dominants):
    """Opening sentence with exact percentages, built without the LLM."""
    peta, tipe = map_data['peta'], map_data.get('tipe')
    rng = {c[0]: c[1] for c in categories}
    kind = _kind(peta, tipe)
    head = f"{_map_title(peta, tipe)} {_build_periode(map_data, with_dates=True)}"

    if not _per_province(map_data):
        place, cat, pct = dominants[0]
        return f"{head} di {place} didominasi {_phrase(kind, cat, rng.get(cat, ''))} sebesar {pct}%."

    if len({d[1] for d in dominants}) == 1:
        cat = dominants[0][1]
        names = _join_id(d[0] for d in dominants)
        if len(dominants) == 1:
            share = f"{dominants[0][2]}%"
        else:
            share = _join_id(f"{d[2]}% di {d[0]}" for d in dominants)
        umumnya = 'umumnya ' if len(dominants) > 1 else ''
        return (f"{head} di Provinsi {names} {umumnya}didominasi "
                f"{_phrase(kind, cat, rng.get(cat, ''))} sebesar {share}.")

    parts = [f"Provinsi {place} didominasi {_phrase(kind, cat, rng.get(cat, ''))} sebesar {pct}%"
             for place, cat, pct in dominants]
    return f"{head} di {parts[0]}, sementara " + ', '.join(parts[1:]) + "."


def _kabupaten_items(map_data, categories, dominants):
    """[(label, range, [kab names]), ...] worth naming after the lead sentence.

    Skips categories that are already dominant everywhere (the lead covers
    them), unless they are extreme.
    """
    groups = group_kabupaten(map_data['kabupaten_data'], categories)
    dominant_cats = {d[1] for d in dominants} if len({d[1] for d in dominants}) == 1 else set()
    return [
        (label, rng, groups[label])
        for label, rng, extreme in categories
        if groups.get(label) and (extreme or label not in dominant_cats)
    ]


def _kabupaten_template(items, kind, verb):
    """Deterministic fallback for the kabupaten sentence."""
    clauses = [f"{_phrase(kind, label, rng)} {verb} di {_kab_list(kabs)}" for label, rng, kabs in items]
    if not clauses:
        return ''
    if len(clauses) == 1:
        text = clauses[0]
    else:
        text = ', '.join(clauses[:-1]) + ', sedangkan ' + clauses[-1]
    return _capitalize(text) + '.'


def _metrics_sentence(map_data):
    if map_data.get('peta') != 'Verifikasi' or 'accuracy' not in map_data:
        return ''
    return (f"Akurasi keseluruhan (PC) mencapai {map_data['accuracy']:.2%}, "
            f"HSS sebesar {map_data['hss']:.2%}, dan PSS sebesar {map_data['pss']:.2%}.")


_MARKDOWN = re.compile(r'[*_#`]+|^\s*[-•]\s*', re.MULTILINE)


def _clean_llm_text(text):
    """Strip markdown and collapse whitespace."""
    return ' '.join(_MARKDOWN.sub('', text or '').split())


def _valid_kabupaten_text(text, items):
    """Reject LLM output with percentages, runaway length, or a missing kabupaten.

    Category ranges such as '(<85%)' are allowed; any other '%' is not.
    """
    if not text or len(text) > 1500:
        return False
    stripped = text
    for _, rng, _ in items:
        if rng:
            stripped = stripped.replace(rng, '')
    if '%' in stripped:
        return False
    low = text.lower()
    return all(kab.lower() in low for _, _, kabs in items for kab in kabs)


_KAB_EXAMPLE = (
    "DATA:\n"
    "curah hujan Tinggi (300-500 mm): Kab. Manokwari, Kaimana\n"
    "curah hujan Sangat Tinggi (>500 mm): Kab. Pegunungan Arfak\n"
    "curah hujan Rendah (0-100 mm): Kab. Sorong Selatan, Fak Fak\n"
    "Output:\n"
    "Curah hujan Tinggi (300-500 mm) hingga Sangat Tinggi (>500 mm) diprakirakan terjadi di "
    "Kab. Manokwari, Kaimana, dan Pegunungan Arfak, sedangkan curah hujan Rendah (0-100 mm) "
    "diprakirakan terjadi di Kab. Sorong Selatan dan Fak Fak."
)


def _llm_kabupaten_text(lead, items, kind, verb):
    """Ask Gemini for the kabupaten sentences; None on any failure or bad output."""
    try:
        _, _, client = _gemini_client()
    except Exception as e:
        status_update(f"Gemini unavailable ({e}); using template narration")
        return None

    data = "\n".join(f"{_phrase(kind, label, rng)}: {_kab_list(kabs)}"
                     for label, rng, kabs in items)
    prompt = (
        "Kamu penulis narasi peta cuaca BMKG. Kalimat pembuka narasi sudah ditulis:\n"
        f"\"{lead}\"\n\n"
        "Tulis 1-2 kalimat LANJUTAN yang menyebutkan kabupaten per kategori pada DATA.\n"
        "ATURAN:\n"
        "1. Sebutkan SEMUA kategori dan SEMUA kabupaten pada DATA, dengan ejaan yang sama persis.\n"
        "2. Tulis kategori beserta rentangnya persis seperti pada DATA.\n"
        f"3. Gunakan kata kerja '{verb}'.\n"
        "4. DILARANG menulis persentase, mengulang kalimat pembuka, menambah informasi "
        "di luar DATA, atau memakai formatting (bold, bullet, heading).\n\n"
        f"=== CONTOH ===\n{_KAB_EXAMPLE}\n=== AKHIR CONTOH ===\n\n"
        f"DATA:\n{data}\nOutput:"
    )

    def _generate(model):
        return client.models.generate_content(model=model, contents=prompt)

    try:
        response = _call_with_model_fallback(_generate, ANALYSIS_MODELS)
    except Exception as e:
        status_update(f"Gemini error ({e}); using template narration")
        return None
    if response is None:
        status_update("All models exhausted for narration; using template narration")
        return None

    text = _clean_llm_text(getattr(response, 'text', None))
    if not _valid_kabupaten_text(text, items):
        status_update("Gemini narration failed checks; using template narration")
        return None
    return text


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def get_analysis(map_data, use_llm=True):
    """Generate the narration paragraph for a BMKG map.

    Args:
        map_data: dict returned by execute() or overlay_image(), must contain
                  'province_data', 'kabupaten_data', and map metadata.
        use_llm: False skips Gemini and uses the template for every sentence.

    Returns:
        str: Narration paragraph in Bahasa Indonesia.
    """
    peta = map_data['peta']

    if peta == 'Probabilistik' and map_data.get('province_data') is None:
        return "Narasi otomatis tidak tersedia untuk peta Probabilistik."
    if map_data.get('province_data') is None or map_data.get('kabupaten_data') is None:
        return "Narasi otomatis tidak tersedia: data provinsi/kabupaten tidak ditemukan."

    status_update("Generating narration")
    categories = _categories(map_data)
    dominants = _dominants(map_data)
    if not dominants:
        return "Narasi otomatis tidak tersedia: tidak ada titik data di wilayah ini."

    lead = _lead_sentence(map_data, categories, dominants)
    items = _kabupaten_items(map_data, categories, dominants)
    kind = _kind(peta, map_data.get('tipe'))
    verb = _VERBS.get(peta, 'terdapat')

    kab_text = ''
    if items:
        if use_llm:
            kab_text = _llm_kabupaten_text(lead, items, kind, verb) or ''
        kab_text = kab_text or _kabupaten_template(items, kind, verb)

    status_update("Narration complete")
    return ' '.join(p for p in (lead, kab_text, _metrics_sentence(map_data)) if p)


def _format_grounding(map_data):
    """Province percentages and kabupaten grouping as plain text for prompts."""
    lines = ["=== PROVINSI ==="]
    for name, counts in map_data['province_data'].items():
        pcts = _counts_to_percentages(counts)
        if pcts:
            pct_str = ", ".join(f"{cat}: {val}%" for cat, val in pcts)
            lines.append(f"{_nice(name)} (dominan: {pcts[0][0]}): {pct_str}")
    groups = group_kabupaten(map_data['kabupaten_data'], _categories(map_data))
    kab_lines = [f"{cat}: {', '.join(kabs)}" for cat, kabs in groups.items() if kabs]
    if kab_lines:
        lines.append("=== KABUPATEN PER KATEGORI ===")
        lines.extend(kab_lines)
    return "\n".join(lines)


def get_visual_interpretation(map_data, analysis_text=None):
    """Generate a freeform visual interpretation of a BMKG map image using Gemini.

    Args:
        map_data: dict returned by execute() or overlay_image(), must contain
                  'image' (PIL Image).

    Returns:
        str: Freeform analytical interpretation in Bahasa Indonesia.
    """
    _, types, client = _gemini_client()

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
        grounding = (
            "\n\nBerikut data statistik aktual sebagai referensi (GUNAKAN angka ini, "
            "JANGAN mengarang angka sendiri):\n"
            + _format_grounding(map_data)
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
        "Kamu analis cuaca BMKG. "
        "Lihat peta berikut dan tulis TEPAT 3 kalimat interpretasi visual.\n\n"
        "FORMAT WAJIB:\n"
        "- Deskripsikan POLA SPASIAL yang terlihat di peta "
        "(konsentrasi warna, gradien, sebaran geografis).\n"
        "- Kalimat harus langsung menyambung narasi sebelumnya "
        "tanpa mengulang periode/judul.\n\n"
        "LARANGAN:\n"
        "1. DILARANG mengarang angka atau persentase yang tidak ada di data referensi.\n"
        "2. DILARANG mengulang kategori, persentase, atau nama wilayah dari narasi sebelumnya.\n"
        "3. DILARANG menggunakan formatting (bold, italic, bullet, heading, asterisk).\n"
        "4. DILARANG menulis lebih dari 3 kalimat.\n"
        "5. DILARANG menambahkan kesimpulan atau rekomendasi."
        + grounding
        + prior_context
    )

    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")

    # --- Generate with model fallback ---
    def _generate(model):
        return client.models.generate_content(
            model=model,
            contents=[prompt, image_part]
        )
    response = _call_with_model_fallback(_generate, VISUAL_MODELS)
    if response is None:
        status_update("All models exhausted for visual interpretation")
        return "Interpretasi visual tidak tersedia: semua model API telah mencapai batas kuota."
    status_update("Visual interpretation complete")
    return _clean_llm_text(response.text)


def get_full_narration(map_data):
    """Generate complete narration for a BMKG map.

    Args:
        map_data: dict returned by execute() or overlay_image().

    Returns:
        str: Generated narration paragraph in Bahasa Indonesia.
    """
    return get_analysis(map_data)


# =============================================================================
# TABLE DATA GENERATION
# =============================================================================

def build_table_data(map_data):
    """Build table data for the Word document report.

    For standard maps (CH, SH, Verifikasi, etc.): produces a KRITERIA vs DAERAH
    table where each row is a category (with its range) and the kabupaten
    listed under it by group_kabupaten — the same grouping the narration uses.

    For HTH maps: produces a station-level table with Provinsi, Kabupaten,
    optional Kecamatan/Pos, and the HTH classification name.

    Skips table for Probabilistik maps and kabupaten-level wilayah.

    Args:
        map_data: dict returned by overlay_image().

    Returns:
        dict with 'columns' (list[str]), 'rows' (list[list[str]]) and
        optionally 'merge_cols' (int), or None if no table should be generated.
    """
    peta = map_data.get('peta')

    # Skip for Probabilistik
    if peta == 'Probabilistik':
        return None

    # Skip if wilayah is kabupaten-level (no meaningful sub-breakdown)
    if not _per_province(map_data):
        return None

    if peta == 'HTH':
        return _build_hth_table(map_data)
    return _build_kriteria_table(map_data)


def _kriteria_column_name(peta, tipe):
    """Determine the KRITERIA column header based on map/data type."""
    if peta == 'Verifikasi':
        return 'Verifikasi'
    if peta == 'Bias':
        return 'Bias Curah Hujan'
    return tipe or 'Kriteria'


def _build_kriteria_table(map_data):
    """Build KRITERIA vs DAERAH table for standard (non-HTH) maps.

    Rows follow the category scheme order (low → high); a category with no
    kabupaten shows '-'.
    """
    kabupaten_data = map_data.get('kabupaten_data')
    if not kabupaten_data:
        return None

    categories = _categories(map_data)
    if not categories:
        return None
    groups = group_kabupaten(kabupaten_data, categories)

    rows = []
    for label, rng, _ in categories:
        kabs = groups.get(label)
        rows.append([f"{label} ({rng})" if rng else label, ', '.join(kabs) if kabs else '-'])

    return {
        'columns': [_kriteria_column_name(map_data.get('peta'), map_data.get('tipe')), 'Daerah'],
        'rows': rows,
    }


def _build_hth_table(map_data):
    """Return pre-computed HTH table data (built in map_creation.py)."""
    return map_data.get('hth_table_data')
