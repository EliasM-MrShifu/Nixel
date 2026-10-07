<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  api,
  type Equipo,
  type EventoCalendario,
  type AvisoAusencia,
  type CuentaGitHub,
  type MensajeChat,
  type Notificacion,
  type Tarea,
  type Usuario,
} from '@/services/api'

type Pantalla = 'personal' | 'calendario' | 'equipo' | 'github'

const usuario = ref<Usuario | null>(null)
const cargando = ref(true)
const trabajando = ref(false)
const aviso = ref('')
const avisoError = ref(false)
const modoAcceso = ref<'entrar' | 'registrar'>('entrar')
const formularioAcceso = reactive({ nombre: '', correo: '', contrasena: '' })
const equipos = ref<Equipo[]>([])
const equipoActivoId = ref<number | null>(null)
const equipoActivo = computed(() => equipos.value.find((equipo) => equipo.id === equipoActivoId.value) ?? null)
const pantalla = ref<Pantalla>('personal')
const vistaEquipo = ref<'chat' | 'tareas' | 'ausencias'>('chat')
const tareasPersonales = ref<Tarea[]>([])
const tareasEquipo = ref<Tarea[]>([])
const tareasTodos = ref<Tarea[]>([])
const eventos = ref<EventoCalendario[]>([])
const mensajes = ref<MensajeChat[]>([])
const textoMensaje = ref('')
const ahora = ref(Date.now())
const notificacionesAbiertas = ref(false)
const notificacionesEstado = ref<Notificacion[]>([])
const permisoNotificaciones = ref(false)
const pushActivado = ref(false)
const cuentaGitHub = ref<CuentaGitHub | null>(null)
const avisosAusencia = ref<AvisoAusencia[]>([])
const formularioAusencia = reactive({
  motivo: 'ausencia' as 'ausencia' | 'enfermedad',
  detalle: '',
  fecha_inicio: fechaLocal(new Date()),
  fecha_fin: fechaLocal(new Date()),
})
const certificadoSeleccionado = ref<File | null>(null)
const certificadoVisible = ref<{ url: string; nombre: string } | null>(null)
const contenedorChat = ref<HTMLElement | null>(null)
const modalServidor = ref(false)
const formularioServidor = reactive({ nombre: '', descripcion: '' })
const correoInvitado = ref('')
function fechaLocal(fecha: Date) {
  return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, '0')}-${String(fecha.getDate()).padStart(2, '0')}`
}

function horariosPredeterminados() {
  const inicio = new Date()
  inicio.setMinutes(0, 0, 0)
  inicio.setHours(inicio.getHours() + 1)
  const fin = new Date(inicio.getTime() + 60 * 60 * 1000)
  return {
    fecha: fechaLocal(inicio),
    hora_inicio: `${String(inicio.getHours()).padStart(2, '0')}:${String(inicio.getMinutes()).padStart(2, '0')}`,
    hora_fin: `${String(fin.getHours()).padStart(2, '0')}:${String(fin.getMinutes()).padStart(2, '0')}`,
  }
}

const horarioInicial = horariosPredeterminados()
const formularioTarea = reactive({
  titulo: '',
  descripcion: '',
  tipo: 'tarea' as 'tarea' | 'proyecto',
  ...horarioInicial,
})
const formularioAgenda = reactive({
  tarea: '',
  fecha: '',
  hora_inicio: '09:00',
  hora_fin: '10:00',
})

const fechaActual = ref(new Date())
const mesActual = computed(() => `${fechaActual.value.getFullYear()}-${String(fechaActual.value.getMonth() + 1).padStart(2, '0')}`)
const nombreMes = computed(() => fechaActual.value.toLocaleDateString('es', { month: 'long', year: 'numeric' }))
const celdasCalendario = computed(() => {
  const primero = new Date(fechaActual.value.getFullYear(), fechaActual.value.getMonth(), 1)
  const desplazamiento = (primero.getDay() + 6) % 7
  const cantidadDias = new Date(fechaActual.value.getFullYear(), fechaActual.value.getMonth() + 1, 0).getDate()
  const total = Math.ceil((desplazamiento + cantidadDias) / 7) * 7
  return Array.from({ length: total }, (_, indice) => {
    const fecha = new Date(primero.getFullYear(), primero.getMonth(), indice - desplazamiento + 1)
    return {
      clave: `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, '0')}-${String(fecha.getDate()).padStart(2, '0')}`,
      numero: fecha.getDate(),
      enMes: fecha.getMonth() === primero.getMonth(),
      hoy: fecha.toDateString() === new Date().toDateString(),
    }
  })
})
const tareasAgendables = computed(() => [...tareasPersonales.value, ...tareasTodos.value])
type NivelUrgencia = 'verde' | 'amarillo' | 'rojo' | 'neutral' | 'sin-fecha'

function nivelUrgencia(tarea: Tarea): NivelUrgencia {
  if (tarea.estado === 'completada') return 'neutral'
  if (!tarea.fecha_limite || !tarea.hora_limite) return 'sin-fecha'
  const limite = new Date(`${tarea.fecha_limite}T${tarea.hora_limite}`).getTime()
  if (!Number.isFinite(limite)) return 'sin-fecha'
  const restante = limite - ahora.value
  if (restante <= 24 * 60 * 60 * 1000) return 'rojo'
  if (restante <= 72 * 60 * 60 * 1000) return 'amarillo'
  return 'verde'
}

function detalleUrgencia(tarea: Tarea) {
  const nivel = nivelUrgencia(tarea)
  if (nivel === 'neutral') return 'Completada'
  if (nivel === 'sin-fecha') return 'Sin fecha'
  const restante = new Date(`${tarea.fecha_limite}T${tarea.hora_limite}`).getTime() - ahora.value
  if (restante <= 0) return 'Vencida'
  if (restante <= 24 * 60 * 60 * 1000) return 'Vence en menos de 24 h'
  if (restante <= 72 * 60 * 60 * 1000) return `Vence en ${Math.ceil(restante / (24 * 60 * 60 * 1000))} días`
  return `En ${Math.ceil(restante / (24 * 60 * 60 * 1000))} días`
}

const notificaciones = computed(() =>
  tareasAgendables.value
    .filter((tarea) => {
      const nivel = nivelUrgencia(tarea)
      return nivel === 'rojo' || nivel === 'amarillo'
    })
    .sort((a, b) => {
      const limiteA = new Date(`${a.fecha_limite}T${a.hora_limite}`).getTime()
      const limiteB = new Date(`${b.fecha_limite}T${b.hora_limite}`).getTime()
      return limiteA - limiteB
    }),
)

const tareaElegida = computed(() => {
  const [alcance, id] = formularioAgenda.tarea.split(':')
  return tareasAgendables.value.find((tarea) => tarea.alcance === alcance && tarea.id === Number(id))
})

let temporizadorChat: number | undefined
let temporizadorSincronizacion: number | undefined
let temporizadorUrgencia: number | undefined

async function autenticar() {
  trabajando.value = true
  aviso.value = ''
  try {
    const iniciado =
      modoAcceso.value === 'registrar'
        ? await api.registrar(formularioAcceso.nombre, formularioAcceso.correo, formularioAcceso.contrasena)
        : await api.iniciarSesion(formularioAcceso.correo, formularioAcceso.contrasena)
    usuario.value = iniciado
    await Promise.all([cargarEspacio(), cargarCuentaGitHub(), cargarNotificaciones()])
  } catch (causa) {
    mostrarError(causa)
  } finally {
    trabajando.value = false
  }
}

function abrirNotificacion(tarea: Tarea) {
  notificacionesAbiertas.value = false
  if (tarea.alcance === 'personal') {
    pantalla.value = 'personal'
    return
  }
  equipoActivoId.value = tarea.equipo_id
  tareasEquipo.value = tareasTodos.value.filter((item) => item.equipo_id === tarea.equipo_id)
  pantalla.value = 'equipo'
  vistaEquipo.value = 'tareas'
}

async function recuperarSesion() {
  if (!api.tieneSesion()) {
    cargando.value = false
    return
  }
  try {
    usuario.value = await api.usuarioActual()
    await Promise.all([cargarEspacio(), cargarCuentaGitHub(), cargarNotificaciones()])
  } catch (causa) {
    usuario.value = null
    mostrarError(causa)
  } finally {
    cargando.value = false
  }
}

async function cargarEspacio(refrescarChat = true) {
  const listas = await Promise.all([
    api.listarEquipos(),
    api.listarTareas('personal'),
    api.listarCalendario(mesActual.value),
  ])
  equipos.value = listas[0]
  tareasPersonales.value = listas[1]
  eventos.value = listas[2]
  if (!equipos.value.some((equipo) => equipo.id === equipoActivoId.value)) {
    equipoActivoId.value = equipos.value[0]?.id ?? null
  }
  await cargarTareasDeEquipos()
  if (refrescarChat) await cargarChat()
}

async function cargarTareasDeEquipos() {
  const listas = await Promise.all(
    equipos.value.map((equipo) => api.listarTareas('equipo', equipo.id)),
  )
  tareasTodos.value = listas.flat()
  if (equipoActivoId.value !== null) {
    tareasEquipo.value = tareasTodos.value.filter((tarea) => tarea.equipo_id === equipoActivoId.value)
  } else {
    tareasEquipo.value = []
  }
}

async function refrescarVistaEquipo() {
  await Promise.all([cargarTareasDeEquipos(), cargarChat()])
}

async function seleccionarEquipo(equipo: Equipo) {
  equipoActivoId.value = equipo.id
  pantalla.value = 'equipo'
  vistaEquipo.value = 'chat'
  await Promise.all([refrescarVistaEquipo(), cargarAvisosAusencia()])
}

async function cambiarPantalla(destino: Pantalla) {
  pantalla.value = destino
  if (destino === 'calendario') await cargarEventos()
  if (destino === 'github') await cargarCuentaGitHub()
  if (destino === 'equipo') await cargarChat()
}

async function cargarEventos() {
  eventos.value = await api.listarCalendario(mesActual.value)
}

async function cargarCuentaGitHub() {
  cuentaGitHub.value = await api.obtenerCuentaGitHub()
}

async function conectarGitHub() {
  try {
    const { authorize_url } = await api.iniciarConexionGitHub()
    window.location.assign(authorize_url)
  } catch (causa) {
    mostrarError(causa)
  }
}

async function desconectarGitHub() {
  try {
    await api.desconectarGitHub()
    cuentaGitHub.value = null
    anunciar('Se desconectó la cuenta de GitHub.')
  } catch (causa) {
    mostrarError(causa)
  }
}

async function cargarAvisosAusencia() {
  if (equipoActivoId.value === null) {
    avisosAusencia.value = []
    return
  }
  avisosAusencia.value = await api.listarAvisosAusencia(equipoActivoId.value)
}

function archivoComoBase64(archivo: File): Promise<string> {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader()
    lector.onload = () => {
      const resultado = lector.result
      if (typeof resultado !== 'string') {
        rechazar(new Error('No se pudo leer el certificado seleccionado.'))
        return
      }
      resolver(resultado.slice(resultado.indexOf(',') + 1))
    }
    lector.onerror = () => rechazar(new Error('No se pudo leer el certificado seleccionado.'))
    lector.readAsDataURL(archivo)
  })
}

function seleccionarCertificado(evento: Event) {
  const archivo = (evento.target as HTMLInputElement).files?.[0] ?? null
  if (archivo && archivo.size > 5_000_000) {
    certificadoSeleccionado.value = null
    mostrarError(new Error('El certificado debe pesar como máximo 5 MB.'))
    return
  }
  certificadoSeleccionado.value = archivo
}

async function crearAvisoAusencia() {
  if (equipoActivoId.value === null) return
  try {
    const archivo = certificadoSeleccionado.value
    await api.crearAvisoAusencia(equipoActivoId.value, {
      ...formularioAusencia,
      ...(archivo
        ? {
            certificado_nombre: archivo.name,
            certificado_base64: await archivoComoBase64(archivo),
          }
        : {}),
    })
    formularioAusencia.detalle = ''
    certificadoSeleccionado.value = null
    await cargarAvisosAusencia()
    anunciar('El aviso de ausencia se compartió con el equipo.')
  } catch (causa) {
    mostrarError(causa)
  }
}

async function verCertificado(aviso: AvisoAusencia) {
  try {
    if (certificadoVisible.value) URL.revokeObjectURL(certificadoVisible.value.url)
    const blob = await api.descargarCertificado(aviso.id)
    certificadoVisible.value = {
      url: URL.createObjectURL(blob),
      nombre: aviso.certificado_nombre ?? 'Certificado médico',
    }
  } catch (causa) {
    mostrarError(causa)
  }
}

function cerrarCertificado() {
  if (certificadoVisible.value) URL.revokeObjectURL(certificadoVisible.value.url)
  certificadoVisible.value = null
}

function bytesClaveVapid(clave: string) {
  const normalizada = clave.replace(/-/g, '+').replace(/_/g, '/')
  const binario = window.atob(normalizada)
  return Uint8Array.from(binario, (caracter) => caracter.charCodeAt(0))
}

async function activarNotificacionesPush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    mostrarError(new Error('Este navegador no admite notificaciones push.'))
    return
  }
  try {
    const permiso = await Notification.requestPermission()
    permisoNotificaciones.value = permiso === 'granted'
    if (permiso !== 'granted') {
      throw new Error('Debes permitir notificaciones para recibir avisos del sistema.')
    }
    const { public_key, configured } = await api.clavePublicaNotificaciones()
    if (!configured || !public_key) {
      throw new Error('El servidor todavía no está configurado para Web Push. Revisa sus claves VAPID.')
    }
    const registro = await navigator.serviceWorker.register('/service-worker.js')
    const suscripcion =
      (await registro.pushManager.getSubscription()) ??
      (await registro.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: bytesClaveVapid(public_key),
      }))
    const json = suscripcion.toJSON()
    if (!json.endpoint || !json.keys?.p256dh || !json.keys.auth) {
      throw new Error('El navegador no pudo crear una suscripción push válida.')
    }
    await api.guardarSuscripcionNotificaciones({
      endpoint: json.endpoint,
      clave_publica: json.keys.p256dh,
      clave_auth: json.keys.auth,
    })
    pushActivado.value = true
    anunciar('Las notificaciones del sistema quedaron activadas.')
    await cargarNotificaciones()
  } catch (causa) {
    mostrarError(causa)
  }
}

async function cargarNotificaciones() {
  const pendientes = await api.listarNotificaciones()
  notificacionesEstado.value = pendientes
  if (!('Notification' in window) || Notification.permission !== 'granted') return
  for (const pendiente of pendientes) {
    try {
      const registro = await navigator.serviceWorker.register('/service-worker.js')
      await registro.showNotification(pendiente.titulo, {
        body: pendiente.mensaje,
        tag: `nexo-${pendiente.id}`,
        data: { url: '/' },
      })
      await api.marcarNotificacionLeida(pendiente.id)
      notificacionesEstado.value = notificacionesEstado.value.filter(
        (item) => item.id !== pendiente.id,
      )
    } catch (causa) {
      console.error('No se pudo mostrar la notificación del sistema.', causa)
      return
    }
  }
}

function abrirNotificacionEstado(notificacion: Notificacion) {
  notificacionesAbiertas.value = false
  if (notificacion.alcance === 'equipo' && notificacion.equipo_id !== null) {
    const equipo = equipos.value.find((item) => item.id === notificacion.equipo_id)
    if (equipo) {
      equipoActivoId.value = equipo.id
      tareasEquipo.value = tareasTodos.value.filter((tarea) => tarea.equipo_id === equipo.id)
      pantalla.value = 'equipo'
      vistaEquipo.value = 'tareas'
    }
  } else {
    pantalla.value = 'personal'
  }
  void api.marcarNotificacionLeida(notificacion.id)
    .then(() => {
      notificacionesEstado.value = notificacionesEstado.value.filter(
        (item) => item.id !== notificacion.id,
      )
    })
    .catch(mostrarError)
}

function moverMes(cantidad: number) {
  fechaActual.value = new Date(fechaActual.value.getFullYear(), fechaActual.value.getMonth() + cantidad, 1)
  if (pantalla.value === 'calendario') void cargarEventos().catch(mostrarError)
}

function irAHoy() {
  fechaActual.value = new Date()
  if (pantalla.value === 'calendario') void cargarEventos().catch(mostrarError)
}

function seleccionarDia(fecha: string) {
  formularioAgenda.fecha = fecha
}

function eventosDelDia(fecha: string) {
  return eventos.value.filter((evento) => evento.fecha === fecha)
}

function nivelUrgenciaEvento(evento: EventoCalendario) {
  const tarea = tareasAgendables.value.find(
    (item) => item.id === evento.tarea_id && item.alcance === evento.alcance,
  )
  return tarea ? `urgencia-${nivelUrgencia(tarea)}` : ''
}

async function cargarChat() {
  if (equipoActivoId.value === null || pantalla.value !== 'equipo' || vistaEquipo.value !== 'chat') {
    mensajes.value = []
    return
  }
  mensajes.value = await api.listarMensajes(equipoActivoId.value)
  await nextTick()
  if (contenedorChat.value) {
    contenedorChat.value.scrollTop = contenedorChat.value.scrollHeight
  }
}

async function enviarMensaje() {
  if (!textoMensaje.value.trim() || equipoActivoId.value === null) return
  const contenido = textoMensaje.value.trim()
  textoMensaje.value = ''
  try {
    await api.enviarMensaje(equipoActivoId.value, contenido)
    await cargarChat()
  } catch (causa) {
    textoMensaje.value = contenido
    mostrarError(causa)
  }
}

async function crearServidor() {
  trabajando.value = true
  try {
    const equipo = await api.crearEquipo(formularioServidor.nombre, formularioServidor.descripcion)
    formularioServidor.nombre = ''
    formularioServidor.descripcion = ''
    modalServidor.value = false
    await cargarEspacio()
    await seleccionarEquipo(equipos.value.find((item) => item.id === equipo.id) ?? equipo)
    anunciar('Servidor creado. Tú eres su administrador.')
  } catch (causa) {
    mostrarError(causa)
  } finally {
    trabajando.value = false
  }
}

async function invitarMiembro() {
  if (!equipoActivoId.value || !correoInvitado.value.trim()) return
  try {
    await api.agregarMiembro(equipoActivoId.value, correoInvitado.value.trim())
    correoInvitado.value = ''
    await cargarEspacio()
    anunciar('La persona se agregó al servidor.')
  } catch (causa) {
    mostrarError(causa)
  }
}

async function crearTarea(alcance: 'personal' | 'equipo') {
  if (alcance === 'equipo' && equipoActivoId.value === null) return
  try {
    await api.crearTarea({
      alcance,
      ...(alcance === 'equipo' ? { equipo_id: equipoActivoId.value! } : {}),
      titulo: formularioTarea.titulo,
      descripcion: formularioTarea.descripcion,
      tipo: formularioTarea.tipo,
      fecha: formularioTarea.fecha,
      hora_inicio: formularioTarea.hora_inicio,
      hora_fin: formularioTarea.hora_fin,
    })
    formularioTarea.titulo = ''
    formularioTarea.descripcion = ''
    if (alcance === 'personal') {
      tareasPersonales.value = await api.listarTareas('personal')
    } else {
      await cargarTareasDeEquipos()
    }
    await cargarEventos()
    anunciar(`${formularioTarea.tipo === 'proyecto' ? 'Proyecto' : 'Tarea'} guardado.`)
  } catch (causa) {
    mostrarError(causa)
  }
}

async function agendarTarea() {
  if (!tareaElegida.value) return
  try {
    await api.agendarTarea({
      tarea_id: tareaElegida.value.id,
      alcance: tareaElegida.value.alcance,
      fecha: formularioAgenda.fecha,
      hora_inicio: formularioAgenda.hora_inicio,
      hora_fin: formularioAgenda.hora_fin,
    })
    await cargarEventos()
    anunciar('La tarea quedó guardada en el calendario.')
  } catch (causa) {
    mostrarError(causa)
  }
}

async function alternarEstado(tarea: Tarea) {
  const siguiente: Record<Tarea['estado'], Tarea['estado']> = {
    pendiente: 'en_progreso',
    en_progreso: 'completada',
    completada: 'pendiente',
  }
  try {
    await api.actualizarEstadoTarea(tarea, siguiente[tarea.estado])
    if (tarea.alcance === 'personal') {
      tareasPersonales.value = await api.listarTareas('personal')
    } else {
      await cargarTareasDeEquipos()
    }
  } catch (causa) {
    mostrarError(causa)
  }
}

async function salir() {
  try {
    await api.cerrarSesion()
  } catch (causa) {
    mostrarError(causa)
  } finally {
    usuario.value = null
    equipos.value = []
    tareasPersonales.value = []
    tareasTodos.value = []
    mensajes.value = []
    notificacionesEstado.value = []
  }
}

function mostrarError(causa: unknown) {
  avisoError.value = true
  aviso.value = causa instanceof Error ? causa.message : 'No se pudo completar la operación.'
}

function anunciar(texto: string) {
  avisoError.value = false
  aviso.value = texto
  window.setTimeout(() => {
    if (aviso.value === texto) aviso.value = ''
  }, 4000)
}

function horaLegible(fecha: string) {
  return new Date(fecha).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })
}

function tareaKey(tarea: Tarea) {
  return `${tarea.alcance}:${tarea.id}`
}

watch([pantalla, vistaEquipo, equipoActivoId], () => {
  if (temporizadorChat !== undefined) window.clearInterval(temporizadorChat)
  if (pantalla.value === 'equipo' && vistaEquipo.value === 'chat' && equipoActivoId.value !== null) {
    void cargarChat().catch(mostrarError)
    temporizadorChat = window.setInterval(() => {
      void cargarChat().catch(mostrarError)
    }, 3000)
  }
})

function alExpirarSesion() {
  usuario.value = null
}

function sincronizarCambiosMySQL() {
  if (temporizadorSincronizacion !== undefined) {
    window.clearInterval(temporizadorSincronizacion)
    temporizadorSincronizacion = undefined
  }
  if (!usuario.value) return
  temporizadorSincronizacion = window.setInterval(() => {
    void Promise.all([cargarEspacio(false), cargarNotificaciones()]).catch(mostrarError)
  }, 5000)
}

onMounted(() => {
  window.addEventListener('auth-expirada', alExpirarSesion)
  temporizadorUrgencia = window.setInterval(() => {
    ahora.value = Date.now()
  }, 60_000)
  permisoNotificaciones.value =
    'Notification' in window && Notification.permission === 'granted'
  const estadoGitHub = new URLSearchParams(window.location.search).get('github')
  if (estadoGitHub) {
    window.history.replaceState({}, '', window.location.pathname)
    void recuperarSesion().then(() => {
      if (estadoGitHub === 'conectado') anunciar('Tu cuenta de GitHub quedó conectada.')
      else mostrarError(new Error('No se pudo conectar GitHub. Revisa la configuración y vuelve a intentarlo.'))
    })
    return
  }
  void recuperarSesion()
})

onBeforeUnmount(() => {
  window.removeEventListener('auth-expirada', alExpirarSesion)
  if (temporizadorChat !== undefined) window.clearInterval(temporizadorChat)
  if (temporizadorSincronizacion !== undefined) window.clearInterval(temporizadorSincronizacion)
  if (temporizadorUrgencia !== undefined) window.clearInterval(temporizadorUrgencia)
  cerrarCertificado()
})

watch(usuario, sincronizarCambiosMySQL)
</script>

<template>
  <main v-if="cargando" class="loading-screen">
    <div class="brand-mark">N</div>
    <span>Preparando tu espacio…</span>
  </main>

  <main v-else-if="!usuario" class="auth-page">
    <section class="auth-decoration">
      <div class="auth-brand"><span class="brand-mark">N</span> NEXO</div>
      <div class="auth-copy">
        <span class="auth-kicker">TRABAJA EN EQUIPO. A TU MANERA.</span>
        <h1>Todo tu equipo,<br>en un mismo lugar.</h1>
        <p>Conversaciones, tareas y planes para tus equipos y para ti.</p>
      </div>
      <span class="auth-footnote">Un espacio para hacer que las cosas pasen.</span>
    </section>

    <section class="auth-form-wrap">
      <form class="auth-form" @submit.prevent="autenticar">
        <span class="auth-kicker">{{ modoAcceso === 'entrar' ? 'QUÉ BUENO VERTE' : 'EMPIEZA POR AQUÍ' }}</span>
        <h2>{{ modoAcceso === 'entrar' ? 'Inicia sesión' : 'Crea tu cuenta' }}</h2>
        <p class="auth-hint">
          {{ modoAcceso === 'entrar' ? 'Entra a tu espacio y sigue donde lo dejaste.' : 'Tu cuenta tendrá su propio espacio y calendario.' }}
        </p>
        <label v-if="modoAcceso === 'registrar'" class="field">
          Nombre
          <input v-model="formularioAcceso.nombre" required maxlength="120" autocomplete="name" placeholder="Tu nombre">
        </label>
        <label class="field">
          Correo electrónico
          <input v-model="formularioAcceso.correo" type="email" required maxlength="254" autocomplete="email" placeholder="nombre@correo.com">
        </label>
        <label class="field">
          Contraseña
          <input v-model="formularioAcceso.contrasena" type="password" required :minlength="modoAcceso === 'registrar' ? 8 : 1" autocomplete="current-password" placeholder="Tu contraseña">
        </label>
        <p v-if="aviso" class="feedback" :class="{ 'feedback-error': avisoError }" role="alert">{{ aviso }}</p>
        <button class="button button-accent" type="submit" :disabled="trabajando">
          {{ trabajando ? 'Un momento…' : modoAcceso === 'entrar' ? 'Entrar a mi espacio' : 'Registrarme' }}
        </button>
        <p class="switch-auth">
          {{ modoAcceso === 'entrar' ? '¿Todavía no tienes cuenta?' : '¿Ya tienes una cuenta?' }}
          <button type="button" @click="modoAcceso = modoAcceso === 'entrar' ? 'registrar' : 'entrar'; aviso = ''">
            {{ modoAcceso === 'entrar' ? 'Regístrate' : 'Inicia sesión' }}
          </button>
        </p>
      </form>
    </section>
  </main>

  <main v-else class="app-shell">
    <aside class="server-rail" aria-label="Espacios">
      <button class="rail-logo" title="Mi espacio personal" @click="cambiarPantalla('personal')">N</button>
      <span class="rail-divider"></span>
      <button
        v-for="equipo in equipos"
        :key="equipo.id"
        class="server-icon"
        :class="{ selected: equipoActivoId === equipo.id && pantalla === 'equipo' }"
        :title="equipo.nombre"
        @click="seleccionarEquipo(equipo)"
      >
        {{ equipo.nombre.slice(0, 2).toUpperCase() }}
      </button>
      <button class="server-create" title="Crear servidor" @click="modalServidor = true">+</button>
      <div class="rail-spacer"></div>
      <button class="avatar avatar-rail" :title="usuario.nombre" @click="salir">{{ usuario.nombre.slice(0, 1).toUpperCase() }}</button>
    </aside>

    <aside class="channel-sidebar">
      <div class="side-title"><span>MI ESPACIO</span><button class="icon-button" title="Crear servidor" @click="modalServidor = true">＋</button></div>
      <button class="side-link" :class="{ active: pantalla === 'personal' }" @click="cambiarPantalla('personal')">
        <span class="side-link-icon">⌂</span><span>Mis tareas</span>
      </button>
      <button class="side-link" :class="{ active: pantalla === 'calendario' }" @click="cambiarPantalla('calendario')">
        <span class="side-link-icon">▦</span><span>Calendario</span>
      </button>
      <button class="side-link" :class="{ active: pantalla === 'github' }" @click="cambiarPantalla('github')">
        <span class="side-link-icon">⌘</span><span>GitHub</span>
      </button>

      <div class="side-title team-title"><span>TUS SERVIDORES</span><button class="icon-button" title="Crear servidor" @click="modalServidor = true">＋</button></div>
      <div v-if="equipos.length" class="team-list">
        <button
          v-for="equipo in equipos"
          :key="equipo.id"
          class="team-link"
          :class="{ active: equipoActivoId === equipo.id && pantalla === 'equipo' }"
          @click="seleccionarEquipo(equipo)"
        >
          <span class="team-hash">#</span><span>{{ equipo.nombre }}</span><small>{{ equipo.cantidad_miembros }}</small>
        </button>
      </div>
      <div v-else class="sidebar-empty">Crea un servidor e invita a tu equipo para empezar.</div>
      <button class="create-server-link" @click="modalServidor = true"><span>＋</span> Crear un servidor</button>

      <div class="profile-card">
        <button class="avatar">{{ usuario.nombre.slice(0, 1).toUpperCase() }}</button>
        <span class="profile-copy"><strong>{{ usuario.nombre }}</strong><small>Mi cuenta</small></span>
        <button class="icon-button logout-button" title="Cerrar sesión" @click="salir">↪</button>
      </div>
    </aside>

    <section class="main-panel">
      <header class="topbar">
        <div class="topbar-heading">
          <span v-if="pantalla === 'equipo'" class="top-hash">#</span>
          <span v-else class="top-icon">{{ pantalla === 'calendario' ? '▦' : '⌂' }}</span>
          <div>
            <h1>{{ pantalla === 'equipo' ? equipoActivo?.nombre : pantalla === 'calendario' ? 'Calendario' : pantalla === 'github' ? 'GitHub' : 'Mis tareas' }}</h1>
            <p>{{ pantalla === 'equipo' ? equipoActivo?.descripcion || 'Espacio de conversación del servidor' : pantalla === 'calendario' ? 'Tu agenda personal y la de tus equipos' : pantalla === 'github' ? 'Conecta tu cuenta de GitHub' : 'Tareas y proyectos solo para ti' }}</p>
          </div>
        </div>
        <div v-if="pantalla === 'equipo'" class="topbar-actions">
          <button class="tab-button" :class="{ chosen: vistaEquipo === 'chat' }" @click="vistaEquipo = 'chat'"># Chat</button>
          <button class="tab-button" :class="{ chosen: vistaEquipo === 'tareas' }" @click="vistaEquipo = 'tareas'">▤ Tareas</button>
          <button class="tab-button" :class="{ chosen: vistaEquipo === 'ausencias' }" @click="vistaEquipo = 'ausencias'; void cargarAvisosAusencia().catch(mostrarError)">Avisos</button>
          <form v-if="equipoActivo?.rol === 'administrador'" class="invite-form" @submit.prevent="invitarMiembro">
            <input v-model="correoInvitado" type="email" required placeholder="Correo para invitar" aria-label="Correo de la persona a invitar">
            <button class="button button-small" type="submit">Invitar</button>
          </form>
        </div>
        <div v-else class="user-menu"><span>{{ usuario.correo }}</span><button class="avatar">{{ usuario.nombre.slice(0, 1).toUpperCase() }}</button></div>
        <div class="notification-anchor">
          <button class="notification-button" :aria-expanded="notificacionesAbiertas" aria-label="Abrir notificaciones" @click="notificacionesAbiertas = !notificacionesAbiertas">
            🔔<span v-if="notificaciones.length + notificacionesEstado.length" class="notification-count">{{ notificaciones.length + notificacionesEstado.length }}</span>
          </button>
          <div v-if="notificacionesAbiertas" class="notification-panel" aria-label="Notificaciones de tareas">
            <strong>Próximos vencimientos</strong>
            <button v-for="tarea in notificaciones.slice(0, 8)" :key="tareaKey(tarea)" class="notification-item" @click="abrirNotificacion(tarea)">
              <span class="notification-dot" :class="`urgencia-${nivelUrgencia(tarea)}`"></span>
              <span><b>{{ tarea.titulo }}</b><small>{{ tarea.alcance === 'personal' ? 'Personal' : tarea.equipo_nombre }} · {{ detalleUrgencia(tarea) }}</small></span>
            </button>
            <button v-for="notificacion in notificacionesEstado" :key="`estado-${notificacion.id}`" class="notification-item" @click="abrirNotificacionEstado(notificacion)">
              <span class="notification-dot notification-dot-state"></span>
              <span><b>{{ notificacion.titulo }}</b><small>{{ notificacion.mensaje }}</small></span>
            </button>
            <button v-if="!permisoNotificaciones || !pushActivado" class="button button-small" @click="activarNotificacionesPush">Activar avisos en este dispositivo</button>
            <p v-if="!notificaciones.length && !notificacionesEstado.length" class="notification-empty">No hay avisos pendientes.</p>
          </div>
        </div>
      </header>

      <div v-if="aviso" class="toast" :class="{ 'toast-error': avisoError }" role="status">{{ aviso }}</div>

      <section v-if="pantalla === 'equipo' && vistaEquipo === 'chat' && equipoActivo" class="chat-panel">
        <div class="chat-history" ref="contenedorChat">
          <div v-if="!mensajes.length" class="chat-welcome">
            <span class="welcome-hash">#</span>
            <h2>Bienvenido a {{ equipoActivo.nombre }}</h2>
            <p>Este es el comienzo del chat de tu servidor. Escribe el primer mensaje.</p>
          </div>
          <article v-for="mensaje in mensajes" :key="mensaje.id" class="message">
            <div class="avatar message-avatar">{{ mensaje.autor.slice(0, 1).toUpperCase() }}</div>
            <div class="message-body">
              <div class="message-meta"><strong>{{ mensaje.autor }}</strong><time>{{ horaLegible(mensaje.creado_en) }}</time></div>
              <p>{{ mensaje.contenido }}</p>
            </div>
          </article>
          <p v-if="mensajes.length >= 50" class="history-note">Mostrando los 50 mensajes más recientes. Los anteriores siguen guardados.</p>
        </div>
        <form class="chat-composer" @submit.prevent="enviarMensaje">
          <span class="composer-plus">＋</span>
          <input v-model="textoMensaje" maxlength="4000" placeholder="Escribe en el chat del servidor…" aria-label="Mensaje" autocomplete="off">
          <button class="send-button" type="submit" :disabled="!textoMensaje.trim()" aria-label="Enviar mensaje">➤</button>
        </form>
      </section>

      <section v-else-if="pantalla === 'equipo' && vistaEquipo === 'tareas'" class="content-scroll">
        <section class="task-layout">
          <form class="task-create-card" @submit.prevent="crearTarea('equipo')">
            <span class="section-kicker">TRABAJO EN EQUIPO</span>
            <h2>Crear tarea o proyecto</h2>
            <label class="field">Título<input v-model="formularioTarea.titulo" required maxlength="200" placeholder="¿Qué hay que hacer?"></label>
            <label class="field">Tipo<select v-model="formularioTarea.tipo"><option value="tarea">Tarea</option><option value="proyecto">Proyecto</option></select></label>
            <label class="field">Descripción<textarea v-model="formularioTarea.descripcion" rows="3" maxlength="5000" placeholder="Añade detalles…"></textarea></label>
            <label class="field">Fecha<input v-model="formularioTarea.fecha" type="date" required></label>
            <label class="field">Desde<input v-model="formularioTarea.hora_inicio" type="time" required></label>
            <label class="field">Hora límite<input v-model="formularioTarea.hora_fin" type="time" required></label>
            <button class="button button-accent" type="submit">Crear en {{ equipoActivo?.nombre }}</button>
          </form>
          <div class="task-list-area">
            <div class="section-title-row"><div><span class="section-kicker">DE ESTE SERVIDOR</span><h2>Tareas del equipo</h2></div><span class="count-pill">{{ tareasEquipo.length }}</span></div>
            <article v-for="tarea in tareasEquipo" :key="tarea.id" class="task-row">
              <button class="task-check" :class="{ checked: tarea.estado === 'completada' }" :aria-label="`Cambiar estado de ${tarea.titulo}`" @click="alternarEstado(tarea)">{{ tarea.estado === 'completada' ? '✓' : '' }}</button>
              <div class="task-row-body"><strong :class="{ struck: tarea.estado === 'completada' }">{{ tarea.titulo }}</strong><span>{{ tarea.tipo }}<template v-if="tarea.descripcion"> · {{ tarea.descripcion }}</template></span><span class="task-urgency" :class="`urgencia-${nivelUrgencia(tarea)}`">{{ detalleUrgencia(tarea) }}</span></div>
              <span class="task-state">{{ tarea.estado.replace('_', ' ') }}</span>
            </article>
            <div v-if="!tareasEquipo.length" class="empty-card">Todavía no hay tareas. Crea la primera para este equipo.</div>
          </div>
        </section>
      </section>

      <section v-else-if="pantalla === 'equipo' && vistaEquipo === 'ausencias'" class="content-scroll absence-view">
        <div class="personal-heading">
          <div><span class="section-kicker">AVISOS DEL SERVIDOR</span><h2>Ausencias del equipo</h2><p>Los avisos y certificados solo los ven las personas miembros de este servidor.</p></div>
          <span class="count-pill">{{ avisosAusencia.length }} avisos</span>
        </div>
        <form class="absence-create" @submit.prevent="crearAvisoAusencia">
          <label class="field">Tipo de aviso<select v-model="formularioAusencia.motivo"><option value="ausencia">Voy a faltar</option><option value="enfermedad">Estoy enfermo/a</option></select></label>
          <label class="field">Desde<input v-model="formularioAusencia.fecha_inicio" type="date" required></label>
          <label class="field">Hasta<input v-model="formularioAusencia.fecha_fin" type="date" required></label>
          <label class="field absence-detail">Aviso para el equipo<textarea v-model="formularioAusencia.detalle" maxlength="1000" rows="3" placeholder="Puedes compartir un mensaje breve (opcional)"></textarea></label>
          <label class="field absence-file">Certificado o imagen (opcional)<input type="file" accept="image/png,image/jpeg,image/webp" @change="seleccionarCertificado"><small>PNG, JPG o WEBP · máximo 5 MB. Será visible para todo el servidor.</small></label>
          <button class="button button-accent" type="submit">Avisar al equipo</button>
        </form>
        <div class="absence-list">
          <article v-for="avisoEquipo in avisosAusencia" :key="avisoEquipo.id" class="absence-card">
            <div class="absence-card-heading"><div><strong>{{ avisoEquipo.usuario_nombre }}</strong><span>{{ avisoEquipo.motivo === 'enfermedad' ? 'Avisó que está enfermo/a' : 'Avisó que faltará' }}</span></div><time>{{ avisoEquipo.fecha_inicio }} — {{ avisoEquipo.fecha_fin }}</time></div>
            <p v-if="avisoEquipo.detalle">{{ avisoEquipo.detalle }}</p>
            <button v-if="avisoEquipo.tiene_certificado" class="button button-small" @click="void verCertificado(avisoEquipo)">Ver {{ avisoEquipo.certificado_nombre || 'certificado' }}</button>
          </article>
          <div v-if="!avisosAusencia.length" class="empty-card">Todavía no hay avisos de ausencia en este servidor.</div>
        </div>
      </section>

      <section v-else-if="pantalla === 'github'" class="content-scroll github-view">
        <article class="github-card">
          <span class="section-kicker">TU PERFIL DE DESARROLLO</span>
          <h2>Conecta GitHub</h2>
          <p>Vincula tu cuenta de GitHub de forma segura mediante OAuth. Nexo solo consulta tu perfil público y no guarda el token de acceso.</p>
          <div v-if="cuentaGitHub" class="github-profile">
            <img :src="cuentaGitHub.avatar_url" alt="" class="github-avatar">
            <div><strong>@{{ cuentaGitHub.github_login }}</strong><a :href="cuentaGitHub.profile_url" target="_blank" rel="noopener noreferrer">Abrir perfil de GitHub ↗</a></div>
            <button class="button button-small" @click="desconectarGitHub">Desconectar</button>
          </div>
          <button v-else class="button button-accent" @click="conectarGitHub">Conectar con GitHub</button>
        </article>
      </section>

      <section v-else-if="pantalla === 'personal'" class="content-scroll personal-view">
        <div class="personal-heading"><div><span class="section-kicker">SOLO PARA TI</span><h2>Tu lista de pendientes</h2><p>Estas tareas y proyectos son privados de tu cuenta.</p></div><span class="count-pill">{{ tareasPersonales.length }} en total</span></div>
        <form class="personal-create" @submit.prevent="crearTarea('personal')">
          <label class="field">Nueva tarea o proyecto<input v-model="formularioTarea.titulo" required maxlength="200" placeholder="Anota algo que quieras hacer…"></label>
          <label class="field type-field">Tipo<select v-model="formularioTarea.tipo"><option value="tarea">Tarea</option><option value="proyecto">Proyecto</option></select></label>
          <label class="field">Fecha<input v-model="formularioTarea.fecha" type="date" required></label>
          <label class="field">Desde<input v-model="formularioTarea.hora_inicio" type="time" required></label>
          <label class="field">Hora límite<input v-model="formularioTarea.hora_fin" type="time" required></label>
          <button class="button button-accent" type="submit">＋ Añadir</button>
        </form>
        <label class="field personal-description">Descripción<textarea v-model="formularioTarea.descripcion" maxlength="5000" rows="2" placeholder="Detalles opcionales para esta tarea"></textarea></label>
        <div class="personal-tasks">
          <article v-for="tarea in tareasPersonales" :key="tarea.id" class="task-row">
            <button class="task-check" :class="{ checked: tarea.estado === 'completada' }" :aria-label="`Cambiar estado de ${tarea.titulo}`" @click="alternarEstado(tarea)">{{ tarea.estado === 'completada' ? '✓' : '' }}</button>
            <div class="task-row-body"><strong :class="{ struck: tarea.estado === 'completada' }">{{ tarea.titulo }}</strong><span>{{ tarea.tipo }}<template v-if="tarea.descripcion"> · {{ tarea.descripcion }}</template></span><span class="task-urgency" :class="`urgencia-${nivelUrgencia(tarea)}`">{{ detalleUrgencia(tarea) }}</span></div>
            <span class="task-state">{{ tarea.estado.replace('_', ' ') }}</span>
          </article>
          <div v-if="!tareasPersonales.length" class="empty-card">Todavía no tienes tareas personales. Escribe una arriba para empezar.</div>
        </div>
      </section>

      <section v-else class="content-scroll calendar-view">
        <div class="calendar-toolbar">
          <div><span class="section-kicker">PLANIFICA A TU RITMO</span><h2>{{ nombreMes }}</h2></div>
          <div class="month-controls"><button class="month-button" aria-label="Mes anterior" @click="moverMes(-1)">‹</button><button class="today-button" @click="irAHoy">Hoy</button><button class="month-button" aria-label="Mes siguiente" @click="moverMes(1)">›</button></div>
        </div>
        <div class="calendar-grid">
          <div v-for="dia in ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']" :key="dia" class="weekday">{{ dia }}</div>
          <button
            v-for="celda in celdasCalendario"
            :key="celda.clave"
            class="day-cell"
            :class="{ 'outside-month': !celda.enMes, 'today-cell': celda.hoy, 'selected-day': formularioAgenda.fecha === celda.clave }"
            @click="seleccionarDia(celda.clave)"
          >
            <span class="day-number">{{ celda.numero }}</span>
            <span
              v-for="evento in eventosDelDia(celda.clave).slice(0, 3)"
              :key="`${evento.alcance}-${evento.id}`"
              class="calendar-event"
              :class="[evento.alcance, nivelUrgenciaEvento(evento)]"
              :title="`${evento.hora_inicio} · ${evento.tarea_titulo}`"
            >{{ evento.hora_inicio }} {{ evento.tarea_titulo }}</span>
            <span v-if="eventosDelDia(celda.clave).length > 3" class="more-events">+{{ eventosDelDia(celda.clave).length - 3 }} más</span>
          </button>
        </div>
        <section class="agenda-card">
          <div class="section-title-row"><div><span class="section-kicker">AGREGAR AL CALENDARIO</span><h3>{{ formularioAgenda.fecha || 'Elige un día' }}</h3></div></div>
          <form class="agenda-form" @submit.prevent="agendarTarea">
            <label class="field">Tarea o proyecto<select v-model="formularioAgenda.tarea" required>
              <option disabled value="">Selecciona una tarea</option>
              <option v-for="tarea in tareasAgendables" :key="tareaKey(tarea)" :value="tareaKey(tarea)">{{ tarea.alcance === 'personal' ? 'Personal' : tarea.equipo_nombre }} · {{ tarea.titulo }}</option>
            </select></label>
            <label class="field">Día<input v-model="formularioAgenda.fecha" type="date" required></label>
            <label class="field">Desde<input v-model="formularioAgenda.hora_inicio" type="time" required></label>
            <label class="field">Hasta<input v-model="formularioAgenda.hora_fin" type="time" required></label>
            <button class="button button-accent" type="submit" :disabled="!tareaElegida">Guardar en calendario</button>
          </form>
          <p class="calendar-legend"><span class="legend-dot personal"></span> Personal <span class="legend-dot team"></span> Equipos</p>
          <p v-if="!tareasAgendables.length" class="empty-calendar-hint">Crea una tarea personal o de equipo para poder agendarla.</p>
        </section>
      </section>
    </section>

    <div v-if="certificadoVisible" class="modal-backdrop" @click.self="cerrarCertificado">
      <section class="certificate-modal" role="dialog" aria-modal="true" :aria-label="certificadoVisible.nombre">
        <button class="modal-close" aria-label="Cerrar certificado" @click="cerrarCertificado">×</button>
        <h2>{{ certificadoVisible.nombre }}</h2>
        <img :src="certificadoVisible.url" :alt="certificadoVisible.nombre">
      </section>
    </div>

    <div v-if="modalServidor" class="modal-backdrop" @click.self="modalServidor = false">
      <form class="modal-card" @submit.prevent="crearServidor">
        <button type="button" class="modal-close" aria-label="Cerrar" @click="modalServidor = false">×</button>
        <span class="section-kicker">UN ESPACIO PARA EL EQUIPO</span>
        <h2>Crea tu servidor</h2>
        <p>Invita a otras personas registradas y compartan chat, tareas y calendario.</p>
        <label class="field">Nombre del servidor<input v-model="formularioServidor.nombre" required maxlength="120" placeholder="Ej. Equipo de diseño"></label>
        <label class="field">Descripción<textarea v-model="formularioServidor.descripcion" maxlength="2000" rows="3" placeholder="¿En qué trabajarán?"></textarea></label>
        <button class="button button-accent" type="submit" :disabled="trabajando">{{ trabajando ? 'Creando…' : 'Crear servidor' }}</button>
      </form>
    </div>
  </main>
</template>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(body) { margin: 0; min-width: 320px; background: #f6f7f9; color: #23252b; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
:global(button), :global(input), :global(select), :global(textarea) { font: inherit; }
.loading-screen { min-height: 100vh; display: grid; place-content: center; justify-items: center; gap: 14px; color: #89909a; background: #f8f9fb; }
.brand-mark { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 14px; color: white; background: #6b67db; font-size: 1.25rem; font-weight: 800; }
.auth-page { min-height: 100vh; display: grid; grid-template-columns: minmax(320px, 1.05fr) minmax(400px, .95fr); background: #fff; }
.auth-decoration { display: flex; flex-direction: column; justify-content: space-between; min-height: 100vh; padding: 44px clamp(32px, 7vw, 100px); color: white; background: radial-gradient(ellipse at 78% 22%, #5752b0 0, transparent 38%), linear-gradient(150deg, #29274e, #363264 58%, #45408a); }
.auth-brand { display: flex; align-items: center; gap: 12px; font-size: .86rem; font-weight: 800; letter-spacing: .2em; }
.auth-brand .brand-mark { width: 36px; height: 36px; border-radius: 12px; color: #333064; background: #f3c879; }
.auth-copy { max-width: 510px; padding: 40px 0; }
.auth-kicker, .section-kicker { color: #8d8aa2; font-size: .68rem; font-weight: 800; letter-spacing: .15em; }
.auth-decoration .auth-kicker { color: #d2c9ff; }
.auth-copy h1 { margin: 18px 0; font-size: clamp(2.8rem, 5vw, 4.6rem); line-height: 1.06; letter-spacing: -.06em; }
.auth-copy p { max-width: 380px; color: #d0cee3; font-size: 1.05rem; line-height: 1.7; }
.auth-footnote { color: #c1bddc; font-size: .78rem; }
.auth-form-wrap { display: grid; place-items: center; padding: 44px 28px; }
.auth-form { display: grid; width: min(100%, 390px); gap: 17px; }
.auth-form h2 { margin: 2px 0 -10px; color: #28263f; font-size: 2rem; letter-spacing: -.04em; }
.auth-hint { margin: 0 0 7px; color: #81818e; font-size: .92rem; line-height: 1.5; }
.field { display: grid; min-width: 0; gap: 7px; color: #555664; font-size: .78rem; font-weight: 700; }
.field input, .field select, .field textarea { width: 100%; min-width: 0; border: 1px solid #e0e1e8; border-radius: 9px; outline: none; padding: 11px 12px; color: #252637; background: #fff; font-size: .86rem; font-weight: 400; }
.field textarea { resize: vertical; }
.field input:focus, .field select:focus, .field textarea:focus { border-color: #807be4; box-shadow: 0 0 0 3px #eeedff; }
.button { border: 0; border-radius: 9px; padding: 11px 15px; color: #fff; background: #6c68d9; font-size: .84rem; font-weight: 750; cursor: pointer; transition: background .16s, transform .16s; }
.button:hover:not(:disabled) { transform: translateY(-1px); background: #5b56c5; }
.button:disabled { cursor: not-allowed; opacity: .56; }
.button-accent { padding: 13px 16px; }
.switch-auth { margin: 3px 0 0; color: #777987; font-size: .83rem; text-align: center; }
.switch-auth button { border: 0; padding: 0 0 0 4px; color: #5e59c3; background: none; font-weight: 750; cursor: pointer; }
.feedback { margin: 0; color: #3e805d; font-size: .83rem; }
.feedback-error { color: #b44c58; }
.app-shell { display: grid; grid-template-columns: 70px 244px minmax(0, 1fr); width: 100%; height: 100vh; overflow: hidden; background: #fff; }
.server-rail { display: flex; flex-direction: column; align-items: center; gap: 11px; padding: 16px 0; background: #eeeff4; }
.rail-logo, .server-icon, .server-create, .avatar { display: grid; flex-shrink: 0; place-items: center; border: 0; cursor: pointer; }
.rail-logo, .server-icon, .server-create { width: 44px; height: 44px; border-radius: 15px; font-weight: 800; transition: border-radius .16s, background .16s; }
.rail-logo { color: #fff; background: #6b67d6; font-size: 1.15rem; }
.server-icon { color: #575a66; background: #fff; font-size: .77rem; }
.server-icon:hover, .server-icon.selected { border-radius: 13px; color: #fff; background: #7772df; }
.rail-divider { width: 30px; height: 2px; border-radius: 2px; background: #d9dae2; }
.server-create { color: #4b9a73; background: #fff; font-size: 1.5rem; }
.server-create:hover { border-radius: 13px; color: #fff; background: #4caa79; }
.rail-spacer { flex: 1; }
.avatar { width: 34px; height: 34px; border-radius: 50%; color: #48436f; background: #e7e4ff; font-weight: 800; }
.avatar-rail { width: 42px; height: 42px; }
.channel-sidebar { position: relative; display: flex; min-width: 0; flex-direction: column; padding: 23px 12px 12px; background: #f7f7fa; border-right: 1px solid #e9e9ee; }
.side-title { display: flex; align-items: center; justify-content: space-between; padding: 0 7px; color: #9697a2; font-size: .65rem; font-weight: 850; letter-spacing: .12em; }
.icon-button { display: grid; width: 28px; height: 28px; place-items: center; border: 0; border-radius: 7px; color: #848591; background: transparent; font-size: 1.05rem; cursor: pointer; }
.icon-button:hover { color: #514db2; background: #ecebfa; }
.side-link { display: flex; align-items: center; gap: 11px; width: 100%; margin-top: 8px; border: 0; border-radius: 8px; padding: 10px 9px; color: #686a76; background: transparent; font-size: .84rem; text-align: left; cursor: pointer; }
.side-link:hover, .side-link.active { color: #514db2; background: #eeedfc; }
.side-link-icon { width: 19px; color: #8c8e9b; font-size: 1.1rem; text-align: center; }
.side-link.active .side-link-icon { color: #625dcc; }
.team-title { margin-top: 28px; }
.team-list { display: grid; gap: 3px; margin-top: 9px; }
.team-link { display: flex; align-items: center; gap: 8px; width: 100%; border: 0; border-radius: 7px; padding: 9px 8px; color: #757682; background: transparent; font-size: .82rem; text-align: left; cursor: pointer; }
.team-link:hover, .team-link.active { color: #514db2; background: #eeedfc; }
.team-link span:nth-child(2) { overflow: hidden; flex: 1; text-overflow: ellipsis; white-space: nowrap; }
.team-link small { color: #a0a1ab; font-size: .68rem; }
.team-hash { color: #9b9ca7; font-size: 1.15rem; }
.sidebar-empty { margin: 14px 8px; color: #9697a2; font-size: .76rem; line-height: 1.55; }
.create-server-link { display: flex; align-items: center; gap: 8px; margin-top: 8px; border: 0; border-radius: 7px; padding: 9px 8px; color: #6864c7; background: transparent; font-size: .8rem; text-align: left; cursor: pointer; }
.create-server-link:hover { background: #eeedfc; }
.create-server-link span { font-size: 1.1rem; }
.profile-card { display: flex; align-items: center; gap: 9px; margin-top: auto; border-top: 1px solid #e8e8ed; padding: 15px 3px 1px; }
.profile-copy { display: grid; flex: 1; min-width: 0; gap: 2px; }
.profile-copy strong { overflow: hidden; color: #41424e; font-size: .77rem; text-overflow: ellipsis; white-space: nowrap; }
.profile-copy small { color: #9697a2; font-size: .68rem; }
.logout-button { font-size: 1.2rem; }
.main-panel { display: flex; min-width: 0; flex-direction: column; background: #fff; }
.topbar { position: relative; display: flex; min-height: 78px; align-items: center; justify-content: space-between; gap: 14px; border-bottom: 1px solid #e9e9ee; padding: 12px 25px; }
.topbar-heading { display: flex; min-width: 0; align-items: center; gap: 12px; }
.top-hash, .top-icon { color: #9394a0; font-size: 1.45rem; }
.topbar-heading h1 { overflow: hidden; margin: 0; color: #343541; font-size: .99rem; text-overflow: ellipsis; white-space: nowrap; }
.topbar-heading p { overflow: hidden; margin: 4px 0 0; color: #9697a2; font-size: .72rem; text-overflow: ellipsis; white-space: nowrap; }
.topbar-actions, .user-menu { display: flex; flex-shrink: 0; align-items: center; gap: 8px; }
.tab-button { border: 0; border-radius: 7px; padding: 8px 10px; color: #777986; background: transparent; font-size: .76rem; cursor: pointer; }
.tab-button.chosen { color: #5651b8; background: #efeffb; font-weight: 750; }
.invite-form { display: flex; gap: 6px; margin-left: 7px; }
.invite-form input { width: 170px; border: 1px solid #e4e4e9; border-radius: 7px; outline: 0; padding: 8px; font-size: .73rem; }
.button-small { padding: 8px 10px; font-size: .72rem; }
.user-menu { color: #858691; font-size: .76rem; }
.notification-anchor { position: relative; flex-shrink: 0; }
.notification-button { position: relative; display: grid; width: 36px; height: 36px; place-items: center; border: 1px solid #e7e7ed; border-radius: 10px; color: #6662c5; background: #fff; font-size: 1.1rem; cursor: pointer; }
.notification-button:hover { background: #f6f5ff; }
.notification-count { position: absolute; top: -6px; right: -6px; display: grid; min-width: 17px; height: 17px; place-items: center; border: 2px solid #fff; border-radius: 999px; padding: 0 3px; color: #fff; background: #d8565e; font-size: .58rem; font-weight: 800; }
.notification-panel { position: absolute; z-index: 8; top: calc(100% + 12px); right: 0; display: grid; width: min(340px, calc(100vw - 32px)); gap: 7px; border: 1px solid #e7e7ed; border-radius: 12px; padding: 14px; background: #fff; box-shadow: 0 12px 35px #22223a20; }
.notification-panel > strong { padding: 2px 4px 7px; color: #42434f; font-size: .82rem; }
.notification-item { display: flex; align-items: flex-start; gap: 9px; border: 0; border-radius: 8px; padding: 9px 7px; background: #fafafd; text-align: left; cursor: pointer; }
.notification-item:hover { background: #f1f0fc; }
.notification-item > span:last-child { display: grid; min-width: 0; gap: 4px; }
.notification-item b { overflow: hidden; color: #4b4c57; font-size: .75rem; text-overflow: ellipsis; white-space: nowrap; }
.notification-item small { color: #888995; font-size: .66rem; }
.notification-empty { margin: 0; padding: 12px 5px; color: #898a95; font-size: .75rem; }
.toast { position: fixed; z-index: 5; top: 90px; right: 24px; max-width: min(420px, calc(100vw - 32px)); border: 1px solid #d9eadf; border-radius: 9px; padding: 11px 14px; color: #397553; background: #f1faf4; box-shadow: 0 8px 24px #26263512; font-size: .8rem; }
.toast-error { border-color: #f2d9d8; color: #a34247; background: #fff5f4; }
.chat-panel { display: flex; min-height: 0; flex: 1; flex-direction: column; padding: 0 26px 21px; }
.chat-history { min-height: 0; flex: 1; overflow: auto; padding: 22px 4px 10px; }
.chat-welcome { margin: auto 0 35px; border-bottom: 1px solid #ededf0; padding: 15px 0 22px; }
.welcome-hash { display: grid; width: 53px; height: 53px; place-items: center; border-radius: 16px; color: #fff; background: #7772dc; font-size: 2rem; font-weight: 800; }
.chat-welcome h2 { margin: 18px 0 6px; color: #343541; font-size: 1.55rem; letter-spacing: -.035em; }
.chat-welcome p { margin: 0; color: #92939e; font-size: .82rem; }
.message { display: flex; gap: 12px; margin: 0 -4px; border-radius: 8px; padding: 10px 4px; }
.message:hover { background: #f8f8fa; }
.message-avatar { width: 36px; height: 36px; font-size: .82rem; }
.message-body { min-width: 0; flex: 1; }
.message-meta { display: flex; align-items: baseline; gap: 9px; }
.message-meta strong { color: #454652; font-size: .81rem; }
.message-meta time { color: #a0a1ab; font-size: .65rem; }
.message-body p { margin: 4px 0 0; color: #62636e; font-size: .83rem; line-height: 1.5; overflow-wrap: anywhere; }
.history-note { margin: 10px 0 0; color: #a0a1ab; font-size: .68rem; text-align: center; }
.chat-composer { display: flex; min-height: 52px; align-items: center; gap: 10px; border: 1px solid #e3e3e9; border-radius: 12px; padding: 5px 9px; background: #fafafd; }
.chat-composer:focus-within { border-color: #aaa7e9; box-shadow: 0 0 0 3px #f0efff; }
.composer-plus { color: #7772d8; font-size: 1.45rem; }
.chat-composer input { min-width: 0; flex: 1; border: 0; outline: 0; color: #444550; background: transparent; font-size: .83rem; }
.chat-composer input::placeholder { color: #a2a3ac; }
.send-button { width: 34px; height: 34px; border: 0; border-radius: 9px; color: #fff; background: #6b67d6; cursor: pointer; }
.send-button:disabled { cursor: default; opacity: .38; }
.content-scroll { min-height: 0; flex: 1; overflow: auto; padding: 30px clamp(18px, 4vw, 48px) 46px; }
.task-layout { display: grid; grid-template-columns: minmax(230px, .75fr) minmax(0, 1.25fr); align-items: start; gap: 27px; max-width: 1060px; margin: 0 auto; }
.task-create-card, .agenda-card { display: grid; gap: 16px; border: 1px solid #e8e8ef; border-radius: 13px; padding: 21px; background: #fff; box-shadow: 0 5px 18px #2e2d4410; }
.task-create-card h2, .personal-heading h2, .calendar-toolbar h2 { margin: -9px 0 0; color: #363744; font-size: 1.35rem; letter-spacing: -.035em; }
.section-title-row, .personal-heading, .calendar-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 15px; }
.section-title-row { margin-bottom: 13px; }
.section-title-row h2 { margin: 4px 0 0; color: #363744; font-size: 1.1rem; }
.count-pill { flex-shrink: 0; border-radius: 999px; padding: 7px 11px; color: #706cbd; background: #f0effc; font-size: .7rem; font-weight: 750; }
.task-row { display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #efeff2; padding: 14px 3px; }
.task-check { display: grid; width: 21px; height: 21px; flex-shrink: 0; place-items: center; border: 1.5px solid #c8c9d2; border-radius: 50%; color: white; background: #fff; cursor: pointer; }
.task-check:hover { border-color: #7a75d7; }
.task-check.checked { border-color: #56a879; background: #56a879; }
.task-row-body { display: grid; min-width: 0; flex: 1; gap: 4px; }
.task-row-body strong { overflow: hidden; color: #4b4c57; font-size: .84rem; text-overflow: ellipsis; white-space: nowrap; }
.task-row-body strong.struck { color: #9a9ba4; text-decoration: line-through; }
.task-row-body span { overflow: hidden; color: #9697a2; font-size: .71rem; text-overflow: ellipsis; white-space: nowrap; }
.task-row-body .task-urgency { width: fit-content; border-radius: 999px; padding: 3px 7px; font-size: .62rem; font-weight: 750; }
.urgencia-verde { color: #337d52; background: #e7f5eb; }
.urgencia-amarillo { color: #8a6716; background: #fff4d5; }
.urgencia-rojo { color: #a83e47; background: #fde9e8; }
.urgencia-neutral, .urgencia-sin-fecha { color: #858691; background: #f0f0f3; }
.notification-dot { width: 9px; height: 9px; flex: 0 0 9px; margin-top: 3px; border-radius: 50%; }
.notification-dot.urgencia-amarillo { background: #e1b53c; }
.notification-dot.urgencia-rojo { background: #d95b62; }
.notification-dot-state { background: #716dd3; }
.task-state { flex-shrink: 0; color: #9394a0; font-size: .68rem; text-transform: capitalize; }
.empty-card { border: 1px dashed #dedee7; border-radius: 10px; padding: 24px 15px; color: #92939e; font-size: .8rem; text-align: center; }
.personal-view { max-width: 900px; width: 100%; margin: 0 auto; }
.personal-heading { margin-bottom: 23px; }
.personal-heading h2 { margin: 6px 0 5px; }
.personal-heading p { margin: 0; color: #91929d; font-size: .8rem; }
.personal-create { display: grid; grid-template-columns: minmax(0, 1fr) 125px repeat(3, minmax(100px, .65fr)) auto; align-items: end; gap: 11px; border: 1px solid #e7e7ed; border-radius: 12px; padding: 16px; background: #fbfbfd; }
.personal-description { margin: 12px 16px 18px; }
.personal-tasks { border-top: 1px solid #e9e9ee; }
.personal-tasks .empty-card { margin-top: 18px; }
.absence-view, .github-view { max-width: 940px; width: 100%; margin: 0 auto; }
.absence-create, .github-card { display: grid; gap: 15px; border: 1px solid #e7e7ed; border-radius: 12px; padding: 19px; background: #fbfbfd; }
.absence-create { grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: end; }
.absence-detail, .absence-file { grid-column: span 3; }
.absence-file input { padding: 9px; }
.absence-file small { color: #888995; font-size: .67rem; font-weight: 400; }
.absence-create > .button { justify-self: start; }
.absence-list { display: grid; gap: 10px; margin-top: 18px; }
.absence-card { display: grid; gap: 10px; border: 1px solid #e8e8ef; border-radius: 11px; padding: 15px; background: #fff; }
.absence-card-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
.absence-card-heading > div { display: grid; gap: 4px; }
.absence-card-heading strong { color: #454652; font-size: .83rem; }
.absence-card-heading span, .absence-card-heading time { color: #878893; font-size: .72rem; }
.absence-card p { margin: 0; color: #666773; font-size: .78rem; white-space: pre-wrap; }
.github-card { width: min(100%, 650px); margin: 20px auto; padding: 28px; background: #fff; box-shadow: 0 5px 18px #2e2d4410; }
.github-card h2 { margin: -8px 0 0; color: #363744; font-size: 1.45rem; }
.github-card > p { margin: 0; color: #777986; font-size: .84rem; line-height: 1.6; }
.github-profile { display: flex; align-items: center; gap: 13px; margin-top: 5px; border-top: 1px solid #ececf1; padding-top: 18px; }
.github-avatar { width: 46px; height: 46px; border-radius: 50%; background: #f1f1f5; }
.github-profile > div { display: grid; flex: 1; gap: 4px; }
.github-profile strong { color: #42434f; font-size: .84rem; }
.github-profile a { color: #625dcc; font-size: .73rem; text-decoration: none; }
.github-profile a:hover { text-decoration: underline; }
.certificate-modal { position: relative; display: grid; width: min(100%, 860px); max-height: 90vh; gap: 12px; overflow: auto; border-radius: 14px; padding: 22px; background: #fff; }
.certificate-modal h2 { margin: 0; padding-right: 35px; color: #42434f; font-size: .95rem; }
.certificate-modal img { display: block; max-width: 100%; max-height: 74vh; justify-self: center; object-fit: contain; }
.calendar-view { max-width: 1120px; width: 100%; margin: 0 auto; }
.calendar-toolbar { margin-bottom: 20px; }
.calendar-toolbar h2 { margin-top: 5px; text-transform: capitalize; }
.month-controls { display: flex; align-items: center; gap: 5px; }
.month-button, .today-button { display: grid; min-width: 36px; height: 34px; place-items: center; border: 1px solid #e5e5eb; border-radius: 8px; color: #6c6d78; background: white; cursor: pointer; }
.month-button { font-size: 1.3rem; }
.today-button { padding: 0 11px; font-size: .72rem; }
.calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); overflow: hidden; border-top: 1px solid #e8e8ed; border-left: 1px solid #e8e8ed; border-radius: 10px; }
.weekday { padding: 10px 5px; color: #8d8e99; background: #f9f9fb; font-size: .7rem; font-weight: 750; text-align: center; }
.day-cell { display: flex; min-width: 0; min-height: 92px; flex-direction: column; align-items: stretch; gap: 4px; overflow: hidden; border: 0; border-top: 1px solid #e8e8ed; border-right: 1px solid #e8e8ed; padding: 7px 5px; background: #fff; text-align: left; cursor: pointer; }
.day-cell:hover { background: #faf9ff; }
.day-cell.outside-month { background: #fafafc; }
.day-cell.outside-month .day-number { color: #b9bac2; }
.day-cell.selected-day { box-shadow: inset 0 0 0 2px #817ce0; }
.day-number { align-self: flex-start; display: grid; width: 24px; height: 24px; place-items: center; border-radius: 50%; color: #666773; font-size: .71rem; }
.today-cell .day-number { color: #fff; background: #706bd7; font-weight: 800; }
.calendar-event { display: block; overflow: hidden; border-radius: 4px; padding: 3px 4px; color: #5752a7; background: #eeedfc; font-size: .62rem; text-overflow: ellipsis; white-space: nowrap; }
.calendar-event.equipo { color: #397a56; background: #e7f4eb; }
.calendar-event.urgencia-verde { color: #337d52; background: #e7f5eb; }
.calendar-event.urgencia-amarillo { color: #8a6716; background: #fff4d5; }
.calendar-event.urgencia-rojo { color: #a83e47; background: #fde9e8; }
.more-events { color: #8b8c97; font-size: .59rem; }
.agenda-card { margin-top: 23px; padding: 19px; }
.agenda-card h3 { margin: 4px 0 0; color: #555661; font-size: .94rem; }
.agenda-form { display: grid; grid-template-columns: minmax(160px, 1.4fr) repeat(3, minmax(90px, .7fr)) auto; align-items: end; gap: 10px; }
.calendar-legend { display: flex; align-items: center; gap: 7px; margin: 0; color: #878893; font-size: .7rem; }
.legend-dot { width: 9px; height: 9px; border-radius: 50%; background: #7772dc; }
.legend-dot.team { margin-left: 9px; background: #68ae80; }
.empty-calendar-hint { margin: 0; color: #9697a2; font-size: .75rem; }
.modal-backdrop { position: fixed; z-index: 10; inset: 0; display: grid; place-items: center; padding: 18px; background: #25243b75; }
.modal-card { position: relative; display: grid; width: min(100%, 430px); gap: 16px; border-radius: 15px; padding: 27px; background: #fff; box-shadow: 0 24px 80px #17162840; }
.modal-card h2 { margin: -7px 0 0; color: #363744; font-size: 1.55rem; }
.modal-card p { margin: -8px 0 0; color: #858691; font-size: .8rem; line-height: 1.55; }
.modal-close { position: absolute; top: 13px; right: 13px; width: 30px; height: 30px; border: 0; border-radius: 8px; color: #82838e; background: #f4f4f7; font-size: 1.2rem; cursor: pointer; }

@media (max-width: 950px) {
  .app-shell { grid-template-columns: 62px 205px minmax(0, 1fr); }
  .invite-form input { width: 130px; }
  .task-layout { grid-template-columns: 1fr; }
  .personal-create { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .personal-create > .field:first-child { grid-column: span 2; }
  .absence-create { grid-template-columns: 1fr 1fr; }
  .absence-detail, .absence-file { grid-column: span 2; }
  .agenda-form { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 680px) {
  .auth-page { grid-template-columns: 1fr; }
  .auth-decoration { min-height: 0; padding: 22px 25px; }
  .auth-copy { padding: 34px 0 18px; }
  .auth-copy h1 { font-size: 2.6rem; }
  .auth-footnote { display: none; }
  .personal-create { grid-template-columns: 1fr 1fr; }
  .personal-create > .field:first-child { grid-column: span 2; }
  .app-shell { grid-template-columns: 54px minmax(0, 1fr); }
  .channel-sidebar { display: none; }
  .server-rail { gap: 9px; }
  .rail-logo, .server-icon, .server-create { width: 38px; height: 38px; }
  .topbar { min-height: 68px; padding: 10px 13px; }
  .topbar-actions { flex-wrap: wrap; justify-content: flex-end; gap: 3px; }
  .invite-form { width: 100%; margin: 0; }
  .invite-form input { min-width: 0; flex: 1; }
  .user-menu > span { display: none; }
  .chat-panel { padding: 0 13px 13px; }
  .content-scroll { padding: 22px 14px 35px; }
  .personal-create { grid-template-columns: 1fr 100px; }
  .personal-create .button { grid-column: 1 / -1; }
  .absence-create { grid-template-columns: 1fr; }
  .absence-detail, .absence-file { grid-column: auto; }
  .github-card { padding: 20px; }
  .day-cell { min-height: 72px; padding: 4px 2px; }
  .weekday { font-size: .61rem; }
  .calendar-event { font-size: .52rem; padding: 2px; }
  .agenda-form { grid-template-columns: 1fr 1fr; }
  .agenda-form .button { grid-column: 1 / -1; }
  .calendar-toolbar h2 { font-size: 1.16rem; }
}
</style>
