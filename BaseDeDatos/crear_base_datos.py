from contextlib import closing
import os
from pathlib import Path
import mysql.connector


CARPETA_BASE_DATOS = Path(__file__).resolve().parent
NOMBRE_BASE_DATOS = "aplicacion"
RUTA_ESQUEMA = CARPETA_BASE_DATOS / "esquema.sql"


def configuracion_mysql(incluir_base: bool = True) -> dict[str, object]:
    configuracion: dict[str, object] = {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "autocommit": False,
    }
    if incluir_base:
        configuracion["database"] = NOMBRE_BASE_DATOS
    return configuracion


def crear_base_datos() -> None:
    """Crea la base MySQL aplicacion y sus tablas sin borrar datos existentes."""
    esquema = RUTA_ESQUEMA.read_text(encoding="utf-8")
    with closing(mysql.connector.connect(**configuracion_mysql(incluir_base=False))) as conexion:
        cursor = conexion.cursor()
        try:
            for sentencia in esquema.split(";"):
                sentencia = sentencia.strip()
                if sentencia:
                    cursor.execute(sentencia)
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'usuarios'
                  AND column_name = 'ultimo_inicio_sesion'
                """,
                (NOMBRE_BASE_DATOS,),
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    """
                    ALTER TABLE usuarios
                    ADD COLUMN ultimo_inicio_sesion TIMESTAMP NULL DEFAULT NULL
                    AFTER creado_en
                    """
                )
            for columna, definicion in (
                ("foto_perfil_mime", "VARCHAR(40) NULL"),
                ("foto_perfil_datos", "MEDIUMBLOB NULL"),
            ):
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = 'usuarios'
                      AND column_name = %s
                    """,
                    (NOMBRE_BASE_DATOS, columna),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {columna} {definicion}")
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'github_cuentas'
                  AND column_name = 'github_access_token'
                """,
                (NOMBRE_BASE_DATOS,),
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "ALTER TABLE github_cuentas ADD COLUMN github_access_token TEXT NULL"
                )
            for columna in ("tarea_personal_id", "tarea_equipo_id"):
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = 'notificaciones'
                      AND column_name = %s
                    """,
                    (NOMBRE_BASE_DATOS, columna),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute(
                        f"ALTER TABLE notificaciones ADD COLUMN {columna} BIGINT UNSIGNED NULL"
                    )
            for constraint, columna, tabla in (
                ("fk_notificaciones_tarea_personal", "tarea_personal_id", "tareas_personales"),
                ("fk_notificaciones_tarea_equipo", "tarea_equipo_id", "tareas"),
            ):
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.table_constraints
                    WHERE constraint_schema = %s AND table_name = 'notificaciones'
                      AND constraint_name = %s
                    """,
                    (NOMBRE_BASE_DATOS, constraint),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute(
                        f"""
                        ALTER TABLE notificaciones
                        ADD CONSTRAINT {constraint}
                        FOREIGN KEY ({columna}) REFERENCES {tabla}(id) ON DELETE CASCADE
                        """
                    )
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise
        finally:
            cursor.close()


if __name__ == "__main__":
    crear_base_datos()
    print(f"Base de datos MySQL lista: {NOMBRE_BASE_DATOS}")
