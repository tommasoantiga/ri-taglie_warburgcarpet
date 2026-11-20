# ri-tagli[e]

small / medium / large.

Indirizzo: https://tommasoantiga.github.io/ri-taglie_warburgcarpet/

## Com'è fatto

- `index.html`: la pagina, tutto in un file.
- `images.js`: l'elenco delle immagini (pagina di provenienza, misura sul tappeto, posizione nei pacchi). In cima c'è `TAPPETO_SITE`, l'indirizzo del sito pubblicato a cui portano le sigle.
- `img/pNN.js`: pacchi con le versioni leggere, quelle del tappeto.
- `img/hNNx.js`: pacchi con le versioni ingrandite, grandi quanto l'originale permette (al massimo 1600 pixel). Le immagini con un originale già piccolo non ne hanno bisogno.
- `font/`: EB Garamond, lo stesso carattere del sito.
- `strumenti/build.py`: lo script che prepara `images.js` e `img/` dalle immagini raccolte.

## Pubblicazione

Il sito è servito da GitHub Pages (Settings → Pages → Deploy from a branch → `main`, cartella `/`). Il file `.nojekyll` evita che GitHub rielabori i file.
