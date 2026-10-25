import re,subprocess,html
def L(h):
  r,g,b=[int(h[i:i+2],16)/255 for i in (1,3,5)]
  f=lambda c:c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
  return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def cr(a,b):
  x,y=sorted([L(a),L(b)]);return f"{(y+0.05)/(x+0.05):.1f}:1"
def rgb(h): return ', '.join(str(int(h[i:i+2],16)) for i in (1,3,5))
def sw(h): return f'<span class="sw" style="background:{h}"></span>'
W='#FFFFFF'; I='#182038'
base=[('ink','الحبر','#182038','#E8ECF5','العناوين والنصوص',cr(I,W)),
('muted','النص الثانوي','#5B6478','#A6AFC4','الشروح والتواريخ',cr('#5B6478',W)),
('page','خلفية الصفحة','#F3F5FA','#0E1426','خلفية كل الشاشات','—'),
('card','البطاقة','#FFFFFF','#161E35','البطاقات والقوائم وشريط العنوان','—'),
('line','الحدود','#E3E7EF','#26304D','حدود البطاقات والفواصل','زخرفي'),
('navy','الكحلي (الأساسي)','#1F3FA0','#8FA8FF','الأزرار الأساسية، الاختيار، الروابط',cr('#1F3FA0',W)+' مع الأبيض'),
('red','الأحمر (الطوارئ)','#D7141A','#FF6B6B','198، النجدة، التنبيهات',cr('#D7141A',W)+' مع الأبيض'),
('orange','البرتقالي (التمييز)','#F08C00','#FFA733','شريط الخطوات وإطار الاختيار، لا يُكتب به نص',cr('#F08C00',I)+' مع الحبر'),
('orangeStrong','البرتقالي الداكن','#C25E00','#FFA733','أزرار ونصوص برتقالية بخط عريض كبير',cr('#C25E00',W)+' مع الأبيض'),
('green','الأخضر','#188038','#4CC772','الاتصال، السلامة، حلقة النسبة',cr('#188038',W)+' مع الأبيض'),
('purple','البنفسجي','#7838A0','#C49BE6','المعلومة، الأطباء، المعرفة',cr('#7838A0',W)+' مع الأبيض'),
('teal','الأخضر المزرق','#00806A','#4DD0B8','الشراكات، الخرائط، الأماكن',cr('#00806A',W)+' مع الأبيض'),
('amber','الكهرماني','#F5B400','#FFC933','المقترحات، التنبيهات (رمز بالحبر)',cr('#F5B400',I)+' مع الحبر'),
('pink','الوردي','#C2185B','#F06292','المكافآت',cr('#C2185B',W)+' مع الأبيض'),
('sky','السماوي','#1976D2','#64B5F6','الطقس، الإشعارات',cr('#1976D2',W)+' مع الأبيض'),
('slate','الرمادي','#5B6478','#A6AFC4','الإعدادات والعناصر المحايدة',cr('#5B6478',W)+' مع الأبيض')]
tones=[('red','#D7141A','#FFFFFF','#FDE8E8','#B3121A','الطوارئ، البلاغ، النجدة، البث'),
('navy','#1F3FA0','#FFFFFF','#E8EDFA','#1F3FA0','المتابعة، المؤسسة، الحساب'),
('purple','#7838A0','#FFFFFF','#F2EAF8','#5E2A80','المعلومة، المعرفة، الأطباء'),
('green','#188038','#FFFFFF','#E6F4EA','#166B2E','السؤال، السلامة، الصحة'),
('amber','#F5B400','#182038','#FFF3D6','#7A4B00','المقترح، التحذير، الصيانة'),
('teal','#00806A','#FFFFFF','#E0F3EF','#00695A','الشراكات، الأماكن، الخرائط'),
('slate','#5B6478','#FFFFFF','#EEF0F4','#3E4657','الإعدادات، الخلل، المحايد'),
('pink','#C2185B','#FFFFFF','#FCE7EF','#9C1248','المكافآت، الثقافة'),
('sky','#1976D2','#FFFFFF','#E3F0FC','#0D5AA7','الطقس، الإشعارات'),
('orange','#F08C00','#182038','#FFF0DC','#8A4600','الحماية المدنية 198، الخطوات')]
sem=[('--status-received','مستلَم','#C62828'),('--status-in_progress','قيد المعالجة','#B45309'),('--status-intervened','تم التدخل','#1D4ED8'),('--status-ongoing','متواصل','#7E22CE'),('--status-closed','مغلق','#15803D'),('--status-rejected','مرفوض','#57606A'),
('--prio-critical','أولوية حرجة','#7F1D1D'),('--prio-high','أولوية عالية','#B91C1C'),('--prio-medium','أولوية متوسطة','#B45309'),('--prio-low','أولوية منخفضة','#4B5563'),
('--poi-hazmat','مواد خطرة على الخريطة','#C2410C'),('--poi-evac','نقطة تجمع','#15803D'),('--poi-water','نقطة ماء','#0369A1'),('--poi-alarm','إنذار','#B91C1C'),('--poi-unit','وحدة','#1E3A8A'),('--poi-volunteer','متطوع','#7E22CE'),('--focus','إطار التركيز (لوحة المفاتيح)','#1A56DB')]
# web icons
src=open('apps/dashboard/src/components/Icon.tsx').read()
block=src.split('const PATHS = {')[1].split('\n}')[0]
paths=dict(re.findall(r'(\w+):\s*"([^"]+)"',block))
usage={'home':('navy','المؤشرات'),'description':('red','البلاغات'),'localFireDepartment':('red','الحوادث'),'map':('teal','الخريطة الحية'),'videocam':('red','البث المباشر'),'volunteerActivism':('green','المتطوعون'),'call':('green','المكالمات'),'inventory2':('amber','طلبات الموارد'),'schedule':('orange','البلاغات المتأخرة'),'wrongLocation':('orange','التحقق الجغرافي'),'stethoscope':('purple','الأطباء'),'groups':('purple','اللجنة الطبية'),'localShipping':('amber','الموارد'),'campaign':('sky','الإشعارات والتنبيهات'),'partlyCloudyDay':('sky','تنبيهات جوية مقترحة'),'monitoring':('navy','اللجان'),'analytics':('navy','التحليلات'),'folderOpen':('slate','التقارير'),'historyEdu':('purple','الذاكرة الوطنية'),'menuBook':('purple','مكتبة الأحداث'),'militaryTech':('pink','المكافآت'),'apartment':('navy','المؤسسات / مؤسساتي'),'workspacePremium':('amber','مراجعة الشهادات'),'healthAndSafety':('green','نصائح السلامة'),'medicalServices':('red','مركز الطوارئ'),'layers':('teal','طبقات الخريطة'),'mail':('sky','اتصل بنا'),'settings':('slate','الإعدادات الوطنية'),'smartToy':('slate','إعدادات الذكاء الاصطناعي'),'manageAccounts':('slate','الحسابات'),'policy':('slate','سجل التدقيق'),'lockOpen':('red','الوصول الاستثنائي'),'verified':('green','التحقق من شهادة (البوابة)'),'chevronRight':('slate','سهم البطاقة'),'warning':('amber','تحذير')}
tonefill={t[0]:t[1] for t in tones}
def snake(c): return re.sub(r'([A-Z0-9]+)',lambda m:'_'+m.group(1).lower(),c).replace('_2','_2')
rows=[]
for k,d in paths.items():
  t,u=usage.get(k,('slate','—')); n=snake(k)
  rows.append(f'<tr><td><span class="tile" style="background:{tonefill[t]}"><svg viewBox="0 -960 960 960" aria-hidden="true"><path fill="{"#182038" if t in ("amber","orange") else "#fff"}" d="{d}"/></svg></span></td><td class="ltr"><code>{n}</code></td><td>{u}</td><td>{t}</td><td><a href="https://fonts.google.com/icons?selected=Material+Symbols+Rounded:{n}:FILL@1" target="_blank" rel="noopener">صفحة الأيقونة</a> · <a href="https://raw.githubusercontent.com/google/material-design-icons/master/symbols/web/{n}/materialsymbolsrounded/{n}_fill1_24px.svg" target="_blank" rel="noopener">SVG</a></td></tr>')
mob=subprocess.run("grep -rhoE 'Icons\\.[a-z0-9_]+' apps/mobile/lib | sed 's/Icons\\.//' | sort -u",shell=True,capture_output=True,text=True).stdout.split()
mobtiles=''.join(f'<li><span class="ms" aria-hidden="true">{re.sub(r"_(outlined|rounded|outline)$","",n) if not n.endswith("_outline") or n in ("star_outline",) else n}</span><code class="ltr">{n}</code></li>' for n in mob)
def t_base():
  return ''.join(f'<tr><td>{sw(l)}</td><td>{ar}<br><code class="ltr">{k}</code></td><td class="ltr"><code>{l}</code><br><small>RGB {rgb(l)}</small></td><td>{sw(d)}</td><td class="ltr"><code>{d}</code></td><td>{u}</td><td class="ltr">{c}</td></tr>' for k,ar,l,d,u,c in base)
def t_tone():
  return ''.join(f'<tr><td><code class="ltr">{k}</code></td><td>{sw(f)} <code class="ltr">{f}</code></td><td>{sw(o)} <code class="ltr">{o}</code></td><td>{sw(ti)} <code class="ltr">{ti}</code></td><td>{sw(ink)} <code class="ltr">{ink}</code></td><td><span class="pill" style="background:{ti};color:{ink}">مثال</span></td><td>{u}</td></tr>' for k,f,o,ti,ink,u in tones)
def t_sem(): return ''.join(f'<tr><td>{sw(h)}</td><td>{ar}</td><td class="ltr"><code>{v}</code></td><td class="ltr"><code>{h}</code></td></tr>' for v,ar,h in sem)
page=f'''<title>مرجع تصميم ء-حماية</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;700&display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&display=block">
<style>
/* Layout: one reference sheet in the project's own design system — grey page, white sections, tables. */
:root{{--page:#f3f5fa;--card:#fff;--ink:#182038;--muted:#5b6478;--line:#e3e7ef;--navy:#1f3fa0;--code:#eef0f4;--font:"IBM Plex Sans Arabic","Segoe UI",Tahoma,sans-serif}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--page:#0e1426;--card:#161e35;--ink:#e8ecf5;--muted:#a6afc4;--line:#26304d;--navy:#8fa8ff;--code:#1c2541;color-scheme:dark}}}}
:root[data-theme="dark"]{{--page:#0e1426;--card:#161e35;--ink:#e8ecf5;--muted:#a6afc4;--line:#26304d;--navy:#8fa8ff;--code:#1c2541;color-scheme:dark}}
body{{background:var(--page);color:var(--ink);font-family:var(--font);font-size:15px;line-height:1.7}}
.wrap{{max-width:1150px;margin:0 auto;padding-block:24px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:20px}}
header h1{{margin:0;font-size:1.9rem}} header p{{margin:4px 0 0;color:var(--muted);max-width:70ch}}
nav{{display:flex;flex-wrap:wrap;gap:6px}} nav a{{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:2px 12px;color:var(--navy);text-decoration:none;font-weight:600;font-size:14px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px;min-width:0}}
h2{{margin:0 0 4px;font-size:1.3rem}} h3{{margin:16px 0 6px;font-size:1.05rem}}
section>p{{margin:0 0 10px;color:var(--muted);max-width:75ch}}
.tbl{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{border-bottom:1px solid var(--line);padding:7px 8px;text-align:start;vertical-align:middle}}
th{{color:var(--muted);font-size:12.5px;font-weight:700;white-space:nowrap}}
code{{background:var(--code);border-radius:6px;padding:0 5px;font-size:12.5px;font-variant-numeric:tabular-nums}}
.ltr{{direction:ltr;unicode-bidi:isolate}} td.ltr{{text-align:left}}
.sw{{display:inline-block;inline-size:34px;block-size:34px;border-radius:10px;border:1px solid var(--line);vertical-align:middle}}
td .sw{{inline-size:26px;block-size:26px;border-radius:8px}}
.pill{{display:inline-block;border-radius:999px;padding:1px 10px;font-size:12px;font-weight:700}}
.tile{{display:inline-grid;place-items:center;inline-size:36px;block-size:36px;border-radius:10px}} .tile svg{{inline-size:20px;block-size:20px}}
a{{color:var(--navy)}}
ul.icons{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px}}
ul.icons li{{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:10px;padding:4px 8px;min-width:0}}
ul.icons code{{font-size:11px;overflow-wrap:anywhere;background:none;padding:0}}
.ms{{font-family:"Material Symbols Rounded";font-size:22px;line-height:1;color:var(--navy);font-feature-settings:"liga";flex:none}}
.shape{{display:inline-block;inline-size:60px;block-size:36px;background:var(--page);border:1px solid var(--line)}}
small{{color:var(--muted)}}
</style>
<div class="wrap" dir="rtl" lang="ar">
<header><h1>مرجع تصميم ء-حماية</h1>
<p>كل الألوان ورموزها، والأيقونات، والإطارات والأشكال، والخطوط وأطر العمل مع مصادرها وروابط تحميلها. هو المرجع الإلزامي للتطبيق والبوابة واللوحات، ومصدره في المستودع <code class="ltr">docs/design-system.md</code>. الإصدار 2026-10-24.</p></header>
<nav aria-label="أقسام المرجع"><a href="#colors">الألوان الأساسية</a><a href="#tones">ألوان الفئات</a><a href="#semantic">ألوان الحالات</a><a href="#type">الخط</a><a href="#icons">الأيقونات</a><a href="#shapes">الإطارات والأشكال</a><a href="#frameworks">أطر العمل والمصادر</a></nav>

<section id="colors"><h2>1. الألوان الأساسية</h2><p>الرمز Hex هو المرجع في الكود. نسبة التباين محسوبة بمعيار WCAG 2.2 (المطلوب 4.5:1 للنص العادي و3:1 للنص العريض الكبير والأيقونات).</p>
<div class="tbl"><table><tr><th>فاتح</th><th>الاسم والرمز البرمجي</th><th>القيمة (فاتح)</th><th>داكن</th><th>القيمة (داكن)</th><th>الاستعمال</th><th>التباين</th></tr>{t_base()}</table></div></section>

<section id="tones"><h2>2. ألوان الفئات (10 ألوان)</h2><p>لكل فئة أربع قيم: التعبئة، ولون الرمز فوقها، والخلفية الفاتحة للشارات والمربعات الناعمة، ولون النص فوق تلك الخلفية. هي نفسها في التطبيق (<code class="ltr">Tone</code> في <code class="ltr">tokens.dart</code>) والويب (<code class="ltr">--tone-*</code>).</p>
<div class="tbl"><table><tr><th>الفئة</th><th>التعبئة</th><th>الرمز فوقها</th><th>الخلفية الفاتحة</th><th>النص فوقها</th><th>شارة</th><th>الاستعمال</th></tr>{t_tone()}</table></div>
<p>في الوضع الداكن تُرفع التعبئة إلى درجة أفتح (مثلا الأحمر <code class="ltr">#FF6B6B</code> والأخضر <code class="ltr">#4CC772</code>)، والخلفية الفاتحة تصبح اللون نفسه بشفافية 18%.</p></section>

<section id="semantic"><h2>3. ألوان الحالات في لوحة القيادة</h2><p>كل لون منها مرفوق دائما بكلمة أو شكل، فلا يحمل المعنى وحده.</p>
<div class="tbl"><table><tr><th></th><th>المعنى</th><th>المتغير</th><th>القيمة</th></tr>{t_sem()}</table></div></section>

<section id="type"><h2>4. الخط</h2>
<div class="tbl"><table><tr><th>الخط</th><th>الأوزان</th><th>أين</th><th>الرخصة</th><th>التحميل</th></tr>
<tr><td style="font-weight:700">IBM Plex Sans Arabic<br><small>عربي ولاتيني في عائلة واحدة</small></td><td>400 · 500 · 600 · 700</td><td>التطبيق: <code class="ltr">apps/mobile/assets/fonts/*.ttf</code><br>الويب: الحزمة <code class="ltr">@fontsource/ibm-plex-sans-arabic</code> 5.3.0</td><td>SIL OFL 1.1</td><td><a href="https://fonts.google.com/specimen/IBM+Plex+Sans+Arabic" target="_blank" rel="noopener">Google Fonts</a> · <a href="https://github.com/google/fonts/tree/main/ofl/ibmplexsansarabic" target="_blank" rel="noopener">ملفات TTF</a> · <a href="https://www.npmjs.com/package/@fontsource/ibm-plex-sans-arabic" target="_blank" rel="noopener">npm</a> · <a href="https://github.com/IBM/plex" target="_blank" rel="noopener">المصدر (IBM)</a></td></tr></table></div>
<div class="tbl"><table><tr><th>النمط</th><th>الحجم / الوزن</th></tr><tr><td>عنوان الشاشة</td><td>22 / 700</td></tr><tr><td>عنوان القسم</td><td>17 / 700</td></tr><tr><td>عنوان البطاقة</td><td>16 / 700</td></tr><tr><td>النص</td><td>15 / 400</td></tr><tr><td>الشرح</td><td>13 / 500 بلون muted</td></tr><tr><td>الزر</td><td>16 / 700</td></tr><tr><td>الشارة</td><td>12 / 700</td></tr></table></div></section>

<section id="icons"><h2>5. الأيقونات</h2><p>مجموعة واحدة: Material Symbols / Material Icons من Google، رخصة Apache 2.0. الشكل المعتمد: مستدير (Rounded) ومعبأ داخل المربعات الملونة. لا أيقونات من تطبيقات أخرى.</p>
<p><a href="https://fonts.google.com/icons?icon.style=Rounded" target="_blank" rel="noopener">تصفح كل الأيقونات وتحميلها</a> · <a href="https://github.com/google/material-design-icons" target="_blank" rel="noopener">المستودع (SVG وخطوط)</a> · <a href="https://api.flutter.dev/flutter/material/Icons-class.html" target="_blank" rel="noopener">قائمة Icons في Flutter</a> · <a href="https://www.apache.org/licenses/LICENSE-2.0" target="_blank" rel="noopener">الرخصة</a></p>
<h3>لوحة القيادة والبوابة ({len(paths)} أيقونة، مضمَّنة في <code class="ltr">Icon.tsx</code>)</h3>
<div class="tbl"><table><tr><th>الأيقونة</th><th>الاسم</th><th>الاستعمال</th><th>الفئة</th><th>التحميل</th></tr>{''.join(rows)}</table></div>
<h3>تطبيق الهاتف ({len(mob)} أيقونة من فئة <code class="ltr">Icons</code> في Flutter)</h3>
<p>تأتي مع Flutter دون أي تحميل. الاسم هو المستعمل في الكود؛ اللاحقة <code class="ltr">_rounded</code> تعني الشكل المستدير و<code class="ltr">_outlined</code> المحيطي.</p>
<ul class="icons">{mobtiles}</ul></section>

<section id="shapes"><h2>6. الإطارات والأشكال</h2>
<div class="tbl"><table><tr><th>العنصر</th><th>الشكل</th><th>الانحناء</th><th>الإطار</th><th>الظل / الحجم</th></tr>
<tr><td>البطاقة</td><td><span class="shape" style="border-radius:16px"></span></td><td>16</td><td>1 بكسل بلون line؛ المختارة 2 بكسل برتقالي</td><td><code class="ltr">0 1px 3px rgb(24 32 56/6%)</code></td></tr>
<tr><td>الزر</td><td><span class="shape" style="border-radius:14px;background:#1f3fa0;border-color:#1f3fa0"></span></td><td>14 (التطبيق) · 12 (الويب)</td><td>دون إطار، أو 1 بكسل للزر المحيطي</td><td>الارتفاع 52 إلى 56</td></tr>
<tr><td>مربع الأيقونة</td><td><span class="shape" style="border-radius:12px;inline-size:36px;background:#188038;border-color:#188038"></span></td><td>12 (الصغير 8)</td><td>دون إطار</td><td>44 (التطبيق) · 44 / 26 / 52 (الويب)</td></tr>
<tr><td>الشارة</td><td><span class="pill" style="background:#e6f4ea;color:#166b2e">عام</span></td><td>كامل (999)</td><td>دون إطار</td><td>حشو 2 × 10</td></tr>
<tr><td>الاختيار المقسّم واللغة</td><td><span class="shape" style="border-radius:999px"></span></td><td>كامل</td><td>المختار: أبيض بإطار كحلي 2 بكسل</td><td>—</td></tr>
<tr><td>حقل الإدخال</td><td><span class="shape" style="border-radius:12px;background:var(--card);border-color:#8a93a6"></span></td><td>12</td><td>1 بكسل outline؛ عند التركيز 2 بكسل كحلي</td><td>—</td></tr>
<tr><td>النوافذ والأوراق السفلية</td><td><span class="shape" style="border-radius:20px"></span></td><td>20</td><td>—</td><td>—</td></tr>
<tr><td>زر النجدة</td><td><span class="shape" style="border-radius:50%;inline-size:36px;background:#d7141a;border-color:#d7141a;box-shadow:0 0 0 5px rgb(215 20 26/12%)"></span></td><td>دائري</td><td>هالة حمراء 12%، وإطار كهرماني 8 بكسل عند التسليح</td><td>القطر 200</td></tr>
</table></div>
<p>المسافات: 4 · 8 · 12 · 16 · 20 · 24. أهداف اللمس 48 على الأقل. الشعار الوحيد هو شعار الديوان (<code class="ltr">assets/brand/logo.png</code>).</p></section>

<section id="frameworks"><h2>7. أطر العمل والمكتبات ومصادرها</h2>
<div class="tbl"><table><tr><th>الأداة</th><th>الإصدار</th><th>الاستعمال في التصميم</th><th>الرخصة</th><th>الرابط</th></tr>
<tr><td>Flutter + Material 3</td><td class="ltr">3.47.7</td><td>واجهة التطبيق والثيم</td><td>BSD-3-Clause</td><td><a href="https://docs.flutter.dev/get-started/install" target="_blank" rel="noopener">تحميل</a> · <a href="https://m3.material.io" target="_blank" rel="noopener">Material 3</a></td></tr>
<tr><td>React</td><td class="ltr">19.3.1</td><td>لوحة القيادة والبوابة</td><td>MIT</td><td><a href="https://react.dev" target="_blank" rel="noopener">react.dev</a></td></tr>
<tr><td>Vite</td><td class="ltr">8.3.4</td><td>بناء الويب (الخطوط ملفات منفصلة لا data:)</td><td>MIT</td><td><a href="https://vite.dev" target="_blank" rel="noopener">vite.dev</a></td></tr>
<tr><td>@fontsource/ibm-plex-sans-arabic</td><td class="ltr">5.3.0</td><td>الخط على الويب من نفس الخادم</td><td>OFL-1.1</td><td><a href="https://fontsource.org/fonts/ibm-plex-sans-arabic" target="_blank" rel="noopener">fontsource.org</a></td></tr>
<tr><td>Material Symbols Rounded</td><td>مستودع google/material-design-icons</td><td>أيقونات الويب (مسارات SVG)</td><td>Apache-2.0</td><td><a href="https://github.com/google/material-design-icons" target="_blank" rel="noopener">GitHub</a></td></tr>
<tr><td>Material Icons (ضمن Flutter)</td><td>مع Flutter 3.47.7</td><td>أيقونات التطبيق</td><td>Apache-2.0</td><td><a href="https://api.flutter.dev/flutter/material/Icons-class.html" target="_blank" rel="noopener">api.flutter.dev</a></td></tr>
<tr><td>axe-core + Playwright</td><td class="ltr">4.13.0 / 1.64.1</td><td>فحص التباين وإمكانية الوصول</td><td>MPL-2.0 / Apache-2.0</td><td><a href="https://github.com/dequelabs/axe-core" target="_blank" rel="noopener">axe-core</a> · <a href="https://playwright.dev" target="_blank" rel="noopener">Playwright</a></td></tr>
<tr><td>حاسبة التباين</td><td>—</td><td>للتحقق من أي لون جديد</td><td>—</td><td><a href="https://webaim.org/resources/contrastchecker/" target="_blank" rel="noopener">WebAIM</a></td></tr>
</table></div></section>
</div>'''
open('docs/design-reference.html','w').write(page)
print(len(paths),len(mob))
