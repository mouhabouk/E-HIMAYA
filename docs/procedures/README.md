# Bibliothèque de procédures — مكتبة الإجراءات

Fiches d'aide à la décision rédigées pour e-Himaya (ء-حماية) à partir de recommandations publiques de la protection
civile tunisienne et d'organismes internationaux. Elles sont indexées par l'API (`app/modules/decision/procedures.py`)
et servent de sources à l'assistant d'aide à la décision (`POST /api/v1/staff/incidents/{id}/assistant`), qui ne
répond qu'à partir d'elles et cite chaque fiche utilisée.

بطاقات مساعدة على القرار كُتبت لمنظومة ء-حماية انطلاقا من توصيات عمومية للحماية المدنية التونسية ومن هيئات دولية.
تفهرسها الواجهة الخلفية ويستعملها المساعد مصدرا وحيدا لأجوبته مع ذكر كل بطاقة استُعملت.

**Ces fiches ne remplacent ni les notes de service de l'Office National de la Protection Civile (ONPC) ni le jugement
du commandant des opérations de secours. Un humain décide.**

## Format

Un fichier par risque et par langue : `<risque>.<ar|fr>.md`. En-tête entre deux lignes `---` :

| clé | sens |
|---|---|
| `id` | identifiant stable du risque (le même dans les deux langues) |
| `lang` | `ar` ou `fr` |
| `title` | titre affiché comme source |
| `categories` | catégories de signalement concernées (`fire`, `flood`, `traffic_accident`, `drowning`, `landslide`, `chemical_leak`, `medical`, `sos`, `other`) |
| `classifications` | classifications d'incident (phase 5) qui désignent plus précisément ce risque, facultatif |
| `reviewed` | mois de la dernière relecture |
| `sources` | une ligne `- <référence> \| <URL>` par source publique consultée |

Le corps est découpé en passages aux titres `## ` : chaque passage est indexé (texte intégral et vecteur e5) et
peut être cité seul. Les passages restent courts (moins de 1 500 caractères) et autonomes.

Le texte est rédigé pour le projet : aucune source n'est recopiée ; les références indiquent où vérifier.

Après modification, l'index se met à jour au démarrage du processus `worker` (boucle `procedures-index`) ou avec
`python -m app.modules.decision.cli index`.

## Fiches

| risque | fichiers |
|---|---|
| feu urbain et industriel | `fire.ar.md`, `fire.fr.md` |
| feu de forêt | `forest-fire.ar.md`, `forest-fire.fr.md` |
| inondation | `flood.ar.md`, `flood.fr.md` |
| accident de la circulation | `traffic-accident.ar.md`, `traffic-accident.fr.md` |
| noyade | `drowning.ar.md`, `drowning.fr.md` |
| glissement de terrain | `landslide.ar.md`, `landslide.fr.md` |
| fuite de produit chimique | `chemical-leak.ar.md`, `chemical-leak.fr.md` |
| effondrement de bâtiment | `building-collapse.ar.md`, `building-collapse.fr.md` |
