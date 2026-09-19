import copy
import json
from unittest.mock import Mock, patch

import pytest
import requests

import core
from renderer import default_selection, render_latex, selected_profile, tex, visible_text


@pytest.fixture
def profile(): return core.load_profile('v1')


def response(p):
    selection=default_selection(p)
    kept={item['id'] for item in selection['projects']}
    return {'selection':selection, 'rewrites':[], 'keywords':[], 'notes':[], 'project_idea':None,
            'project_assessment':[{'id':item['id'],'selected':item['id'] in kept,'reason':'JD evidence comparison.'} for item in p['projects']]}


def http(status=200, body=None, headers=None):
    result = Mock(status_code=status,headers=headers or {})
    result.json.return_value = body
    if status>=400: result.raise_for_status.side_effect=requests.HTTPError()
    return result


def completion(plan):
    return http(body={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(plan)}}]})


@pytest.mark.parametrize('version',['v1','v2'])
def test_education_and_skills_protected_in_both_modes(version):
    p = core.load_profile(version)
    for pages in (1,2):
        s = default_selection(p,pages)
        result = selected_profile(p,s)
        assert result['education']==p['education']
        assert result['skills']==p['skills']
        assert len(result['experience'])==3
        assert 'IIT Madras' in visible_text(p,s)
        assert 'Foundation in Data Science and Programming' in visible_text(p,s)
        latex = render_latex(p,s,pages)
        assert '\\begin{tabular' not in latex
        assert '\\vspace{-' not in latex
        assert '\\fontsize{10.5}{13}' in latex


@pytest.mark.parametrize('bad',[None,[],{'selection':None},'hello',42])
def test_malformed_schema_is_typed_error(profile,bad):
    with pytest.raises(core.UnparsableResponseError): core.parse_llm_output(json.dumps(bad),profile)


def test_fenced_valid_json(profile):
    p = response(profile)
    assert core.parse_llm_output('```json\n'+json.dumps(p)+'\n```',profile)==p


@pytest.mark.parametrize('mutation',['missing-role','duplicate','cross-entry','unknown-project','bad-keywords','bad-notes','bad-rewrite','bad-idea'])
def test_invalid_nested_schema(profile,mutation):
    p = response(profile)
    if mutation=='missing-role': del p['selection']['experience']['e3']
    if mutation=='duplicate': p['selection']['experience']['e1'] *= 2
    if mutation=='cross-entry': p['selection']['experience']['e1']=['v1-e2-b1']
    if mutation=='unknown-project': p['selection']['projects'][0]['id']='unbuilt'
    if mutation=='bad-keywords': p['keywords']=['Python']
    if mutation=='bad-notes': p['notes']={}
    if mutation=='bad-rewrite': p['rewrites']=[{'bullet_id':'unbuilt','text':'Made stuff','reason':'New'}]
    if mutation=='bad-idea': p['project_idea']='idea'
    with pytest.raises(core.UnparsableResponseError): core.parse_llm_output(json.dumps(p),profile)


def test_new_number_and_removed_qualifier_are_rejected(profile):
    p = response(profile)
    b = profile['experience'][1]['bullets'][0]
    for text in [b['text'].replace('200K','900K'), b['text'].replace('estimated ','')]:
        p['rewrites']=[{'bullet_id':b['id'],'text':text,'reason':'Shorter'}]
        with pytest.raises(core.UnparsableResponseError): core.parse_llm_output(json.dumps(p),profile)


def test_proposed_rewrites_are_not_auto_applied(profile):
    p = response(profile)
    p['rewrites']=[{'bullet_id':'v1-e1-b2','text':'Develop Java/Spring Boot components.','reason':'Shorter'}]
    parsed=core.parse_llm_output(json.dumps(p),profile)
    draft=selected_profile(profile,parsed['selection'])
    assert draft['experience'][0]['bullets'][1]['text']==profile['experience'][0]['bullets'][1]['text']


@pytest.mark.parametrize('version',['v1','v2'])
def test_three_bullets_and_project_story_order(version):
    p=core.load_profile(version)
    for pages in (1,2):
        s=default_selection(p,pages)
        core.validate_selection(s,p,pages)
        draft=selected_profile(p,s)
        for r in draft['experience']+draft['projects']:
            assert len(r['bullets'])==3
            if r['metric_bullet_ids']:
                assert {b['id'] for b in r['bullets']} & set(r['metric_bullet_ids'])
        for project in draft['projects']:
            assert [b['kind'] for b in project['bullets']]==['problem','implementation','outcome']
            assert project['metric_kind'] in ('outcome','missing')
        assert len(core.measurement_gaps(p,s))==2
        assert draft['experience'][0]['metric_kind']=='scope'


@pytest.mark.parametrize('count',[1,2,4])
def test_exact_three_is_required_for_roles(profile,count):
    s=default_selection(profile)
    s['experience']['e2']=[b['id'] for b in profile['experience'][1]['bullets'][:count]]
    with pytest.raises(core.UnparsableResponseError,match='exactly 3'):
        core.validate_selection(s,profile)


def test_project_structure_rejected_and_missing_benchmarks_flagged(profile):
    s=default_selection(profile)
    s['projects'][0]['bullets'].reverse()
    with pytest.raises(core.UnparsableResponseError,match='problem, implementation'):
        core.validate_selection(s,profile)
    s=default_selection(profile)
    core.validate_selection(s,profile)
    gaps=core.measurement_gaps(profile,s)
    assert len(gaps)==2
    assert any('PayFlow' in g for g in gaps)
    assert any('Key-Value' in g for g in gaps)


def test_required_metric_cannot_be_removed_by_rewrite(profile):
    p=response(profile)
    p['rewrites']=[{'bullet_id':'v1-e1-b1','text':'Develop Java components for Tidal.','reason':'Shorter'}]
    with pytest.raises(core.UnparsableResponseError,match='removes a required source metric'):
        core.parse_llm_output(json.dumps(p),profile)


def test_latex_injection_escaped():
    value=tex(r'\input{secret} & 20% $5 # _ ^ ~ < >')
    assert r'\input{' not in value
    assert r'\textbackslash{}input\{secret\}' in value
    assert r'20\%' in value


def test_selection_does_not_mutate_source(profile):
    before=copy.deepcopy(profile)
    selected_profile(profile,default_selection(profile),{'v1-e1-b1':'Changed'})
    assert profile==before


def test_keyword_punctuation_boundaries_and_aliases():
    score=core.keyword_coverage('Java C++ C# .NET sklearn SQL. Java','JavaScript C++ C# .NET Scikit-learn SQL')
    assert score['missing']==['java']
    assert score['total']==6
    assert core.keyword_coverage('and the for','Python')['percent'] is None


def test_profile_validation_rejects_duplicate_ids(profile):
    profile['experience'][1]['bullets'][0]['id']='v1-e1-b1'
    with pytest.raises(ValueError): core.validate_profile(profile)


def test_catalog_fails_closed_and_filters():
    with patch('core.requests.get',side_effect=requests.ConnectionError()):
        with pytest.raises(core.CatalogError): core.fetch_free_models()
    row={'id':'free/model','pricing':{'prompt':'0','completion':'0'},'context_length':64000,
         'architecture':{'input_modalities':['text'],'output_modalities':['text']}}
    paid=copy.deepcopy(row); paid['id']='paid'; paid['pricing']['request']='0.01'
    invalid=copy.deepcopy(row); invalid['context_length']='oops'
    audio=copy.deepcopy(row); audio['id']='audio'; audio['architecture']['output_modalities']=['text','audio']
    with patch('core.requests.get',return_value=http(body={'data':[row,paid,invalid,audio,None]})):
        assert core.fetch_free_models()==[{'id':'free/model','context_length':64000}]


CATALOG=[{'id':'free/one','context_length':100000},{'id':'free/two','context_length':100000}]


@patch('core.fetch_free_models',return_value=CATALOG)
def test_auth_failure_never_falls_back(catalog,profile):
    with patch('core.requests.post',return_value=http(401)) as post:
        with pytest.raises(core.InvalidAPIKeyError):
            core.run_optimization(profile,'Java','test-key','free/one',fallback_models=['free/two'])
        assert post.call_count==1


@patch('core.fetch_free_models',return_value=CATALOG)
def test_one_repair_and_contact_omission(catalog,profile):
    with patch('core.requests.post',side_effect=[http(body={'choices':[]}),completion(response(profile))]) as post:
        result=core.run_optimization(profile,'Java','test-key','free/one')
        assert post.call_count==2
        assert result.used_model=='free/one'
        payload=json.dumps(post.call_args.kwargs['json'])
        assert profile['email'] not in payload
        assert profile['phone'] not in payload


@patch('core.fetch_free_models',return_value=CATALOG)
def test_repair_auth_error_stays_auth_error(catalog,profile):
    with patch('core.requests.post',side_effect=[http(body={}),http(401)]):
        with pytest.raises(core.InvalidAPIKeyError): core.run_optimization(profile,'Java','key','free/one')


@patch('core.fetch_free_models',return_value=CATALOG)
def test_fallback_and_mixed_failures(catalog,profile):
    with patch('core.requests.post',side_effect=[http(429,headers={'Retry-After':'30'}),completion(response(profile))]):
        assert core.run_optimization(profile,'Java','key','free/one',fallback_models=['free/two']).used_model=='free/two'
    with patch('core.requests.post',side_effect=[http(429),http(503)]):
        with pytest.raises(core.AllModelsFailedError): core.run_optimization(profile,'Java','key','free/one',fallback_models=['free/two'])


@patch('core.fetch_free_models',return_value=CATALOG)
def test_all_rate_limited(catalog,profile):
    with patch('core.requests.post',return_value=http(429,headers={'Retry-After':'60'})):
        with pytest.raises(core.RateLimitedError) as error:
            core.run_optimization(profile,'Java','key','free/one',fallback_models=['free/two'])
        assert error.value.retry_after==60


def test_pdf_engine_unavailable(profile):
    with patch('core.shutil.which',return_value=None):
        assert not core.build_pdf(profile,default_selection(profile)).success


def test_pdf_timeout(profile):
    import subprocess
    with patch('core.shutil.which',return_value='/bin/tectonic'),patch('core.subprocess.run',side_effect=subprocess.TimeoutExpired('tectonic',1)):
        assert 'exceeded' in core.build_pdf(profile,default_selection(profile),timeout=1).log


@pytest.mark.parametrize('version',['v1','v2'])
@pytest.mark.parametrize('titles',[['PayFlow','Distributed Key-Value'],['Financial Fraud','CampusBuddy'],['Distributed Task','Distributed Key-Value']])
def test_jd_selection_uses_complete_catalog_without_fixed_projects(version,titles):
    p=core.load_profile(version)
    plan=response(p)
    chosen=[next(item for item in p['projects'] if title in item['title']) for title in titles]
    plan['selection']['projects']=[{'id':item['id'],'bullets':[b['id'] for b in item['bullets']]} for item in chosen]
    for assessment in plan['project_assessment']:
        assessment['selected']=assessment['id'] in {item['id'] for item in chosen}
    with patch('core.fetch_free_models',return_value=CATALOG),patch('core.requests.post',return_value=completion(plan)) as post:
        result=core.run_optimization(p,'Job requires '+', '.join(titles),'key','free/one',pages=1)
        payload=json.loads(post.call_args.kwargs['json']['messages'][1]['content'])
        assert payload['profile']['projects']==p['projects']
        assert 'default_projects' not in payload['profile']
        assert result.plan['selection']['projects']==plan['selection']['projects']


@pytest.mark.parametrize('mutation',['missing','duplicate','wrong-decision','empty-reason'])
def test_project_assessment_must_cover_full_library(profile,mutation):
    plan=response(profile)
    rows=plan['project_assessment']
    if mutation=='missing': rows.pop()
    if mutation=='duplicate': rows[-1]=copy.deepcopy(rows[0])
    if mutation=='wrong-decision': rows[0]['selected']=not rows[0]['selected']
    if mutation=='empty-reason': rows[0]['reason']=' '
    with pytest.raises(core.UnparsableResponseError): core.parse_llm_output(json.dumps(plan),profile)


def test_keyword_report_cannot_claim_omitted_evidence(profile):
    plan=response(profile)
    plan['keywords']=[{'priority':'CRITICAL','keyword':'fraud','evidence_ids':['v1-p1-b1'],'reason':'Not present in selected resume'}]
    with pytest.raises(core.UnparsableResponseError): core.parse_llm_output(json.dumps(plan),profile)
