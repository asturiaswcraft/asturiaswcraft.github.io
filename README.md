# {ASC} Asturias Software Crafters

Web de la comunidad: https://asturiaswcraft.github.io

Es HTML y CSS estático, sin paso de compilación. GitHub Pages publica la rama `main` tal cual.

## Probar en local

```bash
python3 -m http.server 8095
```

y abrir http://localhost:8095

## Eventos automáticos

La sección "Últimos eventos" se actualiza sola cada lunes con la GitHub Action
`.github/workflows/eventos.yml`, que ejecuta `scripts/actualizar_eventos.py`:

- Lee los eventos de la comunidad en Saraos y se queda con los 4 más recientes.
- Descarga los carteles a `assets/eventos/` y reescribe el bloque entre
  `<!-- EVENTOS:INICIO -->` y `<!-- EVENTOS:FIN -->` de `index.html`.
- Si Saraos falla o cambia su estructura, no toca nada (el error se ve en Actions).

Para lanzarlo a mano (por ejemplo, justo después de publicar un evento):
pestaña **Actions** → "Actualizar eventos desde Saraos" → **Run workflow**.

En local:

```bash
pip install pillow   # opcional, para redimensionar carteles
python3 scripts/actualizar_eventos.py
```

No edites a mano el bloque entre los marcadores: se sobrescribe en cada ejecución.

## Caché del CSS

GitHub Pages deja que los navegadores guarden `styles.css` un rato. Cada vez que cambies
el CSS, cambia también la versión del enlace en `index.html`
(`<link rel="stylesheet" href="styles.css?v=AAAA-MM-DD">`), para que los móviles
descarguen el nuevo y no mezclen HTML nuevo con CSS antiguo.
