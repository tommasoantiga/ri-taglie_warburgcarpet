# ri-tagli[e]

small / medium / large.

Indirizzo: https://tommasoantiga.github.io/ri-taglie_warburgcarpet/

## Com'è fatto

- `index.html`: la pagina, tutto in un file.
- `images.js`: l'elenco delle immagini (pagina di provenienza, misura sul tappeto, posizione nei pacchi). In cima c'è `TAPPETO_SITE`, l'indirizzo del sito pubblicato a cui portano le sigle.
- `img/pNN.js` (o `pNN-xxxxxxxx.js`): pacchi con le versioni leggere, quelle del tappeto.
- `img/hNNx.js` (o `hNNx-xxxxxxxx.js`): pacchi con le versioni ingrandite, grandi quanto l'originale permette (al massimo 1600 pixel). Le immagini con un originale già piccolo non ne hanno bisogno.
- `font/`: EB Garamond, lo stesso carattere del sito.
- `strumenti/aggiorna.py`: l'aggiornamento automatico (vedi sotto).
- `strumenti/catalogo.json`: le impronte delle immagini già sul tappeto e di quelle escluse.
- `strumenti/correzioni.json`: le correzioni a mano.
- `strumenti/build.py`: lo script con cui è stata fatta la prima versione.

## Pubblicazione

Il sito è servito da GitHub Pages (Settings → Pages → Deploy from a branch → `main`, cartella `/`). Il file `.nojekyll` evita che GitHub rielabori i file.

## Aggiornamento automatico

Ogni notte (verso le 3) GitHub legge le pagine pubblicate di ri-tagli[e] e cambia il tappeto **solo se sono cambiate le immagini**: testi e impaginazione non contano.

- Le immagini nuove nelle sottopagine di Small, Medium, Large, Pubblicazioni e in Cadavre exquis entrano nel tappeto. La misura dipende da quanto sono larghe nella loro pagina: le tavole a tutta larghezza diventano grandi, le copertine e le immagini piccole restano piccole.
- Le immagini tolte dal sito spariscono dal tappeto.
- Le immagini già presenti restano come sono.
- Restano fuori le pagine "in elaborazione", i banner delle intestazioni, il logo, le immagini a tinta unita e i doppioni.

Ogni immagine è riconosciuta dal suo aspetto, non dal nome del file. Se qualcosa non va, l'ultimo resoconto è in `strumenti/rapporto.txt`.

Per non aspettare la notte: Actions → *Aggiorna il Warburg Carpet* → *Run workflow*.

Per correggere a mano, modifica `strumenti/correzioni.json` (l'`id` di ogni immagine è in `images.js`):

```json
{ "classi": { "1a2b3c4d5e": "L" }, "esclusi": ["6f7a8b9c0d"] }
```

Le misure possibili sono `XS`, `S`, `M` e `L`. Le correzioni valgono dal controllo successivo.
