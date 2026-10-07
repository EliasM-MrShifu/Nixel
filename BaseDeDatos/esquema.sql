CREATE DATABASE IF NOT EXISTS `aplicacion`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `aplicacion`;

CREATE TABLE IF NOT EXISTS usuarios (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    correo VARCHAR(254) NOT NULL,
    hash_contrasena VARCHAR(128) NOT NULL,
    foto_perfil_mime VARCHAR(40) NULL,
    foto_perfil_datos MEDIUMBLOB NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultimo_inicio_sesion TIMESTAMP NULL DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_usuarios_correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS solicitudes_contacto (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    solicitante_id BIGINT UNSIGNED NOT NULL,
    destinatario_id BIGINT UNSIGNED NOT NULL,
    estado ENUM('pendiente', 'aceptada', 'rechazada') NOT NULL DEFAULT 'pendiente',
    creada_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    respondida_en TIMESTAMP NULL DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_contacto_direccion (solicitante_id, destinatario_id),
    KEY idx_contactos_destinatario_estado (destinatario_id, estado, creada_en),
    KEY idx_contactos_solicitante_estado (solicitante_id, estado, creada_en),
    CONSTRAINT chk_contacto_no_self CHECK (solicitante_id <> destinatario_id),
    CONSTRAINT fk_contacto_solicitante
        FOREIGN KEY (solicitante_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_contacto_destinatario
        FOREIGN KEY (destinatario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sesiones (
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    usuario_id BIGINT UNSIGNED NOT NULL,
    expira_en BIGINT UNSIGNED NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (token_hash),
    KEY idx_sesiones_usuario (usuario_id),
    CONSTRAINT fk_sesiones_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS equipos (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    descripcion TEXT NOT NULL,
    creador_id BIGINT UNSIGNED NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_equipos_creador (creador_id),
    CONSTRAINT fk_equipos_creador
        FOREIGN KEY (creador_id) REFERENCES usuarios(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuarios_equipos (
    usuario_id BIGINT UNSIGNED NOT NULL,
    equipo_id BIGINT UNSIGNED NOT NULL,
    rol ENUM('administrador', 'miembro') NOT NULL DEFAULT 'miembro',
    unido_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id, equipo_id),
    KEY idx_usuarios_equipos_equipo (equipo_id),
    CONSTRAINT fk_usuarios_equipos_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_usuarios_equipos_equipo
        FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tareas (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    equipo_id BIGINT UNSIGNED NOT NULL,
    creador_id BIGINT UNSIGNED NULL,
    titulo VARCHAR(200) NOT NULL,
    descripcion TEXT NOT NULL,
    tipo ENUM('tarea', 'proyecto') NOT NULL DEFAULT 'tarea',
    estado ENUM('pendiente', 'en_progreso', 'completada') NOT NULL DEFAULT 'pendiente',
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_tareas_equipo_estado (equipo_id, estado),
    KEY idx_tareas_creador (creador_id),
    CONSTRAINT fk_tareas_equipo
        FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE,
    CONSTRAINT fk_tareas_creador
        FOREIGN KEY (creador_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tareas_personales (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    usuario_id BIGINT UNSIGNED NOT NULL,
    titulo VARCHAR(200) NOT NULL,
    descripcion TEXT NOT NULL,
    tipo ENUM('tarea', 'proyecto') NOT NULL DEFAULT 'tarea',
    estado ENUM('pendiente', 'en_progreso', 'completada') NOT NULL DEFAULT 'pendiente',
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_tareas_personales_usuario (usuario_id, estado),
    CONSTRAINT fk_tareas_personales_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS calendario (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    tarea_id BIGINT UNSIGNED NOT NULL,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_calendario_fecha_hora (fecha, hora_inicio),
    KEY idx_calendario_tarea (tarea_id),
    CONSTRAINT fk_calendario_tarea
        FOREIGN KEY (tarea_id) REFERENCES tareas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS calendario_personal (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    tarea_id BIGINT UNSIGNED NOT NULL,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_calendario_personal_fecha (fecha, hora_inicio),
    KEY idx_calendario_personal_tarea (tarea_id),
    CONSTRAINT fk_calendario_personal_tarea
        FOREIGN KEY (tarea_id) REFERENCES tareas_personales(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mensajes_chat (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    equipo_id BIGINT UNSIGNED NOT NULL,
    usuario_id BIGINT UNSIGNED NOT NULL,
    contenido TEXT NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_mensajes_equipo_id (equipo_id, id),
    KEY idx_mensajes_usuario (usuario_id),
    CONSTRAINT fk_mensajes_equipo
        FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE,
    CONSTRAINT fk_mensajes_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS github_cuentas (
    usuario_id BIGINT UNSIGNED NOT NULL,
    github_user_id BIGINT UNSIGNED NOT NULL,
    github_login VARCHAR(120) NOT NULL,
    avatar_url VARCHAR(1000) NOT NULL,
    profile_url VARCHAR(1000) NOT NULL,
    github_access_token TEXT NULL,
    conectado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id),
    UNIQUE KEY uq_github_user_id (github_user_id),
    CONSTRAINT fk_github_cuenta_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS github_oauth_states (
    state_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    usuario_id BIGINT UNSIGNED NOT NULL,
    redirect_url VARCHAR(1000) NOT NULL,
    expira_en BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (state_hash),
    KEY idx_github_oauth_expira (expira_en),
    CONSTRAINT fk_github_oauth_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS archivos_equipo (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    equipo_id BIGINT UNSIGNED NOT NULL,
    usuario_id BIGINT UNSIGNED NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    mime VARCHAR(120) NOT NULL,
    datos LONGBLOB NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_archivos_equipo_fecha (equipo_id, creado_en),
    KEY idx_archivos_usuario (usuario_id),
    CONSTRAINT fk_archivos_equipo
        FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE,
    CONSTRAINT fk_archivos_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS avisos_ausencia (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    equipo_id BIGINT UNSIGNED NOT NULL,
    usuario_id BIGINT UNSIGNED NOT NULL,
    motivo ENUM('ausencia', 'enfermedad') NOT NULL,
    detalle VARCHAR(1000) NOT NULL DEFAULT '',
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    certificado_nombre VARCHAR(255) NULL,
    certificado_mime VARCHAR(100) NULL,
    certificado_datos LONGBLOB NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_avisos_equipo_fecha (equipo_id, fecha_inicio, fecha_fin),
    KEY idx_avisos_usuario (usuario_id),
    CONSTRAINT fk_avisos_equipo
        FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE,
    CONSTRAINT fk_avisos_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notificaciones (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    usuario_id BIGINT UNSIGNED NOT NULL,
    actor_id BIGINT UNSIGNED NULL,
    equipo_id BIGINT UNSIGNED NULL,
    tarea_id BIGINT UNSIGNED NULL,
    tarea_personal_id BIGINT UNSIGNED NULL,
    tarea_equipo_id BIGINT UNSIGNED NULL,
    alcance ENUM('personal', 'equipo') NOT NULL,
    titulo VARCHAR(200) NOT NULL,
    mensaje VARCHAR(500) NOT NULL,
    leida_en TIMESTAMP NULL DEFAULT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_notificaciones_usuario (usuario_id, leida_en, id),
    CONSTRAINT fk_notificaciones_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_notificaciones_actor
        FOREIGN KEY (actor_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    CONSTRAINT fk_notificaciones_equipo
        FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE,
    CONSTRAINT fk_notificaciones_tarea_personal
        FOREIGN KEY (tarea_personal_id) REFERENCES tareas_personales(id) ON DELETE CASCADE,
    CONSTRAINT fk_notificaciones_tarea_equipo
        FOREIGN KEY (tarea_equipo_id) REFERENCES tareas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS suscripciones_push (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    usuario_id BIGINT UNSIGNED NOT NULL,
    endpoint_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    endpoint TEXT NOT NULL,
    clave_publica VARCHAR(255) NOT NULL,
    clave_auth VARCHAR(255) NOT NULL,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_push_endpoint_hash (endpoint_hash),
    KEY idx_push_usuario (usuario_id),
    CONSTRAINT fk_push_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
