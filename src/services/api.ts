const API_BASE = '/api'
const TOKEN_KEY = 'espacio-token'

export interface Usuario {
  id: number
  nombre: string
  correo: string
  creado_en: string
}

export interface Equipo {
  id: number
  nombre: string
  descripcion: string
  creador_id: number
  cantidad_miembros: number
  rol: 'administrador' | 'miembro'
}

export interface Tarea {
  id: number
  equipo_id: number | null
  equipo_nombre: string | null
  alcance: 'personal' | 'equipo'
  titulo: string
  descripcion: string
  tipo: 'tarea' | 'proyecto'
  estado: 'pendiente' | 'en_progreso' | 'completada'
  creado_en: string
  fecha_limite: string | null
  hora_limite: string | null
}

export interface EventoCalendario {
  id: number
  tarea_id: number
  fecha: string
  hora_inicio: string
  hora_fin: string
  tarea_titulo: string
  alcance: 'personal' | 'equipo'
  equipo_nombre: string | null
}

export interface MensajeChat {
  id: number
  equipo_id: number
  usuario_id: number
  autor: string
  contenido: string
  creado_en: string
}

export interface CuentaGitHub {
  github_login: string
  avatar_url: string
  profile_url: string
  conectado_en: string
}

export interface AvisoAusencia {
  id: number
  equipo_id: number
  usuario_id: number
  usuario_nombre: string
  motivo: 'ausencia' | 'enfermedad'
  detalle: string
  fecha_inicio: string
  fecha_fin: string
  certificado_nombre: string | null
  tiene_certificado: boolean
  creado_en: string
}

export interface Notificacion {
  id: number
  equipo_id: number | null
  tarea_id: number | null
  alcance: 'personal' | 'equipo'
  titulo: string
  mensaje: string
  leida_en: string | null
  creado_en: string
}

async function solicitar<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY)
  const respuesta = await fetch(`${API_BASE}${ruta}`, {
    ...opciones,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opciones.headers,
    },
  })
  const contenido: unknown = respuesta.status === 204 ? null : await respuesta.json()
  if (!respuesta.ok) {
    const mensaje =
      typeof contenido === 'object' &&
      contenido !== null &&
      'error' in contenido &&
      typeof contenido.error === 'string'
        ? contenido.error
        : `Error HTTP ${respuesta.status}`
    if (respuesta.status === 401 && !ruta.startsWith('/auth/')) {
      localStorage.removeItem(TOKEN_KEY)
      window.dispatchEvent(new Event('auth-expirada'))
    }
    throw new Error(mensaje)
  }
  return contenido as T
}

function post<T>(ruta: string, datos: Record<string, unknown>): Promise<T> {
  return solicitar<T>(ruta, { method: 'POST', body: JSON.stringify(datos) })
}

async function iniciarSesion(
  ruta: '/auth/login' | '/auth/register',
  datos: Record<string, unknown>,
): Promise<Usuario> {
  const respuesta = await post<{ token: string; usuario: Usuario }>(ruta, datos)
  localStorage.setItem(TOKEN_KEY, respuesta.token)
  return respuesta.usuario
}

export const api = {
  tieneSesion: () => localStorage.getItem(TOKEN_KEY) !== null,
  comprobar: () => solicitar<{ status: string }>('/health'),
  usuarioActual: () => solicitar<Usuario>('/auth/me'),
  iniciarSesion: (correo: string, contrasena: string) =>
    iniciarSesion('/auth/login', { correo, contrasena }),
  registrar: (nombre: string, correo: string, contrasena: string) =>
    iniciarSesion('/auth/register', { nombre, correo, contrasena }),
  cerrarSesion: async () => {
    try {
      await post('/auth/logout', {})
    } finally {
      localStorage.removeItem(TOKEN_KEY)
    }
  },
  listarEquipos: () => solicitar<Equipo[]>('/equipos'),
  crearEquipo: (nombre: string, descripcion: string) =>
    post<Equipo>('/equipos', { nombre, descripcion }),
  agregarMiembro: (equipoId: number, correo: string) =>
    post(`/equipos/${equipoId}/miembros`, { correo }),
  listarTareas: (alcance: 'personal' | 'equipo', equipoId?: number) => {
    const parametros = new URLSearchParams({ alcance })
    if (equipoId !== undefined) parametros.set('equipo_id', String(equipoId))
    return solicitar<Tarea[]>(`/tareas?${parametros}`)
  },
  crearTarea: (datos: {
    alcance: 'personal' | 'equipo'
    equipo_id?: number
    titulo: string
    descripcion: string
    tipo: 'tarea' | 'proyecto'
    fecha: string
    hora_inicio: string
    hora_fin: string
  }) => post<Tarea>(`/tareas?alcance=${datos.alcance}`, datos),
  actualizarEstadoTarea: (tarea: Tarea, estado: Tarea['estado']) =>
    solicitar<Tarea>(`/tareas/${tarea.alcance}/${tarea.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ estado }),
    }),
  listarCalendario: (mes: string) =>
    solicitar<EventoCalendario[]>(`/calendario?mes=${encodeURIComponent(mes)}`),
  agendarTarea: (datos: {
    tarea_id: number
    alcance: 'personal' | 'equipo'
    fecha: string
    hora_inicio: string
    hora_fin: string
  }) => post<EventoCalendario>('/calendario', datos),
  listarMensajes: (equipoId: number) => solicitar<MensajeChat[]>(`/chat/${equipoId}`),
  enviarMensaje: (equipoId: number, contenido: string) =>
    post<MensajeChat>(`/chat/${equipoId}`, { contenido }),
  obtenerCuentaGitHub: () => solicitar<CuentaGitHub | null>('/github/cuenta'),
  iniciarConexionGitHub: () =>
    post<{ authorize_url: string }>('/github/authorize', { app_url: window.location.origin }),
  desconectarGitHub: () =>
    solicitar<{ ok: boolean }>('/github/cuenta', { method: 'DELETE' }),
  listarAvisosAusencia: (equipoId: number) =>
    solicitar<AvisoAusencia[]>(`/equipos/${equipoId}/ausencias`),
  crearAvisoAusencia: (
    equipoId: number,
    datos: {
      motivo: 'ausencia' | 'enfermedad'
      detalle: string
      fecha_inicio: string
      fecha_fin: string
      certificado_nombre?: string
      certificado_base64?: string
    },
  ) => post<AvisoAusencia>(`/equipos/${equipoId}/ausencias`, datos),
  descargarCertificado: async (avisoId: number) => {
    const token = localStorage.getItem(TOKEN_KEY)
    const respuesta = await fetch(`${API_BASE}/ausencias/${avisoId}/certificado`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!respuesta.ok) throw new Error(`No se pudo abrir el certificado (HTTP ${respuesta.status}).`)
    return respuesta.blob()
  },
  clavePublicaNotificaciones: () =>
    solicitar<{ public_key: string; configured: boolean }>('/notificaciones/clave-publica'),
  guardarSuscripcionNotificaciones: (datos: {
    endpoint: string
    clave_publica: string
    clave_auth: string
  }) => post<{ ok: boolean }>('/notificaciones/suscripciones', datos),
  listarNotificaciones: () => solicitar<Notificacion[]>('/notificaciones'),
  marcarNotificacionLeida: (id: number) =>
    post<{ ok: boolean }>(`/notificaciones/${id}/leida`, {}),
}
