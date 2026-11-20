# Tappeto ri-tagli[e]

La porta d'ingresso di [ri-tagli[e]](https://sites.google.com/view/ri-taglie): un piano nero infinito di immagini prese dalle sue pagine (Small, Medium, Large, Pubblicazioni e Cadavre exquis). Si trascina in tutte le direzioni, si zooma, si tocca un'immagine per ingrandirla; la sigla sotto l'immagine porta alla pagina da cui viene, e il pulsante "entra nel sito" in basso a destra porta alla home. A ogni visita l'ordine cambia.

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
