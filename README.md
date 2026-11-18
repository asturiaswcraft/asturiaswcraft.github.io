# {ASC} Asturias Software Crafters

Web de la comunidad: https://asturiaswcraft.github.io

Es HTML y CSS estático, sin paso de compilación. GitHub Pages publica la rama `main` tal cual.

## Probar en local

```bash
python3 -m http.server 8095
```

y abrir http://localhost:8095

## Añadir un evento

1. Guarda el cartel en `assets/eventos/AAAA-MM.webp` (o `.jpg`).
2. Copia un bloque `<a class="event">` en la sección `#eventos` de `index.html` y cambia enlace, imagen, fecha, ciudad y título.
3. Deja los 4 más recientes: en móvil solo se muestran los 2 primeros.
