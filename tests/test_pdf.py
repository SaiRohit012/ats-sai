"""Real renderer/compiler checks; require Tectonic or pdflatex on PATH."""
import io
import re
import shutil
import unicodedata

import pymupdf
import pytest
from pypdf import PdfReader

import core
from renderer import default_selection, visible_text

pytestmark=pytest.mark.skipif(not(shutil.which('tectonic') or shutil.which('pdflatex')),reason='LaTeX engine not installed')


@pytest.mark.parametrize('version',['v1','v2'])
def test_final_pdf_is_one_page_complete_readable_and_aligned(version):
    p=core.load_profile(version)
    choice=default_selection(p,1)
    result=core.build_pdf(p,choice,pages=1)
    assert result.success,result.log[-2000:]
    assert result.pages==1
    assert not result.warnings
    assert core.render_latex(p,choice,pages=1).count('\\item ')==15
    # Check with an independent extraction engine too.
    reader=PdfReader(io.BytesIO(result.pdf_bytes))
    text=unicodedata.normalize('NFKC',reader.pages[0].extract_text())
    normalized=' '.join(text.split())
    for phrase in ['IIT Madras','Foundation in Data Science and Programming','BITS Pilani',
                   'Sharda University','Redwood Software','HSBC','Codinoverse']:
        assert phrase in normalized
    assert set(core.tokens(visible_text(p,choice))) <= set(core.tokens(text))
    with pymupdf.open(stream=result.pdf_bytes,filetype='pdf') as doc:
        page=doc[0]
        for heading in ['Education','Technical Skills','Experience','Projects','Redwood Software Pvt. Ltd.','HSBC','Codinoverse']:
            rect=page.search_for(heading)[0]
            assert abs(rect.x0-43.2)<1, (heading,rect)
        for block in page.get_text('dict')['blocks']:
            if 'lines' not in block: continue
            for line in block['lines']:
                for span in line['spans']:
                    assert span['size']>=10.4
                    x0,y0,x1,y1=span['bbox']
                    assert x0>=42 and x1<=page.rect.width-42
                    assert y0>=35 and y1<=page.rect.height-35


def test_one_page_overflow_is_reported_without_hidden_trimming():
    p=core.load_profile('v1')
    for role in p['experience']:
        for b in role['bullets']: b['text']+=' Additional detailed evidence.'*25
    result=core.build_pdf(p,default_selection(p),pages=1)
    assert result.success
    assert result.pages>1
    assert any('Page target exceeded' in w for w in result.warnings)
