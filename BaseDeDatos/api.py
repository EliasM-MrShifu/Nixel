from contextlib import contextmanager
import base64
from datetime import date, datetime, time as hora_mysql, timedelta
from hashlib import pbkdf2_hmac, sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import io
import json
import logging
import mysql.connector
import mimetypes
import os
import re
from requests.exceptions import RequestException as WebPushRequestError
import secrets
import time
import zipfile
import zlib
from cryptography.fernet import Fernet, InvalidToken
from typing import Any, Generator
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from pywebpush import WebPushException, webpush

from crear_base_datos import (
    NOMBRE_BASE_DATOS,
    configuracion_mysql,
    crear_base_datos,
)


HOST = "127.0.0.1"
PORT = 5000
PBKDF2_ITERATIONS = 310_000
SESSION_SECONDS = 60 * 60 * 24 * 30
MAX_BODY_SIZE = 30_000_000
CHAT_PAGE_SIZE = 50
CERTIFICATE_MAX_BYTES = 5_000_000
PROFILE_PHOTO_MAX_BYTES = 2_000_000
TEAM_FILE_MAX_BYTES = 20_000_000
GITHUB_ZIP_MAX_BYTES = 15_000_000
GITHUB_REPO_MAX_BYTES = 50_000_000
GITHUB_REPO_MAX_FILES = 100
GITHUB_FILE_MAX_BYTES = 20_000_000
OAUTH_STATE_SECONDS = 600
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class RequestError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class RedirectResponse(Exception):
    def __init__(self, location: str) -> None:
        self.location = location


class BinaryResponse(Exception):
    def __init__(
        self, content_type: str, content: bytes, filename: str, attachment: bool = False
    ) -> None:
        self.content_type = content_type
        self.content = content
        self.filename = filename
        self.attachment = attachment


@contextmanager
def conectar() -> Generator["ConexionMySQL", None, None]:
    conexion = ConexionMySQL(mysql.connector.connect(**configuracion_mysql()))
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


class ConexionMySQL:
    def __init__(self, conexion: mysql.connector.MySQLConnection) -> None:
        self._conexion = conexion

    def execute(
        self, consulta: str, parametros: tuple[Any, ...] = ()
    ) -> mysql.connector.cursor.MySQLCursorDict:
        cursor = self._conexion.cursor(dictionary=True, buffered=True)
        cursor.execute(consulta.replace("?", "%s"), parametros)
        return cursor

    def commit(self) -> None:
        self._conexion.commit()

    def rollback(self) -> None:
        self._conexion.rollback()

    def close(self) -> None:
        self._conexion.close()


def hash_contrasena(contrasena: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = pbkdf2_hmac("sha256", contrasena.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verificar_contrasena(contrasena: str, almacenada: str) -> bool:
    try:
        algoritmo, iteraciones, salt_hex, digest_hex = almacenada.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        digest = pbkdf2_hmac(
            "sha256", contrasena.encode("utf-8"), bytes.fromhex(salt_hex), int(iteraciones)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def hash_token(token: str) -> str:
    return sha256(token.encode("ascii")).hexdigest()


def fila_a_dict(fila: dict[str, Any]) -> dict[str, Any]:
    resultado: dict[str, Any] = {}
    for campo, valor in fila.items():
        if isinstance(valor, timedelta):
            segundos = int(valor.total_seconds())
            horas, resto = divmod(segundos, 3600)
            minutos, segundos = divmod(resto, 60)
            valor = f"{horas:02}:{minutos:02}:{segundos:02}" if segundos else f"{horas:02}:{minutos:02}"
        elif isinstance(valor, (date, datetime, hora_mysql)):
            valor = valor.isoformat()
        resultado[campo] = valor
    return resultado


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "ProyectoAPI/2.0"

    def log_message(self, format_string: str, *args: Any) -> None:
        logging.info("%s - %s", self.address_string(), format_string % args)

    def end_headers(self) -> None:
        origen = self.headers.get("Origin", "")
        if origen in ("http://localhost:5173", "http://127.0.0.1:5173"):
            self.send_header("Access-Control-Allow-Origin", origen)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        self._manejar_peticion("GET")

    def do_POST(self) -> None:
        self._manejar_peticion("POST")

    def do_PATCH(self) -> None:
        self._manejar_peticion("PATCH")

    def do_DELETE(self) -> None:
        self._manejar_peticion("DELETE")

    def _manejar_peticion(self, metodo: str) -> None:
        try:
            resultado, estado = self._despachar(metodo)
            self._responder(estado, resultado)
        except RedirectResponse as respuesta:
            self.send_response(302)
            self.send_header("Location", respuesta.location)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        except BinaryResponse as respuesta:
            self.send_response(200)
            self.send_header("Content-Type", respuesta.content_type)
            self.send_header("Content-Length", str(len(respuesta.content)))
            fallback = re.sub(r"[^A-Za-z0-9._-]", "_", respuesta.filename) or "archivo"
            tipo_disposicion = "attachment" if respuesta.attachment else "inline"
            nombre_codificado = quote(respuesta.filename, safe="")
            self.send_header(
                "Content-Disposition",
                f"{tipo_disposicion}; filename=\"{fallback}\"; filename*=UTF-8''{nombre_codificado}",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(respuesta.content)
        except RequestError as error:
            self._responder(error.status, {"error": str(error)})
        except mysql.connector.IntegrityError:
            self._responder(409, {"error": "La operación entra en conflicto con los datos existentes."})
        except mysql.connector.Error:
            logging.exception("Error al consultar la base de datos")
            self._responder(500, {"error": "Error interno al consultar la base de datos."})

    def _despachar(self, metodo: str) -> tuple[Any, int]:
        url = urlsplit(self.path)
        ruta = url.path.rstrip("/") or "/"
        query = parse_qs(url.query)

        if ruta == "/api/github/callback" and metodo == "GET":
            destino, estado = self._completar_github_oauth(query)
            raise RedirectResponse(f"{destino}/?github={estado}")

        if ruta == "/api/health" and metodo == "GET":
            with conectar() as conexion:
                fila = conexion.execute(
                    "SELECT DATABASE() AS database_name, @@hostname AS host, @@port AS port"
                ).fetchone()
            return {"status": "ok", **fila_a_dict(fila)}, 200

        if ruta == "/api/auth/register" and metodo == "POST":
            datos = self._leer_json()
            nombre = self._texto(datos, "nombre", 120)
            correo = self._correo(datos)
            contrasena = self._contrasena(datos)
            if len(contrasena) < 8:
                raise RequestError("La contraseña debe tener al menos 8 caracteres.")
            with conectar() as conexion:
                cursor = conexion.execute(
                    """
                    INSERT INTO usuarios
                        (nombre, correo, hash_contrasena, ultimo_inicio_sesion)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (nombre, correo, hash_contrasena(contrasena)),
                )
                usuario = conexion.execute(
                    "SELECT id, nombre, correo, creado_en FROM usuarios WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
                token = self._crear_sesion(conexion, int(cursor.lastrowid))
            return {"token": token, "usuario": fila_a_dict(usuario)}, 201

        if ruta == "/api/auth/login" and metodo == "POST":
            datos = self._leer_json()
            correo = self._correo(datos)
            contrasena = self._contrasena(datos)
            with conectar() as conexion:
                usuario = conexion.execute(
                    """
                    SELECT id, nombre, correo, creado_en, hash_contrasena
                    FROM usuarios WHERE correo = ?
                    """,
                    (correo,),
                ).fetchone()
                if usuario is None or not verificar_contrasena(
                    contrasena, usuario["hash_contrasena"]
                ):
                    raise RequestError("Correo o contraseña incorrectos.", 401)
                conexion.execute(
                    "UPDATE usuarios SET ultimo_inicio_sesion = CURRENT_TIMESTAMP WHERE id = ?",
                    (usuario["id"],),
                )
                token = self._crear_sesion(conexion, int(usuario["id"]))
                usuario_publico = fila_a_dict(
                    {campo: usuario[campo] for campo in ("id", "nombre", "correo", "creado_en")}
                )
            return {"token": token, "usuario": usuario_publico}, 200

        if ruta == "/api/auth/logout" and metodo == "POST":
            usuario_id, token = self._sesion_actual()
            del usuario_id
            with conectar() as conexion:
                conexion.execute("DELETE FROM sesiones WHERE token_hash = ?", (hash_token(token),))
            return {"ok": True}, 200

        if ruta == "/api/auth/me" and metodo == "GET":
            usuario_id, _ = self._sesion_actual()
            with conectar() as conexion:
                usuario = conexion.execute(
                    "SELECT id, nombre, correo, creado_en FROM usuarios WHERE id = ?",
                    (usuario_id,),
                ).fetchone()
            if usuario is None:
                raise RequestError("La sesión ya no es válida.", 401)
            return fila_a_dict(usuario), 200

        usuario_id, _ = self._sesion_actual()

        if ruta == "/api/perfil" and metodo == "PATCH":
            datos = self._leer_json()
            with conectar() as conexion:
                usuario = conexion.execute(
                    "SELECT nombre FROM usuarios WHERE id = ?", (usuario_id,)
                ).fetchone()
                if usuario is None:
                    raise RequestError("La sesión ya no es válida.", 401)
                nombre = (
                    self._texto(datos, "nombre", 120)
                    if "nombre" in datos
                    else str(usuario["nombre"])
                )
                if datos.get("quitar_foto") is True:
                    if "foto_base64" in datos:
                        raise RequestError("Elige una foto o quítala, pero no envíes ambas acciones.")
                    conexion.execute(
                        """
                        UPDATE usuarios SET nombre = ?, foto_perfil_mime = NULL,
                                            foto_perfil_datos = NULL
                        WHERE id = ?
                        """,
                        (nombre, usuario_id),
                    )
                elif "foto_base64" in datos:
                    mime, contenido = self._leer_foto_perfil(datos)
                    conexion.execute(
                        """
                        UPDATE usuarios SET nombre = ?, foto_perfil_mime = ?,
                                            foto_perfil_datos = ?
                        WHERE id = ?
                        """,
                        (nombre, mime, contenido, usuario_id),
                    )
                else:
                    conexion.execute(
                        "UPDATE usuarios SET nombre = ? WHERE id = ?", (nombre, usuario_id)
                    )
                perfil = conexion.execute(
                    "SELECT id, nombre, correo, creado_en FROM usuarios WHERE id = ?",
                    (usuario_id,),
                ).fetchone()
            return fila_a_dict(perfil), 200

        coincidencia = re.fullmatch(r"/api/usuarios/(\d+)/foto", ruta)
        if coincidencia and metodo == "GET":
            perfil_id = int(coincidencia.group(1))
            with conectar() as conexion:
                acceso = conexion.execute(
                    """
                    SELECT u.foto_perfil_mime, u.foto_perfil_datos
                    FROM usuarios u
                    WHERE u.id = ? AND (
                        u.id = ?
                        OR EXISTS (
                            SELECT 1 FROM solicitudes_contacto sc
                            WHERE sc.estado = 'aceptada'
                              AND ((sc.solicitante_id = u.id AND sc.destinatario_id = ?)
                                   OR (sc.solicitante_id = ? AND sc.destinatario_id = u.id))
                        )
                        OR EXISTS (
                            SELECT 1 FROM usuarios_equipos perfil_equipo
                            JOIN usuarios_equipos visitante_equipo
                              ON visitante_equipo.equipo_id = perfil_equipo.equipo_id
                            WHERE perfil_equipo.usuario_id = u.id
                              AND visitante_equipo.usuario_id = ?
                        )
                        OR EXISTS (
                            SELECT 1 FROM solicitudes_contacto pendiente
                            WHERE pendiente.estado = 'pendiente'
                              AND ((pendiente.solicitante_id = u.id
                                    AND pendiente.destinatario_id = ?)
                                   OR (pendiente.solicitante_id = ?
                                       AND pendiente.destinatario_id = u.id))
                        )
                    )
                    """,
                    (
                        perfil_id,
                        usuario_id,
                        usuario_id,
                        usuario_id,
                        usuario_id,
                        usuario_id,
                        usuario_id,
                    ),
                ).fetchone()
            if acceso is None:
                raise RequestError("No tienes acceso a esta foto de perfil.", 404)
            if acceso["foto_perfil_datos"] is None:
                raise RequestError("Este perfil no tiene una foto.", 404)
            raise BinaryResponse(
                str(acceso["foto_perfil_mime"]),
                bytes(acceso["foto_perfil_datos"]),
                "perfil",
            )

        if ruta == "/api/contactos":
            if metodo == "GET":
                with conectar() as conexion:
                    contactos = conexion.execute(
                        """
                        SELECT sc.id AS solicitud_id, u.id, u.nombre, u.correo,
                               sc.creada_en AS conectado_en
                        FROM solicitudes_contacto sc
                        JOIN usuarios u ON u.id = CASE
                            WHEN sc.solicitante_id = ? THEN sc.destinatario_id
                            ELSE sc.solicitante_id
                        END
                        WHERE (sc.solicitante_id = ? OR sc.destinatario_id = ?)
                          AND sc.estado = 'aceptada'
                        ORDER BY u.nombre, u.id
                        """,
                        (usuario_id, usuario_id, usuario_id),
                    ).fetchall()
                    recibidas = conexion.execute(
                        """
                        SELECT sc.id, u.id AS usuario_id, u.nombre, u.correo, sc.creada_en
                        FROM solicitudes_contacto sc
                        JOIN usuarios u ON u.id = sc.solicitante_id
                        WHERE sc.destinatario_id = ? AND sc.estado = 'pendiente'
                        ORDER BY sc.creada_en DESC, sc.id DESC
                        """,
                        (usuario_id,),
                    ).fetchall()
                    enviadas = conexion.execute(
                        """
                        SELECT sc.id, u.id AS usuario_id, u.nombre, u.correo, sc.creada_en
                        FROM solicitudes_contacto sc
                        JOIN usuarios u ON u.id = sc.destinatario_id
                        WHERE sc.solicitante_id = ? AND sc.estado = 'pendiente'
                        ORDER BY sc.creada_en DESC, sc.id DESC
                        """,
                        (usuario_id,),
                    ).fetchall()
                return {
                    "contactos": [fila_a_dict(fila) for fila in contactos],
                    "recibidas": [fila_a_dict(fila) for fila in recibidas],
                    "enviadas": [fila_a_dict(fila) for fila in enviadas],
                }, 200
            if metodo == "POST":
                correo = self._correo(self._leer_json())
                with conectar() as conexion:
                    usuario = conexion.execute(
                        "SELECT id FROM usuarios WHERE correo = ?", (correo,)
                    ).fetchone()
                    if usuario is None:
                        raise RequestError("No encontramos una cuenta registrada con ese correo.", 404)
                    destinatario_id = int(usuario["id"])
                    if destinatario_id == usuario_id:
                        raise RequestError("No puedes enviarte una solicitud a tu propia cuenta.")
                    relacion = conexion.execute(
                        """
                        SELECT solicitante_id, destinatario_id, estado
                        FROM solicitudes_contacto
                        WHERE (solicitante_id = ? AND destinatario_id = ?)
                           OR (solicitante_id = ? AND destinatario_id = ?)
                        """,
                        (usuario_id, destinatario_id, destinatario_id, usuario_id),
                    ).fetchall()
                    for existente in relacion:
                        if existente["estado"] == "aceptada":
                            raise RequestError("Esa persona ya está entre tus contactos.", 409)
                        if existente["estado"] == "pendiente":
                            mensaje = (
                                "Esa persona ya te envió una solicitud. Puedes aceptarla en Contactos."
                                if int(existente["solicitante_id"]) == destinatario_id
                                else "Ya enviaste una solicitud pendiente a esa persona."
                            )
                            raise RequestError(mensaje, 409)
                    propia = next(
                        (
                            fila for fila in relacion
                            if int(fila["solicitante_id"]) == usuario_id
                        ),
                        None,
                    )
                    if propia is None:
                        cursor = conexion.execute(
                            """
                            INSERT INTO solicitudes_contacto (solicitante_id, destinatario_id)
                            VALUES (?, ?)
                            """,
                            (usuario_id, destinatario_id),
                        )
                        solicitud_id = int(cursor.lastrowid)
                    else:
                        conexion.execute(
                            """
                            UPDATE solicitudes_contacto
                            SET estado = 'pendiente', creada_en = CURRENT_TIMESTAMP,
                                respondida_en = NULL
                            WHERE solicitante_id = ? AND destinatario_id = ?
                            """,
                            (usuario_id, destinatario_id),
                        )
                        fila_solicitud = conexion.execute(
                            """
                            SELECT id FROM solicitudes_contacto
                            WHERE solicitante_id = ? AND destinatario_id = ?
                            """,
                            (usuario_id, destinatario_id),
                        ).fetchone()
                        if fila_solicitud is None:
                            raise RuntimeError("La solicitud de contacto no quedó guardada.")
                        solicitud_id = int(fila_solicitud["id"])
                return {"id": solicitud_id, "estado": "pendiente"}, 201

        coincidencia = re.fullmatch(r"/api/contactos/(\d+)", ruta)
        if coincidencia:
            solicitud_id = int(coincidencia.group(1))
            if metodo == "PATCH":
                accion = self._texto(self._leer_json(), "accion", 12)
                if accion not in ("aceptar", "rechazar"):
                    raise RequestError("La acción debe ser 'aceptar' o 'rechazar'.")
                estado = "aceptada" if accion == "aceptar" else "rechazada"
                with conectar() as conexion:
                    cursor = conexion.execute(
                        """
                        UPDATE solicitudes_contacto
                        SET estado = ?, respondida_en = CURRENT_TIMESTAMP
                        WHERE id = ? AND destinatario_id = ? AND estado = 'pendiente'
                        """,
                        (estado, solicitud_id, usuario_id),
                    )
                    if cursor.rowcount == 0:
                        raise RequestError(
                            "La solicitud no existe, ya fue respondida o no te pertenece.", 404
                        )
                return {"id": solicitud_id, "estado": estado}, 200
            if metodo == "DELETE":
                with conectar() as conexion:
                    cursor = conexion.execute(
                        """
                        DELETE FROM solicitudes_contacto
                        WHERE id = ? AND estado = 'aceptada'
                          AND (solicitante_id = ? OR destinatario_id = ?)
                        """,
                        (solicitud_id, usuario_id, usuario_id),
                    )
                    if cursor.rowcount == 0:
                        raise RequestError("No se encontró ese contacto.", 404)
                return {"ok": True}, 200

        if ruta == "/api/github/authorize" and metodo == "POST":
            client_id = os.environ.get("GITHUB_CLIENT_ID", "").strip()
            if not client_id:
                raise RequestError(
                    "La API no cargó GITHUB_CLIENT_ID. Iníciala con "
                    ".\\BaseDeDatos\\iniciar.ps1; no ejecutes api.py directamente.",
                    503,
                )
            if not os.environ.get("GITHUB_TOKEN_ENCRYPTION_KEY", "").strip():
                raise RequestError(
                    "Configura GitHub con BaseDeDatos\\configurar_github.ps1 para guardar los permisos cifrados.",
                    503,
                )
            datos = self._leer_json()
            state = secrets.token_urlsafe(32)
            origin = self.headers.get("Origin", "")
            app_url = os.environ.get("WEB_APP_URL", "").strip().rstrip("/")
            if not app_url:
                for candidato in (origin, str(datos.get("app_url", ""))):
                    try:
                        destino = urlsplit(candidato)
                        puerto_destino = destino.port
                    except ValueError:
                        continue
                    if (
                        destino.scheme == "http"
                        and destino.hostname in ("localhost", "127.0.0.1")
                        and puerto_destino is not None
                        and 1 <= puerto_destino <= 65535
                        and not destino.path
                        and not destino.query
                        and not destino.fragment
                    ):
                        app_url = f"{destino.scheme}://{destino.netloc}"
                        break
            if not app_url:
                app_url = "http://localhost:5173"
            with conectar() as conexion:
                conexion.execute(
                    "DELETE FROM github_oauth_states WHERE expira_en <= ?",
                    (int(time.time()),),
                )
                conexion.execute(
                    """
                    INSERT INTO github_oauth_states
                        (state_hash, usuario_id, redirect_url, expira_en)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        hash_token(state),
                        usuario_id,
                        app_url,
                        int(time.time()) + OAUTH_STATE_SECONDS,
                    ),
                )
            params = {
                "client_id": client_id,
                "redirect_uri": self._github_redirect_uri(),
                "scope": "read:user public_repo",
                "state": state,
            }
            return {"authorize_url": f"https://github.com/login/oauth/authorize?{urlencode(params)}"}, 200

        if ruta == "/api/github/repos":
            token = self._github_access_token(usuario_id)
            if metodo == "GET":
                repositorios: list[dict[str, Any]] = []
                for pagina in range(1, 11):
                    filas = self._github_json(
                        token,
                        f"/user/repos?visibility=public&affiliation=owner%2Ccollaborator%2Corganization"
                        f"&per_page=100&page={pagina}&sort=updated",
                    )
                    if not isinstance(filas, list):
                        raise RequestError("GitHub devolvió una lista de repositorios no válida.", 502)
                    repositorios.extend(
                        {
                            "name": fila["name"],
                            "full_name": fila["full_name"],
                            "description": fila.get("description") or "",
                            "html_url": fila["html_url"],
                            "default_branch": fila.get("default_branch") or "main",
                            "language": fila.get("language"),
                            "updated_at": fila.get("updated_at"),
                            "stargazers_count": fila.get("stargazers_count", 0),
                        }
                        for fila in filas
                        if isinstance(fila, dict)
                        and fila.get("private") is False
                        and isinstance(fila.get("name"), str)
                        and isinstance(fila.get("full_name"), str)
                        and isinstance(fila.get("html_url"), str)
                    )
                    if len(filas) < 100:
                        break
                return repositorios, 200
            if metodo == "POST":
                datos = self._leer_json()
                resultado = self._crear_repositorio_publico(token, datos)
                return resultado, 201

        coincidencia = re.fullmatch(
            r"/api/github/repos/([A-Za-z0-9_.-]{1,100})/([A-Za-z0-9_.-]{1,100})/zip",
            ruta,
        )
        if coincidencia and metodo == "GET":
            token = self._github_access_token(usuario_id)
            propietario, nombre = coincidencia.groups()
            repositorio = self._github_json(
                token, f"/repos/{quote(propietario, safe='')}/{quote(nombre, safe='')}"
            )
            if not isinstance(repositorio, dict) or repositorio.get("private") is not False:
                raise RequestError("Solo se permiten repositorios públicos.", 403)
            try:
                solicitud_zip = Request(
                    f"https://api.github.com/repos/{quote(propietario, safe='')}/"
                    f"{quote(nombre, safe='')}/zipball",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {token}",
                        "User-Agent": "Nexus-App",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                with urlopen(solicitud_zip, timeout=30) as respuesta:
                    contenido_zip = respuesta.read(GITHUB_ZIP_MAX_BYTES + 1)
            except HTTPError as error:
                self._error_github(error)
            except (URLError, TimeoutError):
                logging.exception("GitHub repository archive download failed")
                raise RequestError("No se pudo descargar el archivo ZIP desde GitHub.", 502) from None
            if len(contenido_zip) > GITHUB_ZIP_MAX_BYTES:
                raise RequestError("El ZIP del repositorio supera el límite de 15 MB.", 413)
            raise BinaryResponse(
                "application/zip", contenido_zip, f"{nombre}.zip", attachment=True
            )

        if ruta == "/api/github/cuenta":
            if metodo == "GET":
                with conectar() as conexion:
                    cuenta = conexion.execute(
                        """
                        SELECT github_login, avatar_url, profile_url, conectado_en,
                               github_access_token IS NOT NULL AS permisos_repositorios
                        FROM github_cuentas WHERE usuario_id = ?
                        """,
                        (usuario_id,),
                    ).fetchone()
                if cuenta is not None:
                    cuenta["permisos_repositorios"] = bool(cuenta["permisos_repositorios"])
                return fila_a_dict(cuenta) if cuenta else None, 200
            if metodo == "DELETE":
                with conectar() as conexion:
                    conexion.execute("DELETE FROM github_cuentas WHERE usuario_id = ?", (usuario_id,))
                return {"ok": True}, 200

        if ruta == "/api/notificaciones":
            if metodo == "GET":
                with conectar() as conexion:
                    filas = conexion.execute(
                        """
                        SELECT id, equipo_id, tarea_id, alcance, titulo, mensaje, leida_en, creado_en
                        FROM notificaciones
                        WHERE usuario_id = ? AND leida_en IS NULL
                        ORDER BY id DESC LIMIT 50
                        """,
                        (usuario_id,),
                    ).fetchall()
                return [fila_a_dict(fila) for fila in filas], 200

        if ruta == "/api/notificaciones/clave-publica" and metodo == "GET":
            private_key = os.environ.get("VAPID_PRIVATE_KEY_PATH", "").strip()
            claims_email = os.environ.get("VAPID_CLAIMS_EMAIL", "").strip()
            return {
                "public_key": os.environ.get("VAPID_PUBLIC_KEY", "").strip(),
                "configured": bool(
                    private_key
                    and os.path.isfile(private_key)
                    and claims_email.startswith("mailto:")
                ),
            }, 200

        if ruta == "/api/notificaciones/suscripciones" and metodo == "POST":
            datos = self._leer_json()
            endpoint = self._texto(datos, "endpoint", 2048)
            clave_publica = self._texto(datos, "clave_publica", 255)
            clave_auth = self._texto(datos, "clave_auth", 255)
            endpoint_url = urlsplit(endpoint)
            endpoint_host = (endpoint_url.hostname or "").lower()
            push_host_allowed = (
                endpoint_host == "fcm.googleapis.com"
                or endpoint_host.endswith(".push.services.mozilla.com")
                or endpoint_host.endswith(".push.apple.com")
                or endpoint_host.endswith(".notify.windows.com")
            )
            if (
                endpoint_url.scheme != "https"
                or endpoint_url.port not in (None, 443)
                or endpoint_url.username is not None
                or endpoint_url.password is not None
                or not push_host_allowed
            ):
                raise RequestError("El endpoint de notificaciones debe usar HTTPS.")
            with conectar() as conexion:
                conexion.execute(
                    """
                    INSERT INTO suscripciones_push
                        (usuario_id, endpoint_hash, endpoint, clave_publica, clave_auth)
                    VALUES (?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE
                        usuario_id = VALUES(usuario_id),
                        endpoint = VALUES(endpoint),
                        clave_publica = VALUES(clave_publica),
                        clave_auth = VALUES(clave_auth)
                    """,
                    (usuario_id, hash_token(endpoint), endpoint, clave_publica, clave_auth),
                )
            return {"ok": True}, 201

        coincidencia = re.fullmatch(r"/api/notificaciones/(\d+)/leida", ruta)
        if coincidencia and metodo == "POST":
            notificacion_id = int(coincidencia.group(1))
            with conectar() as conexion:
                cursor = conexion.execute(
                    """
                    UPDATE notificaciones SET leida_en = CURRENT_TIMESTAMP
                    WHERE id = ? AND usuario_id = ? AND leida_en IS NULL
                    """,
                    (notificacion_id, usuario_id),
                )
                if cursor.rowcount == 0:
                    raise RequestError("No se encontró la notificación o ya fue leída.", 404)
            return {"ok": True}, 200

        coincidencia = re.fullmatch(r"/api/equipos/(\d+)/ausencias", ruta)
        if coincidencia:
            equipo_id = int(coincidencia.group(1))
            if metodo == "GET":
                with conectar() as conexion:
                    self._requiere_membresia(conexion, usuario_id, equipo_id)
                    filas = conexion.execute(
                        """
                        SELECT a.id, a.equipo_id, a.usuario_id, u.nombre AS usuario_nombre,
                               a.motivo, a.detalle, a.fecha_inicio, a.fecha_fin,
                               CASE WHEN a.usuario_id = ? OR EXISTS (
                                   SELECT 1 FROM usuarios_equipos admin_ue
                                   WHERE admin_ue.usuario_id = ? AND admin_ue.equipo_id = a.equipo_id
                                     AND admin_ue.rol = 'administrador'
                               ) THEN a.certificado_nombre ELSE NULL END AS certificado_nombre,
                               a.creado_en,
                               a.certificado_datos IS NOT NULL AS tiene_certificado,
                               (a.usuario_id = ? OR EXISTS (
                                   SELECT 1 FROM usuarios_equipos admin_ue
                                   WHERE admin_ue.usuario_id = ? AND admin_ue.equipo_id = a.equipo_id
                                     AND admin_ue.rol = 'administrador'
                               )) AS puede_ver_certificado
                        FROM avisos_ausencia a
                        JOIN usuarios u ON u.id = a.usuario_id
                        WHERE a.equipo_id = ?
                        ORDER BY a.creado_en DESC, a.id DESC
                        """,
                        (usuario_id, usuario_id, usuario_id, usuario_id, equipo_id),
                    ).fetchall()
                for fila in filas:
                    fila["tiene_certificado"] = bool(fila["tiene_certificado"])
                    fila["puede_ver_certificado"] = bool(fila["puede_ver_certificado"])
                return [fila_a_dict(fila) for fila in filas], 200
            if metodo == "POST":
                datos = self._leer_json()
                motivo = datos.get("motivo")
                if motivo not in ("ausencia", "enfermedad"):
                    raise RequestError("El motivo debe ser ausencia o enfermedad.")
                fecha_inicio = self._fecha(datos, "fecha_inicio")
                fecha_fin = self._fecha(datos, "fecha_fin")
                if fecha_fin < fecha_inicio:
                    raise RequestError("La fecha final no puede ser anterior a la inicial.")
                detalle = self._texto_opcional(datos, "detalle", 1000)
                nombre, mime, contenido = self._leer_certificado(datos)
                notificaciones_creadas: list[dict[str, Any]] = []
                suscripciones: list[dict[str, Any]] = []
                with conectar() as conexion:
                    self._requiere_membresia(conexion, usuario_id, equipo_id)
                    cursor = conexion.execute(
                        """
                        INSERT INTO avisos_ausencia
                            (equipo_id, usuario_id, motivo, detalle, fecha_inicio, fecha_fin,
                             certificado_nombre, certificado_mime, certificado_datos)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            equipo_id, usuario_id, motivo, detalle, fecha_inicio, fecha_fin,
                            nombre, mime, contenido,
                        ),
                    )
                    aviso = conexion.execute(
                        """
                        SELECT a.id, a.equipo_id, a.usuario_id, u.nombre AS usuario_nombre,
                               a.motivo, a.detalle, a.fecha_inicio, a.fecha_fin,
                               a.certificado_nombre, a.creado_en,
                               a.certificado_datos IS NOT NULL AS tiene_certificado
                        FROM avisos_ausencia a JOIN usuarios u ON u.id = a.usuario_id
                        WHERE a.id = ?
                        """,
                        (cursor.lastrowid,),
                    ).fetchone()
                    destinatarios = [
                        int(item["usuario_id"])
                        for item in conexion.execute(
                            """
                            SELECT usuario_id FROM usuarios_equipos
                            WHERE equipo_id = ? AND usuario_id <> ?
                            """,
                            (equipo_id, usuario_id),
                        ).fetchall()
                    ]
                    texto_motivo = "enfermedad" if motivo == "enfermedad" else "ausencia"
                    for destinatario in destinatarios:
                        notificacion = self._crear_notificacion(
                            conexion,
                            destinatario,
                            usuario_id,
                            equipo_id,
                            None,
                            "equipo",
                            "Aviso de ausencia",
                            f"{aviso['usuario_nombre']} informó una {texto_motivo} del {fecha_inicio} al {fecha_fin}.",
                        )
                        notificaciones_creadas.append(notificacion)
                    suscripciones = self._suscripciones_usuarios(
                        conexion, destinatarios
                    )
                self._enviar_notificaciones_push(notificaciones_creadas, suscripciones)
                return fila_a_dict(aviso), 201

        coincidencia = re.fullmatch(r"/api/ausencias/(\d+)/certificado", ruta)
        if coincidencia and metodo == "GET":
            aviso_id = int(coincidencia.group(1))
            with conectar() as conexion:
                archivo = conexion.execute(
                    """
                    SELECT a.certificado_mime, a.certificado_nombre, a.certificado_datos
                    FROM avisos_ausencia a
                    JOIN usuarios_equipos ue ON ue.equipo_id = a.equipo_id
                    WHERE a.id = ? AND ue.usuario_id = ?
                      AND (a.usuario_id = ? OR ue.rol = 'administrador')
                    """,
                    (aviso_id, usuario_id, usuario_id),
                ).fetchone()
            if archivo is None or archivo["certificado_datos"] is None:
                raise RequestError("No se encontró el certificado o no tienes acceso.", 404)
            raise BinaryResponse(
                archivo["certificado_mime"],
                bytes(archivo["certificado_datos"]),
                archivo["certificado_nombre"],
            )

        coincidencia = re.fullmatch(r"/api/equipos/(\d+)/archivos", ruta)
        if coincidencia:
            equipo_id = int(coincidencia.group(1))
            if metodo == "GET":
                with conectar() as conexion:
                    self._requiere_membresia(conexion, usuario_id, equipo_id)
                    filas = conexion.execute(
                        """
                        SELECT a.id, a.equipo_id, a.usuario_id, u.nombre AS usuario_nombre,
                               a.nombre, a.mime, OCTET_LENGTH(a.datos) AS tamano, a.creado_en
                        FROM archivos_equipo a
                        JOIN usuarios u ON u.id = a.usuario_id
                        WHERE a.equipo_id = ?
                        ORDER BY a.creado_en DESC, a.id DESC
                        """,
                        (equipo_id,),
                    ).fetchall()
                return [fila_a_dict(fila) for fila in filas], 200
            if metodo == "POST":
                datos = self._leer_json()
                nombre, mime, contenido = self._leer_archivo_equipo(datos)
                with conectar() as conexion:
                    self._requiere_membresia(conexion, usuario_id, equipo_id)
                    cursor = conexion.execute(
                        """
                        INSERT INTO archivos_equipo (equipo_id, usuario_id, nombre, mime, datos)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (equipo_id, usuario_id, nombre, mime, contenido),
                    )
                    archivo = conexion.execute(
                        """
                        SELECT a.id, a.equipo_id, a.usuario_id, u.nombre AS usuario_nombre,
                               a.nombre, a.mime, OCTET_LENGTH(a.datos) AS tamano, a.creado_en
                        FROM archivos_equipo a JOIN usuarios u ON u.id = a.usuario_id
                        WHERE a.id = ?
                        """,
                        (cursor.lastrowid,),
                    ).fetchone()
                return fila_a_dict(archivo), 201

        coincidencia = re.fullmatch(r"/api/archivos-equipo/(\d+)/descarga", ruta)
        if coincidencia and metodo == "GET":
            archivo_id = int(coincidencia.group(1))
            with conectar() as conexion:
                archivo = conexion.execute(
                    """
                    SELECT a.nombre, a.mime, a.datos
                    FROM archivos_equipo a
                    JOIN usuarios_equipos ue ON ue.equipo_id = a.equipo_id
                    WHERE a.id = ? AND ue.usuario_id = ?
                    """,
                    (archivo_id, usuario_id),
                ).fetchone()
            if archivo is None:
                raise RequestError("No se encontró el archivo o no tienes acceso.", 404)
            raise BinaryResponse(
                archivo["mime"], bytes(archivo["datos"]), archivo["nombre"], attachment=True
            )

        if ruta == "/api/equipos":
            if metodo == "GET":
                with conectar() as conexion:
                    filas = conexion.execute(
                        """
                        SELECT e.id, e.nombre, e.descripcion, e.creador_id, e.creado_en,
                               ue.rol, COUNT(miembros.usuario_id) AS cantidad_miembros
                        FROM usuarios_equipos ue
                        JOIN equipos e ON e.id = ue.equipo_id
                        LEFT JOIN usuarios_equipos miembros ON miembros.equipo_id = e.id
                        WHERE ue.usuario_id = ?
                        GROUP BY e.id, e.nombre, e.descripcion, e.creador_id, e.creado_en, ue.rol
                        ORDER BY e.nombre
                        """,
                        (usuario_id,),
                    ).fetchall()
                return [fila_a_dict(fila) for fila in filas], 200
            if metodo == "POST":
                datos = self._leer_json()
                nombre = self._texto(datos, "nombre", 120)
                descripcion = self._texto_opcional(datos, "descripcion", 2000)
                with conectar() as conexion:
                    cursor = conexion.execute(
                        "INSERT INTO equipos (nombre, descripcion, creador_id) VALUES (?, ?, ?)",
                        (nombre, descripcion, usuario_id),
                    )
                    equipo_id = int(cursor.lastrowid)
                    conexion.execute(
                        "INSERT INTO usuarios_equipos (usuario_id, equipo_id, rol) VALUES (?, ?, 'administrador')",
                        (usuario_id, equipo_id),
                    )
                    fila = conexion.execute(
                        """
                        SELECT e.id, e.nombre, e.descripcion, e.creador_id, e.creado_en,
                               'administrador' AS rol, 1 AS cantidad_miembros
                        FROM equipos e WHERE e.id = ?
                        """,
                        (equipo_id,),
                    ).fetchone()
                return fila_a_dict(fila), 201

        coincidencia = re.fullmatch(r"/api/equipos/(\d+)/miembros", ruta)
        if coincidencia and metodo == "POST":
            equipo_id = int(coincidencia.group(1))
            datos = self._leer_json()
            correo = self._correo(datos)
            with conectar() as conexion:
                self._requiere_rol(conexion, usuario_id, equipo_id, "administrador")
                usuario = conexion.execute(
                    "SELECT id, nombre, correo FROM usuarios WHERE correo = ?",
                    (correo,),
                ).fetchone()
                if usuario is None:
                    raise RequestError("No existe una cuenta con ese correo.", 404)
                conexion.execute(
                    "INSERT INTO usuarios_equipos (usuario_id, equipo_id) VALUES (?, ?)",
                    (usuario["id"], equipo_id),
                )
            return {"id": usuario["id"], "nombre": usuario["nombre"], "correo": usuario["correo"]}, 201

        if ruta == "/api/tareas":
            alcance = query.get("alcance", ["equipo"])[0]
            if alcance not in ("personal", "equipo"):
                raise RequestError("El alcance debe ser personal o equipo.")
            if metodo == "GET":
                with conectar() as conexion:
                    if alcance == "personal":
                        filas = conexion.execute(
                            """
                            SELECT t.id, t.titulo, t.descripcion, t.tipo, t.estado, t.creado_en,
                                   'personal' AS alcance, NULL AS equipo_id, NULL AS equipo_nombre,
                                   (
                                       SELECT c.fecha
                                       FROM calendario_personal c
                                       WHERE c.tarea_id = t.id
                                       ORDER BY ABS(TIMESTAMPDIFF(
                                           SECOND, CURRENT_TIMESTAMP, TIMESTAMP(c.fecha, c.hora_fin)
                                       )), c.id
                                       LIMIT 1
                                   ) AS fecha_limite,
                                   (
                                       SELECT c.hora_fin
                                       FROM calendario_personal c
                                       WHERE c.tarea_id = t.id
                                       ORDER BY ABS(TIMESTAMPDIFF(
                                           SECOND, CURRENT_TIMESTAMP, TIMESTAMP(c.fecha, c.hora_fin)
                                       )), c.id
                                       LIMIT 1
                                   ) AS hora_limite
                            FROM tareas_personales t
                            WHERE t.usuario_id = ?
                            ORDER BY t.creado_en DESC, t.id DESC
                            """,
                            (usuario_id,),
                        ).fetchall()
                    else:
                        equipo_id = self._query_entero(query, "equipo_id")
                        self._requiere_membresia(conexion, usuario_id, equipo_id)
                        filas = conexion.execute(
                            """
                            SELECT t.id, t.equipo_id, t.creador_id, t.titulo, t.descripcion,
                                   t.tipo, t.estado, t.creado_en, 'equipo' AS alcance,
                                   e.nombre AS equipo_nombre,
                                   (
                                       SELECT c.fecha
                                       FROM calendario c
                                       WHERE c.tarea_id = t.id
                                       ORDER BY ABS(TIMESTAMPDIFF(
                                           SECOND, CURRENT_TIMESTAMP, TIMESTAMP(c.fecha, c.hora_fin)
                                       )), c.id
                                       LIMIT 1
                                   ) AS fecha_limite,
                                   (
                                       SELECT c.hora_fin
                                       FROM calendario c
                                       WHERE c.tarea_id = t.id
                                       ORDER BY ABS(TIMESTAMPDIFF(
                                           SECOND, CURRENT_TIMESTAMP, TIMESTAMP(c.fecha, c.hora_fin)
                                       )), c.id
                                       LIMIT 1
                                   ) AS hora_limite
                            FROM tareas t JOIN equipos e ON e.id = t.equipo_id
                            WHERE t.equipo_id = ?
                            ORDER BY t.creado_en DESC, t.id DESC
                            """,
                            (equipo_id,),
                        ).fetchall()
                return [fila_a_dict(fila) for fila in filas], 200
            if metodo == "POST":
                datos = self._leer_json()
                titulo = self._texto(datos, "titulo", 200)
                descripcion = self._texto_opcional(datos, "descripcion", 5000)
                tipo = datos.get("tipo", "tarea")
                if tipo not in ("tarea", "proyecto"):
                    raise RequestError("El tipo debe ser tarea o proyecto.")
                fecha = self._fecha(datos)
                hora_inicio = self._hora(datos, "hora_inicio")
                hora_fin = self._hora(datos, "hora_fin")
                if hora_fin <= hora_inicio:
                    raise RequestError("La hora final debe ser posterior a la inicial.")
                with conectar() as conexion:
                    if alcance == "personal":
                        cursor = conexion.execute(
                            """
                            INSERT INTO tareas_personales (usuario_id, titulo, descripcion, tipo)
                            VALUES (?, ?, ?, ?)
                            """,
                            (usuario_id, titulo, descripcion, tipo),
                        )
                        tarea_id = int(cursor.lastrowid)
                        conexion.execute(
                            """
                            INSERT INTO calendario_personal (tarea_id, fecha, hora_inicio, hora_fin)
                            VALUES (?, ?, ?, ?)
                            """,
                            (tarea_id, fecha, hora_inicio, hora_fin),
                        )
                        tarea = conexion.execute(
                            """
                            SELECT id, titulo, descripcion, tipo, estado, creado_en,
                                   'personal' AS alcance, NULL AS equipo_id, NULL AS equipo_nombre,
                                   ? AS fecha_limite, ? AS hora_limite
                            FROM tareas_personales WHERE id = ?
                            """,
                            (fecha, hora_fin, tarea_id),
                        ).fetchone()
                    else:
                        equipo_id = self._entero(datos, "equipo_id")
                        self._requiere_membresia(conexion, usuario_id, equipo_id)
                        cursor = conexion.execute(
                            """
                            INSERT INTO tareas (equipo_id, creador_id, titulo, descripcion, tipo)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (equipo_id, usuario_id, titulo, descripcion, tipo),
                        )
                        tarea_id = int(cursor.lastrowid)
                        conexion.execute(
                            """
                            INSERT INTO calendario (tarea_id, fecha, hora_inicio, hora_fin)
                            VALUES (?, ?, ?, ?)
                            """,
                            (tarea_id, fecha, hora_inicio, hora_fin),
                        )
                        tarea = conexion.execute(
                            """
                            SELECT t.id, t.equipo_id, t.creador_id, t.titulo, t.descripcion,
                                   t.tipo, t.estado, t.creado_en, 'equipo' AS alcance,
                                   e.nombre AS equipo_nombre, ? AS fecha_limite, ? AS hora_limite
                            FROM tareas t JOIN equipos e ON e.id = t.equipo_id
                            WHERE t.id = ?
                            """,
                            (fecha, hora_fin, tarea_id),
                        ).fetchone()
                return fila_a_dict(tarea), 201

        coincidencia = re.fullmatch(r"/api/tareas/(personal|equipo)/(\d+)", ruta)
        if coincidencia and metodo == "DELETE":
            alcance, tarea_id = coincidencia.group(1), int(coincidencia.group(2))
            with conectar() as conexion:
                if alcance == "personal":
                    cursor = conexion.execute(
                        "DELETE FROM tareas_personales WHERE id = ? AND usuario_id = ?",
                        (tarea_id, usuario_id),
                    )
                else:
                    tarea = conexion.execute(
                        """
                        SELECT t.creador_id, ue.rol
                        FROM tareas t
                        JOIN usuarios_equipos ue ON ue.equipo_id = t.equipo_id
                        WHERE t.id = ? AND ue.usuario_id = ?
                        """,
                        (tarea_id, usuario_id),
                    ).fetchone()
                    if tarea is None:
                        raise RequestError("No se encontró la tarea o no tienes acceso.", 404)
                    if tarea["creador_id"] != usuario_id and tarea["rol"] != "administrador":
                        raise RequestError(
                            "Solo quien creó la tarea o un administrador puede eliminarla.",
                            403,
                        )
                    cursor = conexion.execute(
                        "DELETE FROM tareas WHERE id = ?",
                        (tarea_id,),
                    )
                if cursor.rowcount == 0:
                    raise RequestError("No se encontró la tarea o no tienes acceso.", 404)
            return {"ok": True}, 200

        if coincidencia and metodo == "PATCH":
            alcance, tarea_id = coincidencia.group(1), int(coincidencia.group(2))
            datos = self._leer_json()
            campos: dict[str, str] = {}
            if "titulo" in datos:
                campos["titulo"] = self._texto(datos, "titulo", 200)
            if "descripcion" in datos:
                campos["descripcion"] = self._texto_opcional(datos, "descripcion", 5000)
            if "estado" in datos:
                estado = datos["estado"]
                if estado not in ("pendiente", "en_progreso", "completada"):
                    raise RequestError("Estado de tarea no válido.")
                campos["estado"] = estado
            if not campos:
                raise RequestError("Indica al menos un campo para actualizar.")
            tabla = "tareas_personales" if alcance == "personal" else "tareas"
            filtro = "usuario_id = ?" if alcance == "personal" else "equipo_id IN (SELECT equipo_id FROM usuarios_equipos WHERE usuario_id = ?)"
            asignaciones = ", ".join(f"{campo} = ?" for campo in campos)
            suscripciones: list[dict[str, Any]] = []
            notificaciones_creadas: list[dict[str, Any]] = []
            with conectar() as conexion:
                anterior = conexion.execute(
                    f"SELECT estado, titulo FROM {tabla} WHERE id = ? AND {filtro}",
                    (tarea_id, usuario_id),
                ).fetchone()
                if anterior is None:
                    raise RequestError("No se encontró la tarea o no tienes acceso.", 404)
                cursor = conexion.execute(
                    f"UPDATE {tabla} SET {asignaciones} WHERE id = ? AND {filtro}",
                    (*campos.values(), tarea_id, usuario_id),
                )
                if alcance == "personal":
                    fila = conexion.execute(
                        """
                        SELECT t.id, t.titulo, t.descripcion, t.tipo, t.estado, t.creado_en,
                               'personal' AS alcance, NULL AS equipo_id, NULL AS equipo_nombre,
                               (SELECT c.fecha FROM calendario_personal c WHERE c.tarea_id = t.id
                                ORDER BY c.fecha DESC, c.hora_fin DESC, c.id DESC LIMIT 1) AS fecha_limite,
                               (SELECT c.hora_fin FROM calendario_personal c WHERE c.tarea_id = t.id
                                ORDER BY c.fecha DESC, c.hora_fin DESC, c.id DESC LIMIT 1) AS hora_limite
                        FROM tareas_personales t WHERE t.id = ?
                        """,
                        (tarea_id,),
                    ).fetchone()
                else:
                    fila = conexion.execute(
                        """
                        SELECT t.id, t.equipo_id, t.creador_id, t.titulo, t.descripcion,
                               t.tipo, t.estado, t.creado_en, 'equipo' AS alcance,
                               e.nombre AS equipo_nombre,
                               (SELECT c.fecha FROM calendario c WHERE c.tarea_id = t.id
                                ORDER BY c.fecha DESC, c.hora_fin DESC, c.id DESC LIMIT 1) AS fecha_limite,
                               (SELECT c.hora_fin FROM calendario c WHERE c.tarea_id = t.id
                                ORDER BY c.fecha DESC, c.hora_fin DESC, c.id DESC LIMIT 1) AS hora_limite
                        FROM tareas t JOIN equipos e ON e.id = t.equipo_id WHERE t.id = ?
                        """,
                        (tarea_id,),
                    ).fetchone()
                if "estado" in campos and campos["estado"] != anterior["estado"]:
                    if alcance == "personal":
                        destinatarios = [usuario_id]
                        equipo_id = None
                    else:
                        equipo = conexion.execute(
                            "SELECT equipo_id FROM tareas WHERE id = ?", (tarea_id,)
                        ).fetchone()
                        equipo_id = int(equipo["equipo_id"])
                        destinatarios = [
                            int(item["usuario_id"])
                            for item in conexion.execute(
                                "SELECT usuario_id FROM usuarios_equipos WHERE equipo_id = ?",
                                (equipo_id,),
                            ).fetchall()
                        ]
                    mensaje = (
                        f"{anterior['titulo']}: {anterior['estado'].replace('_', ' ')} → "
                        f"{campos['estado'].replace('_', ' ')}"
                    )
                    for destinatario in destinatarios:
                        notificacion = self._crear_notificacion(
                            conexion,
                            destinatario,
                            usuario_id,
                            equipo_id,
                            tarea_id,
                            alcance,
                            "Cambió el estado de una tarea",
                            mensaje,
                        )
                        notificaciones_creadas.append(notificacion)
                    suscripciones = self._suscripciones_usuarios(
                        conexion, destinatarios
                    )
            self._enviar_notificaciones_push(notificaciones_creadas, suscripciones)
            return fila_a_dict(fila), 200

        if ruta == "/api/calendario" and metodo == "GET":
            mes = query.get("mes", [datetime.now().strftime("%Y-%m")])[0]
            try:
                inicio = datetime.strptime(f"{mes}-01", "%Y-%m-%d").date()
            except ValueError as error:
                raise RequestError("El mes debe tener formato AAAA-MM.") from error
            if inicio.strftime("%Y-%m") != mes:
                raise RequestError("El mes debe tener formato AAAA-MM.")
            if inicio.month == 12:
                siguiente = inicio.replace(year=inicio.year + 1, month=1)
            else:
                siguiente = inicio.replace(month=inicio.month + 1)
            with conectar() as conexion:
                personales = conexion.execute(
                    """
                    SELECT c.id, c.tarea_id, c.fecha, c.hora_inicio, c.hora_fin,
                           t.titulo AS tarea_titulo, 'personal' AS alcance, NULL AS equipo_nombre
                    FROM calendario_personal c
                    JOIN tareas_personales t ON t.id = c.tarea_id
                    WHERE t.usuario_id = ? AND c.fecha >= ? AND c.fecha < ?
                    """,
                    (usuario_id, inicio.isoformat(), siguiente.isoformat()),
                ).fetchall()
                equipos = conexion.execute(
                    """
                    SELECT c.id, c.tarea_id, c.fecha, c.hora_inicio, c.hora_fin,
                           t.titulo AS tarea_titulo, 'equipo' AS alcance, e.nombre AS equipo_nombre
                    FROM calendario c
                    JOIN tareas t ON t.id = c.tarea_id
                    JOIN equipos e ON e.id = t.equipo_id
                    JOIN usuarios_equipos ue ON ue.equipo_id = t.equipo_id
                    WHERE ue.usuario_id = ? AND c.fecha >= ? AND c.fecha < ?
                    """,
                    (usuario_id, inicio.isoformat(), siguiente.isoformat()),
                ).fetchall()
            eventos = [fila_a_dict(fila) for fila in (*personales, *equipos)]
            eventos.sort(key=lambda evento: (evento["fecha"], evento["hora_inicio"]))
            return eventos, 200

        if ruta == "/api/calendario" and metodo == "POST":
            datos = self._leer_json()
            tarea_id = self._entero(datos, "tarea_id")
            alcance = datos.get("alcance")
            if alcance not in ("personal", "equipo"):
                raise RequestError("El alcance debe ser personal o equipo.")
            fecha = self._fecha(datos)
            hora_inicio = self._hora(datos, "hora_inicio")
            hora_fin = self._hora(datos, "hora_fin")
            if hora_fin <= hora_inicio:
                raise RequestError("La hora final debe ser posterior a la inicial.")
            tabla = "calendario_personal" if alcance == "personal" else "calendario"
            with conectar() as conexion:
                if alcance == "personal":
                    tarea = conexion.execute(
                        "SELECT id FROM tareas_personales WHERE id = ? AND usuario_id = ?",
                        (tarea_id, usuario_id),
                    ).fetchone()
                else:
                    tarea = conexion.execute(
                        """
                        SELECT t.id FROM tareas t
                        JOIN usuarios_equipos ue ON ue.equipo_id = t.equipo_id
                        WHERE t.id = ? AND ue.usuario_id = ?
                        """,
                        (tarea_id, usuario_id),
                    ).fetchone()
                if tarea is None:
                    raise RequestError("No se encontró la tarea o no tienes acceso.", 404)
                cursor = conexion.execute(
                    f"""
                    INSERT INTO {tabla} (tarea_id, fecha, hora_inicio, hora_fin)
                    VALUES (?, ?, ?, ?)
                    """,
                    (tarea_id, fecha, hora_inicio, hora_fin),
                )
                fila = conexion.execute(
                    f"""
                    SELECT c.id, c.tarea_id, c.fecha, c.hora_inicio, c.hora_fin,
                           t.titulo AS tarea_titulo, ? AS alcance, NULL AS equipo_nombre
                    FROM {tabla} c
                    JOIN {"tareas_personales" if alcance == "personal" else "tareas"} t
                      ON t.id = c.tarea_id
                    WHERE c.id = ?
                    """,
                    (alcance, cursor.lastrowid),
                ).fetchone()
            return fila_a_dict(fila), 201

        coincidencia = re.fullmatch(r"/api/chat/(\d+)", ruta)
        if coincidencia:
            equipo_id = int(coincidencia.group(1))
            with conectar() as conexion:
                self._requiere_membresia(conexion, usuario_id, equipo_id)
                if metodo == "GET":
                    antes_de = query.get("antes", [None])[0]
                    if antes_de is None:
                        filas = conexion.execute(
                            """
                            SELECT m.id, m.equipo_id, m.usuario_id, u.nombre AS autor,
                                   m.contenido, m.creado_en
                            FROM (
                                SELECT * FROM mensajes_chat
                                WHERE equipo_id = ? ORDER BY id DESC LIMIT ?
                            ) m JOIN usuarios u ON u.id = m.usuario_id
                            ORDER BY m.id ASC
                            """,
                            (equipo_id, CHAT_PAGE_SIZE),
                        ).fetchall()
                    else:
                        try:
                            cursor_id = int(antes_de)
                        except ValueError as error:
                            raise RequestError("El cursor del chat no es válido.") from error
                        filas = conexion.execute(
                            """
                            SELECT m.id, m.equipo_id, m.usuario_id, u.nombre AS autor,
                                   m.contenido, m.creado_en
                            FROM (
                                SELECT * FROM mensajes_chat
                                WHERE equipo_id = ? AND id < ? ORDER BY id DESC LIMIT ?
                            ) m JOIN usuarios u ON u.id = m.usuario_id
                            ORDER BY m.id ASC
                            """,
                            (equipo_id, cursor_id, CHAT_PAGE_SIZE),
                        ).fetchall()
                    return [fila_a_dict(fila) for fila in filas], 200
                if metodo == "POST":
                    datos = self._leer_json()
                    contenido = self._texto(datos, "contenido", 4000)
                    cursor = conexion.execute(
                        "INSERT INTO mensajes_chat (equipo_id, usuario_id, contenido) VALUES (?, ?, ?)",
                        (equipo_id, usuario_id, contenido),
                    )
                    fila = conexion.execute(
                        """
                        SELECT m.id, m.equipo_id, m.usuario_id, u.nombre AS autor,
                               m.contenido, m.creado_en
                        FROM mensajes_chat m JOIN usuarios u ON u.id = m.usuario_id
                        WHERE m.id = ?
                        """,
                        (cursor.lastrowid,),
                    ).fetchone()
                    return fila_a_dict(fila), 201

        raise RequestError("Ruta no encontrada.", 404)

    def _crear_sesion(self, conexion: ConexionMySQL, usuario_id: int) -> str:
        token = secrets.token_urlsafe(32)
        conexion.execute(
            "INSERT INTO sesiones (token_hash, usuario_id, expira_en) VALUES (?, ?, ?)",
            (hash_token(token), usuario_id, int(time.time()) + SESSION_SECONDS),
        )
        return token

    @staticmethod
    def _github_cipher() -> Fernet:
        clave = os.environ.get("GITHUB_TOKEN_ENCRYPTION_KEY", "").strip()
        if not clave:
            raise RequestError("Falta configurar el cifrado local de GitHub.", 503)
        try:
            return Fernet(clave.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as error:
            raise RequestError("La clave local de cifrado de GitHub no es válida.", 503) from error

    def _github_access_token(self, usuario_id: int) -> str:
        with conectar() as conexion:
            cuenta = conexion.execute(
                "SELECT github_access_token FROM github_cuentas WHERE usuario_id = ?",
                (usuario_id,),
            ).fetchone()
        if cuenta is None or not cuenta["github_access_token"]:
            raise RequestError(
                "Conecta o vuelve a autorizar GitHub para consultar repositorios públicos.", 403
            )
        try:
            return self._github_cipher().decrypt(
                str(cuenta["github_access_token"]).encode("ascii")
            ).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as error:
            logging.exception("Stored GitHub token could not be decrypted")
            raise RequestError(
                "No se pudo descifrar el permiso de GitHub. Vuelve a conectar la cuenta.", 503
            ) from error

    def _github_json(
        self,
        token: str,
        ruta: str,
        metodo: str = "GET",
        datos: dict[str, Any] | None = None,
    ) -> Any:
        contenido = json.dumps(datos).encode("utf-8") if datos is not None else None
        solicitud = Request(
            f"https://api.github.com{ruta}",
            data=contenido,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "Nexus-App",
                "X-GitHub-Api-Version": "2022-11-28",
                **({"Content-Type": "application/json"} if contenido is not None else {}),
            },
            method=metodo,
        )
        try:
            with urlopen(solicitud, timeout=30) as respuesta:
                cuerpo = respuesta.read(8_000_001)
        except HTTPError as error:
            self._error_github(error)
        except (URLError, TimeoutError):
            logging.exception("GitHub API request failed")
            raise RequestError("No se pudo completar la solicitud a GitHub.", 502) from None
        if len(cuerpo) > 8_000_000:
            raise RequestError("La respuesta de GitHub supera el límite permitido.", 502)
        try:
            return json.loads(cuerpo) if cuerpo else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RequestError("GitHub devolvió una respuesta no válida.", 502) from error

    @staticmethod
    def _error_github(error: HTTPError) -> None:
        try:
            cuerpo = json.loads(error.read(4096))
            mensaje = cuerpo.get("message") if isinstance(cuerpo, dict) else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            mensaje = None
        mensaje = mensaje if isinstance(mensaje, str) else "GitHub rechazó la solicitud."
        estado = (
            error.code
            if error.code in (400, 401, 403, 404, 409, 413, 429)
            else 409 if error.code == 422 else 502
        )
        if error.code == 401:
            mensaje = "GitHub rechazó el permiso. Vuelve a autorizar la conexión."
            estado = 403
        raise RequestError(f"GitHub: {mensaje[:300]}", estado) from error

    def _crear_repositorio_publico(
        self, token: str, datos: dict[str, Any]
    ) -> dict[str, str]:
        nombre = self._texto(datos, "nombre", 100)
        if not re.fullmatch(r"[A-Za-z0-9._-]+", nombre) or nombre in (".", ".."):
            raise RequestError("El nombre del repositorio contiene caracteres no permitidos.")
        descripcion = self._texto_opcional(datos, "descripcion", 350)
        archivo_codificado = datos.get("archivo_base64")
        if not isinstance(archivo_codificado, str):
            raise RequestError("Selecciona un archivo ZIP para crear el repositorio.")
        try:
            contenido_zip = base64.b64decode(archivo_codificado, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise RequestError("El archivo del repositorio no es un ZIP válido.") from error
        if not contenido_zip or len(contenido_zip) > GITHUB_ZIP_MAX_BYTES:
            raise RequestError("El ZIP debe pesar como máximo 15 MB.")

        archivos: list[tuple[str, bytes]] = []
        try:
            with zipfile.ZipFile(io.BytesIO(contenido_zip)) as paquete:
                entradas = [entrada for entrada in paquete.infolist() if not entrada.is_dir()]
                if not entradas or len(entradas) > GITHUB_REPO_MAX_FILES:
                    raise RequestError("El ZIP debe contener entre 1 y 100 archivos.")
                total = 0
                rutas: set[str] = set()
                for entrada in entradas:
                    ruta = entrada.filename
                    partes = ruta.split("/")
                    modo = (entrada.external_attr >> 16) & 0o170000
                    if (
                        not ruta
                        or ruta.startswith("/")
                        or "\\" in ruta
                        or "\x00" in ruta
                        or any(parte in ("", ".", "..") for parte in partes)
                        or any(parte.lower() == ".git" for parte in partes)
                        or modo == 0o120000
                        or len(ruta) > 240
                    ):
                        raise RequestError("El ZIP contiene una ruta o enlace no permitido.")
                    if ruta in rutas:
                        raise RequestError("El ZIP contiene rutas de archivo duplicadas.")
                    rutas.add(ruta)
                    if entrada.file_size > GITHUB_FILE_MAX_BYTES:
                        raise RequestError("Cada archivo del ZIP debe pesar como máximo 20 MB.")
                    total += entrada.file_size
                    if total > GITHUB_REPO_MAX_BYTES:
                        raise RequestError("El contenido descomprimido del ZIP supera 50 MB.")
                    contenido = paquete.read(entrada)
                    if len(contenido) != entrada.file_size:
                        raise RequestError("El ZIP contiene un archivo incompleto.")
                    archivos.append((ruta, contenido))
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError, zlib.error) as error:
            raise RequestError("El archivo seleccionado no es un ZIP válido.") from error

        repositorio = self._github_json(
            token,
            "/user/repos",
            "POST",
            {"name": nombre, "description": descripcion, "private": False, "auto_init": True},
        )
        if (
            not isinstance(repositorio, dict)
            or not isinstance(repositorio.get("full_name"), str)
            or not isinstance(repositorio.get("default_branch"), str)
            or not isinstance(repositorio.get("html_url"), str)
        ):
            raise RequestError("GitHub creó una respuesta de repositorio incompleta.", 502)
        full_name = repositorio["full_name"]
        owner, repo_name = full_name.split("/", 1)
        base = f"/repos/{quote(owner, safe='')}/{quote(repo_name, safe='')}"
        branch = quote(repositorio["default_branch"], safe="")
        try:
            referencia = self._github_json(token, f"{base}/git/ref/heads/{branch}")
            arbol_base = referencia["object"]["sha"]
            elementos = []
            for ruta, contenido in archivos:
                blob = self._github_json(
                    token,
                    f"{base}/git/blobs",
                    "POST",
                    {
                        "content": base64.b64encode(contenido).decode("ascii"),
                        "encoding": "base64",
                    },
                )
                elementos.append(
                    {"path": ruta, "mode": "100644", "type": "blob", "sha": blob["sha"]}
                )
            arbol = self._github_json(
                token,
                f"{base}/git/trees",
                "POST",
                {"base_tree": arbol_base, "tree": elementos},
            )
            confirmacion = self._github_json(
                token,
                f"{base}/git/commits",
                "POST",
                {
                    "message": "Subir archivos desde Nexus",
                    "tree": arbol["sha"],
                    "parents": [referencia["object"]["sha"]],
                },
            )
            self._github_json(
                token,
                f"{base}/git/refs/heads/{branch}",
                "PATCH",
                {"sha": confirmacion["sha"], "force": False},
            )
        except (KeyError, TypeError) as error:
            raise RequestError(
                f"El repositorio {repositorio['html_url']} se creó, pero GitHub no devolvió "
                "la información necesaria para completar la carga.",
                502,
            ) from error
        except RequestError as error:
            raise RequestError(
                f"El repositorio público {repositorio['html_url']} se creó, pero la carga "
                f"no pudo completarse: {error}",
                502,
            ) from error
        return {
            "full_name": full_name,
            "html_url": repositorio["html_url"],
            "default_branch": repositorio["default_branch"],
        }

    def _completar_github_oauth(
        self, query: dict[str, list[str]]
    ) -> tuple[str, str]:
        state = query.get("state", [""])[0]
        if not state:
            return os.environ.get("WEB_APP_URL", "http://localhost:5173").rstrip("/"), "error"
        with conectar() as conexion:
            registro = conexion.execute(
                """
                SELECT usuario_id, redirect_url FROM github_oauth_states
                WHERE state_hash = ? AND expira_en > ?
                """,
                (hash_token(state), int(time.time())),
            ).fetchone()
            conexion.execute(
                "DELETE FROM github_oauth_states WHERE state_hash = ?",
                (hash_token(state),),
            )
        if registro is None:
            return os.environ.get("WEB_APP_URL", "http://localhost:5173").rstrip("/"), "error"
        destino = registro["redirect_url"].rstrip("/")
        if query.get("error") or not query.get("code", [""])[0]:
            return destino, "cancelado"
        client_id = os.environ.get("GITHUB_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GITHUB_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            logging.error("GitHub OAuth callback reached without client credentials")
            return destino, "error"
        try:
            solicitud_token = Request(
                "https://github.com/login/oauth/access_token",
                data=json.dumps(
                    {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": query["code"][0],
                        "redirect_uri": self._github_redirect_uri(),
                    }
                ).encode("utf-8"),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Nexus-App",
                },
                method="POST",
            )
            with urlopen(solicitud_token, timeout=15) as respuesta:
                token_data = json.loads(respuesta.read())
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                logging.warning("GitHub OAuth did not return an access token")
                return destino, "error"
            scopes = set(str(token_data.get("scope", "")).replace(",", " ").split())
            if "public_repo" not in scopes:
                logging.warning("GitHub OAuth did not grant public repository access")
                return destino, "error"
            solicitud_usuario = Request(
                "https://api.github.com/user",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": "Nexus-App",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            with urlopen(solicitud_usuario, timeout=15) as respuesta:
                perfil = json.loads(respuesta.read())
            github_id = perfil.get("id")
            login = perfil.get("login")
            if (
                isinstance(github_id, bool)
                or not isinstance(github_id, int)
                or not isinstance(login, str)
                or not login
            ):
                logging.warning("GitHub returned an incomplete user profile")
                return destino, "error"
            with conectar() as conexion:
                linked = conexion.execute(
                    "SELECT usuario_id FROM github_cuentas WHERE github_user_id = ?",
                    (github_id,),
                ).fetchone()
                if linked is not None and int(linked["usuario_id"]) != int(registro["usuario_id"]):
                    logging.warning("A GitHub account is already linked to another Nexus user")
                    return destino, "error"
                conexion.execute(
                    "DELETE FROM github_cuentas WHERE usuario_id = ?",
                    (registro["usuario_id"],),
                )
                conexion.execute(
                    """
                    INSERT INTO github_cuentas
                        (usuario_id, github_user_id, github_login, avatar_url, profile_url,
                         github_access_token)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        registro["usuario_id"],
                        github_id,
                        login[:120],
                        str(perfil.get("avatar_url", ""))[:1000],
                        str(perfil.get("html_url", f"https://github.com/{login}"))[:1000],
                        self._github_cipher().encrypt(access_token.encode("utf-8")).decode("ascii"),
                    ),
                )
            return destino, "conectado"
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, mysql.connector.Error):
            logging.exception("GitHub OAuth connection failed")
            return destino, "error"

    @staticmethod
    def _github_redirect_uri() -> str:
        return os.environ.get(
            "GITHUB_REDIRECT_URI", f"http://127.0.0.1:{PORT}/api/github/callback"
        ).strip()

    @staticmethod
    def _crear_notificacion(
        conexion: "ConexionMySQL",
        usuario_id: int,
        actor_id: int | None,
        equipo_id: int | None,
        tarea_id: int | None,
        alcance: str,
        titulo: str,
        mensaje: str,
    ) -> dict[str, Any]:
        cursor = conexion.execute(
            """
            INSERT INTO notificaciones
                (usuario_id, actor_id, equipo_id, tarea_id, tarea_personal_id,
                 tarea_equipo_id, alcance, titulo, mensaje)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usuario_id,
                actor_id,
                equipo_id,
                tarea_id,
                tarea_id if alcance == "personal" else None,
                tarea_id if alcance == "equipo" else None,
                alcance,
                titulo,
                mensaje,
            ),
        )
        return {
            "id": int(cursor.lastrowid),
            "usuario_id": usuario_id,
            "titulo": titulo,
            "mensaje": mensaje,
        }

    @staticmethod
    def _suscripciones_usuarios(
        conexion: "ConexionMySQL", usuario_ids: list[int]
    ) -> list[dict[str, Any]]:
        if not usuario_ids:
            return []
        marcadores = ", ".join("?" for _ in usuario_ids)
        return conexion.execute(
            f"""
            SELECT usuario_id, endpoint_hash, endpoint, clave_publica, clave_auth
            FROM suscripciones_push WHERE usuario_id IN ({marcadores})
            """,
            tuple(usuario_ids),
        ).fetchall()

    @staticmethod
    def _enviar_notificaciones_push(
        notificaciones: list[dict[str, Any]],
        suscripciones: list[dict[str, Any]],
    ) -> None:
        private_key = os.environ.get("VAPID_PRIVATE_KEY_PATH", "").strip()
        claims_email = os.environ.get("VAPID_CLAIMS_EMAIL", "").strip()
        if (
            not private_key
            or not os.path.isfile(private_key)
            or not os.environ.get("VAPID_PUBLIC_KEY", "").strip()
            or not claims_email.startswith("mailto:")
        ):
            return
        por_usuario: dict[int, list[dict[str, Any]]] = {}
        for notificacion in notificaciones:
            por_usuario.setdefault(notificacion["usuario_id"], []).append(notificacion)
        for suscripcion in suscripciones:
            for notificacion in por_usuario.get(int(suscripcion["usuario_id"]), []):
                try:
                    webpush(
                        subscription_info={
                            "endpoint": suscripcion["endpoint"],
                            "keys": {
                                "p256dh": suscripcion["clave_publica"],
                                "auth": suscripcion["clave_auth"],
                            },
                        },
                        data=json.dumps(
                            {
                                "id": notificacion["id"],
                                "title": notificacion["titulo"],
                                "body": notificacion["mensaje"],
                            },
                            ensure_ascii=False,
                        ),
                        vapid_private_key=private_key,
                        vapid_claims={"sub": claims_email},
                    )
                except WebPushException as error:
                    codigo = error.response.status_code if error.response else None
                    if codigo in (404, 410):
                        with conectar() as conexion:
                            conexion.execute(
                                "DELETE FROM suscripciones_push WHERE endpoint_hash = ?",
                                (suscripcion["endpoint_hash"],),
                            )
                    logging.warning(
                        "Web Push failed for subscription (%s): %s", codigo, error
                    )
                except (OSError, ValueError, WebPushRequestError):
                    logging.exception("Web Push could not send a notification")

    def _sesion_actual(self) -> tuple[int, str]:
        autorizacion = self.headers.get("Authorization", "")
        esquema, _, token = autorizacion.partition(" ")
        if esquema.lower() != "bearer" or not token:
            raise RequestError("Inicia sesión para continuar.", 401)
        with conectar() as conexion:
            sesion = conexion.execute(
                """
                SELECT usuario_id FROM sesiones
                WHERE token_hash = ? AND expira_en > ?
                """,
                (hash_token(token), int(time.time())),
            ).fetchone()
            if sesion is None:
                raise RequestError("La sesión expiró. Inicia sesión nuevamente.", 401)
        return int(sesion["usuario_id"]), token

    @staticmethod
    def _requiere_membresia(
        conexion: ConexionMySQL, usuario_id: int, equipo_id: int
    ) -> None:
        miembro = conexion.execute(
            "SELECT 1 FROM usuarios_equipos WHERE usuario_id = ? AND equipo_id = ?",
            (usuario_id, equipo_id),
        ).fetchone()
        if miembro is None:
            raise RequestError("No perteneces a este equipo.", 403)

    @staticmethod
    def _requiere_rol(
        conexion: ConexionMySQL, usuario_id: int, equipo_id: int, rol: str
    ) -> None:
        miembro = conexion.execute(
            "SELECT rol FROM usuarios_equipos WHERE usuario_id = ? AND equipo_id = ?",
            (usuario_id, equipo_id),
        ).fetchone()
        if miembro is None or miembro["rol"] != rol:
            raise RequestError("Se requiere ser administrador de este equipo.", 403)

    def _leer_json(self) -> dict[str, Any]:
        try:
            longitud = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise RequestError("Content-Length no es válido.") from error
        if longitud < 1 or longitud > MAX_BODY_SIZE:
            raise RequestError("El cuerpo de la solicitud está vacío o excede el límite.")
        try:
            datos = json.loads(self.rfile.read(longitud))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RequestError("El cuerpo debe ser JSON válido.") from error
        if not isinstance(datos, dict):
            raise RequestError("El cuerpo JSON debe ser un objeto.")
        return datos

    @staticmethod
    def _texto(datos: dict[str, Any], campo: str, maximo: int) -> str:
        valor = datos.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise RequestError(f"'{campo}' es obligatorio.")
        valor = valor.strip()
        if len(valor) > maximo:
            raise RequestError(f"'{campo}' excede el máximo de {maximo} caracteres.")
        return valor

    @staticmethod
    def _texto_opcional(datos: dict[str, Any], campo: str, maximo: int) -> str:
        valor = datos.get(campo, "")
        if not isinstance(valor, str):
            raise RequestError(f"'{campo}' debe ser texto.")
        valor = valor.strip()
        if len(valor) > maximo:
            raise RequestError(f"'{campo}' excede el máximo de {maximo} caracteres.")
        return valor

    @staticmethod
    def _leer_certificado(
        datos: dict[str, Any],
    ) -> tuple[str | None, str | None, bytes | None]:
        contenido_codificado = datos.get("certificado_base64")
        nombre_original = datos.get("certificado_nombre")
        if contenido_codificado is None and nombre_original is None:
            return None, None, None
        if not isinstance(contenido_codificado, str) or not isinstance(nombre_original, str):
            raise RequestError("El archivo del certificado está incompleto.")
        try:
            contenido = base64.b64decode(contenido_codificado, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise RequestError("El certificado debe ser una imagen válida.") from error
        if not contenido or len(contenido) > CERTIFICATE_MAX_BYTES:
            raise RequestError("El certificado debe pesar como máximo 5 MB.")
        if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
            mime, extension = "image/png", ".png"
        elif contenido.startswith(b"\xff\xd8\xff"):
            mime, extension = "image/jpeg", ".jpg"
        elif (
            len(contenido) >= 12
            and contenido[:4] == b"RIFF"
            and contenido[8:12] == b"WEBP"
        ):
            mime, extension = "image/webp", ".webp"
        else:
            raise RequestError("Solo se aceptan imágenes PNG, JPG o WEBP.")
        nombre = os.path.basename(nombre_original.replace("\\", "/"))
        nombre = re.sub(r"[^A-Za-z0-9._-]", "_", nombre)[:200]
        if not nombre or not nombre.lower().endswith(extension):
            nombre = f"certificado{extension}"
        return nombre, mime, contenido

    @staticmethod
    def _leer_archivo_equipo(datos: dict[str, Any]) -> tuple[str, str, bytes]:
        nombre_original = datos.get("nombre")
        contenido_codificado = datos.get("archivo_base64")
        if not isinstance(nombre_original, str) or not isinstance(contenido_codificado, str):
            raise RequestError("El archivo seleccionado está incompleto.")
        try:
            contenido = base64.b64decode(contenido_codificado, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise RequestError("El archivo seleccionado no es válido.") from error
        if not contenido or len(contenido) > TEAM_FILE_MAX_BYTES:
            raise RequestError("El archivo debe pesar como máximo 20 MB.")
        nombre = os.path.basename(nombre_original.replace("\\", "/"))
        nombre = re.sub(r"[\x00-\x1f\x7f]", "", nombre).strip(" .")
        if not nombre or len(nombre) > 200:
            raise RequestError("El nombre del archivo no es válido.")
        mime = mimetypes.guess_type(nombre, strict=False)[0] or "application/octet-stream"
        return nombre, mime[:120], contenido

    @staticmethod
    def _leer_foto_perfil(datos: dict[str, Any]) -> tuple[str, bytes]:
        codificado = datos.get("foto_base64")
        if not isinstance(codificado, str):
            raise RequestError("Selecciona una foto de perfil válida.")
        try:
            contenido = base64.b64decode(codificado, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise RequestError("La imagen de perfil no es válida.") from error
        if not contenido or len(contenido) > PROFILE_PHOTO_MAX_BYTES:
            raise RequestError("La foto de perfil debe pesar como máximo 2 MB.")
        if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif contenido.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif (
            len(contenido) >= 12
            and contenido[:4] == b"RIFF"
            and contenido[8:12] == b"WEBP"
        ):
            mime = "image/webp"
        else:
            raise RequestError("La foto debe ser una imagen PNG, JPG o WEBP.")
        return mime, contenido

    @staticmethod
    def _entero(datos: dict[str, Any], campo: str) -> int:
        valor = datos.get(campo)
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise RequestError(f"'{campo}' debe ser un entero positivo.")
        return valor

    @staticmethod
    def _query_entero(query: dict[str, list[str]], campo: str) -> int:
        valores = query.get(campo)
        if not valores:
            raise RequestError(f"Falta el parámetro '{campo}'.")
        try:
            resultado = int(valores[0])
        except ValueError as error:
            raise RequestError(f"'{campo}' debe ser un número entero.") from error
        if resultado <= 0:
            raise RequestError(f"'{campo}' debe ser un número entero positivo.")
        return resultado

    @staticmethod
    def _correo(datos: dict[str, Any]) -> str:
        correo = ApiHandler._texto(datos, "correo", 254).lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
            raise RequestError("El correo electrónico no es válido.")
        return correo

    @staticmethod
    def _contrasena(datos: dict[str, Any]) -> str:
        valor = datos.get("contrasena")
        if not isinstance(valor, str) or not valor:
            raise RequestError("La contraseña es obligatoria.")
        if len(valor) > 1024:
            raise RequestError("La contraseña excede el máximo permitido.")
        return valor

    @staticmethod
    def _fecha(datos: dict[str, Any], campo: str = "fecha") -> str:
        valor = ApiHandler._texto(datos, campo, 10)
        try:
            fecha = datetime.strptime(valor, "%Y-%m-%d").date()
        except ValueError as error:
            raise RequestError(f"'{campo}' debe tener formato AAAA-MM-DD.") from error
        if fecha.isoformat() != valor:
            raise RequestError(f"'{campo}' debe tener formato AAAA-MM-DD.")
        return valor

    @staticmethod
    def _hora(datos: dict[str, Any], campo: str) -> str:
        valor = ApiHandler._texto(datos, campo, 5)
        try:
            datetime.strptime(valor, "%H:%M")
        except ValueError as error:
            raise RequestError(f"'{campo}' debe tener formato HH:MM.") from error
        return valor

    def _responder(self, estado: int, contenido: Any) -> None:
        cuerpo = json.dumps(contenido, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


def iniciar_api(host: str = HOST, port: int = PORT) -> None:
    _cargar_configuracion_github_local()
    crear_base_datos()
    servidor = ThreadingHTTPServer((host, port), ApiHandler)
    logging.info("API escuchando en http://%s:%s", host, port)
    configuracion = configuracion_mysql()
    logging.info(
        "MySQL destino: %s:%s/%s (usuario %s)",
        configuracion["host"],
        configuracion["port"],
        NOMBRE_BASE_DATOS,
        configuracion["user"],
    )
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        logging.info("Deteniendo API...")
    finally:
        servidor.server_close()


def _cargar_configuracion_github_local() -> None:
    carpeta_local = os.environ.get("LOCALAPPDATA")
    if not carpeta_local:
        return
    ruta_configuracion = os.path.join(carpeta_local, "Nexo", "github_oauth.json")
    if not os.path.isfile(ruta_configuracion):
        return
    try:
        with open(ruta_configuracion, encoding="utf-8") as archivo:
            configuracion = json.load(archivo)
    except (OSError, json.JSONDecodeError):
        logging.exception("Could not read the local GitHub OAuth configuration")
        raise
    if not isinstance(configuracion, dict):
        raise ValueError("La configuración local de GitHub debe ser un objeto JSON.")
    for variable, campo in (
        ("GITHUB_CLIENT_ID", "client_id"),
        ("GITHUB_CLIENT_SECRET", "client_secret"),
        ("GITHUB_TOKEN_ENCRYPTION_KEY", "token_encryption_key"),
    ):
        valor = configuracion.get(campo)
        if isinstance(valor, str) and valor.strip() and not os.environ.get(variable, "").strip():
            os.environ[variable] = valor.strip()


if __name__ == "__main__":
    iniciar_api(host=HOST, port=PORT)
