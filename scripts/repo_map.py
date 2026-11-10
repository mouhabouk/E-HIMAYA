"""The repository map shown in the dashboard's «تطوير النظام» menu (Yamen, 2026-11-09; docs/dev/repo-map.md).

Run from the repository root, standard library only:
    python3 -I scripts/repo_map.py . services/api/app/modules/devtools/repo_map.json
Nodes: dashboard and portal pages, mobile features, API modules, services, infrastructure, external services.
Edges: import (code imports), http (/api/v1 paths of the front ends matched to FastAPI routers), calls (settings URLs).
"""

import os, re, json, collections, sys
R = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
def rd(p):
    try: return open(p, encoding='utf-8', errors='ignore').read()
    except: return ''
def walk(d, exts):
    for root, ds, fs in os.walk(os.path.join(R, d)):
        ds[:] = [x for x in ds if x not in ('node_modules','build','.dart_tool','dist','__pycache__')]
        for f in fs:
            if f.endswith(exts): yield os.path.join(root, f)
def loc(p): return rd(p).count('\n')
nodes = {}; edges = collections.Counter(); via = collections.defaultdict(set)
def node(i, label, group, **kw):
    if i not in nodes: nodes[i] = dict(id=i, label=label, group=group, files=0, loc=0, **kw)
    return nodes[i]
def add(n, p):
    n['files'] += 1; n['loc'] += loc(p)

# ---- API modules
API = 'services/api/app'
routes = []  # (literal_prefix, module)
pyfiles = list(walk(API, ('.py',)))
def api_mod(p):
    rel = os.path.relpath(p, os.path.join(R, API)).split(os.sep)
    if rel[0] == 'modules' and len(rel) > 1 and not rel[1].endswith('.py'): return 'api:' + rel[1]
    if rel[0] == 'core': return 'api:core'
    return 'api:app'
SETTINGS = {'vision_service_url':'svc:vision','vision_callback_url':'svc:vision','ai_service_url':'svc:ai','telephony_ari_url':'svc:telephony','telephony_ws_public_url':'svc:telephony','sms_phone_url':'ext:sms','sms_http_url':'ext:sms','routing_url':'infra:routing','opensearch_url':'infra:opensearch','ollama_url':'infra:ollama','mediamtx_api_url':'infra:mediamtx','stream_webrtc_public_url':'infra:mediamtx','stream_hls_public_url':'infra:mediamtx','stream_internal_rtsp_url':'infra:mediamtx','keycloak_admin_url':'infra:keycloak','oidc_jwks_base_url':'infra:keycloak','fcm_api_url':'ext:fcm','weather_api_url':'ext:weather','marine_api_url':'ext:weather','tsa_url':'ext:tsa','valkey_url':'infra:valkey','nats_url':'infra:nats','database_url':'infra:postgres','s3_endpoint_url':'infra:seaweedfs'}
for p in pyfiles:
    m = api_mod(p); label = m.split(':')[1]
    n = node(m, label, 'api'); add(n, p)
    s = rd(p)
    for t in re.findall(r'from app\.(modules\.[a-z_]+|core)', s) + re.findall(r'import app\.(modules\.[a-z_]+|core)', s):
        tgt = 'api:' + (t.split('.')[1] if t.startswith('modules') else 'core')
        if tgt != m: edges[(m, tgt, 'import')] += 1
    for k in re.findall(r'settings\.([a-z_]+_url)', s):
        if k in SETTINGS: edges[(m, SETTINGS[k], 'calls')] += 1
    if 'boto' in s or 'aioboto' in s or 'storage.' in s and m=='api:core': pass
    pref = dict(re.findall(r'(\w+)\s*=\s*APIRouter\(\s*prefix="([^"]*)"', s))
    for var, path in re.findall(r'@(\w+)\.(?:get|post|put|patch|delete|websocket|api_route)\(\s*"([^"]*)"', s):
        if var in pref: routes.append((pref[var] + path, m))
    for var, pf in pref.items():
        routes.append((pf, m))
# storage → seaweedfs, sessions → valkey
edges[('api:core','infra:seaweedfs','calls')] += 1
def lit(u): return re.split(r'[{$]', u)[0]
def norm_seg(u): return [x for x in u.split("/") if x]
ROUTES = [(lit(r), m, r) for r, m in routes]
def match(url):
    u = lit(url)
    best = 0; mods = collections.Counter()
    us = norm_seg(u)
    for rl, m, full in ROUTES:
        rs = norm_seg(full)
        k = 0
        for a, b in zip(us, rs):
            if a == b or (b.startswith('{')): k += 1
            else: break
        need = 4 if len(us) > 2 and us[2] in ('staff','me','internal') else 3
        if k < need: continue
        # must consume all literal url segments or all route segments
        if k > best: best, mods = k, collections.Counter({m: 1})
        elif k == best: mods[m] += 1
    if not mods: return set()
    top = max(mods.values())
    r = {m for m, c in mods.items() if c == top}
    return r if len(r) <= 2 else set()

URLRE = re.compile(r'''["'`](/api/v1/[^"'`\s]*)''')
# ---- TS apps
def ts_resolve(src, spec):
    if not spec.startswith('.'): return None
    b = os.path.normpath(os.path.join(os.path.dirname(src), spec))
    for c in (b, b+'.ts', b+'.tsx', b+'/index.ts', b+'/index.tsx'):
        if os.path.isfile(c): return c
def frontend(app, group, page_key):
    files = [p for p in walk(f'apps/{app}/src', ('.ts','.tsx')) if '.test.' not in p and '/test/' not in p]
    imp = {}; urls = {}; sym = {}; used = {}; methods = {}; imp_keys = set(os.path.normpath(f) for f in files)
    for p in files:
        s = rd(p)
        imp[p] = [x for x in (ts_resolve(p, sp) for sp in re.findall(r'''(?:from|import)\s*\(?\s*["']([^"']+)["']''', s)) if x and os.path.normpath(x) in imp_keys]
        urls[p] = set(URLRE.findall(s))
        consts = dict(re.findall(r'''const\s+(\w+)\s*=\s*(?:\([^)]*\)\s*(?::\s*\w+\s*)?=>\s*)?["'`](/api/v1/[^"'`]*)''', s))
        for _ in range(2):
            for k in list(consts): consts[k] = re.sub(r'\$\{(\w+)(?:\([^)]*\))?\}', lambda mo: consts.get(mo.group(1), mo.group(0)), consts[k])
        parts = re.split(r'\nexport\s+(?:async\s+)?(?:function\*?|const|let|class)\s+(\w+)', s)
        sm = {}
        for name, body in zip(parts[1::2], parts[2::2]):
            u = set(URLRE.findall(body)) | {v for k, v in consts.items() if re.search(r'\b%s\b' % k, body)}
            sm[name] = u
        sym[p] = sm
        names = {}
        for spec_names, sp in re.findall(r'''import\s+(?:type\s+)?\{([^}]*)\}\s*from\s*["']([^"']+)["']''', s):
            t = ts_resolve(p, sp)
            if t: names.setdefault(t, set()).update(x.strip().split(' as ')[0].replace('type ','').strip() for x in spec_names.split(','))
        used[p] = names
        if '/pages/' not in p:
            cur = None
            for line in s.split('\n'):
                mm = re.match(r'\s+(?:async\s+)?(\w+)\s*(?::\s*(?:async\s*)?(?:\(|\w+\s*=>|function)|\([^)]*\)\s*(?::[^{]*)?\{)', line)
                if mm and mm.group(1) not in ('if','for','while','switch','return','catch'): cur = mm.group(1)
                if cur:
                    ex = re.sub(r'`\$\{(\w+)(?:\([^)]*\))?\}', lambda mo: '`' + consts[mo.group(1)] if mo.group(1) in consts else mo.group(0), line)
                    found = set(URLRE.findall(ex)) | {v for k, v in consts.items() if re.search(r'\(\s*%s\b' % k, line)}
                    if found: methods.setdefault(cur, set()).update(found)
    def closure(p, stop):
        seen = {p}; st = [p]
        while st:
            x = st.pop()
            for y in imp.get(x, []):
                if y not in seen and not stop(y): seen.add(y); st.append(y)
        return seen
    def depth2(p):
        out = {p}
        for y in imp.get(p, []):
            if is_page(y): continue
            out.add(y)
            if '/lib/' in y:
                out.update(z for z in imp.get(y, []) if '/lib/' in z)
        return out
    pagedir = os.path.join(R, f'apps/{app}/src/pages')
    is_page = lambda y: y.startswith(pagedir)
    fanin = collections.Counter()
    for p in files:
        if is_page(p):
            for q in closure(p, is_page) - {p}: fanin[q] += 1
    npages = sum(1 for p in files if is_page(p))
    hub = {q for q, c in fanin.items() if c > max(6, npages * 0.15)}
    print(app, 'hub files:', len(hub), sorted(os.path.relpath(h, R) for h in hub if urls[h])[:10])
    for p in files:
        if not is_page(p): continue
        name = os.path.splitext(os.path.relpath(p, pagedir))[0]
        i = f'{group}:{name}'
        n = node(i, name.replace('Page','') or name, group); add(n, p)
        for q in depth2(p):
            pass
        def urls_from(src, depth):
            out = set(urls[src]) if src == p or '/components/' in src else set()
            for mname in re.findall(r'\bapi\.(\w+)\(', rd(src)): out |= methods.get(mname, set())
            for t in imp.get(src, []):
                if is_page(t): continue
                if t in used.get(src, {}) and t in sym and sym[t]:
                    for nm in used[src][t]: out |= sym[t].get(nm, set())
                elif '/components/' in t and depth < 2:
                    out |= urls_from(t, depth + 1)
                if '/components/' in t and depth < 2: out |= urls_from(t, depth + 1)
            return out
        for u in urls_from(p, 0):
            for m in match(u):
                edges[(i, m, 'http')] += 1; via[(i, m)].add(u)
        for y in imp[p]:
            if is_page(y):
                j = f'{group}:' + os.path.splitext(os.path.relpath(y, pagedir))[0]
                edges[(i, j, 'import')] += 1
frontend('dashboard', 'dashboard', 'pages')
frontend('portal', 'portal', 'pages')

# ---- Mobile (Dart)
ML = os.path.join(R, 'apps/mobile/lib')
dfiles = list(walk('apps/mobile/lib', ('.dart',)))
def dmod(p):
    rel = os.path.relpath(p, ML).split(os.sep)
    if rel[0] == 'features': return 'mobile:' + rel[1]
    if rel[0] in ('staff','core','l10n'): return 'mobile:' + rel[0]
    return 'mobile:app'
def dres(src, spec):
    if spec.startswith('package:ehimaya/'): return os.path.join(ML, spec[len('package:ehimaya/'):])
    if spec.startswith('package:') or spec.startswith('dart:'): return None
    return os.path.normpath(os.path.join(os.path.dirname(src), spec))
dimp = {}; durl = {}
for p in dfiles:
    s = rd(p); m = dmod(p)
    n = node(m, m.split(':')[1], 'mobile'); add(n, p)
    dimp[p] = [x for x in (dres(p, sp) for sp in re.findall(r'''^(?:import|export)\s+'([^']+)';''', s, re.M)) if x]
    durl[p] = set(URLRE.findall(s))
for p in dfiles:
    m = dmod(p)
    for y in dimp[p]:
        t = dmod(y)
        if t != m and os.path.isfile(y): edges[(m, t, 'import')] += 1
    for u in durl[p]:
        for t in match(u): edges[(m, t, 'http')] += 1; via[(m, t)].add(u)

# ---- other services & infra
for svc in ['ai','vision','notify-sim','sensor-gateway','camera-bridge','telephony']:
    n = node('svc:'+svc, svc, 'service')
    for p in walk('services/'+svc, ('.py','.conf','.sh','.lua')):
        if '/tests/' in p or '/eval/' in p: continue
        add(n, p)
for i, l in [('infra:postgres','PostgreSQL'),('infra:valkey','Valkey'),('infra:nats','NATS'),('infra:seaweedfs','SeaweedFS (S3)'),('infra:keycloak','Keycloak'),('infra:mediamtx','MediaMTX'),('infra:opensearch','OpenSearch'),('infra:ollama','Ollama'),('infra:routing','Routing')]:
    node(i, l, 'infra')
for i, l in [('ext:sms','SMS gateway'),('ext:fcm','FCM push'),('ext:weather','Open-Meteo'),('ext:tsa','Timestamp TSA')]:
    node(i, l, 'external')
# service → api / infra (from source text)
for svc, pat in [('vision', r'api:8000|API_URL|api_url'), ('sensor-gateway', r'api_url|API_URL|/api/v1'), ('notify-sim', r'api_url|API_URL'), ('camera-bridge', r'api_url|API_URL|mediamtx|rtsp')]:
    txt = ''.join(rd(p) for p in walk('services/'+svc, ('.py',)) if '/tests/' not in p)
    if re.search(r'api:8000|api_url|API_URL|/api/v1', txt): edges[('svc:'+svc, 'api:app', 'calls')] += 1
    if re.search(r'nats', txt, re.I): edges[('svc:'+svc, 'infra:nats', 'calls')] += 1
    if re.search(r'rtsp|mediamtx', txt, re.I): edges[('svc:'+svc, 'infra:mediamtx', 'calls')] += 1
ai = ''.join(rd(p) for p in walk('services/ai', ('.py',)) if '/tests/' not in p)
if re.search('ollama', ai, re.I): edges[('svc:ai','infra:ollama','calls')] += 1
edges[('api:core','infra:postgres','calls')] += 1
edges[('svc:telephony','api:telephony','calls')] += 0

E = [dict(s=a, t=b, k=k, w=w, via=sorted(via.get((a,b), []))[:6]) for (a,b,k), w in edges.items() if w > 0 and a in nodes and b in nodes and a != b]
deg = collections.Counter()
for e in E: deg[e['s']] += 1; deg[e['t']] += 1
for n in nodes.values(): n['deg'] = deg[n['id']]
json.dump(dict(nodes=list(nodes.values()), edges=E, routes=len(routes)), open(OUT,'w'), ensure_ascii=False)
g = collections.Counter(n['group'] for n in nodes.values()); k = collections.Counter(e['k'] for e in E)
print(len(nodes), len(E), dict(g), dict(k), len(routes))
print('top in:', collections.Counter({n['id']: sum(1 for e in E if e['t']==n['id']) for n in nodes.values()}).most_common(12))
unmatched = [n['id'] for n in nodes.values() if n['group'] in ('dashboard','portal') and not any(e['s']==n['id'] and e['k']=='http' for e in E)]
print('pages w/o api:', len(unmatched), unmatched[:30])
