# unused.py
"""
Functions moved here for archival. Not actively used in the pipeline.
"""

from .narasi import _compute_all_percentages, _format_percentages
from .status import update as status_update


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
