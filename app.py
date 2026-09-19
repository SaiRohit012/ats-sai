"""Streamlit interface; all source and run state is private to the current session."""
import copy
import datetime as dt
import hashlib
import json

import streamlit as st

import core
from renderer import default_selection, render_latex, visible_text

st.set_page_config(page_title='Resume Studio | Sai Rohit', page_icon='📄', layout='wide')
st.title('Resume Studio')
st.caption('Readable resumes, evidence-based tailoring, and inspectable PDFs.')

for version in ('v1','v2'):
    if version not in st.session_state:
        st.session_state[version] = core.load_profile(version)
for key, default in [('history',[]),('current',None),('models',[]),('model_error','')]:
    if key not in st.session_state: st.session_state[key] = default


def save_run(profile, selection, pages, jd, plan=None, model='Local selection', rewrites=None):
    run = {'id':dt.datetime.now().isoformat(timespec='microseconds'), 'profile':copy.deepcopy(profile),
           'selection':copy.deepcopy(selection), 'pages':pages, 'jd':jd, 'plan':copy.deepcopy(plan),
           'model':model, 'rewrites':copy.deepcopy(rewrites or {}), 'pdf':None}
    with st.spinner('Building and checking the PDF…'):
        run['pdf'] = core.build_pdf(run['profile'],run['selection'],pages,run['rewrites'])
    st.session_state.current = run
    st.session_state.history = [run] + st.session_state.history[:7]


with st.sidebar:
    st.header('Your resume')
    version = st.selectbox('Source version',['v1','v2'],format_func=lambda v: 'V1 · Detailed source / serif' if v=='v1' else 'V2 · Engineering source / sans serif')
    pages = st.radio('Page target',[1,2],format_func=lambda x:f'{x} pages' if x==2 else '1 page · selected projects',horizontal=True)
    st.caption('Exactly 3 bullets per job and selected project. Projects follow problem, implementation and outcome, with measured figures where available. All jobs, education and skills remain.')
    api_key = st.text_input('OpenRouter API key',type='password',key='api_key')
    st.caption('AI receives career evidence and the job description. Contact details stay local. Providers have their own data policies.')
    if st.button('Refresh free models'):
        try:
            st.session_state.models = core.fetch_free_models()
            st.session_state.model_error = ''
        except core.CatalogError as e:
            st.session_state.models = []
            st.session_state.model_error = str(e)
    if st.session_state.model_error: st.warning(st.session_state.model_error)
    models = st.session_state.models
    selected_model = st.selectbox('Free model',[m['id'] for m in models],index=0 if models else None,
                                  placeholder='Refresh to load the live catalog')
    st.caption('Sorted by context capacity, which is not a quality rating. Pricing is rechecked at run time.')
    suggest_project = st.checkbox('Suggest an unbuilt project for gaps',value=False)
    if st.session_state.history:
        st.subheader('Session history')
        for run in st.session_state.history:
            label = f"{run['id'][11:19]} · {run['profile']['version'].upper()} · {(run['jd'][:24] or 'Local preview')}"
            if st.button(label,key='history-'+run['id']): st.session_state.current = run
        if st.button('Clear results and history'):
            st.session_state.current = None
            st.session_state.history = []
            st.rerun()

profile = st.session_state[version]
with st.expander('Review source facts and edit your resume'):
    st.write('Both versions use your confirmed employment dates and retain both HSBC achievement sets for tailoring.')
    for fact in profile.get('confirmed_facts',[]): st.info(fact)
    for note in profile['review_notes']: st.warning(note)
    profile_json = st.text_area('Editable profile JSON',value=json.dumps(profile,indent=2,ensure_ascii=False),height=320,key='editor-'+version)
    if st.button('Save profile for this session'):
        try:
            edited = json.loads(profile_json)
            core.validate_profile(edited)
            if edited['version'] != version: raise ValueError('Keep the version field unchanged.')
            st.session_state[version] = edited
            st.success('Profile saved. Generate a new draft to use these changes.')
            profile = edited
        except (ValueError,TypeError) as e: st.error(str(e))
    st.download_button('Download profile JSON',json.dumps(profile,indent=2,ensure_ascii=False),file_name=f'resume_{version}.json',mime='application/json')
    st.caption('Session edits are not permanent. Replace the matching file in profiles/ with the downloaded JSON to save changes in the project.')

jd = st.text_area('Job description',height=170,placeholder='Paste a job description for tailoring, or leave blank to preview the base resume.',key='jd')
st.caption(f'AI tailoring evaluates all {len(profile["projects"])} projects against this JD. Manual preview choices do not constrain AI selection.')
selection = default_selection(profile,pages)
with st.expander('Choose projects and bullets manually'):
    st.caption('These controls affect only Build resume preview. The AI selects independently from the full library.')
    fingerprint = hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest()[:10]
    prefix = f'{version}-{pages}-{fingerprint}'
    for role in profile['experience']:
        bullet_map = {b['id']:b['text'] for b in role['bullets']}
        selection['experience'][role['id']] = st.multiselect(role['company']+' bullets',list(bullet_map),
            default=selection['experience'][role['id']],format_func=lambda k,m=bullet_map:m[k],key=prefix+role['id'],max_selections=3)
        st.caption(role.get('metric_note',''))
    projects = {p['id']:p for p in profile['projects']}
    chosen = st.multiselect('Projects to include',list(projects),default=[p['id'] for p in selection['projects']],
                            format_func=lambda k:projects[k]['title'],key=prefix+'projects',max_selections=2 if pages==1 else 3)
    selection['projects'] = []
    for pid in chosen:
        bullet_map = {b['id']:b['text'] for b in projects[pid]['bullets']}
        ids = st.multiselect(projects[pid]['title']+' bullets',list(bullet_map),
                             default=profile.get('default_project_bullets',{}).get(pid,list(bullet_map)[:3]),format_func=lambda k,m=bullet_map:m[k],key=prefix+pid,max_selections=3)
        st.caption(projects[pid].get('metric_note',''))
        selection['projects'].append({'id':pid,'bullets':ids})

c1,c2 = st.columns(2)
with c1:
    if st.button('Build resume preview',type='primary',use_container_width=True):
        try:
            core.validate_selection(selection,profile,pages)
            save_run(profile,selection,pages,jd)
            st.rerun()
        except (core.OptimizationError,ValueError) as e: st.error(str(e))
with c2:
    if st.button('Tailor to this job with AI',disabled=not(api_key and jd.strip() and selected_model),use_container_width=True):
        try:
            with st.spinner('Selecting relevant evidence and proposing edits. Provider calls have bounded timeouts…'):
                result = core.run_optimization(profile,jd,api_key,selected_model,pages,suggest_project,
                                               [m['id'] for m in models if m['id']!=selected_model][:2])
            save_run(profile,result.plan['selection'],pages,jd,result.plan,result.used_model)
            st.rerun()
        except core.RateLimitedError as e:
            st.error(str(e)+(f' Retry in approximately {e.retry_after:.0f}s.' if e.retry_after is not None else ''))
        except core.OptimizationError as e: st.error(str(e))

run = st.session_state.current
if run:
    st.divider()
    st.subheader('JD-tailored draft for review' if run['plan'] else 'Generic / manual preview')
    if not run['plan']: st.info('This preview has not selected projects for your JD. Use Tailor to this job with AI to evaluate the full library.')
    st.caption(f"Source: {run['profile']['version'].upper()} · Created: {run['id'][:19]} · Method: {run['model']}")
    st.caption('This result uses its saved profile and job description. Changing the controls above does not change an earlier result.')
    p, choice, approved = run['profile'], run['selection'], run['rewrites']
    for gap in core.measurement_gaps(p,choice): st.warning(gap)
    result_text = visible_text(p,choice,approved,run['pages'])
    baseline_text = visible_text(p,default_selection(p,run['pages']),pages=run['pages'])
    if run['jd'].strip():
        before = core.keyword_coverage(run['jd'],baseline_text)
        after = core.keyword_coverage(run['jd'],result_text)
        c1,c2,c3=st.columns(3)
        c1.metric('Keyword coverage · base',f"{before['percent']}%" if before['percent'] is not None else 'N/A')
        c2.metric('Keyword coverage · draft',f"{after['percent']}%" if after['percent'] is not None else 'N/A')
        c3.metric('Terms not found',len(after['missing']))
        st.caption('Unique word overlap with basic aliases; includes nontechnical JD words. Not an ATS score, fit assessment or shortlisting probability. Do not add unsupported skills to raise it.')
    preview, review, comparison, report, export = st.tabs(['PDF & extracted text','Review wording','Changes','Job analysis','Export'])
    with preview:
        pdf = run['pdf']
        if pdf and pdf.success:
            st.write(f'**{pdf.pages} page(s) rendered** · {pdf.engine}')
            for warning in pdf.warnings: st.warning(warning)
            for i,png in enumerate(core.pdf_previews(pdf.pdf_bytes),1):
                st.image(png,caption=f'Page {i} of {pdf.pages}',width=760)
            with st.expander('Text extracted from this PDF'):
                st.text(pdf.text)
            st.caption('Inspect every page. Extractable text is useful evidence of readability, but does not certify every ATS parser.')
        else:
            st.error('PDF could not be built. The editable source is available in Export.')
            if pdf: st.code(pdf.log[-6000:])
            if st.button('Retry PDF build'):
                with st.spinner('Building PDF…'): run['pdf'] = core.build_pdf(p,choice,run['pages'],approved)
                st.rerun()
    with review:
        plan = run['plan']
        if not plan or not plan['rewrites']:
            st.info('No wording changes proposed. The draft uses source bullets.')
        else:
            st.write('Select only rewrites that still describe your work accurately. Unselected bullets keep their original wording.')
            source_bullets = {b['id']:b['text'] for r in p['experience']+p['projects'] for b in r['bullets']}
            accepted = {}
            for item in plan['rewrites']:
                st.write('**Source:** '+source_bullets[item['bullet_id']])
                st.write('**Proposed:** '+item['text'])
                st.caption(item['reason'])
                if st.checkbox('I verified this wording',value=item['bullet_id'] in approved,key=run['id']+item['bullet_id']):
                    accepted[item['bullet_id']] = item['text']
            if st.button('Apply reviewed wording and rebuild'):
                save_run(p,choice,run['pages'],run['jd'],plan,run['model'],accepted)
                st.rerun()
    with comparison:
        st.code(core.unified_diff(baseline_text,result_text) or 'No changes from the base selection.',language='diff')
        kept = {s['id'] for s in choice['projects']}
        st.write('**Projects retained:** '+', '.join(r['title'] for r in p['projects'] if r['id'] in kept))
        st.write('**Projects available but omitted:** '+(', '.join(r['title'] for r in p['projects'] if r['id'] not in kept) or 'None'))
    with report:
        for note in p['review_notes']: st.warning(note)
        st.write('**Saved job description**')
        st.text(run['jd'] or 'No job description supplied.')
        if run['jd'].strip():
            st.write('**Matched terms:** '+', '.join(after['matched']))
            st.write('**Terms not found:** '+', '.join(after['missing']))
        if run['plan']:
            st.write('**AI analysis · verify against the source**')
            names = {item['id']:item['title'] for item in p['projects']}
            st.write('**Project selection across the full library**')
            st.table([{'Project':names[item['id']], 'Decision':'Include' if item['selected'] else 'Omit',
                       'JD rationale':item['reason']} for item in run['plan']['project_assessment']])
            st.json({'keywords':run['plan']['keywords'],'notes':run['plan']['notes']})
            if run['plan']['project_idea']:
                st.write('**Unbuilt project idea · excluded from the resume**')
                st.json(run['plan']['project_idea'])
    with export:
        stem = f"sai_rohit_{p['version']}"
        if run['pdf'] and run['pdf'].success:
            if run['pdf'].warnings: st.warning('PDF checks need attention. This export remains a draft; resolve the reported issues before applying.')
            st.download_button('Download PDF draft',run['pdf'].pdf_bytes,file_name=stem+'.pdf',mime='application/pdf')
            st.download_button('Download extracted PDF text',run['pdf'].text,file_name=stem+'.txt',mime='text/plain')
        st.download_button('Download LaTeX',render_latex(p,choice,run['pages'],approved),file_name=stem+'.tex',mime='text/x-tex')
        snapshot = {k:v for k,v in run.items() if k != 'pdf'}
        st.download_button('Download run record',json.dumps(snapshot,indent=2,ensure_ascii=False),file_name=stem+'_run.json',mime='application/json')
