"""Aggiornamento automatico del Warburg Carpet.

Ogni notte (GitHub Actions) legge le pagine pubblicate di ri-tagli[e], riconosce le immagini
che conosce già e cambia il tappeto solo se sul sito ci sono immagini nuove o tolte:

- le immagini già presenti restano come sono (stessa misura sul tappeto, stessi file);
- quelle nuove ricevono una misura in base a quanto sono larghe nella loro pagina
  (come le altre: tavole a tutta larghezza -> grandi, copertine e immagini piccole -> piccole),
  una versione leggera e, se l'originale è abbastanza grande, una versione ingrandita;
- quelle tolte dal sito spariscono dal tappeto (anche molte insieme).

Si leggono solo le sottopagine di Small, Medium, Large, Pubblicazioni e la pagina Cadavre exquis;
si saltano le pagine "in elaborazione", i banner delle intestazioni, i loghi e le immagini a tinta unita.
Un'immagine è riconosciuta dal suo aspetto (una miniatura 16x16 in grigio), non dall'indirizzo.

Correzioni a mano: strumenti/correzioni.json
  {"classi": {"<id>": "L"}, "esclusi": ["<id>", ...]}
L'<id> di ogni immagine è nel campo "id" di images.js.

Uso:  python strumenti/aggiorna.py           aggiorna se serve
      python strumenti/aggiorna.py --prova   controlla e scrive solo il rapporto
"""
import base64, hashlib, html, io, json, math, os, re, subprocess, sys, time, datetime
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
IMG = os.path.join(RADICE, 'img')
IMAGES_JS = os.path.join(RADICE, 'images.js')
CATALOGO = os.path.join(QUI, 'catalogo.json')
CORREZIONI = os.path.join(QUI, 'correzioni.json')
RAPPORTO = os.path.join(QUI, 'rapporto.txt')
ULTIMO = os.path.join(QUI, 'ultimo-controllo.txt')

SITO = 'https://sites.google.com/view/ri-taglie'
SEZIONI = ['small', 'medium', 'large', 'pubblicazioni']
ALTRE = ['cadavre-exquis']                   # pagine singole fuori dalle sezioni
THUMB = {'XS': 600, 'S': 760, 'M': 540, 'L': 720}
HD_MAX, HD_GAIN, HD_PACK = 1600, 1.2, 1_000_000
PER_PACK, PACK_MAX = 24, 30                   # immagini per pacco leggero (si apre un pacco nuovo oltre PACK_MAX)
SOGLIA_FP, SOGLIA_AR = 5.0, 0.04              # riconoscimento: differenza media della miniatura (0-255) e delle proporzioni
DOPPIONE = 2.0                                # sotto questa differenza e' proprio la stessa immagine (anche due volte nella stessa pagina)
RITROVA = 12.0                                # una 'nuova' e una 'tolta' della stessa pagina cosi' simili sono la stessa immagine
UA = {'User-Agent': 'Mozilla/5.0 (warburgcarpet; aggiornamento notturno)'}

log_righe = []
def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    log_righe.append(s)


# ---------------------------------------------------------------- impronte

def piatta(im):
    """Le immagini con parti trasparenti (PNG ritagliati) si appoggiano sul bianco, come sul sito."""
    if im.mode in ('RGBA', 'LA', 'PA') or (im.mode == 'P' and 'transparency' in im.info):
        im = im.convert('RGBA')
        fondo = Image.new('RGB', im.size, (255, 255, 255))
        fondo.paste(im, mask=im.getchannel('A'))
        return fondo
    return im.convert('RGB')

def impronta(im):
    """Miniatura 32x32 in grigio (media dei pixel) e proporzioni: quasi uguale per la stessa immagine a qualsiasi misura."""
    im = piatta(im).convert('L')
    a = np.asarray(im.resize((32, 32), Image.BOX), dtype=np.uint8)
    return a.tobytes().hex(), im.width / im.height

def vettore(fp):
    return np.frombuffer(bytes.fromhex(fp), dtype=np.uint8).astype(np.int16)

def distanze(fp, ar, archivio):
    """Distanze da tutte le impronte di un archivio {chiave: {fp, ar}} (proporzioni troppo diverse = infinito)."""
    if not archivio:
        return [], np.array([])
    chiavi = list(archivio)
    M = np.stack([vettore(archivio[k]['fp']) for k in chiavi])
    A = np.array([archivio[k]['ar'] for k in chiavi])
    d = np.abs(M - vettore(fp)).mean(axis=1)
    d[np.abs(A / ar - 1) > SOGLIA_AR] = 1e9
    return chiavi, d

def dettaglio(im):
    a = np.asarray(piatta(im).convert('L').resize((64, 64), Image.BOX), dtype=np.float32)
    return float(a.std())


# ---------------------------------------------------------------- images.js e pacchi

def leggi_images_js(path=IMAGES_JS):
    t = open(path, encoding='utf-8').read()
    testa, resto = t.split('window.TAPPETO = [', 1)
    voci = json.loads('[' + resto.rsplit('];', 1)[0] + ']')
    var = dict(re.findall(r"window\.(TAPPETO_[A-Z]+) = (.+?);", testa))
    nomi = json.loads(var['TAPPETO_PACKNAMES']) if 'TAPPETO_PACKNAMES' in var else None
    ng = int(var.get('TAPPETO_PACKS', '1').split()[0])
    if not nomi:
        nomi = [f'p{g:02d}' for g in range(ng)]
    return {'voci': voci, 'nomi': nomi, 'testo': t}

def scrivi_images_js(voci, nomi):
    voci = sorted(voci, key=lambda x: (x['g'], x['o']))
    righe = [
        "// generato da strumenti/aggiorna.py dalle sottopagine di ri-tagli[e] (Small, Medium, Large, Pubblicazioni) e da Cadavre exquis",
        "// g/o/n: versione leggera (pacco TAPPETO_PACKNAMES[g], posizione, byte); H/ho/hn: versione ingrandita (pacco H), se l'originale lo permette;",
        "// w/h: misure della versione piu' grande; s: XS/S/M/L; p: codice pagina; u: percorso sul sito pubblicato; id: impronta (vedi strumenti/correzioni.json)",
        f"window.TAPPETO_SITE = '{SITO}';",
        f"window.TAPPETO_PACKS = {len(nomi)};",
        f"window.TAPPETO_PACKNAMES = {json.dumps(nomi)};",
        "window.TAPPETO_PREVIEW = '';",
        'window.TAPPETO = [',
        ',\n'.join(json.dumps(v, separators=(',', ':'), ensure_ascii=False) for v in voci),
        '];', '']
    open(IMAGES_JS, 'w', encoding='utf-8').write('\n'.join(righe))

_cache_pacchi = {}
def leggi_pacco(nome):
    if nome not in _cache_pacchi:
        t = open(os.path.join(IMG, nome + '.js'), encoding='ascii').read()
        b64 = t[t.index(',"') + 2: t.rindex('")')]
        _cache_pacchi[nome] = base64.b64decode(b64)
    return _cache_pacchi[nome]

def scrivi_pacco(prefisso, dati):
    nome = f'{prefisso}-{hashlib.sha1(dati).hexdigest()[:8]}'
    with open(os.path.join(IMG, nome + '.js'), 'w', encoding='ascii') as fh:
        fh.write(f'__tp("{nome}","' + base64.b64encode(dati).decode('ascii') + '");\n')
    return nome

def jpeg(im, lato, q):
    im = piatta(im)
    if max(im.size) > lato:
        im = im.copy(); im.thumbnail((lato, lato), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=q, optimize=True, progressive=True)
    return im.size, b.getvalue()


# ---------------------------------------------------------------- lettura del sito

def scarica(url, tentativi=4):
    import requests
    for i in range(tentativi):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200:
                return r.content
            log('  risposta', r.status_code, url[:90])
        except Exception as e:
            log('  errore', type(e).__name__, url[:90])
        time.sleep(3 * (i + 1))
    raise RuntimeError('non riesco a scaricare ' + url)

TOKEN = r'sitesv-images-rt/([A-Za-z0-9_\-]+)'
IMMAGINE = 'https://sites.google.com/sitesv-images-rt/'

def pagine_del_sito():
    """Percorsi e codici delle sottopagine, nell'ordine del menu."""
    casa = scarica(SITO).decode('utf-8', 'replace')
    visti, pagine = set(), []
    for m in re.finditer(r'<a\b[^>]*href="(/view/ri-taglie/[^"#?]+)"[^>]*>(.*?)</a>', casa, re.S):
        percorso = m.group(1).replace('/view/ri-taglie', '')
        parti = percorso.strip('/').split('/')
        ok = (len(parti) == 2 and parti[0] in SEZIONI) or (len(parti) == 1 and parti[0] in ALTRE)
        if not ok or percorso in visti:
            continue
        codice = html.unescape(re.sub(r'<[^>]+>', '', m.group(2))).strip()
        visti.add(percorso)
        pagine.append({'u': percorso, 'p': codice})
    return pagine

def leggi_pagina(pag):
    t = scarica(SITO + pag['u']).decode('utf-8', 'replace')
    testo = re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)\b.*?</\1>', ' ', t, flags=re.S))
    if 'pagina in elaborazione' in html.unescape(testo).lower():
        return None
    if not pag['p']:
        m = re.search(r'<title>(.*?)</title>', t, re.S)
        pag['p'] = html.unescape(m.group(1)).split(' - ')[-1].strip() if m else pag['u'].split('/')[-1]
    # banner dell'intestazione e logo del sito: mai sul tappeto
    fuori = set()
    for m in re.finditer(r'class="[^"]*\bIFuOkc\b[^"]*"[^>]*', t):
        fuori.update(re.findall(TOKEN, m.group(0)))
    for m in re.finditer(r'<img\b[^>]*class="[^"]*\b(r9CsCb|lzy1Td)\b[^"]*"[^>]*>', t):
        fuori.update(re.findall(TOKEN, m.group(0)))
    token = []
    for tk in re.findall(TOKEN, t):
        if tk not in fuori and tk not in token:
            token.append(tk)
    return token


# ---------------------------------------------------------------- misura delle immagini nuove nella pagina

def misura_larghezze(richieste):
    """{percorso: [token]} -> {token: larghezza dell'immagine / larghezza della sezione} con un browser vero."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'playwright'], check=True)
        from playwright.sync_api import sync_playwright
    subprocess.run([sys.executable, '-m', 'playwright', 'install', '--with-deps', 'chromium'], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    js = """(tokens) => {
      const out = {};
      const tiles = [...document.querySelectorAll('.jXK9ad-SmKAyb')];
      const W = Math.max(1, ...tiles.map(t => t.getBoundingClientRect().width));      // larghezza della colonna del testo
      const els = [...document.querySelectorAll('img, [style*="background-image"]')];
      for (const tk of tokens) {
        const e = els.find(e => (e.getAttribute('src') || '').includes(tk) || (e.getAttribute('style') || '').includes(tk));
        if (!e) continue;
        const box = e.closest('[jsname=kEMzy]') || e;          // nei caroselli si misura il carosello
        const w = box.getBoundingClientRect().width;
        if (w > 0) out[tk] = Math.min(1.2, w / W);
      }
      return out;
    }"""
    risultato = {}
    try:
        _misura(sync_playwright, js, richieste, risultato)
    except Exception as e:                        # senza browser le nuove prendono la misura media
        log('  misura delle larghezze non riuscita:', type(e).__name__, str(e)[:120])
    return risultato

def _misura(sync_playwright, js, richieste, risultato):
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1280, 'height': 900})
        for percorso, tokens in richieste.items():
            try:
                pg.goto(SITO + percorso, wait_until='load', timeout=90000)
                for _ in range(12):
                    pg.mouse.wheel(0, 1500); pg.wait_for_timeout(250)
                pg.wait_for_timeout(1500)
                risultato.update(pg.evaluate(js, tokens))
            except Exception as e:
                log('  misura non riuscita per', percorso, type(e).__name__)
        b.close()

def classe_nuova(rapporto_larghezza, det, misure):
    r, lato = rapporto_larghezza, max(misure)
    if r is None:
        s = 'M'
    elif r < 0.2:
        s = 'XS'
    elif r < 0.36:
        s = 'S'
    elif r < 0.62:
        s = 'M'
    else:
        s = 'L' if det >= 10 else 'M'
    # un originale piccolo e' quasi sempre una copertina o un'immagine di contorno
    if lato <= 320:
        s = 'XS'
    elif lato <= 520 and s in ('M', 'L'):
        s = 'S'
    return s


# ---------------------------------------------------------------- aggiornamento

def main():
    prova = '--prova' in sys.argv
    cat = json.load(open(CATALOGO, encoding='utf-8'))
    corr = json.load(open(CORREZIONI, encoding='utf-8')) if os.path.exists(CORREZIONI) else {}
    stato = leggi_images_js()
    voci = {v['id']: v for v in stato['voci']}
    noti = cat['immagini']                      # id -> {fp, ar}
    esclusi = cat['esclusi']                    # [{fp, ar, nota}]
    tokmap = {}                                 # token -> id oppure "x" (gli indirizzi di Google cambiano a ogni lettura: valgono solo per questa)
    cat.pop('token', None)

    # 1. il sito com'è adesso
    pagine = pagine_del_sito()
    log(f'{len(pagine)} sottopagine nel menu')
    if len(pagine) < 20:
        raise SystemExit('troppo poche pagine trovate: il sito non si legge bene, non cambio nulla')
    presenti, nuove, saltate, pagine_di = {}, {}, [], {}
    arch_esclusi = {str(k): e for k, e in enumerate(esclusi)}
    for pag in pagine:
        token = leggi_pagina(pag)
        if token is None:
            saltate.append(pag['u']); continue
        # le immagini mai viste: scaricate e confrontate con quelle del tappeto
        info = {}
        da_leggere = [tk for tk in token if tk not in tokmap]
        def apri(tk):
            try:
                im = Image.open(io.BytesIO(scarica(IMMAGINE + tk))); im.load()
                return tk, im
            except Exception:
                return tk, None
        with ThreadPoolExecutor(max_workers=6) as ex:
            for tk, im in ex.map(apri, da_leggere):
                if im is None:
                    tokmap[tk] = 'x'; continue
                fp, ar = impronta(im)
                info[tk] = {'fp': fp, 'ar': ar, 'im': im}
        # abbinamento: dalla coppia piu' simile in giu', un'immagine del tappeto per immagine della pagina
        cand = []
        for tk, f in info.items():
            chiavi, d = distanze(f['fp'], f['ar'], noti)
            for j in np.nonzero(d <= SOGLIA_FP)[0]:
                cand.append((float(d[j]), tk, chiavi[j]))
        cand.sort()
        sulla_pagina = {tokmap[tk] for tk in token if tokmap.get(tk) not in (None, 'x')}
        for d, tk, i in cand:
            if tk in tokmap:
                continue
            if i in sulla_pagina and d > DOPPIONE:
                continue
            tokmap[tk] = i; sulla_pagina.add(i)
        for tk, f in info.items():
            if tk in tokmap:
                continue
            _, de = distanze(f['fp'], f['ar'], arch_esclusi)
            if len(de) and de.min() <= SOGLIA_FP:
                tokmap[tk] = 'x'; continue
            im = f['im']; det = dettaglio(im)
            if det < 3 or max(im.size) < 160:                   # tinta unita o minuscola
                esclusi.append({'fp': f['fp'], 'ar': f['ar'], 'nota': f'automatico: {"tinta unita" if det < 3 else "minuscola"} ({pag["p"]})'})
                arch_esclusi[str(len(esclusi) - 1)] = esclusi[-1]
                tokmap[tk] = 'x'; continue
            chiavi, dn = distanze(f['fp'], f['ar'], nuove)
            if len(dn) and dn.min() <= SOGLIA_FP:
                tokmap[tk] = chiavi[int(dn.argmin())]; continue
            i = hashlib.sha1(bytes.fromhex(f['fp'])).hexdigest()[:10]
            ck, dk = distanze(f['fp'], f['ar'], noti)
            vicina = f'{ck[int(dk.argmin())]} a {dk.min():.1f}' if len(dk) and dk.min() < 1e8 else 'nessuna con le stesse proporzioni'
            nuove[i] = {'fp': f['fp'], 'ar': f['ar'], 'im': im, 'det': det, 'pag': dict(pag), 'tk': tk,
                        'nota': f'{im.size[0]}x{im.size[1]}, piu\' vicina sul tappeto {vicina}, esclusa piu\' vicina a {de.min() if len(de) else 0:.1f}'}
            tokmap[tk] = i
        for tk in token:
            i = tokmap.get(tk)
            if i and i != 'x':
                pagine_di.setdefault(i, []).append(dict(pag))
                if i not in presenti:
                    presenti[i] = dict(pag)
        info.clear()

    # un'immagine che sta in piu' pagine resta legata a quella di prima, se c'e' ancora
    for i, pp in pagine_di.items():
        if i in voci and i in presenti:
            stessa = next((q for q in pp if q['u'] == voci[i]['u']), None)
            if stessa:
                presenti[i] = stessa

    # una 'nuova' quasi uguale a una 'tolta' della stessa pagina e' la stessa immagine letta un po' diversa
    mancanti = {i: noti[i] for i in voci if i not in presenti and i in noti}
    coppie = []
    for n, f in nuove.items():
        chiavi, d = distanze(f['fp'], f['ar'], mancanti)
        for j in np.nonzero(d <= RITROVA)[0]:
            t = chiavi[j]
            if voci[t]['u'] == f['pag']['u']:
                coppie.append((float(d[j]), n, t))
    coppie.sort()
    for d, n, t in coppie:
        if n not in nuove or t in presenti:
            continue
        log(f'  ritrovata {t} in {voci[t]["p"]} (differenza {d:.1f})')
        presenti[t] = presenti.pop(n, nuove[n]['pag'])
        nuove.pop(n)

    for i in corr.get('esclusi', []):
        presenti.pop(i, None); nuove.pop(i, None)

    tolte = [i for i in voci if i not in presenti]
    aggiunte = [i for i in presenti if i not in voci and i in nuove]
    spostate = [i for i in presenti if i in voci and (voci[i]['p'], voci[i]['u']) != (presenti[i]['p'], presenti[i]['u'])]
    riclassate = [i for i, c in corr.get('classi', {}).items() if i in voci and voci[i]['s'] != c]
    log(f'immagini sul tappeto {len(voci)}, riconosciute sul sito {sum(1 for i in presenti if i in voci)}, '
        f'nuove {len(aggiunte)}, tolte {len(tolte)}, cambiate di pagina {len(spostate)}, corrette a mano {len(riclassate)}')
    if saltate:
        log('pagine in elaborazione saltate:', ', '.join(saltate))
    for i in aggiunte:
        log('  nuova', i, 'da', nuove[i]['pag']['p'], '-', nuove[i]['nota'])
        if prova:                                    # miniature per controllare a occhio
            os.makedirs(os.path.join(QUI, 'prova'), exist_ok=True)
            m = piatta(nuove[i]['im']); m.thumbnail((360, 360))
            m.save(os.path.join(QUI, 'prova', i + '.jpg'), 'JPEG', quality=80)
    for i in tolte:
        log('  tolta', i, 'era in', voci[i]['p'])


    cambia = aggiunte or tolte or spostate or riclassate
    if prova or not cambia:
        if not cambia:
            log('nessuna modifica alle immagini del sito: il tappeto resta com\'è')
        if not prova:                                # in prova il catalogo non si tocca
            json.dump(cat, open(CATALOGO, 'w', encoding='utf-8'), separators=(',', ':'))
        return fine(prova, cambia)

    # 2. misura delle immagini nuove nella loro pagina
    larghezze = {}
    if aggiunte:
        richieste = {}
        for i in aggiunte:
            richieste.setdefault(nuove[i]['pag']['u'], []).append(nuove[i]['tk'])
        larghezze = misura_larghezze(richieste)
    # 3. ricostruzione dei soli pacchi toccati
    nomi = list(stato['nomi'])
    vecchi_file = set(os.listdir(IMG))
    toccati = set()
    gruppi = {}
    for i, v in voci.items():
        if i in presenti:
            gruppi.setdefault(v['g'], []).append(i)
    for i in tolte:
        toccati.add(voci[i]['g'])
    for i in spostate:
        voci[i]['p'], voci[i]['u'] = presenti[i]['p'], presenti[i]['u']
    for i in riclassate:
        voci[i]['s'] = corr['classi'][i]           # cambia solo la misura sul tappeto, i file restano
    dati_leggeri, dati_grandi = {}, {}
    for i in aggiunte:
        n = nuove[i]
        r = larghezze.get(n['tk'])
        s = corr.get('classi', {}).get(i) or classe_nuova(r, n['det'], n['im'].size)
        (W, H), lo = jpeg(n['im'], THUMB[s], 80)
        v = {'id': i, 's': s, 'p': n['pag']['p'], 'u': n['pag']['u'], 'q': ''}
        if max(n['im'].size) > max(W, H) * HD_GAIN:
            (W, H), hi = jpeg(n['im'], HD_MAX, 82)
            dati_grandi[i] = hi
        v['w'], v['h'] = W, H
        dati_leggeri[i] = lo
        conta = lambda g: (sum(1 for j in gruppi.get(g, []) if (voci.get(j) or {}).get('s') == s), len(gruppi.get(g, [])))
        liberi = [g for g in range(len(nomi)) if len(gruppi.get(g, [])) < PACK_MAX]
        if not liberi:
            nomi.append(''); liberi = [len(nomi) - 1]
        g = min(liberi, key=conta)
        v['g'] = g
        voci[i] = v
        gruppi.setdefault(g, []).append(i)
        toccati.add(g)
        log(f'  {i}: misura {s} ({n["pag"]["p"]}, larga {"?" if r is None else f"{r:.2f}"} della colonna), pacco {g}')
    for i in tolte:
        voci.pop(i)
    for g in sorted(toccati):
        membri = gruppi.get(g, [])
        buf, hd = bytearray(), []
        for i in membri:
            v = voci[i]
            lo = dati_leggeri[i] if i in dati_leggeri else leggi_pacco(stato['nomi'][g])[v['o']: v['o'] + v['n']]
            v['o'], v['n'] = len(buf), len(lo)
            buf += lo
            hi = dati_grandi.get(i)
            if hi is None and v.get('H'):
                hi = leggi_pacco(v['H'])[v['ho']: v['ho'] + v['hn']]
            if hi is not None:
                hd.append((i, hi))
            for k in ('H', 'ho', 'hn'):
                v.pop(k, None)
        nomi[g] = scrivi_pacco(f'p{g:02d}', bytes(buf))
        k, hb, quali = 0, bytearray(), []
        def chiudi():
            nome = scrivi_pacco(f'h{g:02d}{chr(97 + k)}', bytes(hb))
            for j in quali:
                voci[j]['H'] = nome
        for i, hi in hd:
            if hb and len(hb) + len(hi) > HD_PACK:
                chiudi(); k += 1; hb = bytearray(); quali = []
            voci[i]['ho'], voci[i]['hn'] = len(hb), len(hi)
            hb += hi; quali.append(i)
        if hb:
            chiudi()
    # 4. scrittura, e pulizia dei file non usati né ora né dalla versione precedente (cache dei browser)
    usati_prima = set(f + '.js' for f in stato['nomi']) | set(v['H'] + '.js' for v in stato['voci'] if v.get('H'))
    scrivi_images_js(list(voci.values()), nomi)
    nuovo = leggi_images_js()
    usati_ora = set(f + '.js' for f in nuovo['nomi']) | set(v['H'] + '.js' for v in nuovo['voci'] if v.get('H'))
    for f in os.listdir(IMG):
        if f.endswith('.js') and f not in usati_ora and f not in usati_prima:
            os.remove(os.path.join(IMG, f))
    for i in aggiunte:
        noti[i] = {'fp': nuove[i]['fp'], 'ar': nuove[i]['ar']}
    for i in tolte:
        noti.pop(i, None)
    json.dump(cat, open(CATALOGO, 'w', encoding='utf-8'), separators=(',', ':'))
    log(f'tappeto aggiornato: {len(voci)} immagini, {len(nomi)} pacchi leggeri')
    return fine(prova, cambia)

def fine(prova, cambia):
    ora = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    if prova or cambia:
        testo = f'controllo del {ora}' + (' (prova: nessun file del tappeto cambiato)' if prova else '') + '\n\n' + '\n'.join(log_righe) + '\n'
        open(RAPPORTO, 'w', encoding='utf-8').write(testo)
    # una traccia al mese anche senza modifiche: GitHub spegne le azioni notturne dopo 60 giorni senza attivita'
    vecchio = open(ULTIMO).read().strip()[:7] if os.path.exists(ULTIMO) else ''
    if not prova and (cambia or vecchio != ora[:7]):
        open(ULTIMO, 'w').write(ora + '\n')

if __name__ == '__main__':
    main()
