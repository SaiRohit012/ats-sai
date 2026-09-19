"""Fixed, single-column layout. AI output never becomes executable LaTeX."""
from __future__ import annotations

import copy
import re


def tex(text: str) -> str:
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
                    '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
                    '^': r'\textasciicircum{}', '<': r'\textless{}', '>': r'\textgreater{}'}
    text = text.replace('\u2013','--').replace('\u2014','--').replace('\u2019', "'")
    return ''.join(replacements.get(c, c) for c in text)


def default_selection(profile: dict, pages: int = 1) -> dict:
    project_ids = profile.get('default_projects', [p['id'] for p in profile['projects'][:2]])
    project_map = {p['id']:p for p in profile['projects']}
    return copy.deepcopy({
        'experience': {r['id']: profile.get('default_experience_bullets',{}).get(r['id'],[b['id'] for b in r['bullets']][:3])
                       for r in profile['experience']},
        'projects': [{'id': pid, 'bullets': profile.get('default_project_bullets',{}).get(pid,[b['id'] for b in project_map[pid]['bullets']][:3])}
                     for pid in project_ids],
    })


def selected_profile(profile: dict, selection: dict, rewrites: dict | None = None) -> dict:
    result = copy.deepcopy(profile)
    rewrites = rewrites or {}
    for role in result['experience']:
        lookup = {b['id']: b for b in role['bullets']}
        role['bullets'] = [lookup[i] for i in selection['experience'][role['id']]]
    lookup = {p['id']: p for p in result['projects']}
    result['projects'] = []
    for choice in selection['projects']:
        project = lookup[choice['id']]
        bullets = {b['id']: b for b in project['bullets']}
        project['bullets'] = [bullets[i] for i in choice['bullets']]
        result['projects'].append(project)
    for entry in result['experience'] + result['projects']:
        for bullet in entry['bullets']:
            bullet['text'] = rewrites.get(bullet['id'], bullet['text'])
    return result


def visible_text(profile: dict, selection: dict, rewrites: dict | None = None, pages: int = 1) -> str:
    p = selected_profile(profile, selection, rewrites)
    lines = [p['name'], p['phone'], p['email'], p['location'], p['linkedin'], p['github']]
    if pages == 2: lines += ['Summary',p['summary']]
    lines.append('Education')
    for e in p['education']:
        lines += [e['institution'], e['credential'], e['dates'], e['grade']]
    lines.append('Technical Skills')
    for s in p['skills']: lines.append(s['category'] + ': ' + s['items'])
    lines.append('Experience')
    for r in p['experience']:
        lines += [r['company'], r['dates'], r['title'], r['location']]
        lines += [b['text'] for b in r['bullets']]
    lines.append('Projects')
    for r in p['projects']:
        lines += [r['title'], r['dates']]
        lines.append(r['technologies'])
        lines += [b['text'] for b in r['bullets']]
    if pages == 2:
        lines.append('Leadership')
        for r in p['leadership']: lines += [r['title'], r['dates']]
    return '\n'.join(lines)


def render_latex(profile: dict, selection: dict, pages: int = 1, rewrites: dict | None = None) -> str:
    if pages not in (1, 2): raise ValueError('Choose a one- or two-page target.')
    p = selected_profile(profile, selection, rewrites)
    # Explicit fontsize: article silently ignores a 10.5pt document-class option.
    preamble = r'''\documentclass[a4paper,11pt]{article}
\usepackage[left=0.6in,right=0.6in,top=0.6in,bottom=0.55in]{geometry}
\ifdefined\XeTeXversion
\usepackage{fontspec}
\defaultfontfeatures{Ligatures=NoCommon,Kerning=Off}
\setmainfont{lmroman10-regular.otf}[BoldFont=lmroman10-bold.otf,ItalicFont=lmroman10-italic.otf,BoldItalicFont=lmroman10-bolditalic.otf]
\setsansfont{lmsans10-regular.otf}[BoldFont=lmsans10-bold.otf,ItalicFont=lmsans10-oblique.otf,BoldItalicFont=lmsans10-boldoblique.otf]
\else
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\fi
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{needspace}
\usepackage[hidelinks]{hyperref}
\ifdefined\pdfgentounicode
\input{glyphtounicode}
\pdfgentounicode=1
\fi
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\raggedright
\raggedbottom
\urlstyle{same}
\titleformat{\section}{\fontsize{11.5}{14}\selectfont\bfseries}{}{0pt}{}[\titlerule]
\titlespacing*{\section}{0pt}{7pt}{4pt}
\setlist[itemize]{leftmargin=13pt,label=\textbullet,itemsep=2pt,topsep=3pt,parsep=0pt,partopsep=0pt}
\newcommand{\entry}[3]{\par\addvspace{4pt}\Needspace{5\baselineskip}\textbf{#1}\hfill #2\par\nopagebreak[4]{\itshape #3}\par\nopagebreak[4]}
\newcommand{\project}[2]{\par\addvspace{4pt}\Needspace{4\baselineskip}\textbf{#1}\hfill #2\par\nopagebreak[4]}
\begin{document}
\fontsize{10.5}{13}\selectfont
'''
    # Same stable geometry in both variants; an understated serif/sans choice.
    if p['version'] == 'v2':
        preamble = preamble.replace(r'\begin{document}', r'\renewcommand{\familydefault}{\sfdefault}' + '\n' + r'\begin{document}')
    lines = [preamble, r'{\centering {\fontsize{21}{24}\selectfont\bfseries ' + tex(p['name']) + r'}\par\vspace{5pt}',
             tex(p['phone'] + ' | ' + p['email'] + ' | ' + p['location']) + r'\par\vspace{2pt}',
             tex(p['linkedin']) + ' | ' + r'\href{https://' + tex(p['github']) + '}{' + tex(p['github']) + r'}\par}']
    if pages == 2: lines += [r'\section{Summary}', tex(p['summary'])]
    lines.append(r'\section{Education}')
    for e in p['education']:
        lines += [r'\Needspace{3\baselineskip}\textbf{' + tex(e['institution']) + r'}\hfill ' + tex(e['dates']) + r'\par\nopagebreak[4]',
                  tex(e['credential'] + ' | ' + e['grade']) + r'\par\addvspace{2pt}']
    lines.append(r'\section{Technical Skills}')
    for s in p['skills']:
        lines.append(r'\textbf{' + tex(s['category']) + ':} ' + tex(s['items']) + r'\par\addvspace{2pt}')
    lines.append(r'\section{Experience}')
    def bullets(items):
        return [r'\begin{itemize}'] + [r'\item ' + tex(b['text']) for b in items] + [r'\end{itemize}']
    for r in p['experience']:
        lines += [r'\entry{' + tex(r['company']) + '}{' + tex(r['dates']) + '}{' + tex(r['title'] + ' | ' + r['location']) + '}']
        lines += bullets(r['bullets'])
    lines.append(r'\section{Projects}')
    for r in p['projects']:
        lines += [r'\entry{' + tex(r['title']) + '}{' + tex(r['dates']) + '}{' + tex(r['technologies']) + '}']
        lines += bullets(r['bullets'])
    if pages == 2:
        lines.append(r'\section{Leadership}')
        for r in p['leadership']:
            lines += [tex(r['title']) + r'\hfill ' + tex(r['dates']) + r'\par\addvspace{2pt}']
    lines.append(r'\end{document}')
    return '\n'.join(lines)
