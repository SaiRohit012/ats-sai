"""Build both base drafts and their matching .tex/.txt files."""
import argparse
import json
from pathlib import Path

from core import build_pdf, load_profile
from renderer import default_selection, render_latex

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='resumes')
    parser.add_argument('--timeout',type=int,default=90)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    results = {}
    for version in ('v1','v2'):
        p = load_profile(version)
        selection = default_selection(p,1)
        (output/f'resume_{version}.tex').write_text(render_latex(p,selection),encoding='utf-8')
        pdf = build_pdf(p,selection,pages=1,timeout=args.timeout)
        results[version] = {'success':pdf.success,'pages':pdf.pages,'warnings':pdf.warnings,'engine':pdf.engine}
        (output/f'resume_{version}.log').write_text(pdf.log,encoding='utf-8')
        if pdf.success:
            (output/f'resume_{version}.pdf').write_bytes(pdf.pdf_bytes)
            (output/f'resume_{version}.txt').write_text(pdf.text,encoding='utf-8')
        else: print(pdf.log[-3000:])
    print(json.dumps(results,indent=2))
    if not all(r['success'] and not r['warnings'] for r in results.values()): raise SystemExit(1)

if __name__ == '__main__': main()
