"""Builds tappeto/images.js and tappeto/img/ (one folder for every section).

Every image has a light version (for the carpet) in a light pack img/pNN.js. When the original is clearly
sharper than the light version it also gets an enlarged version, as big as its original allows (at most
HD_MAX), placed in an enlarged pack img/hNNx.js of about HD_PACK bytes. The number of files grows with the
total weight of the images, not with their number: about 1 file per HD_PACK bytes, far from the 512 limit.
Classes: XS very small (reference book covers, reference artworks, logos), S small (text pages, posters,
press), M medium, L large (boards/drawings). Each image keeps the code of the ri-tagli[e] page it comes from.
"""
import json, os, re, collections
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
SITE_ID = '1UvIbO7aYR4_oO6zpnr3D9VXq2SrnX8RE'
HD_MAX = 1600                                           # lato lungo massimo della versione ingrandita (basta per ogni schermo)
HD_GAIN = 1.2                                           # versione ingrandita solo se l'originale e' almeno il 20% piu' grande della leggera
HD_PACK = 1_000_000                                     # byte per pacco ingrandito (img/h00a.js ...)
THUMB = {'XS': 600, 'S': 760, 'M': 540, 'L': 720}       # versioni leggere, raccolte nei pacchi
PER_PACK = 24                                           # immagini per pacco leggero (img/p00.js ...): i pacchi crescono di numero, non di peso
SECTION_PATH = {'Small': '/small/', 'Medium': '/medium/', 'Large': '/large/', 'Pubblicazioni': '/pubblicazioni/', 'Cadavre exquis': '/'}

def slug(t):
    # default Google Sites path fragment: lower case, only letters, digits and hyphens
    return re.sub(r'[^a-z0-9-]', '', t.lower().replace(' ', '-'))

R = lambda a, b: list(range(a, b + 1))

# ---------- Small (classified by eye, indices of order.json) ----------
SMALL_IDS = {
    "EdCdA": "1DR1v7zol_SzitYb0w36Zc8FN6Q4pvg8M", "LdTdAeD": "10OvdRpbBOpZuvKfATMMn2e_CApwFjlxd",
    "AdP19.I": "11tow9bVa8z1KY3VvVd24cz_JrpqULn6z", "TeTdCA": "1D7hqWRQ147ebxANj5ZuLEGRNdKokeREK",
    "AdP20.Mre": "1dSFMQSjYX6CNXVlxZ1Y4Z7pXbVQXITQQ", "EAW": "1j3ovBugu_zbtnHUf4Bo5RMk2k1R7tz9d",
    "AdP22.NdR": "1tiX0Rrf1W5fWbdsLpUl8XNkvMkROSqz5", "TdLM": "1Ov7BVNhKwcAFIUZ0c8h_-dkAq-6ufogH",
    "AdP24.slgp": "1c0b00dzeG5JYUtvUMxe-zI-Wm9lj8XJY", "Cg.Anm": "18ZQFQTE3_Ou44x2018awq_16uP9dXWp4",
    "Cg.Ed": "1uGqKlUg_HPq53KGsFB-2U6iRCScKqP7K", "Pda.Iit-Tv": "1ykX8A9IyY9lHna991I6mLMfm8ZqwxZBl",
    "TdDdR": "1-u6Ldi_a5neLNCfkQ8lBfovHkUoN-_uD", "Pda.Dn": "1JnBRYA4CAOI8-dEoLXEpyr2_-xrEZuas",
}
S_EXCL = set([0, 6, 11, 14, 23, 29, 59, 86, 102, 112, 150, 113])
S_XS = set([5] + R(49, 51) + R(53, 58) + [85] + R(99, 101) + R(137, 149) + R(172, 175))
S_S = set(R(151, 171) + R(128, 132) + [97, 98, 109, 110, 111, 126, 127])
S_L = set([7, 8] + R(31, 48) + [52] + R(60, 73) + R(75, 83) + R(87, 92) + [96, 103, 104, 108])

def small_items():
    meta = {x['id']: x for x in json.load(open(os.path.join(HERE, 'tappeto-small/meta.json')))}
    order = json.load(open(os.path.join(HERE, 'order.json')))
    for i, id_ in enumerate(order):
        if i in S_EXCL:
            continue
        x = meta[id_]
        s = 'XS' if i in S_XS else 'S' if i in S_S else 'L' if i in S_L else 'M'
        yield dict(x, src=os.path.join(HERE, 'tappeto-small', x['f']), s=s, grp='Small', q=SMALL_IDS[x['page']])

# ---------- other sections (classified by eye, indices of order2.json; auto_class for anything new) ----------
EX2 = set([0, 34, 50, 66, 79, 93, 120, 151, 242, 248, 273, 274, 277, 330, 340, 362, 374, 375, 376, 389, 391, 399,
           420, 435, 440, 447, 452, 302, 416, 182, 157, 249])
L2 = set(R(1, 32) + R(35, 48) + R(54, 63) + R(69, 77) + R(80, 92) + R(104, 113) + [119] + R(121, 129) + R(143, 147)
         + R(173, 181) + R(199, 225) + R(227, 229)) - {33, 86, 90, 91}
M2 = set([51, 52, 53, 64, 67, 68, 78, 86, 90, 91] + R(94, 103) + [114] + R(130, 142) + R(152, 156) + R(158, 172)
         + R(183, 185) + [187] + R(189, 193) + [197, 198, 226, 243, 244, 245, 255, 257, 258, 268, 275, 296, 319, 320, 321]
         + R(331, 335) + R(343, 346) + [368, 369, 390, 434, 436, 437, 438, 439] + R(442, 445) + R(453, 482))
S2 = set([186, 188, 194, 195, 196] + R(230, 234) + [246, 247] + R(250, 262) + [269, 270, 271, 272, 276] + R(278, 289)
         + [297] + R(303, 313) + R(336, 339) + R(355, 358) + R(363, 367) + R(392, 394) + R(400, 410) + R(421, 433)
         + [441, 449, 450]) - {255, 257, 258}
XS2 = set([33, 49, 65, 115, 116, 117, 118, 148, 149, 150] + R(235, 241) + R(263, 267) + R(290, 295) + R(298, 301)
          + R(314, 318) + R(322, 329) + [341, 342] + R(347, 354) + R(359, 361) + R(370, 373) + R(377, 388)
          + R(395, 398) + R(411, 415) + R(417, 419) + [446, 448, 451])

def auto_class(x):
    ratio = min(x['rw'] / 1154, 1.2) if x['rw'] else 1.0
    if x['kind'] == 'banner':
        return 'M'
    if ratio < 0.2:
        return 'XS'
    if ratio < 0.36:
        return 'S'
    if ratio < 0.62:
        return 'M'
    return 'L' if x['D'] >= 9 else 'M'

def other_items():
    p = os.path.join(HERE, 'tappeto-altre/meta.json')
    if not os.path.exists(p):
        return
    idx = {id_: i for i, id_ in enumerate(json.load(open(os.path.join(HERE, 'order2.json'))))}
    for x in json.load(open(p)):
        i = idx.get(x['id'], -1)
        if i in EX2:
            continue
        if x['kind'] == 'banner' and x['D'] < 1.0:      # banner a tinta unita
            continue
        if x['D'] < 0.3:                               # immagine vuota
            continue
        s = 'XS' if i in XS2 else 'S' if i in S2 else 'M' if i in M2 else 'L' if i in L2 else auto_class(x)
        yield dict(x, src=os.path.join(HERE, 'tappeto-altre', x['f']), s=s)

if __name__ == '__main__':
    imgdir = os.path.join(OUT, 'img')
    os.makedirs(imgdir, exist_ok=True)
    for f in os.listdir(imgdir):
        os.remove(os.path.join(imgdir, f))
    out, tot = [], 0
    # stesse immagini caricate su pagine diverse (copertine ripetute ecc.): ne tengo una sola
    import numpy as np
    allx, kept, seen = list(small_items()) + list(other_items()), [], []
    for x in allx:
        ar = x['W'] / x['H']
        a = np.asarray(Image.open(x['src']).convert('L').resize((24, 32) if ar < 1 else (32, 24), Image.BILINEAR), dtype=np.float32)
        if any(abs(ar - ar2) / ar2 < 0.08 and a.shape == a2.shape and np.abs(a - a2).mean() < 3 for a2, ar2 in seen):
            continue
        seen.append((a, ar)); kept.append(x)
    print('dedup', len(allx), '->', len(kept))
    # gruppi misti (ogni pacco ha un po' di tutte le classi e di tutte le sezioni)
    import random, io
    rnd = random.Random(20261120)
    import math
    NG = max(1, math.ceil(len(kept) / PER_PACK))
    groups = [[] for _ in range(NG)]
    for cls in ['L', 'M', 'S', 'XS']:
        xs = [x for x in kept if x['s'] == cls]
        rnd.shuffle(xs)
        for i, x in enumerate(xs):
            groups[(i + NG * 0) % NG].append(x)
    import base64
    def write_pack(name, buf):                                # pacco come script: __tp("nome", "base64")
        with open(os.path.join(imgdir, name + '.js'), 'w') as fh:
            fh.write(f'__tp("{name}","' + base64.b64encode(bytes(buf)).decode('ascii') + '");\n')
    def jpeg(im, side, q):
        im = im.copy()
        if max(im.size) > side:
            im.thumbnail((side, side), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, 'JPEG', quality=q, optimize=True, progressive=True)
        return im.size, b.getvalue()
    nhd = nhdpacks = 0
    for g, members in enumerate(groups):
        buf, hd = bytearray(), []
        for x in members:
            s, id_ = x['s'], x['id']
            im = Image.open(x['src']).convert('RGB')
            (W, H), data = jpeg(im, THUMB[s], 80)
            rec = {'g': g, 'o': len(buf), 'n': len(data)}
            buf += data
            # versione ingrandita secondo la qualita' dell'originale
            if max(im.size) > max(W, H) * HD_GAIN:
                (W, H), big = jpeg(im, HD_MAX, 82)
                hd.append((rec, big))
            page = x['page']
            rec.update({'w': W, 'h': H, 's': s, 'p': page, 'q': x['q'], 'u': SECTION_PATH[x['grp']] + slug(page)})
            out.append(rec)
        name = f'p{g:02d}'
        write_pack(name, buf)
        tot += len(buf)
        # pacchi ingranditi del gruppo: le immagini di uno stesso riquadro stanno vicine
        k, hb = 0, bytearray()
        for i, (rec, big) in enumerate(hd):
            if hb and len(hb) + len(big) > HD_PACK:
                write_pack(f'h{g:02d}{chr(97 + k)}', hb); tot += len(hb); k += 1; hb = bytearray()
            rec.update({'H': f'h{g:02d}{chr(97 + k)}', 'ho': len(hb), 'hn': len(big)})
            hb += big; nhd += 1
        if hb:
            write_pack(f'h{g:02d}{chr(97 + k)}', hb); tot += len(hb); k += 1
        nhdpacks += k
    with open(os.path.join(OUT, 'images.js'), 'w') as fh:
        fh.write('// generato dalle sottopagine di ri-tagli[e] (Small, Medium, Large, Pubblicazioni) e da Cadavre exquis\n')
        fh.write('// g/o/n: versione leggera (pacco pNN, posizione, byte); H/ho/hn: versione ingrandita (pacco hNNx), se l\'originale lo permette;\n')
        fh.write('// w/h: misure della versione piu\' grande; s: XS/S/M/L; p: codice pagina;\n')
        fh.write('// u: percorso sul sito pubblicato; q: id pagina (anteprima dell\'editor)\n')
        fh.write("// TAPPETO_SITE: indirizzo del sito pubblicato (es. https://sites.google.com/view/...); vuoto = apre l'anteprima dell'editor\n")
        fh.write("window.TAPPETO_SITE = '';\n")
        fh.write(f"window.TAPPETO_PACKS = {NG};   // img/p00.js ... : versioni leggere in fila (g pacco, o posizione, n byte)\n")
        fh.write(f"window.TAPPETO_PREVIEW = 'https://sites.google.com/d/{SITE_ID}/p/';\n")
        fh.write('window.TAPPETO = [\n')
        fh.write(',\n'.join(json.dumps(o, separators=(',', ':'), ensure_ascii=False) for o in out))
        fh.write('\n];\n')
    c = collections.Counter((o['s']) for o in out)
    print(len(out), dict(c), 'ingrandite', nhd, 'pacchi ingranditi', nhdpacks, 'file in img', len(os.listdir(imgdir)), round(tot / 1e6, 1), 'MB')
