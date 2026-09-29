# Deploy de Salimos

Guía para dejar **las dos apps** publicadas en internet, unidas por la misma
base de datos. Las dos son repos separados, así que son dos servicios de Render
distintos, pero ambas apuntan a **el mismo Neon**:

```
admin (Render #1)  ─┐
                     ├──→  Neon  (una sola base, se llama "el nexo")
web   (Render #2)  ─┘
```

El nexo es la base: si las dos leen la misma, aprobás un evento en el panel y
aparece en la web al instante. Si una queda apuntando al Postgres de tu PC y
la otra a Neon, dejan de hablarse y el síntoma es un evento aprobado que no
aparece en la web.

## Orden de los pasos

1. Base de datos en Neon (una sola vez, para las dos apps).
2. Copiar los datos de tu Postgres local a Neon (una sola vez).
3. Desplegar `admin` en Render.
4. Desplegar `web` en Render.

Los pasos 1 y 2 están en este archivo. El 4 tiene su propio archivo corto en
`web/DEPLOY.md`, porque casi todo es igual.

---

## 1. Base de datos en Neon

Neon tiene un plan gratis que no expira (a diferencia del Postgres gratis de
Render, que se borra a los 30 días).

1. Entrá a <https://console.neon.tech> y creá una cuenta con GitHub.
2. **Create a project** → nombre `salimos` → elegí la región más cercana a
   donde vas a correr la app → plan **Free**.
3. Neon crea una base llamada `neondb` con un usuario y una contraseña
   generados. Abrí el panel **Connect** y te muestra los datos de conexión.
4. Anotá por separado:

   | Campo         | Dónde está en Neon                |
   | ------------- | --------------------------------- |
   | `DB_HOST`     | Host del panel Connect            |
   | `DB_PORT`     | `5432`                            |
   | `DB_NAME`     | `neondb`                          |
   | `DB_USER`     | Usuario del panel Connect         |
   | `DB_PASSWORD` | Contraseña del panel Connect       |

No uses la URL completa de conexión. `backend/db.py` toma los campos por
separado, así que hay que pegarlos de a uno.

---

## 2. Migrar los datos que ya tenés

El esquema de tablas se crea solo al arrancar la app (`inicializar_db()` en
`app.py:59` y todo el `SCHEMA` de `backend/db.py` es `IF NOT EXISTS`). Lo que
**no** se crea solo son tus datos: los eventos, las fuentes y las imágenes que
ya cargaste. Eso se copia con `pg_dump`.

En tu PC, PostgreSQL 18 ya está instalado con las herramientas en
`C:\Program Files\PostgreSQL\18\bin` (no están en el PATH, por eso las
invocamos con la ruta completa).

### 2.1 Exportar la base local

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" `
  -h localhost -p 5432 -U TU_USUARIO -d TU_BASE `
  --no-owner --no-privileges -F plain -f "$env:TEMP\salimos_dump.sql"
```

Te va a pedir el password de tu Postgres local. Si no lo sabés, abrilo en
`psql` o mirá el `pgpass.conf`. Reemplazá `TU_USUARIO` y `TU_BASE` por los
valores de tu `.env`.

### 2.2 Importarlo en Neon

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" `
  "postgresql://USUARIO:PASSWORD@HOST/neondb?sslmode=require" `
  -f "$env:TEMP\salimos_dump.sql"
```

Acá va el usuario, la contraseña y el host **de Neon**, no los de tu máquina.

> Corré esto una sola vez. El dump son `INSERT`, así que si lo repetís vas a
> duplicar los eventos.

### 2.3 Verificar

En el SQL Editor de Neon:

```sql
SELECT (SELECT count(*) FROM eventos)  AS eventos,
       (SELECT count(*) FROM fuentes)  AS fuentes;
```

Si los números coinciden con lo que tenías local, salió bien.

---

## 3. Deploy en Render

1. Entrá a <https://render.com> y creá cuenta con GitHub.
2. **New + → Web Service** → elegí el repo `salimosapp/admin`.
3. Configuración:

   | Campo                | Valor                                          |
   | -------------------- | ---------------------------------------------- |
   | Name                 | `salimos-admin`                                |
   | Region               | La más cercana a la región de Neon             |
   | Runtime              | Python                                         |
   | Build command        | `pip install -r requirements.txt`             |
   | Start command        | `gunicorn app:app --workers 1 --threads 4 --timeout 300` |
   | Instance type        | Free                                           |

   El start command ya está en el `Procfile`, así que Render debería tomarlo
   solo. Dejalo explícito si te da error.

4. En **Environment**, agregá una por una:

   ```
   DB_HOST       = (el host de Neon)
   DB_PORT       = 5432
   DB_NAME       = neondb
   DB_USER       = (el usuario de Neon)
   DB_PASSWORD   = (la contraseña de Neon)
   DB_SSLMODE    = require
   AI_API_KEY    = (tu clave de Gemini)
   AI_MODEL      = (tu modelo)
   ADMIN_USER    = (el usuario que quieras para entrar al panel)
   ADMIN_PASSWORD= (la contraseña del panel)
   SECRET_KEY    = (ver abajo)
   COOKIE_SECURE = true
   ```

   `DB_SSLMODE=require` es lo que hace que la conexión a Neon vaya cifrada. Sin
   esa variable, `backend/db.py` usa el comportamiento por defecto de psycopg2
   y tu Postgres local sigue funcionando igual.

   `COOKIE_SECURE=true` marca la cookie de sesión como "solo por HTTPS". En
   local va `false` porque ahí la app corre por `http://` y con `true` el
   navegador no te dejaría entrar nunca.

   `SECRET_KEY` es la clave con la que se firman las cookies de sesión.
   Generala una vez con:

   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

   Si no la ponés, la app genera una al azar en cada arranque, y eso significa
   que se te desloguea cada vez que Render reinicia el servidor.

5. **Create Web Service**. Render hace el build y te da una URL tipo
   `https://salimos-admin.onrender.com`. Eso es: abrís esa URL desde el
   celular, en cualquier red, y estás dentro.

El `.env` **nunca** se sube al repo (está en `.gitignore`). Los secretos van
solo en el panel de Render.

Las seis variables de la base (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
`DB_PASSWORD`, `DB_SSLMODE`) son **exactamente las mismas** que vas a poner en
el servicio de `web`. Copiégalas y pegá. Si difieren en un solo carácter, las
dos apps leen bases distintas y se rompe el nexo.

---

## 4. Desplegar `web`

Va en `web/DEPLOY.md`. Es casi lo mismo, con tres diferencias: no lleva clave de
IA, no lleva variables de login (esa web es pública), y el timeout de gunicorn
es menor porque no hace scraping.

---

## 5. Antes del primer deploy

En los dos repos:

```bash
git add -A
git commit -m "prepara deploy en Render: gunicorn, PORT por entorno, sslmode y login"
git push
```

---

## Límites de Neon que hay que tener en el radar

El plan gratis tiene topes, pero **ninguno borra datos**. Lo que pasa es que
cuando los tocás, el proyecto queda suspendido hasta el mes siguiente:

| Límite               | Valor   | Qué pasa si lo pasás                              |
| -------------------- | ------- | -------------------------------------------------- |
| Storage              | 0.5 GB  | Los `INSERT` fallan hasta que liberes espacio     |
| Compute              | 100 CU-h/mes | El proyecto queda suspendido hasta el mes que viene |
| Transferencia pública | 5 GB/mes | El proyecto queda suspendido                       |

El que más te va a afectar es el **storage**, porque tus imágenes viven en la
base (`imagen_datos BYTEA`). Hoy la base pesa 8.9 MB, así que hay margen de
sobra, pero si el scraping empieza a traer cientos de eventos con imagen, eso
crece rápido. Cuando te acerques al tope, mirá cuántos eventos tenés y sacá los
viejos.

El compute se consume solo cuando la base está despierta. O sea que no es un
gasto fijo, pero tampoco es gratis: si las dos apps reciben visitas todo el
tiempo, la base se despierta cada rato y se van las horas.

Aparte, el compute se **duerme a los 5 minutos** de inactividad y se despierta
solo en unos milisegundos con la siguiente consulta. Eso no es un problema
(andá a mirarlo: el arranque lento de 30-60 segundos que vas a notar es el de
Render, no el de Neon).

---

## Limitaciones del plan gratis de Render

- **Arranque en frío**: Render apaga el servidor a los 15 minutos de inactividad.
  La próxima visita tarda 30-60 segundos en levantar. Es normal, no es un error.
- **Sin protección por IP ni CAPTCHA**: el login del panel es de un solo
  usuario, así que alcanza con adivinar la contraseña para tener acceso
  completo. Para un link público compartido por WhatsApp eso es un problema.
  Si hace falta más, el siguiente paso es un login por usuario con password
  hasheada en la base, más un límite de intentos.
- **Scraping**: es un request largo (lotes de 10 con pausas, más descarga de
  imágenes). Con los recursos del free tier puede cortarse a mitad de camino. El
  `--timeout 300` del Procfile le da 5 minutos de margen. Si igual se corta,
  subí el plan o corré el scraping con un worker dedicado.
- **1 worker a propósito**: el free tier da 512 MB y 0.1 CPU. Con más workers
  vas al swap, que es más lento. Además evita que dos procesos compitan
  creando el esquema al arrancar.
- **El disco es efímero**: cada deploy borra el sistema de archivos. No pasa
  nada con tu caso porque las imágenes ya viven en la base (`imagen_datos
  BYTEA`), no en disco.

---

## Volver a trabajar en local

`app.py` ahora lee `HOST` y `PORT` del entorno, con `0.0.0.0:5000` por
default, así que `python app.py` sigue funcionando y además ahora podés entrar
desde el celular en la misma red (usá la IP local de la PC, `ipconfig`).

El panel pide usuario y contraseña (`admin` / `123456` por defecto, definidos en
`ADMIN_USER` y `ADMIN_PASSWORD` del `.env`). Son las mismas variables que vas a
cargar en Render, así que cambialas en los dos lados a la vez.

Si el firewall de Windows te bloquea el puerto, habilitalo para redes privadas:

```powershell
New-NetFirewallRule -DisplayName "Salimos 5000" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow -Profile Private
```
