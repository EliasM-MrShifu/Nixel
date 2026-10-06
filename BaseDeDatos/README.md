# MySQL y API

La aplicación usa MySQL con la base `aplicacion`. El esquema completo está en
`esquema.sql` y también crea la base si todavía no existe:

```sql
CREATE DATABASE IF NOT EXISTS `aplicacion`;
USE `aplicacion`;
```

## Preparar MySQL/phpMyAdmin

1. Inicia el servidor MySQL (por ejemplo, desde XAMPP).
2. Opcionalmente, abre phpMyAdmin, selecciona **Importar** y ejecuta `esquema.sql`.
   El script crea/selecciona `aplicacion` y crea las tablas sin borrar datos existentes.
3. Instala las dependencias de Python:

```powershell
& C:\Python314\python.exe -m pip install -r .\BaseDeDatos\requirements.txt
```

## Configurar conexión

La API acepta estas variables de entorno; si no defines ninguna, intenta conectar al
MySQL local como `root` sin contraseña (configuración común en XAMPP):

```powershell
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "root"
$env:MYSQL_PASSWORD = "tu contraseña"
```

Configúralas en la misma terminal donde inicies la API. La cuenta MySQL necesita permiso
para crear la base `aplicacion` y sus tablas. Si ya importaste `esquema.sql`, también
puedes usar una cuenta con permisos sobre esa base.

## Iniciar la aplicación

MySQL debe estar iniciado antes de la API. Desde la terminal de PowerShell, en la carpeta
del proyecto, inicia la API con:

```powershell
.\BaseDeDatos\iniciar.ps1
```

El script usa `.venv` cuando está disponible. Como alternativa, también puedes ejecutar
directamente `& .\.venv\Scripts\python.exe .\BaseDeDatos\api.py`. Al iniciar, la API
asegura que la base y las tablas existan y escucha en `http://127.0.0.1:5000`.

Deja esa terminal abierta. En una segunda terminal, inicia Vue:

```powershell
Set-Location .\Aplicaion
npm run dev
```

Vite reenvía las solicitudes `/api` al backend. Comprueba la conexión con:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

## Persistencia y sincronización

El registro guarda la cuenta en `usuarios`. Cada inicio de sesión actualiza
`usuarios.ultimo_inicio_sesion` y crea una sesión en `sesiones`; el navegador conserva el
token para mantener la sesión después de actualizar la página. Cerrar sesión invalida esa
sesión, pero no elimina la cuenta.

Al crear una tarea o proyecto, se guardan juntos el registro en `tareas` o
`tareas_personales` y su evento en el calendario correspondiente. La fecha y las horas
son obligatorias. La interfaz marca en verde lo que vence en más de 72 horas, en amarillo
lo que vence entre 24 y 72 horas y en rojo lo que vence dentro de 24 horas o ya venció;
las tareas completadas se muestran en estado neutral.

La interfaz y phpMyAdmin escriben y leen la misma base MySQL `aplicacion`. Los cambios
manuales hechos en MySQL se vuelven a consultar en la interfaz cada 5 segundos; el chat
se actualiza cada 3 segundos. Los cambios de la aplicación quedan guardados en MySQL al
responder cada operación.

## GitHub, avisos del equipo y notificaciones del sistema

Cada usuario conecta su propio perfil de GitHub con OAuth. Nexo solo solicita `read:user`,
consulta el perfil y guarda el ID y el enlace público; el token OAuth no se conserva y no
se solicitan permisos para repositorios. Crea una OAuth App en GitHub y configura, en la
misma terminal donde levantas la API:

```powershell
$env:GITHUB_CLIENT_ID = "ID_DE_LA_OAUTH_APP"
$env:GITHUB_CLIENT_SECRET = "SECRETO_DE_LA_OAUTH_APP"
$env:GITHUB_REDIRECT_URI = "http://127.0.0.1:5000/api/github/callback"
$env:WEB_APP_URL = "http://localhost:5173"
```

Registra en la OAuth App exactamente la URL de callback indicada en `GITHUB_REDIRECT_URI`.
No publiques el secreto ni lo guardes en los archivos del proyecto. Después de crearla,
ejecuta `.\BaseDeDatos\configurar_github.ps1`: te pide el Client ID y solicita el Client
Secret en modo oculto; las credenciales quedan en `%LOCALAPPDATA%\Nexo\github_oauth.json`,
fuera del repositorio, con permisos restringidos al usuario y SYSTEM. Reinicia la API con
`.\BaseDeDatos\iniciar.ps1` para leerlas.

En cada servidor existe una sección de avisos de ausencia/enfermedad. Las imágenes
aceptadas son PNG, JPG y WEBP de hasta 5 MB; quedan en MySQL y son visibles a todas las
personas que pertenecen a ese servidor. Los avisos no son públicos fuera de sus miembros.

Para recibir alertas aunque Nexo no esté abierto, habilita Web Push. La aplicación necesita
HTTPS en despliegue (localhost se considera seguro en desarrollo), permiso de notificaciones
en cada dispositivo y claves VAPID configuradas en la API. Puedes generar las claves fuera
del proyecto desde PowerShell (las guarda en la carpeta actual):

```powershell
Set-Location $HOME
& "C:\ruta\al\proyecto\.venv\Scripts\vapid.exe" --gen
& "C:\ruta\al\proyecto\.venv\Scripts\vapid.exe" --applicationServerKey --private-key "$HOME\private_key.pem"
```

Copia el valor `Application Server Key` de la segunda orden. Configura el path de la clave
privada y la clave pública en la terminal que inicia la API:

```powershell
$env:VAPID_PUBLIC_KEY = "VALOR_APPLICATION_SERVER_KEY"
$env:VAPID_PRIVATE_KEY_PATH = "$HOME\private_key.pem"
$env:VAPID_CLAIMS_EMAIL = "mailto:administracion@tu-dominio.com"
```

El launcher lee automáticamente las claves desde `%LOCALAPPDATA%\Nexo` en cada inicio. La
clave pública VAPID se entrega desde la API a la aplicación al crear la suscripción. Cada usuario debe entrar desde cada dispositivo y pulsar **Activar
avisos en este dispositivo**. La web instala un service worker y su manifiesto PWA; las
notificaciones pendientes también se conservan en MySQL y se muestran al volver a abrir la
aplicación si el navegador concedió permiso. El sistema operativo/navegador debe permitir
notificaciones en segundo plano para entregarlas con el dispositivo cerrado o suspendido.
Guarda el correo de contacto VAPID (formato `mailto:correo@dominio`) en
`%LOCALAPPDATA%\Nexo\vapid_claims_email.txt`. Las claves privadas generadas deben permanecer
fuera del repositorio; la carpeta local se restringe al usuario de Windows y SYSTEM.

Los cambios de estado de tareas del servidor y los avisos de ausencia generan notificaciones
persistentes para los demás miembros; las tareas personales generan una notificación para
la propia cuenta, útil para sus otros dispositivos.

## Tablas

- `usuarios` y `sesiones`: cuentas, último inicio de sesión y sesiones con contraseñas/tokens almacenados como hashes.
- `equipos` y `usuarios_equipos`: servidores y pertenencia de sus usuarios.
- `tareas` y `tareas_personales`: tareas/proyectos compartidos o privados.
- `calendario` y `calendario_personal`: fecha y horas de las tareas.
- `mensajes_chat`: mensajes de servidor persistentes.
- `github_cuentas` y `github_oauth_states`: perfiles GitHub vinculados y estados OAuth temporales.
- `avisos_ausencia`: avisos y certificados de imagen asociados a un servidor.
- `notificaciones` y `suscripciones_push`: historial de avisos y suscripciones de cada dispositivo.

El chat muestra los 50 mensajes más recientes, mientras conserva el historial anterior.
El creador de un servidor queda como administrador; para invitar, el administrador escribe
el correo de otra cuenta ya registrada.
