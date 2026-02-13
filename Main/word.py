# word.py
"""
Word document generation from map data using docxtpl templates.
"""

import os
import io

from .config import cfg, CACHE_DIR
from .utils import number_to_bulan, dasarian_romawi
from .status import update as status_update
from .narasi import get_analysis, get_visual_interpretation


def arrange_word(map_data):
    """Generate a Word document report from map data.

    Args:
        map_data: dict returned by execute(), must contain 'image' (PIL Image)
                  and map metadata (peta, tipe, skala, year, month, etc.).

    Returns:
        str: Output file path on success, None on failure.
    """
    try:
        try:
            from docxtpl import DocxTemplate, InlineImage
        except ImportError:
            import subprocess
            status_update("Installing docxtpl...")
            subprocess.check_call(['pip', 'install', 'docxtpl', '-q'])
            from docxtpl import DocxTemplate, InlineImage
        from docx.shared import Cm
        from google.colab import files

        status_update("Generating Word document...")

        peta = map_data['peta']
        tipe = map_data['tipe']
        skala = map_data['skala']
        year = map_data['year']
        month = map_data['month']

        # Build title and period strings
        title1 = f'{peta} {tipe}'
        if skala == 'Bulanan':
            title2 = f'Bulan {number_to_bulan(month)} {year}'
        else:
            title2 = f'Bulan {number_to_bulan(month)} Dasarian {dasarian_romawi(map_data["dasarian"])} {year}'
        desc = f'Peta {title1} {title2}'

        # Get AI narration
        analysis = get_analysis(map_data)
        visual = get_visual_interpretation(map_data)

        # Convert PIL Image to BytesIO buffer
        image_buffer = io.BytesIO()
        map_data['image'].save(image_buffer, format='PNG')
        image_buffer.seek(0)

        # Load template and build context
        template_path = os.path.join(CACHE_DIR, 'template_doc.docx')
        doc = DocxTemplate(template_path)

        context = {
            'title1': f'{title1} {title2}',
            'image1': InlineImage(doc, image_buffer, width=Cm(15)),
            'desc': desc,
            'text1': analysis,
            'text2': visual,
        }

        # Render and save
        doc.render(context)
        output_path = f'/content/Laporan {peta} {tipe}.docx'
        doc.save(output_path)

        status_update(f"Word document saved: {output_path}")
        files.download(output_path)

        return output_path

    except Exception as e:
        print(f"Error generating Word document: {e}")
        return None
