"""Validated tailoring, live model discovery, bounded API calls and PDF inspection."""
from __future__ import annotations

import copy
import datetime as dt
import difflib
import email.utils
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import requests

from renderer import default_selection, render_latex, selected_profile, visible_text
from prompts import SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parent
BASE_URL = 'https://openrouter.ai/api/v1'


class OptimizationError(Exception): pass
class InvalidAPIKeyError(OptimizationError): pass
class CatalogError(OptimizationError): pass
class AllModelsFailedError(OptimizationError): pass
class UnparsableResponseError(OptimizationError): pass
class RateLimitedError(OptimizationError):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


def load_profile(version: str) -> dict:
    if version not in ('v1', 'v2'): raise ValueError('Unknown resume version.')
    profile = json.loads((ROOT / 'profiles' / f'resume_{version}.json').read_text(encoding='utf-8'))
    validate_profile(profile)
    return profile


def validate_profile(p: dict) -> None:
    """Validate editable JSON before it reaches either API or renderer."""
    def strings(obj, keys):
        if not isinstance(obj, dict): raise ValueError('Expected an object.')
        for key in keys:
            if not isinstance(obj.get(key), str) or not obj[key].strip() or len(obj[key]) > 4000:
                raise ValueError(f'{key} must be a nonempty string of at most 4,000 characters.')
    strings(p, ['version','name','email','phone','linkedin','github','location','summary'])
    if not re.fullmatch(r'github\.com/[A-Za-z0-9-]+/?',p['github']):
        raise ValueError('github must be a profile address such as github.com/sairohitsk.')
    if p['version'] not in ('v1','v2'): raise ValueError('version must be v1 or v2.')
    ids = set()
    for key, fields in [
        ('education', ['institution','dates','credential','grade']),
        ('experience', ['id','company','title','dates','location','technologies']),
        ('projects', ['id','title','dates','technologies']),
        ('skills', ['category','items']), ('leadership', ['title','dates'])]:
        entries = p.get(key)
        if not isinstance(entries, list) or not 1 <= len(entries) <= 30:
            raise ValueError(f'{key} must contain 1 to 30 entries.')
        for entry in entries:
            strings(entry, fields)
            if 'id' in fields:
                if entry['id'] in ids: raise ValueError('Entry IDs must be unique.')
                ids.add(entry['id'])
                if not isinstance(entry.get('bullets'), list) or not 1 <= len(entry['bullets']) <= 12:
                    raise ValueError('Each entry needs 1 to 12 bullets.')
                for bullet in entry['bullets']:
                    strings(bullet, ['id', 'text'])
                    if bullet['id'] in ids: raise ValueError('Bullet IDs must be unique.')
                    ids.add(bullet['id'])
    if not isinstance(p.get('review_notes'), list) or any(not isinstance(s,str) for s in p['review_notes']):
        raise ValueError('review_notes must be a list of strings.')
    try:
        validate_selection(default_selection(p,1),p,1)
    except (KeyError,TypeError,UnparsableResponseError) as e:
        raise ValueError('Default project/bullet IDs must reference the current profile. Update the default selections after changing IDs.') from e


def validate_selection(selection: dict, profile: dict, pages: int = 2) -> None:
    def check_ids(values, allowed, maximum):
        if not isinstance(values,list) or len(values) != 3:
            raise UnparsableResponseError('Invalid number of selected bullets: exactly 3 are required per experience and project.')
        if any(not isinstance(v,str) for v in values) or len(set(values)) != len(values) or not set(values) <= allowed:
            raise UnparsableResponseError('Unknown, duplicate or cross-entry bullet ID.')
    if not isinstance(selection,dict) or set(selection) != {'experience','projects'}:
        raise UnparsableResponseError('selection must contain experience and projects.')
    roles = selection['experience']
    if not isinstance(roles,dict) or set(roles) != {r['id'] for r in profile['experience']}:
        raise UnparsableResponseError('Every source experience role must be retained exactly once.')
    for r in profile['experience']:
        check_ids(roles[r['id']], {b['id'] for b in r['bullets']}, len(r['bullets']))
        if not set(roles[r['id']]) & set(r.get('metric_bullet_ids',[])):
            raise UnparsableResponseError(r['company']+': retain at least one source-backed quantitative bullet.')
    projects = selection['projects']
    if not isinstance(projects,list) or not 1 <= len(projects) <= (2 if pages==1 else 3):
        raise UnparsableResponseError('Select 1-2 projects for one page or 1-3 for two pages.')
    allowed = {p['id']: p for p in profile['projects']}
    seen = set()
    for p in projects:
        if not isinstance(p,dict) or set(p) != {'id','bullets'} or not isinstance(p['id'],str) or p['id'] not in allowed or p['id'] in seen:
            raise UnparsableResponseError('Unknown or duplicate project ID.')
        seen.add(p['id'])
        check_ids(p['bullets'], {b['id'] for b in allowed[p['id']]['bullets']}, len(allowed[p['id']]['bullets']))
        project=allowed[p['id']]
        lookup={b['id']:b for b in project['bullets']}
        if [lookup[i].get('kind') for i in p['bullets']] != ['problem','implementation','outcome']:
            raise UnparsableResponseError('Project bullets must follow problem, implementation/method, then outcome.')
        if project.get('metric_bullet_ids') and not set(p['bullets']) & set(project['metric_bullet_ids']):
            raise UnparsableResponseError(project['title']+': retain the supplied outcome metric.')


def measurement_gaps(profile: dict, selection: dict) -> list[str]:
    """Flag absent measurements without substituting a less relevant project."""
    selected={p['id'] for p in selection['projects']}
    return [p['title']+': no measured numerical outcome supplied; current result describes correctness/functionality.'
            for p in profile['projects'] if p['id'] in selected and p.get('metric_kind')=='missing']


def parse_llm_output(raw: str, profile: dict, pages: int = 2) -> dict:
    if not isinstance(raw,str): raise UnparsableResponseError('Response is not text.')
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
    try: result = json.loads(raw)
    except (ValueError, TypeError) as e: raise UnparsableResponseError('Response is not valid JSON.') from e
    if not isinstance(result,dict) or set(result) != {'selection','rewrites','keywords','notes','project_idea','project_assessment'}:
        raise UnparsableResponseError('Response does not match the required object contract.')
    validate_selection(result['selection'],profile,pages)
    assessments = result['project_assessment']
    project_ids = {p['id'] for p in profile['projects']}
    kept = {p['id'] for p in result['selection']['projects']}
    if not isinstance(assessments, list) or len(assessments) != len(project_ids):
        raise UnparsableResponseError('Assess every library project exactly once, including omitted projects.')
    assessed = set()
    for item in assessments:
        if (not isinstance(item, dict) or set(item) != {'id','selected','reason'}
                or not isinstance(item['id'],str) or item['id'] not in project_ids
                or item['id'] in assessed or type(item['selected']) is not bool
                or item['selected'] != (item['id'] in kept)
                or not isinstance(item['reason'],str) or not item['reason'].strip()):
            raise UnparsableResponseError('Project assessment must match the selected projects and explain every decision.')
        assessed.add(item['id'])
    source = {b['id']: b['text'] for r in profile['experience']+profile['projects'] for b in r['bullets']}
    selected = selected_profile(profile,result['selection'])
    selected_ids = {b['id'] for r in selected['experience']+selected['projects'] for b in r['bullets']}
    if not isinstance(result['rewrites'],list) or len(result['rewrites']) > len(selected_ids):
        raise UnparsableResponseError('Invalid rewrites array.')
    seen = set()
    for rewrite in result['rewrites']:
        if not isinstance(rewrite,dict) or set(rewrite) != {'bullet_id','text','reason'} or any(not isinstance(v,str) or not v.strip() for v in rewrite.values()):
            raise UnparsableResponseError('Each rewrite needs bullet_id, text and reason strings.')
        bid = rewrite['bullet_id']
        if bid not in selected_ids or bid in seen or len(rewrite['text']) > 1200:
            raise UnparsableResponseError('Rewrite references an unknown, unselected or duplicate bullet.')
        seen.add(bid)
        # This guard catches numeric invention, not semantic invention. Human review remains required.
        numbers = lambda t: set(re.findall(r'\d[\d,.]*(?:%|\+)?', t))
        if not numbers(rewrite['text']) <= numbers(source[bid]):
            raise UnparsableResponseError('A proposed rewrite introduces a new numerical claim.')
        metric_ids={i for r in profile['experience']+profile['projects'] for i in r.get('metric_bullet_ids',[])}
        if bid in metric_ids and not numbers(source[bid]) <= numbers(rewrite['text']):
            raise UnparsableResponseError('A proposed rewrite removes a required source metric.')
        qualifiers = ('estimated', 'targeting', 'target', 'simulating')
        for q in qualifiers:
            if re.search(r'\b'+q+r'\b',source[bid],re.I) and not re.search(r'\b'+q+r'\b',rewrite['text'],re.I):
                raise UnparsableResponseError(f'A rewrite removes the qualifier "{q}".')
    if not isinstance(result['keywords'],list) or len(result['keywords']) > 30:
        raise UnparsableResponseError('Invalid keywords array.')
    for kw in result['keywords']:
        if not isinstance(kw,dict) or set(kw) != {'priority','keyword','evidence_ids','reason'}:
            raise UnparsableResponseError('Invalid keyword entry.')
        if kw['priority'] not in ('CRITICAL','IMPORTANT','BONUS'):
            raise UnparsableResponseError('Invalid keyword priority.')
        if any(not isinstance(kw[k],str) for k in ['keyword','reason']) or not isinstance(kw['evidence_ids'],list) or any(not isinstance(i,str) or i not in selected_ids for i in kw['evidence_ids']):
            raise UnparsableResponseError('Invalid keyword evidence.')
    if not isinstance(result['notes'],list) or any(not isinstance(n,str) for n in result['notes']):
        raise UnparsableResponseError('notes must be a list of strings.')
    idea = result['project_idea']
    if idea is not None and (not isinstance(idea,dict) or set(idea) != {'title','why','build_steps','verification'} or any(not isinstance(v,str) for v in idea.values())):
        raise UnparsableResponseError('Invalid project idea.')
    return result


# Free-model ranking. Substring -> weight; higher is tried first. Free IDs churn, so
# nothing is hardcoded: the live catalog is fetched and ranked by these hints.
# Coding/instruction-following MoE models rank above small, omni or niche models.
MODEL_PRIORITY_HINTS = [
    ('qwen3-coder',100),('coder',40),('deepseek',88),('glm',80),('kimi',78),('mimo',76),
    ('laguna-m',92),('laguna',85),('nemotron-3-ultra',90),('nemotron',70),('hy3',75),
    ('gpt-oss',68),('llama-3.3-70b',60),('llama',50),('gemma',45),('code',25),
    ('omni',-40),('small',-15),('mini',-15),('vl',-30),
]
# Reasoning-heavy models can spend the whole token budget on hidden thinking and
# return nothing; ask these not to reason.
NO_THINKING_SUBSTRINGS = ('deepseek','hy3','nemotron')
MAX_MODEL_ATTEMPTS = 6


def model_priority(model_id: str) -> int:
    low = model_id.lower()
    return sum(w for sub,w in MODEL_PRIORITY_HINTS if sub in low)


def fetch_free_models(timeout: int = 15) -> list[dict]:
    try:
        response = requests.get(BASE_URL+'/models', timeout=timeout)
        response.raise_for_status()
        rows = response.json()['data']
        if not isinstance(rows,list): raise ValueError()
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        raise CatalogError('Could not verify the live free-model catalog. Retry refresh; no stale models will be called.') from e
    models = []
    for row in rows:
        if not isinstance(row,dict): continue
        try:
            pricing = row.get('pricing') or {}
            free = all(float(pricing.get(k, 1 if k in ('prompt','completion') else 0)) == 0 for k in ('prompt','completion','request'))
            context = int(row.get('context_length') or 0)
            architecture = row.get('architecture') or {}
            model_id = row.get('id')
            if (free and context >= 16000 and isinstance(model_id,str)
                    and architecture.get('output_modalities') == ['text']
                    and 'text' in architecture.get('input_modalities', [])
                    and not any(t in model_id.lower() for t in ('guard','moderation','safety'))):
                models.append({'id':model_id,'context_length':context})
        except (ValueError, TypeError, AttributeError): continue
    if not models: raise CatalogError('The catalog has no eligible free text models right now.')
    return sorted(models,key=lambda m:(-model_priority(m['id']),-m['context_length'],m['id']))


def provider_error(resp) -> str:
    """Short, single-line provider explanation so a bare 403 is diagnosable."""
    try:
        err = resp.json().get('error')
        msg = err.get('message') if isinstance(err,dict) else err
    except (ValueError, AttributeError, TypeError):
        msg = None
    msg = str(msg or getattr(resp,'text','') or '').replace('\n',' ').strip()
    return ('('+msg[:160]+')') if msg else ''


def retry_seconds(value):
    try: return max(0,float(value))
    except (ValueError,TypeError):
        try: return max(0,(email.utils.parsedate_to_datetime(value)-dt.datetime.now(dt.timezone.utc)).total_seconds())
        except (ValueError,TypeError,OverflowError): return None


@dataclass
class OptimizationResult:
    plan: dict
    used_model: str
    attempts: list[str]


def run_optimization(profile: dict, jd: str, api_key: str, model: str,
                     pages: int = 2, suggest_project: bool = False,
                     fallback_models: list[str] | None = None) -> OptimizationResult:
    validate_profile(profile)
    if pages not in (1,2): raise OptimizationError('Invalid page target.')
    if not jd.strip() or len(jd) > 30000: raise OptimizationError('Use a job description of 1 to 30,000 characters.')
    if not api_key.strip(): raise InvalidAPIKeyError('Enter an OpenRouter API key.')
    # Revalidate cost at click-time. A cached catalog is only for the model picker.
    catalog = {m['id']: m for m in fetch_free_models()}
    candidates = list(dict.fromkeys([model]+(fallback_models or [])))[:MAX_MODEL_ATTEMPTS]
    candidates = [m for m in candidates if m in catalog]
    if not candidates: raise CatalogError('Selected models are no longer eligible for free calls. Refresh the list.')
    # Contact details stay local; no need for the provider to receive them.
    evidence = {k:profile[k] for k in ('summary','education','experience','projects','skills')}
    user = json.dumps({'page_target':pages,'suggest_project':suggest_project,'job_description':jd,'profile':evidence},ensure_ascii=False)
    headers = {'Authorization':'Bearer '+api_key.strip(),'Content-Type':'application/json',
               'HTTP-Referer':'https://github.com/SaiRohit012/ats-resume','X-Title':'Resume Studio'}
    attempts, errors, rate_waits = [], [], []
    for candidate in candidates:
        # Conservative byte upper bound, plus output budget, avoids obvious context overflow.
        if len((SYSTEM_PROMPT+user).encode('utf-8'))+6000 > catalog[candidate]['context_length']:
            errors.append(candidate+': insufficient context capacity'); continue
        messages = [{'role':'system','content':SYSTEM_PROMPT},{'role':'user','content':user}]
        for repair in range(2):
            attempts.append(candidate)
            try:
                body = {'model':candidate,'messages':messages,'max_tokens':6000,'temperature':0.2}
                if any(t in candidate.lower() for t in NO_THINKING_SUBSTRINGS): body['reasoning'] = {'enabled':False}
                resp = requests.post(BASE_URL+'/chat/completions',headers=headers,json=body,timeout=(10,75))
            except requests.RequestException:
                errors.append(candidate+': connection failure'); break
            if resp.status_code == 401: raise InvalidAPIKeyError('OpenRouter rejected the API key (401).')
            if resp.status_code == 429:
                rate_waits.append(retry_seconds(resp.headers.get('Retry-After')))
                errors.append(candidate+': rate limited'); break
            if resp.status_code >= 400:
                errors.append(candidate+f': HTTP {resp.status_code} {provider_error(resp)}'); break
            try:
                data = resp.json()
                choice = data['choices'][0]
                if choice.get('finish_reason') == 'length': raise UnparsableResponseError('Response was truncated.')
                plan = parse_llm_output(choice['message']['content'],profile,pages)
                if not suggest_project: plan['project_idea'] = None
                return OptimizationResult(plan,candidate,attempts)
            except (ValueError, KeyError, IndexError, TypeError, UnparsableResponseError) as e:
                if repair == 0:
                    messages.append({'role':'user','content':f'Your response failed validation: {str(e)[:200]}. Return a fresh JSON object matching the contract. Do not change source facts.'})
                else: errors.append(candidate+': invalid structured response after one repair')
    if errors and all(e.endswith(': rate limited') for e in errors):
        raise RateLimitedError('All attempted models are rate limited.',max((w for w in rate_waits if w is not None),default=None))
    raise AllModelsFailedError('No usable result. '+'; '.join(errors))


# A transparent lexical check, not a vendor ATS score or hiring probability.
STOPWORDS = set('a an the and or with for of to in on at by as is are be we you your our will can from this that it have has experience skills role work team ability required preferred years year strong good knowledge using use across including responsibilities qualifications looking must would should such also into who all more'.split())
ALIASES = {'javascript':'javascript','js':'javascript','scikit-learn':'scikit-learn','sklearn':'scikit-learn','postgres':'postgresql','postgresql':'postgresql','gcp':'gcp'}


def tokens(text):
    text = text.casefold().replace('google cloud platform','gcp').replace('google bigquery','bigquery')
    found = re.findall(r'(?<!\w)(?:c\+\+|c#|\.net|[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*)(?!\w)',text)
    return [ALIASES.get(t,t) for t in found if t not in STOPWORDS and (len(t)>1 or t=='c')]


def keyword_coverage(jd: str, text: str) -> dict:
    keywords = list(dict.fromkeys(tokens(jd)))
    present = set(tokens(text))
    matched = [w for w in keywords if w in present]
    missing = [w for w in keywords if w not in present]
    return {'percent':round(100*len(matched)/len(keywords),1) if keywords else None,
            'matched':matched,'missing':missing,'total':len(keywords)}


@dataclass
class PDFResult:
    success: bool
    pdf_bytes: bytes | None = None
    log: str = ''
    engine: str | None = None
    pages: int = 0
    text: str = ''
    warnings: list[str] = field(default_factory=list)


def build_pdf(profile: dict, selection: dict, pages: int = 2, rewrites: dict | None = None,
              timeout: int = 90) -> PDFResult:
    """Compile only internally rendered data, never arbitrary model-supplied TeX."""
    validate_profile(profile)
    validate_selection(selection,profile,pages)
    latex = render_latex(profile,selection,pages,rewrites)
    engine = shutil.which('tectonic') or shutil.which('pdflatex')
    if not engine: return PDFResult(False,log='Install Tectonic or TeX Live (see README) to build PDFs.')
    name = Path(engine).stem.lower()
    with tempfile.TemporaryDirectory(prefix='resume-') as tmp:
        src = Path(tmp)/'resume.tex'
        src.write_text(latex,encoding='utf-8')
        env = dict(os.environ, TECTONIC_UNTRUSTED_MODE='1', openin_any='p', openout_any='p')
        cmd = ([engine,'-X','compile','--untrusted','--keep-logs','--outdir',tmp,str(src)] if name=='tectonic'
               else [engine,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error','resume.tex'])
        try:
            run = subprocess.run(cmd,cwd=tmp,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        except subprocess.TimeoutExpired: return PDFResult(False,log=f'Compilation exceeded {timeout}s. A first Tectonic run may need to download packages.',engine=name)
        except OSError as e: return PDFResult(False,log=f'Could not launch compiler: {e}',engine=name)
        log_path = Path(tmp)/'resume.log'
        log = run.stdout+'\n'+run.stderr+'\n'+(log_path.read_text(encoding='utf-8',errors='replace') if log_path.exists() else '')
        pdf = Path(tmp)/'resume.pdf'
        if run.returncode or not pdf.exists(): return PDFResult(False,log=log,engine=name)
        pdf_bytes = pdf.read_bytes()
    try:
        import pymupdf
        with pymupdf.open(stream=pdf_bytes,filetype='pdf') as doc:
            count = len(doc)
            text = unicodedata.normalize('NFKC','\n'.join(page.get_text(sort=True) for page in doc))
            warnings = []
            for n,page in enumerate(doc,1):
                if not page.get_text().strip(): warnings.append(f'Page {n} has no extractable text.')
                for block in page.get_text('blocks'):
                    x0,y0,x1,y1 = block[:4]
                    if min(x0,y0)<20 or x1>page.rect.width-20 or y1>page.rect.height-20:
                        warnings.append(f'Page {n} has text close to or outside the printable edge.'); break
    except Exception as e:
        return PDFResult(False,log=f'Compiled PDF could not be inspected: {type(e).__name__}',engine=name)
    if count > pages: warnings.append(f'Page target exceeded: requested {pages}, rendered {count}. Shorten wording or select fewer projects; exactly 3 bullets per entry must remain.')
    if 'Overfull \\hbox' in log or 'Overfull \\vbox' in log: warnings.append('The compiler reported overflowing text. Inspect the preview before using it.')
    normalized = ' '.join(text.split()).casefold()
    for e in profile['education']:
        if e['institution'].casefold() not in normalized: warnings.append('Education text missing from PDF extraction: '+e['institution'])
    for category in profile['skills']:
        if category['category'].casefold() not in normalized: warnings.append('Skills category missing from PDF extraction: '+category['category'])
    expected = visible_text(profile,selection,rewrites,pages)
    missing = set(tokens(expected))-set(tokens(text))
    if missing: warnings.append('Words missing from PDF extraction: '+', '.join(sorted(missing)))
    return PDFResult(True,pdf_bytes,log,name,count,text,list(dict.fromkeys(warnings)))


def pdf_previews(pdf_bytes: bytes):
    import pymupdf
    with pymupdf.open(stream=pdf_bytes,filetype='pdf') as doc:
        return [page.get_pixmap(matrix=pymupdf.Matrix(1.4,1.4)).tobytes('png') for page in doc]


def unified_diff(before, after):
    return '\n'.join(difflib.unified_diff(before.splitlines(),after.splitlines(),fromfile='source snapshot',tofile='tailored draft',lineterm=''))
