# Contexto del proyecto

## Salimos: dos repos, una sola base

Este repo (`admin`) **no va solo**. Es una de las dos mitades de la misma
aplicación "Salimos", que vive en la organización de GitHub `salimosapp`:

| Repo                | Path local                              | Rol                                  |
| ------------------- | --------------------------------------- | ------------------------------------ |
| `salimosapp/admin`  | `Documents/GitHub/admin` (este)         | Panel de gestión. Escribe en la BD.  |
| `salimosapp/web`    | `Documents/GitHub/web`                  | Sitio público. Solo lee de la BD.    |

Son dos vistas distintas del mismo proyecto. Se mantienen separadas a propósito
(cada una se despliega y escala por su lado), pero comparten datos.

## Cómo se unen

Los dos repos usan la **misma base**, llamada `berisso_cultura`. La tabla que
funciona como bisagra es `eventos`:

- **admin** scrapea las fuentes, crea eventos y los **aprueba** (`aprobado`).
- **web** muestra en el sitio público **solo** los eventos que admin ya aprobó.

El filtro de `web` es explícito (`web/backend/eventos.py`):

```sql
WHERE aprobado = true AND fecha_hora >= NOW()
```

O sea: aprobar un evento en el panel admin es lo que lo publica en la web.
`aprobado = false` significa "aún no se ve". Ese es el flujo entre las dos apps
y hay que respetarlo: si agregás columnas a `eventos`, las dos apps tienen que
saber leerlas.

Los dos repos tienen la misma estructura (`app.py`, `backend/`, `templates/`,
`static/`), así que los cambios de estilo se replican entre uno y otro. Pero
**no son el mismo código**: el `backend/` de cada uno tiene su propia lógica.

## Consecuencia práctica: la base tiene que ser la misma

Si movés una de las dos apps a otra base, dejan de hablarse. Ejemplo del caso
que se está armando (ver `DEPLOY.md`):

- Si `admin` se despliega en Render apuntando a Neon, y `web` sigue corriendo
  en tu PC apuntando al Postgres local, **aprobar un evento en el admin
  desplegado no va a aparecer en el web local**. Cada una leería una base
  distinta.
- Para que sigan conectadas, cuando una se mude a Neon hay que apuntar la otra
  al mismo Neon.

Por eso la decisión de dónde vive la base es una decisión compartida por los dos
repos, no de uno solo.

## Convenciones

- `.env` está en `.gitignore` y nunca se sube. Los secretos (claves de IA,
  passwords de BD) van en variables de entorno del entorno donde corra.
- `DB_SSLMODE` es opcional a propósito: vacío en tu Postgres local, `require`
  en Neon/Supabase.
- `ADMIN_USER` / `ADMIN_PASSWORD` / `SECRET_KEY` / `COOKIE_SECURE` son del
  login del panel. Defaults: `admin` / `123456`. `SECRET_KEY` fija es para que
  la sesión sobreviva reinicios; sin ella se genera una al azar y se cae la
  sesión cada vez que Render levanta el server. `COOKIE_SECURE=true` solo
  cuando corre por HTTPS (en Render), `false` en local.
- Las imágenes de los eventos viven en la base (`imagen_datos BYTEA`), no en
  disco. Eso es lo que hace que las dos apps puedan verlas sin compartir
  sistema de archivos.
