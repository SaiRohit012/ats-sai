from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import core

APP=Path(__file__).resolve().parents[1]/'app.py'


def button(app,label): return next(b for b in app.button if b.label==label)


def test_app_boot_switch_edit_and_build():
    with patch('core.fetch_free_models',side_effect=AssertionError('No automatic network call')):
        app=AppTest.from_file(str(APP)).run(timeout=20)
        assert not app.exception
        assert app.selectbox[0].value=='v1'
        app.selectbox[0].set_value('v2').run()
        assert not app.exception
        editor=next(t for t in app.text_area if t.label=='Editable profile JSON')
        assert 'sai.rohit.shaik@gmail.com' in editor.value
        with patch('core.build_pdf',return_value=core.PDFResult(False,log='No engine for this UI test')):
            button(app,'Build resume preview').click().run()
        assert not app.exception
        assert app.session_state['current']['profile']['version']=='v2'
        app.text_area(key='jd').set_value('New unrelated JD').run()
        assert app.session_state['current']['jd']==''
        app.selectbox[0].set_value('v1').run()
        assert app.session_state['current']['profile']['version']=='v2'


def test_empty_selection_is_recoverable():
    app=AppTest.from_file(str(APP)).run(timeout=20)
    app.multiselect[0].set_value([]).run()
    button(app,'Build resume preview').click().run()
    assert not app.exception
    assert any('Invalid number' in e.value for e in app.error)
