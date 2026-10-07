<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  api,
  type ContactosEspacio,
  type Equipo,
  type EventoCalendario,
  type AvisoAusencia,
  type ArchivoEquipo,
  type CuentaGitHub,
  type MensajeChat,
  type Notificacion,
  type RepositorioGitHub,
  type Tarea,
  type Usuario,
} from '@/services/api'

type Pantalla = 'personal' | 'calendario' | 'equipo' | 'github' | 'contactos' | 'perfil'
type Tema = 'auto' | 'violeta' | 'negro'

const usuario = ref<Usuario | null>(null)
const cargando = ref(true)
const trabajando = ref(false)
const aviso = ref('')
const avisoError = ref(false)
const modoAcceso = ref<'entrar' | 'registrar'>('entrar')
const formularioAcceso = reactive({ nombre: '', correo: '', contrasena: '' })
const temaPreferido = ref<Tema>(leerTemaPreferido())
const equipos = ref<Equipo[]>([])
const equipoActivoId = ref<number | null>(null)
const equipoActivo = computed(() => equipos.value.find((equipo) => equipo.id === equipoActivoId.value) ?? null)
const pantalla = ref<Pantalla>('personal')
const vistaEquipo = ref<'chat' | 'tareas' | 'ausencias' | 'archivos'>('chat')
const tareasPersonales = ref<Tarea[]>([])
const tareasEquipo = ref<Tarea[]>([])
const tareasTodos = ref<Tarea[]>([])
const eventos = ref<EventoCalendario[]>([])
const mensajes = ref<MensajeChat[]>([])
const textoMensaje = ref('')
const ahora = ref(Date.now())
const temaActivo = computed<Tema>(() => {
  if (temaPreferido.value !== 'auto') return temaPreferido.value
  const horaLocal = new Date(ahora.value).getHours()
  return horaLocal >= 7 && horaLocal < 20 ? 'violeta' : 'negro'
})
const fechaCalendarioEquipo = ref(new Date())
const diaCalendarioEquipo = ref(fechaLocal(new Date()))
const notificacionesAbiertas = ref(false)
const notificacionesEstado = ref<Notificacion[]>([])
const permisoNotificaciones = ref(false)
const pushActivado = ref(false)
const cuentaGitHub = ref<CuentaGitHub | null>(null)
const contactosEspacio = ref<ContactosEspacio>({ contactos: [], recibidas: [], enviadas: [] })
const correoContacto = ref('')
const perfilNombre = ref('')
const fotoPerfil = ref<File | null>(null)
const vistaPreviaFoto = ref('')
const quitarFotoPendiente = ref(false)
const fotosPerfil = ref<Record<number, string>>({})
const repositoriosGitHub = ref<RepositorioGitHub[]>([])
const formularioRepositorio = reactive({ nombre: '', descripcion: '' })
const archivoRepositorio = ref<File | null>(null)
const avisosAusencia = ref<AvisoAusencia[]>([])
const archivosEquipo = ref<ArchivoEquipo[]>([])
const archivoEquipoSeleccionado = ref<File | null>(null)
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

function leerTemaPreferido(): Tema {
  const valor = localStorage.getItem('nexus-tema')
  return valor === 'violeta' || valor === 'negro' ? valor : 'auto'
}

watch(temaPreferido, (tema) => {
  localStorage.setItem('nexus-tema', tema)
})

watch(
  temaActivo,
  (tema) => {
    document.documentElement.dataset.theme = tema
    document.body.dataset.theme = tema
    const metaTema = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    if (metaTema) metaTema.content = tema === 'negro' ? '#11131b' : '#7062d5'
  },
  { immediate: true },
)

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
const nombreMesCalendarioEquipo = computed(() =>
  fechaCalendarioEquipo.value.toLocaleDateString('es', { month: 'long', year: 'numeric' }),
)
const tareasCalendarioEquipo = computed(() =>
  tareasEquipo.value.filter(
    (tarea) => tarea.equipo_id === equipoActivoId.value && tarea.fecha_limite !== null,
  ),
)
const tareasDelDiaCalendarioEquipo = computed(() =>
  tareasCalendarioEquipo.value.filter((tarea) => tarea.fecha_limite === diaCalendarioEquipo.value),
)
const tareasVisiblesCalendarioEquipo = computed(() => {
  if (tareasDelDiaCalendarioEquipo.value.length) return tareasDelDiaCalendarioEquipo.value
  const ordenarPorFecha = (tareas: Tarea[]) =>
    [...tareas].sort((a, b) =>
      `${a.fecha_limite ?? ''}T${a.hora_limite ?? ''}`.localeCompare(
        `${b.fecha_limite ?? ''}T${b.hora_limite ?? ''}`,
      ),
    )
  const proximas = ordenarPorFecha(
    tareasCalendarioEquipo.value.filter(
      (tarea) => tarea.fecha_limite !== null && tarea.fecha_limite >= diaCalendarioEquipo.value,
    ),
  )
  return (proximas.length ? proximas : ordenarPorFecha(tareasCalendarioEquipo.value)).slice(0, 4)
})
const celdasCalendarioEquipo = computed(() => {
  const primero = new Date(
    fechaCalendarioEquipo.value.getFullYear(),
    fechaCalendarioEquipo.value.getMonth(),
    1,
  )
  const desplazamiento = (primero.getDay() + 6) % 7
  const cantidadDias = new Date(
    fechaCalendarioEquipo.value.getFullYear(),
    fechaCalendarioEquipo.value.getMonth() + 1,
    0,
  ).getDate()
  const total = Math.ceil((desplazamiento + cantidadDias) / 7) * 7
  return Array.from({ length: total }, (_, indice) => {
    const fecha = new Date(primero.getFullYear(), primero.getMonth(), indice - desplazamiento + 1)
    const clave = fechaLocal(fecha)
    return {
      clave,
      numero: fecha.getDate(),
      enMes: fecha.getMonth() === primero.getMonth(),
      hoy: fecha.toDateString() === new Date().toDateString(),
      cantidadTareas: tareasCalendarioEquipo.value.filter((tarea) => tarea.fecha_limite === clave)
        .length,
    }
  })
})
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
let temporizadorContenidoEquipo: number | undefined
let temporizadorContactos: number | undefined
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
    await Promise.all([
      cargarEspacio(),
      cargarCuentaGitHub(),
      cargarNotificaciones(),
      cargarContactos(),
      cargarFotoPerfil(iniciado.id),
    ])
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
    const iniciado = await api.usuarioActual()
    usuario.value = iniciado
    await Promise.all([
      cargarEspacio(),
      cargarCuentaGitHub(),
      cargarNotificaciones(),
      cargarContactos(),
      cargarFotoPerfil(iniciado.id),
    ])
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

async function cargarArchivosEquipo() {
  if (equipoActivoId.value === null) {
    archivosEquipo.value = []
    return
  }
  archivosEquipo.value = await api.listarArchivosEquipo(equipoActivoId.value)
}

async function seleccionarEquipo(equipo: Equipo) {
  equipoActivoId.value = equipo.id
  pantalla.value = 'equipo'
  vistaEquipo.value = 'chat'
  await Promise.all([refrescarVistaEquipo(), cargarAvisosAusencia(), cargarArchivosEquipo()])
}

async function cambiarPantalla(destino: Pantalla) {
  pantalla.value = destino
  if (destino === 'calendario') await cargarEventos()
  if (destino === 'github') await cargarGitHub()
  if (destino === 'contactos') await cargarContactos()
  if (destino === 'equipo') await cargarChat()
}

function abrirVistaEquipo(vista: 'chat' | 'tareas' | 'ausencias' | 'archivos') {
  vistaEquipo.value = vista
}

async function abrirPerfil() {
  if (!usuario.value) return
  perfilNombre.value = usuario.value.nombre
  fotoPerfil.value = null
  quitarFotoPendiente.value = false
  limpiarVistaPreviaFoto()
  pantalla.value = 'perfil'
  try {
    await cargarFotoPerfil(usuario.value.id)
  } catch (causa) {
    mostrarError(causa)
  }
}

async function cargarEventos() {
  eventos.value = await api.listarCalendario(mesActual.value)
}

async function cargarContactos() {
  if (!usuario.value) return
  const lista = await api.listarContactos()
  contactosEspacio.value = lista
  const ids = new Set([
    usuario.value.id,
    ...lista.contactos.map((contacto) => contacto.id),
    ...lista.recibidas.map((solicitud) => solicitud.usuario_id),
    ...lista.enviadas.map((solicitud) => solicitud.usuario_id),
  ])
  await Promise.all([...ids].map((id) => cargarFotoPerfil(id)))
  for (const [id, foto] of Object.entries(fotosPerfil.value)) {
    if (ids.has(Number(id))) continue
    URL.revokeObjectURL(foto)
    delete fotosPerfil.value[Number(id)]
  }
}

async function cargarFotoPerfil(usuarioId: number) {
  if (fotosPerfil.value[usuarioId]) return
  try {
    const foto = await api.descargarFotoPerfil(usuarioId)
    fotosPerfil.value[usuarioId] = URL.createObjectURL(foto)
  } catch (causa) {
    if (causa instanceof Error && causa.message.includes('HTTP 404')) return
    throw causa
  }
}

function seleccionarFotoPerfil(evento: Event) {
  const archivo = (evento.target as HTMLInputElement).files?.[0] ?? null
  if (!archivo) return
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(archivo.type) || archivo.size > 2_000_000) {
    fotoPerfil.value = null
    mostrarError(new Error('Elige una foto PNG, JPG o WEBP de hasta 2 MB.'))
    return
  }
  limpiarVistaPreviaFoto()
  fotoPerfil.value = archivo
  quitarFotoPendiente.value = false
  vistaPreviaFoto.value = URL.createObjectURL(archivo)
}

function limpiarVistaPreviaFoto() {
  if (vistaPreviaFoto.value) URL.revokeObjectURL(vistaPreviaFoto.value)
  vistaPreviaFoto.value = ''
}

async function guardarPerfil() {
  if (!usuario.value) return
  trabajando.value = true
  try {
    const datos: { nombre: string; foto_base64?: string; quitar_foto?: boolean } = {
      nombre: perfilNombre.value,
    }
    if (fotoPerfil.value) datos.foto_base64 = await archivoComoBase64(fotoPerfil.value)
    else if (quitarFotoPendiente.value) datos.quitar_foto = true
    usuario.value = await api.actualizarPerfil(datos)
    const fotoActual = fotosPerfil.value[usuario.value.id]
    if (fotoActual) URL.revokeObjectURL(fotoActual)
    delete fotosPerfil.value[usuario.value.id]
    fotoPerfil.value = null
    quitarFotoPendiente.value = false
    limpiarVistaPreviaFoto()
    await cargarFotoPerfil(usuario.value.id)
    anunciar('Tu perfil se guardó en la base de datos.')
  } catch (causa) {
    mostrarError(causa)
  } finally {
    trabajando.value = false
  }
}

function quitarFotoPerfil() {
  fotoPerfil.value = null
  limpiarVistaPreviaFoto()
  quitarFotoPendiente.value = Boolean(usuario.value && fotosPerfil.value[usuario.value.id])
}

async function solicitarContacto() {
  const correo = correoContacto.value.trim()
  if (!correo) return
  trabajando.value = true
  try {
    await api.solicitarContacto(correo)
    correoContacto.value = ''
    await cargarContactos()
    anunciar('Solicitud enviada. Se agregará a tus contactos cuando la acepten.')
  } catch (causa) {
    mostrarError(causa)
  } finally {
    trabajando.value = false
  }
}

async function responderContacto(solicitudId: number, accion: 'aceptar' | 'rechazar') {
  try {
    await api.responderSolicitudContacto(solicitudId, accion)
    await cargarContactos()
    anunciar(accion === 'aceptar' ? 'La persona ya está en tus contactos.' : 'Solicitud rechazada.')
  } catch (causa) {
    mostrarError(causa)
  }
}

async function eliminarContacto(solicitudId: number, nombre: string) {
  if (!window.confirm(`¿Quieres quitar a ${nombre} de tus contactos?`)) return
  try {
    await api.eliminarContacto(solicitudId)
    await cargarContactos()
    anunciar('Contacto eliminado.')
  } catch (causa) {
    mostrarError(causa)
  }
}

async function cargarCuentaGitHub() {
  cuentaGitHub.value = await api.obtenerCuentaGitHub()
}

async function cargarGitHub() {
  await cargarCuentaGitHub()
  if (!cuentaGitHub.value?.permisos_repositorios) {
    repositoriosGitHub.value = []
    return
  }
  try {
    repositoriosGitHub.value = await api.listarRepositoriosGitHub()
  } catch (causa) {
    repositoriosGitHub.value = []
    mostrarError(causa)
  }
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
    repositoriosGitHub.value = []
    anunciar('Se desconectó la cuenta de GitHub.')
  } catch (causa) {
    mostrarError(causa)
  }
}

function seleccionarZipRepositorio(evento: Event) {
  const archivo = (evento.target as HTMLInputElement).files?.[0] ?? null
  if (archivo && (!archivo.name.toLowerCase().endsWith('.zip') || archivo.size > 15_000_000)) {
    archivoRepositorio.value = null
    mostrarError(new Error('El repositorio debe ser un archivo ZIP de hasta 15 MB.'))
    return
  }
  archivoRepositorio.value = archivo
  if (archivo && !formularioRepositorio.nombre) {
    formularioRepositorio.nombre = archivo.name.replace(/\.zip$/i, '').replace(/[^A-Za-z0-9._-]/g, '-')
  }
}

async function publicarRepositorio() {
  const archivo = archivoRepositorio.value
  if (!archivo) return
  trabajando.value = true
  try {
    await api.crearRepositorioGitHub({
      nombre: formularioRepositorio.nombre,
      descripcion: formularioRepositorio.descripcion,
      archivo_base64: await archivoComoBase64(archivo),
    })
    formularioRepositorio.nombre = ''
    formularioRepositorio.descripcion = ''
    archivoRepositorio.value = null
    await cargarGitHub()
    anunciar('Se creó y publicó el repositorio público en GitHub.')
  } catch (causa) {
    mostrarError(causa)
  } finally {
    trabajando.value = false
  }
}

async function descargarRepositorio(repositorio: RepositorioGitHub) {
  try {
    const [propietario] = repositorio.full_name.split('/')
    if (!propietario) throw new Error('El repositorio de GitHub no tiene un propietario válido.')
    const archivo = await api.descargarZipRepositorio(propietario, repositorio.name)
    descargarBlob(archivo, `${repositorio.name}.zip`)
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

function seleccionarArchivoEquipo(evento: Event) {
  const archivo = (evento.target as HTMLInputElement).files?.[0] ?? null
  if (archivo && archivo.size > 20_000_000) {
    archivoEquipoSeleccionado.value = null
    mostrarError(new Error('El archivo debe pesar como máximo 20 MB.'))
    return
  }
  archivoEquipoSeleccionado.value = archivo
}

async function subirArchivoEquipo() {
  if (equipoActivoId.value === null || archivoEquipoSeleccionado.value === null) return
  try {
    await api.subirArchivoEquipo(
      equipoActivoId.value,
      archivoEquipoSeleccionado.value.name,
      await archivoComoBase64(archivoEquipoSeleccionado.value),
    )
    archivoEquipoSeleccionado.value = null
    await cargarArchivosEquipo()
    anunciar('El archivo quedó disponible para el servidor.')
  } catch (causa) {
    mostrarError(causa)
  }
}

async function descargarArchivoEquipo(archivo: ArchivoEquipo) {
  try {
    descargarBlob(await api.descargarArchivoEquipo(archivo.id), archivo.nombre)
  } catch (causa) {
    mostrarError(causa)
  }
}

function descargarBlob(blob: Blob, nombre: string) {
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombre
  enlace.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function tamanoLegible(bytes: number) {
  if (bytes < 1000) return `${bytes} B`
  if (bytes < 1_000_000) return `${(bytes / 1000).toFixed(1)} KB`
  return `${(bytes / 1_000_000).toFixed(1)} MB`
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
        tag: `nexus-${pendiente.id}`,
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

function moverMesCalendarioEquipo(cantidad: number) {
  fechaCalendarioEquipo.value = new Date(
    fechaCalendarioEquipo.value.getFullYear(),
    fechaCalendarioEquipo.value.getMonth() + cantidad,
    1,
  )
}

function detalleTareaCalendarioEquipo(tarea: Tarea) {
  const fecha = tarea.fecha_limite === diaCalendarioEquipo.value ? '' : `${tarea.fecha_limite} · `
  return `${fecha}${tarea.hora_limite || 'Sin hora límite'} · ${tarea.estado.replace('_', ' ')}`
}

function irAHoyCalendarioEquipo() {
  const hoy = new Date()
  fechaCalendarioEquipo.value = hoy
  diaCalendarioEquipo.value = fechaLocal(hoy)
}

function irAHoy() {
  fechaActual.value = new Date()
  if (pantalla.value === 'calendario') void cargarEventos().catch(mostrarError)
}

function seleccionarDia(fecha: string) {
  formularioAgenda.fecha = fecha
}

function crearTareaDesdeCalendario() {
  formularioTarea.fecha = formularioAgenda.fecha || fechaLocal(new Date())
  formularioTarea.hora_inicio = formularioAgenda.hora_inicio
  formularioTarea.hora_fin = formularioAgenda.hora_fin
  pantalla.value = 'personal'
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
  const tarea = tareaElegida.value
  if (!tarea) return
  try {
    await api.agendarTarea({
      tarea_id: tarea.id,
      alcance: tarea.alcance,
      fecha: formularioAgenda.fecha,
      hora_inicio: formularioAgenda.hora_inicio,
      hora_fin: formularioAgenda.hora_fin,
    })
    if (tarea.alcance === 'personal') {
      tareasPersonales.value = await api.listarTareas('personal')
    } else {
      await cargarTareasDeEquipos()
    }
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

async function eliminarTarea(tarea: Tarea) {
  const articulo = tarea.tipo === 'proyecto' ? 'el proyecto' : 'la tarea'
  if (!window.confirm(`¿Quieres eliminar ${articulo} «${tarea.titulo}»?`)) return
  try {
    await api.eliminarTarea(tarea)
    if (tarea.alcance === 'personal') {
      tareasPersonales.value = tareasPersonales.value.filter((item) => item.id !== tarea.id)
    } else {
      await cargarTareasDeEquipos()
    }
    await cargarEventos()
    anunciar(`${tarea.tipo === 'proyecto' ? 'Proyecto' : 'Tarea'} eliminada.`)
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
    contactosEspacio.value = { contactos: [], recibidas: [], enviadas: [] }
    liberarFotosPerfil()
  }
}

function liberarFotosPerfil() {
  for (const url of Object.values(fotosPerfil.value)) URL.revokeObjectURL(url)
  fotosPerfil.value = {}
  limpiarVistaPreviaFoto()
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
  if (temporizadorContenidoEquipo !== undefined) {
    window.clearInterval(temporizadorContenidoEquipo)
    temporizadorContenidoEquipo = undefined
  }
  if (temporizadorContactos !== undefined) {
    window.clearInterval(temporizadorContactos)
    temporizadorContactos = undefined
  }
  if (pantalla.value === 'contactos') {
    void cargarContactos().catch(mostrarError)
    temporizadorContactos = window.setInterval(() => {
      void cargarContactos().catch(mostrarError)
    }, 8000)
    return
  }
  if (pantalla.value !== 'equipo' || equipoActivoId.value === null) return
  if (vistaEquipo.value === 'chat') {
    void cargarChat().catch(mostrarError)
    temporizadorChat = window.setInterval(() => {
      void cargarChat().catch(mostrarError)
    }, 3000)
  } else if (vistaEquipo.value === 'ausencias') {
    void cargarAvisosAusencia().catch(mostrarError)
    temporizadorContenidoEquipo = window.setInterval(() => {
      void cargarAvisosAusencia().catch(mostrarError)
    }, 5000)
  } else if (vistaEquipo.value === 'archivos') {
    void cargarArchivosEquipo().catch(mostrarError)
    temporizadorContenidoEquipo = window.setInterval(() => {
      void cargarArchivosEquipo().catch(mostrarError)
    }, 5000)
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
    void Promise.all([
      cargarEspacio(false),
      cargarNotificaciones(),
      ...(pantalla.value === 'contactos' ? [cargarContactos()] : []),
    ]).catch(mostrarError)
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
  if (temporizadorContenidoEquipo !== undefined) window.clearInterval(temporizadorContenidoEquipo)
  if (temporizadorContactos !== undefined) window.clearInterval(temporizadorContactos)
  if (temporizadorSincronizacion !== undefined) window.clearInterval(temporizadorSincronizacion)
  if (temporizadorUrgencia !== undefined) window.clearInterval(temporizadorUrgencia)
  cerrarCertificado()
  liberarFotosPerfil()
})

watch(usuario, sincronizarCambiosMySQL)
</script>

<template>
  <main v-if="cargando" class="loading-screen">
    <div class="brand-mark">N</div>
    <span>Preparando tu espacio…</span>
  </main>

  <main v-else-if="!usuario" class="auth-page" :data-theme="temaActivo">
    <section class="auth-decoration">
      <div class="auth-brand">
        <span class="brand-mark">N</span> NEXUS
        <label class="theme-control auth-theme-control">
          <span>Tema</span>
          <select v-model="temaPreferido" aria-label="Tema de Nexus">
            <option value="auto">Auto</option>
            <option value="violeta">Violeta</option>
            <option value="negro">Negro</option>
          </select>
        </label>
      </div>
      <div class="auth-copy">
        <span class="auth-kicker">TRABAJA EN EQUIPO. A TU MANERA.</span>
        <h1>Todo tu equipo,<br>en un mismo lugar.</h1>
        <p>Conversaciones, tareas y planes para tus equipos y para ti.</p>
      </div>
      <div class="auth-art" aria-hidden="true">
        <svg viewBox="0 0 320 260" fill="none">
          <circle class="art-orbit" cx="171" cy="133" r="101" stroke="white" stroke-opacity=".18" stroke-dasharray="4 8"/>
          <circle cx="62" cy="191" r="20" fill="#f3c879" fill-opacity=".92"/>
          <circle cx="275" cy="54" r="11" fill="#a8a0ff"/>
          <g class="art-card art-card-main">
            <rect x="77" y="57" width="169" height="126" rx="18" fill="white" fill-opacity=".96"/>
            <rect x="96" y="76" width="36" height="36" rx="11" fill="#eeebff"/>
            <path d="M107 95h14m-7-7v14" stroke="#7062d5" stroke-width="3" stroke-linecap="round"/>
            <rect x="143" y="81" width="82" height="8" rx="4" fill="#d9d8e8"/>
            <rect x="143" y="96" width="57" height="6" rx="3" fill="#eeedf4"/>
            <rect x="96" y="127" width="131" height="1" fill="#eeeef3"/>
            <rect x="96" y="141" width="76" height="7" rx="3.5" fill="#e4e3ef"/>
            <rect x="96" y="156" width="112" height="7" rx="3.5" fill="#eeedf4"/>
          </g>
          <g class="art-card art-card-note">
            <rect x="202" y="148" width="83" height="62" rx="14" fill="#f3c879"/>
            <path d="M218 167h48m-48 12h35m-35 12h25" stroke="#6551a7" stroke-width="4" stroke-linecap="round" opacity=".75"/>
          </g>
          <g class="art-card art-card-check">
            <rect x="31" y="87" width="57" height="57" rx="17" fill="#8fdfc3"/>
            <path d="m47 115 10 9 17-20" stroke="#315d72" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
          </g>
        </svg>
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

  <main v-else class="app-shell" :data-theme="temaActivo">
    <aside class="channel-sidebar">
      <button class="workspace-brand" @click="cambiarPantalla('personal')">
        <span class="brand-mark">N</span>
        <span class="brand-copy"><strong>Nexus</strong><small>ESTUDIO DE TRABAJO</small></span>
      </button>
      <span class="sidebar-caption">TU ESPACIO</span>
      <nav class="workspace-nav" aria-label="Navegación">
      <button class="side-link" :class="{ active: pantalla === 'personal' }" @click="cambiarPantalla('personal')">
        <span class="side-link-icon">⌂</span><span>Mis tareas</span>
      </button>
      <button class="side-link" :class="{ active: pantalla === 'calendario' }" @click="cambiarPantalla('calendario')">
        <span class="side-link-icon">▦</span><span>Calendario</span>
      </button>
      <button class="side-link" :class="{ active: pantalla === 'contactos' }" @click="cambiarPantalla('contactos')">
        <span class="side-link-icon">♧</span><span>Contactos</span>
        <small v-if="contactosEspacio.recibidas.length" class="nav-count">{{ contactosEspacio.recibidas.length }}</small>
      </button>
      <button class="side-link" :class="{ active: pantalla === 'github' }" @click="cambiarPantalla('github')">
        <span class="side-link-icon">⌘</span><span>GitHub</span>
      </button>
      <button class="side-link" :class="{ active: pantalla === 'perfil' }" @click="void abrirPerfil()">
        <span class="side-link-icon">◉</span><span>Mi perfil</span>
      </button>
      </nav>

      <div class="team-section">
      <div class="side-title team-title"><span>TUS EQUIPOS</span><button class="icon-button" title="Crear espacio de equipo" @click="modalServidor = true">＋</button></div>
      <div v-if="equipos.length" class="team-list">
        <button
          v-for="equipo in equipos"
          :key="equipo.id"
          class="team-link"
          :class="{ active: equipoActivoId === equipo.id && pantalla === 'equipo' }"
          @click="seleccionarEquipo(equipo)"
        >
          <span class="team-symbol">{{ equipo.nombre.slice(0, 1).toUpperCase() }}</span><span>{{ equipo.nombre }}</span><small>{{ equipo.cantidad_miembros }}</small>
        </button>
      </div>
      <div v-else class="sidebar-empty">Crea un servidor e invita a tu equipo para empezar.</div>
      <button class="create-server-link" @click="modalServidor = true"><span>＋</span> Crear un equipo</button>
      </div>

      <div class="profile-card">
        <button class="avatar profile-avatar" title="Editar foto de perfil" @click="void abrirPerfil()">
          <img v-if="fotosPerfil[usuario.id]" :src="fotosPerfil[usuario.id]" alt="">
          <span v-else>{{ usuario.nombre.slice(0, 1).toUpperCase() }}</span>
        </button>
        <button class="profile-copy" @click="void abrirPerfil()"><strong>{{ usuario.nombre }}</strong><small>Editar mi perfil</small></button>
        <button class="icon-button logout-button" title="Cerrar sesión" @click="salir">↪</button>
      </div>
    </aside>

    <section class="main-panel">
      <header class="topbar">
        <div class="topbar-heading">
          <span class="top-icon">{{ pantalla === 'equipo' ? (vistaEquipo === 'chat' ? '✳' : vistaEquipo === 'tareas' ? '▤' : vistaEquipo === 'archivos' ? '▧' : '◌') : pantalla === 'calendario' ? '▦' : pantalla === 'github' ? '⌘' : pantalla === 'contactos' ? '♧' : pantalla === 'perfil' ? '◉' : '⌂' }}</span>
          <div>
            <h1>{{ pantalla === 'equipo' ? `${equipoActivo?.nombre ?? 'Equipo'} · ${vistaEquipo === 'chat' ? 'Conversaciones' : vistaEquipo === 'tareas' ? 'Tareas' : vistaEquipo === 'archivos' ? 'Documentos' : 'Avisos'}` : pantalla === 'calendario' ? 'Calendario' : pantalla === 'github' ? 'Proyectos conectados' : pantalla === 'contactos' ? 'Contactos' : pantalla === 'perfil' ? 'Tu perfil' : 'Panel personal' }}</h1>
            <p>{{ pantalla === 'equipo' ? equipoActivo?.descripcion || 'Un espacio para trabajar en equipo' : pantalla === 'calendario' ? 'Una vista clara de lo que sigue' : pantalla === 'github' ? 'Tus repositorios y proyectos' : pantalla === 'contactos' ? 'Conecta con personas de tu red' : pantalla === 'perfil' ? 'Tu identidad en tus espacios' : 'Todo lo que quieres avanzar' }}</p>
          </div>
        </div>
        <div v-if="pantalla === 'equipo'" class="topbar-actions">
          <button class="tab-button" :class="{ chosen: vistaEquipo === 'chat' }" @click="abrirVistaEquipo('chat')"># Chat</button>
          <button class="tab-button" :class="{ chosen: vistaEquipo === 'tareas' }" @click="abrirVistaEquipo('tareas')">▤ Tareas</button>
          <button class="tab-button" :class="{ chosen: vistaEquipo === 'ausencias' }" @click="abrirVistaEquipo('ausencias')"># Avisos</button>
          <button class="tab-button" :class="{ chosen: vistaEquipo === 'archivos' }" @click="abrirVistaEquipo('archivos')">▧ Archivos</button>
          <form v-if="equipoActivo?.rol === 'administrador'" class="invite-form" @submit.prevent="invitarMiembro">
            <input v-model="correoInvitado" type="email" required placeholder="Correo para invitar" aria-label="Correo de la persona a invitar">
            <button class="button button-small" type="submit">Invitar</button>
          </form>
        </div>
        <button v-else class="top-profile" @click="void abrirPerfil()">
          <span class="avatar">
            <img v-if="fotosPerfil[usuario.id]" :src="fotosPerfil[usuario.id]" alt="">
            <span v-else>{{ usuario.nombre.slice(0, 1).toUpperCase() }}</span>
          </span>
          <span>{{ usuario.nombre }}</span>
        </button>
        <label class="theme-control app-theme-control">
          <span>Tema</span>
          <select v-model="temaPreferido" aria-label="Tema de Nexus">
            <option value="auto">Auto</option>
            <option value="violeta">Violeta</option>
            <option value="negro">Negro</option>
          </select>
        </label>
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
        <div class="team-chat-column">
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
        </div>
        <aside class="team-calendar-card" :aria-label="`Calendario de tareas de ${equipoActivo.nombre}`">
          <div class="team-calendar-heading">
            <div>
              <span class="section-kicker">PLAN DEL EQUIPO</span>
              <h2>Calendario</h2>
            </div>
            <button class="tab-button" @click="vistaEquipo = 'tareas'">Ver tareas</button>
          </div>
          <div class="team-calendar-toolbar">
            <strong>{{ nombreMesCalendarioEquipo }}</strong>
            <div class="month-controls">
              <button class="month-button" aria-label="Mes anterior" @click="moverMesCalendarioEquipo(-1)">‹</button>
              <button class="today-button" @click="irAHoyCalendarioEquipo">Hoy</button>
              <button class="month-button" aria-label="Mes siguiente" @click="moverMesCalendarioEquipo(1)">›</button>
            </div>
          </div>
          <div class="team-calendar-grid">
            <span v-for="dia in ['L', 'M', 'X', 'J', 'V', 'S', 'D']" :key="dia" class="team-calendar-weekday">{{ dia }}</span>
            <button
              v-for="celda in celdasCalendarioEquipo"
              :key="celda.clave"
              class="team-calendar-day"
              :class="{
                'outside-month': !celda.enMes,
                'today-cell': celda.hoy,
                'selected-day': diaCalendarioEquipo === celda.clave,
                'has-team-tasks': celda.cantidadTareas > 0,
              }"
              :aria-label="`${celda.clave}, ${celda.cantidadTareas} tareas`"
              :aria-pressed="diaCalendarioEquipo === celda.clave"
              @click="diaCalendarioEquipo = celda.clave"
            >
              <span>{{ celda.numero }}</span>
              <small v-if="celda.cantidadTareas">{{ celda.cantidadTareas }}</small>
            </button>
          </div>
          <div class="team-calendar-agenda">
            <div class="team-calendar-agenda-heading">
              <strong>{{ tareasDelDiaCalendarioEquipo.length ? diaCalendarioEquipo : 'Próximas tareas' }}</strong>
              <span>{{ tareasDelDiaCalendarioEquipo.length ? `${tareasDelDiaCalendarioEquipo.length} ${tareasDelDiaCalendarioEquipo.length === 1 ? 'tarea' : 'tareas'}` : `${tareasVisiblesCalendarioEquipo.length} en agenda` }}</span>
            </div>
            <div v-if="tareasVisiblesCalendarioEquipo.length" class="team-calendar-task-list">
              <article v-for="tarea in tareasVisiblesCalendarioEquipo" :key="tarea.id" class="team-calendar-task">
                <span class="team-calendar-task-dot" :class="`urgencia-${nivelUrgencia(tarea)}`"></span>
                <div>
                  <strong :class="{ struck: tarea.estado === 'completada' }">{{ tarea.titulo }}</strong>
                  <small>{{ detalleTareaCalendarioEquipo(tarea) }}</small>
                </div>
              </article>
            </div>
            <p v-else class="team-calendar-empty">
              Este equipo todavía no tiene tareas con fecha.
            </p>
          </div>
        </aside>
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
              <button
                v-if="tarea.creador_id === usuario.id || equipoActivo?.rol === 'administrador'"
                class="task-delete"
                :aria-label="`Eliminar ${tarea.titulo}`"
                title="Eliminar tarea"
                @click="void eliminarTarea(tarea)"
              >×</button>
            </article>
            <div v-if="!tareasEquipo.length" class="empty-card">Todavía no hay tareas. Crea la primera para este equipo.</div>
          </div>
        </section>
      </section>

      <section v-else-if="pantalla === 'equipo' && vistaEquipo === 'ausencias'" class="content-scroll absence-view">
        <div class="personal-heading">
          <div><span class="section-kicker">CANAL PRIVADO DEL SERVIDOR</span><h2># Avisos</h2><p>Los miembros ven los avisos; solo quien lo publicó y el encargado pueden abrir el certificado.</p></div>
          <span class="count-pill">{{ avisosAusencia.length }} avisos</span>
        </div>
        <div class="absence-list">
          <article v-for="avisoEquipo in avisosAusencia" :key="avisoEquipo.id" class="absence-card notice-message">
            <div class="avatar notice-avatar">{{ avisoEquipo.usuario_nombre.slice(0, 1).toUpperCase() }}</div>
            <div class="notice-content">
              <div class="absence-card-heading"><div><strong>{{ avisoEquipo.usuario_nombre }}</strong><span>{{ avisoEquipo.motivo === 'enfermedad' ? 'Avisó que está enfermo/a' : 'Avisó que faltará' }}</span></div><time>{{ horaLegible(avisoEquipo.creado_en) }} · {{ avisoEquipo.fecha_inicio }} — {{ avisoEquipo.fecha_fin }}</time></div>
              <p v-if="avisoEquipo.detalle">{{ avisoEquipo.detalle }}</p>
              <span v-if="avisoEquipo.tiene_certificado && !avisoEquipo.puede_ver_certificado" class="certificate-private">Certificado privado para el encargado y quien publicó el aviso</span>
              <button v-if="avisoEquipo.tiene_certificado && avisoEquipo.puede_ver_certificado" class="button button-small" @click="void verCertificado(avisoEquipo)">Ver {{ avisoEquipo.certificado_nombre || 'certificado' }}</button>
            </div>
          </article>
          <div v-if="!avisosAusencia.length" class="empty-card">Todavía no hay avisos. Este canal es solo para las personas de {{ equipoActivo?.nombre }}.</div>
        </div>
        <form class="absence-create notice-composer" @submit.prevent="crearAvisoAusencia">
          <span class="section-kicker">NUEVO AVISO</span>
          <label class="field">Tipo de aviso<select v-model="formularioAusencia.motivo"><option value="ausencia">Voy a faltar</option><option value="enfermedad">Estoy enfermo/a</option></select></label>
          <div class="notice-dates"><label class="field">Desde<input v-model="formularioAusencia.fecha_inicio" type="date" required></label><label class="field">Hasta<input v-model="formularioAusencia.fecha_fin" type="date" required></label></div>
          <label class="field absence-detail">Mensaje<textarea v-model="formularioAusencia.detalle" maxlength="1000" rows="3" placeholder="Escribe un mensaje breve para el encargado"></textarea></label>
          <label class="field absence-file">Certificado o imagen (opcional)<input type="file" accept="image/png,image/jpeg,image/webp" @change="seleccionarCertificado"><small>PNG, JPG o WEBP · máximo 5 MB. Solo tú y el administrador podrán abrirlo.</small></label>
          <button class="button button-accent" type="submit">Publicar aviso</button>
        </form>
      </section>

      <section v-else-if="pantalla === 'equipo' && vistaEquipo === 'archivos'" class="content-scroll files-view">
        <div class="personal-heading">
          <div><span class="section-kicker">ARCHIVOS COMPARTIDOS</span><h2>{{ equipoActivo?.nombre }}</h2><p>Documentos y archivos disponibles para los miembros de este servidor.</p></div>
          <span class="count-pill">{{ archivosEquipo.length }} archivos</span>
        </div>
        <form class="file-upload-card" @submit.prevent="subirArchivoEquipo">
          <span class="section-kicker">COMPARTIR CON EL SERVIDOR</span>
          <label class="field">Selecciona un documento o archivo<input type="file" @change="seleccionarArchivoEquipo"><small>Word, PowerPoint, PDF, ZIP y otros formatos · máximo 20 MB.</small></label>
          <button class="button button-accent" type="submit" :disabled="!archivoEquipoSeleccionado">Subir archivo</button>
        </form>
        <div class="shared-files">
          <article v-for="archivo in archivosEquipo" :key="archivo.id" class="shared-file-card">
            <span class="file-icon">{{ archivo.nombre.split('.').pop()?.slice(0, 4).toUpperCase() || 'FILE' }}</span>
            <div class="shared-file-meta"><strong>{{ archivo.nombre }}</strong><span>{{ archivo.usuario_nombre }} · {{ tamanoLegible(archivo.tamano) }} · {{ horaLegible(archivo.creado_en) }}</span></div>
            <button class="button button-small" @click="void descargarArchivoEquipo(archivo)">Descargar</button>
          </article>
          <div v-if="!archivosEquipo.length" class="empty-card">Aún no hay archivos compartidos. Sube el primero para tu servidor.</div>
        </div>
      </section>

      <section v-else-if="pantalla === 'github'" class="content-scroll github-view">
        <article class="github-card">
          <span class="section-kicker">REPOSITORIOS PÚBLICOS</span>
          <h2>{{ cuentaGitHub ? 'GitHub conectado' : 'Conecta GitHub' }}</h2>
          <p>Explora y descarga repositorios públicos como ZIP. También puedes publicar un proyecto ZIP como un nuevo repositorio público; Nexus no solicita acceso a repositorios privados.</p>
          <div v-if="cuentaGitHub" class="github-profile">
            <img :src="cuentaGitHub.avatar_url" alt="" class="github-avatar">
            <div><strong>@{{ cuentaGitHub.github_login }}</strong><a :href="cuentaGitHub.profile_url" target="_blank" rel="noopener noreferrer">Abrir perfil de GitHub ↗</a></div>
            <button class="button button-small button-secondary" @click="conectarGitHub">{{ cuentaGitHub.permisos_repositorios ? 'Actualizar permisos' : 'Autorizar repositorios públicos' }}</button>
            <button class="button button-small" @click="desconectarGitHub">Desconectar</button>
          </div>
          <button v-else class="button button-accent" @click="conectarGitHub">Conectar y autorizar repositorios públicos</button>
        </article>
        <form v-if="cuentaGitHub?.permisos_repositorios" class="repo-upload-card" @submit.prevent="publicarRepositorio">
          <div><span class="section-kicker">PUBLICA UN PROYECTO</span><h2>Subir un repositorio</h2><p>El ZIP se publicará en un repositorio público nuevo, sin modificar proyectos existentes.</p></div>
          <label class="field">Nombre del repositorio<input v-model="formularioRepositorio.nombre" required maxlength="100" pattern="[A-Za-z0-9._-]+" placeholder="mi-proyecto"></label>
          <label class="field">Descripción (opcional)<input v-model="formularioRepositorio.descripcion" maxlength="350" placeholder="De qué trata el proyecto"></label>
          <label class="field">Proyecto ZIP<input type="file" accept=".zip,application/zip" required @change="seleccionarZipRepositorio"><small>Hasta 15 MB comprimidos, 100 archivos y 50 MB descomprimidos.</small></label>
          <button class="button button-accent" type="submit" :disabled="trabajando || !archivoRepositorio">{{ trabajando ? 'Publicando…' : 'Crear repositorio público' }}</button>
        </form>
        <div v-if="cuentaGitHub?.permisos_repositorios" class="repository-grid">
          <div class="section-title-row"><div><span class="section-kicker">TU CUENTA</span><h2>Repositorios</h2></div><span class="count-pill">{{ repositoriosGitHub.length }}</span></div>
          <article v-for="repositorio in repositoriosGitHub" :key="repositorio.full_name" class="repository-card">
            <div class="repository-card-heading"><span class="repo-mark">⌘</span><div><a :href="repositorio.html_url" target="_blank" rel="noopener noreferrer">{{ repositorio.full_name }}</a><span>{{ repositorio.language || 'Repositorio público' }} · ★ {{ repositorio.stargazers_count }}</span></div></div>
            <p>{{ repositorio.description || 'Sin descripción.' }}</p>
            <div class="repository-card-footer"><span>Actualizado {{ repositorio.updated_at ? new Date(repositorio.updated_at).toLocaleDateString('es') : 'recientemente' }}</span><button class="button button-small" @click="void descargarRepositorio(repositorio)">Descargar ZIP</button></div>
          </article>
          <div v-if="!repositoriosGitHub.length" class="empty-card">No se encontraron repositorios públicos en esta cuenta.</div>
        </div>
      </section>

      <section v-else-if="pantalla === 'perfil'" class="content-scroll profile-view">
        <div class="page-intro">
          <span class="section-kicker">TU ESPACIO, TU IDENTIDAD</span>
          <h2>Un perfil que se siente tuyo.</h2>
          <p>Tu nombre y foto se guardan para que tus contactos y equipos te reconozcan.</p>
        </div>
        <form class="profile-editor" @submit.prevent="guardarPerfil">
          <div class="profile-picture-field">
            <span class="avatar profile-picture-preview">
              <img v-if="vistaPreviaFoto || fotosPerfil[usuario.id]" :src="vistaPreviaFoto || fotosPerfil[usuario.id]" alt="Vista previa de tu foto de perfil">
              <span v-else>{{ perfilNombre.slice(0, 1).toUpperCase() || 'N' }}</span>
            </span>
            <div class="profile-picture-copy">
              <strong>Tu foto</strong>
              <span>PNG, JPG o WEBP · hasta 2 MB</span>
              <label class="button button-light upload-photo-button">
                Elegir foto
                <input type="file" accept="image/png,image/jpeg,image/webp" @change="seleccionarFotoPerfil">
              </label>
              <button v-if="vistaPreviaFoto || fotosPerfil[usuario.id]" class="text-button" type="button" @click="quitarFotoPerfil">Quitar foto</button>
            </div>
          </div>
          <label class="field">Nombre para mostrar<input v-model="perfilNombre" required maxlength="120" autocomplete="name" placeholder="Cómo quieres que te llamen"></label>
          <label class="field">Correo de tu cuenta<input :value="usuario.correo" readonly type="email"><small>El correo se usa para iniciar sesión y enviar solicitudes de contacto.</small></label>
          <div class="profile-save-row">
            <span>Los cambios se guardan en tu cuenta.</span>
            <button class="button button-accent" type="submit" :disabled="trabajando || !perfilNombre.trim()">{{ trabajando ? 'Guardando…' : 'Guardar perfil' }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="pantalla === 'contactos'" class="content-scroll contacts-view">
        <div class="page-intro contacts-intro">
          <div><span class="section-kicker">TU CÍRCULO DE TRABAJO</span><h2>Las buenas ideas se hacen en compañía.</h2><p>Envía una invitación por correo. El contacto aparecerá en tu red cuando la otra persona la acepte.</p></div>
          <span class="contacts-total">{{ contactosEspacio.contactos.length }}<small>contactos</small></span>
        </div>
        <form class="contact-invite-card" @submit.prevent="solicitarContacto">
          <span class="invite-symbol">＋</span>
          <label class="field">Invitar a alguien<input v-model="correoContacto" type="email" required maxlength="254" autocomplete="email" placeholder="correo@ejemplo.com"></label>
          <button class="button button-accent" type="submit" :disabled="trabajando || !correoContacto.trim()">{{ trabajando ? 'Enviando…' : 'Enviar invitación' }}</button>
        </form>

        <section v-if="contactosEspacio.recibidas.length" class="contact-section">
          <div class="section-title-row"><div><span class="section-kicker">ESPERAN TU RESPUESTA</span><h2>Invitaciones recibidas</h2></div><span class="count-pill">{{ contactosEspacio.recibidas.length }}</span></div>
          <div class="contact-card-grid">
            <article v-for="solicitud in contactosEspacio.recibidas" :key="solicitud.id" class="person-card request-card">
              <span class="avatar person-avatar">
                <img v-if="fotosPerfil[solicitud.usuario_id]" :src="fotosPerfil[solicitud.usuario_id]" alt="">
                <span v-else>{{ solicitud.nombre.slice(0, 1).toUpperCase() }}</span>
              </span>
              <div class="person-copy"><strong>{{ solicitud.nombre }}</strong><span>{{ solicitud.correo }}</span><small>Te invitó a conectar</small></div>
              <div class="request-actions">
                <button class="button button-small" @click="void responderContacto(solicitud.id, 'aceptar')">Aceptar</button>
                <button class="button button-small button-light" @click="void responderContacto(solicitud.id, 'rechazar')">Ahora no</button>
              </div>
            </article>
          </div>
        </section>

        <section v-if="contactosEspacio.enviadas.length" class="contact-section">
          <div class="section-title-row"><div><span class="section-kicker">EN CAMINO</span><h2>Invitaciones enviadas</h2></div><span class="count-pill">{{ contactosEspacio.enviadas.length }}</span></div>
          <div class="contact-card-grid">
            <article v-for="solicitud in contactosEspacio.enviadas" :key="solicitud.id" class="person-card pending-card">
              <span class="avatar person-avatar">
                <img v-if="fotosPerfil[solicitud.usuario_id]" :src="fotosPerfil[solicitud.usuario_id]" alt="">
                <span v-else>{{ solicitud.nombre.slice(0, 1).toUpperCase() }}</span>
              </span>
              <div class="person-copy"><strong>{{ solicitud.nombre }}</strong><span>{{ solicitud.correo }}</span><small>Esperando a que acepte</small></div>
              <span class="pending-mark">Pendiente</span>
            </article>
          </div>
        </section>

        <section class="contact-section">
          <div class="section-title-row"><div><span class="section-kicker">CONECTADOS CONTIGO</span><h2>Tu gente</h2></div><span class="count-pill">{{ contactosEspacio.contactos.length }}</span></div>
          <div v-if="contactosEspacio.contactos.length" class="contact-card-grid">
            <article v-for="contacto in contactosEspacio.contactos" :key="contacto.id" class="person-card">
              <span class="avatar person-avatar">
                <img v-if="fotosPerfil[contacto.id]" :src="fotosPerfil[contacto.id]" alt="">
                <span v-else>{{ contacto.nombre.slice(0, 1).toUpperCase() }}</span>
              </span>
              <div class="person-copy"><strong>{{ contacto.nombre }}</strong><span>{{ contacto.correo }}</span><small>En tu red de contactos</small></div>
              <button class="icon-button remove-contact-button" :aria-label="`Quitar a ${contacto.nombre} de tus contactos`" title="Quitar contacto" @click="void eliminarContacto(contacto.solicitud_id, contacto.nombre)">×</button>
            </article>
          </div>
          <div v-else class="empty-card contacts-empty">Todavía no hay contactos. Envía una invitación: cuando la acepten, aparecerá aquí.</div>
        </section>
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
            <button
              class="task-delete"
              :aria-label="`Eliminar ${tarea.titulo}`"
              title="Eliminar tarea"
              @click="void eliminarTarea(tarea)"
            >×</button>
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
          <div class="section-title-row">
            <div><span class="section-kicker">AGREGAR AL CALENDARIO</span><h3>{{ formularioAgenda.fecha || 'Elige un día' }}</h3></div>
            <button class="button button-small button-light" type="button" @click="crearTareaDesdeCalendario">＋ Crear tarea o proyecto</button>
          </div>
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
          <p class="calendar-legend"><span class="legend-dot personal"></span> Personal <span class="legend-dot team"></span> Equipos · Al crear una tarea o proyecto con fecha, aparece aquí automáticamente.</p>
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
:global(body) { margin: 0; min-width: 320px; background: #f3f5fb; color: #23283c; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
:global(button), :global(input), :global(select), :global(textarea) { font: inherit; }
.loading-screen { min-height: 100vh; display: grid; place-content: center; justify-items: center; gap: 14px; color: #89909a; background: #f8f9fb; }
.brand-mark { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 14px; color: white; background: linear-gradient(135deg, #4775d4, #7562d8); font-size: 1.25rem; font-weight: 800; }
.auth-page { min-height: 100vh; display: grid; grid-template-columns: minmax(320px, 1.05fr) minmax(400px, .95fr); background: #fff; }
.auth-decoration { position: relative; display: flex; flex-direction: column; justify-content: space-between; min-height: 100vh; overflow: hidden; padding: 44px clamp(32px, 7vw, 100px); color: white; background: radial-gradient(ellipse at 78% 22%, #7270e7 0, transparent 38%), linear-gradient(150deg, #1d3156, #344a82 55%, #574d9e); }
.auth-brand { display: flex; align-items: center; gap: 12px; font-size: .86rem; font-weight: 800; letter-spacing: .2em; }
.theme-control { display: flex; align-items: center; gap: 7px; color: #828b9a; font-size: .68rem; font-weight: 700; letter-spacing: 0; }
.theme-control select { border: 1px solid #dfe4ed; border-radius: 8px; padding: 7px 24px 7px 9px; color: #4f5b70; background: #fff; font-size: .72rem; cursor: pointer; }
.auth-theme-control { margin-left: auto; color: #e0dcff; }
.auth-theme-control select { border-color: #ffffff3d; color: white; background: #ffffff1c; }
.auth-theme-control option { color: #30364a; }
.auth-brand .brand-mark { width: 36px; height: 36px; border-radius: 12px; color: #fff; background: linear-gradient(135deg, #7188ef, #a18ae8); }
.auth-copy { position: relative; z-index: 1; max-width: 510px; padding: 40px 0; }
.auth-art { position: absolute; right: clamp(18px, 5vw, 72px); bottom: 17%; width: min(34%, 330px); opacity: .96; pointer-events: none; }
.auth-art svg { display: block; width: 100%; overflow: visible; }
.art-orbit { transform-origin: 171px 133px; animation: orbit-turn 32s linear infinite; }
.art-card { filter: drop-shadow(0 12px 15px #11152b32); }
.art-card-main { transform-origin: 161px 120px; animation: art-float 6s ease-in-out infinite; }
.art-card-note { transform-origin: 243px 179px; animation: art-float-side 5s ease-in-out infinite; }
.art-card-check { transform-origin: 60px 115px; animation: art-float-side 5.8s ease-in-out -1.5s infinite; }
.auth-kicker, .section-kicker { color: #8d8aa2; font-size: .68rem; font-weight: 800; letter-spacing: .15em; }
.auth-decoration .auth-kicker { color: #d2c9ff; }
.auth-copy h1 { margin: 18px 0; font-size: clamp(2.8rem, 5vw, 4.6rem); line-height: 1.06; letter-spacing: -.06em; }
.auth-copy p { max-width: 380px; color: #d0cee3; font-size: 1.05rem; line-height: 1.7; }
.auth-footnote { color: #c1bddc; font-size: .78rem; }
.auth-form-wrap { display: grid; place-items: center; padding: 44px 28px; }
.auth-form { display: grid; width: min(100%, 390px); gap: 17px; animation: settle-in .45s cubic-bezier(.2,.8,.2,1) both; }
.auth-form h2 { margin: 2px 0 -10px; color: #28263f; font-size: 2rem; letter-spacing: -.04em; }
.auth-hint { margin: 0 0 7px; color: #81818e; font-size: .92rem; line-height: 1.5; }
.field { display: grid; min-width: 0; gap: 7px; color: #555664; font-size: .78rem; font-weight: 700; }
.field input, .field select, .field textarea { width: 100%; min-width: 0; border: 1px solid #e0e1e8; border-radius: 9px; outline: none; padding: 11px 12px; color: #252637; background: #fff; font-size: .86rem; font-weight: 400; }
.field textarea { resize: vertical; }
.field input:focus, .field select:focus, .field textarea:focus { border-color: #807be4; box-shadow: 0 0 0 3px #eeedff; }
.button { border: 0; border-radius: 9px; padding: 11px 15px; color: #fff; background: linear-gradient(120deg, #4d73ca, #7061d2); font-size: .84rem; font-weight: 750; cursor: pointer; transition: background .16s, transform .16s; }
.button:hover:not(:disabled) { transform: translateY(-1px); background: linear-gradient(120deg, #3d63b9, #5c51bf); }
.button:disabled { cursor: not-allowed; opacity: .56; }
.button-accent { padding: 13px 16px; }
.switch-auth { margin: 3px 0 0; color: #777987; font-size: .83rem; text-align: center; }
.switch-auth button { border: 0; padding: 0 0 0 4px; color: #5e59c3; background: none; font-weight: 750; cursor: pointer; }
.feedback { margin: 0; color: #3e805d; font-size: .83rem; }
.feedback-error { color: #b44c58; }
.app-shell { display: grid; grid-template-columns: 70px 244px minmax(0, 1fr); width: 100%; height: 100vh; overflow: hidden; background: #f8f9fd; }
.server-rail { display: flex; flex-direction: column; align-items: center; gap: 11px; padding: 16px 0; background: #e9edf7; }
.rail-logo, .server-icon, .server-create, .avatar { display: grid; flex-shrink: 0; place-items: center; border: 0; cursor: pointer; }
.rail-logo, .server-icon, .server-create { width: 44px; height: 44px; border-radius: 15px; font-weight: 800; transition: border-radius .16s, background .16s; }
.rail-logo { color: #fff; background: linear-gradient(135deg, #4c74d1, #7262d5); font-size: 1.15rem; }
.server-icon { color: #575a66; background: #fff; font-size: .77rem; }
.server-icon:hover, .server-icon.selected { border-radius: 13px; color: #fff; background: linear-gradient(135deg, #4d75d2, #7664d8); }
.rail-divider { width: 30px; height: 2px; border-radius: 2px; background: #d9dae2; }
.server-create { color: #4b9a73; background: #fff; font-size: 1.5rem; }
.server-create:hover { border-radius: 13px; color: #fff; background: #4caa79; }
.rail-spacer { flex: 1; }
.avatar { width: 34px; height: 34px; border-radius: 50%; color: #48436f; background: #e7e4ff; font-weight: 800; }
.avatar-rail { width: 42px; height: 42px; }
.channel-sidebar { position: relative; display: flex; min-width: 0; flex-direction: column; padding: 23px 12px 12px; background: #f5f7fc; border-right: 1px solid #e3e8f2; }
.side-title { display: flex; align-items: center; justify-content: space-between; padding: 0 7px; color: #9697a2; font-size: .65rem; font-weight: 850; letter-spacing: .12em; }
.icon-button { display: grid; width: 28px; height: 28px; place-items: center; border: 0; border-radius: 7px; color: #848591; background: transparent; font-size: 1.05rem; cursor: pointer; }
.icon-button:hover { color: #514db2; background: #ecebfa; }
.side-link { display: flex; align-items: center; gap: 11px; width: 100%; margin-top: 8px; border: 0; border-radius: 8px; padding: 10px 9px; color: #686a76; background: transparent; font-size: .84rem; text-align: left; cursor: pointer; }
.side-link:hover, .side-link.active { color: #425fb8; background: #e9edfb; }
.side-link-icon { width: 19px; color: #8c8e9b; font-size: 1.1rem; text-align: center; }
.side-link.active .side-link-icon { color: #625dcc; }
.team-title { margin-top: 28px; }
.team-list { display: grid; gap: 3px; margin-top: 9px; }
.team-link { display: flex; align-items: center; gap: 8px; width: 100%; border: 0; border-radius: 7px; padding: 9px 8px; color: #757682; background: transparent; font-size: .82rem; text-align: left; cursor: pointer; }
.team-link:hover, .team-link.active { color: #425fb8; background: #e9edfb; }
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
.main-panel { display: flex; min-width: 0; flex-direction: column; background: #fcfdff; }
.topbar { position: relative; display: flex; min-height: 78px; align-items: center; justify-content: space-between; gap: 14px; border-bottom: 1px solid #e4e9f3; padding: 12px 25px; background: #fff; }
.topbar-heading { display: flex; min-width: 0; align-items: center; gap: 12px; }
.top-hash, .top-icon { color: #9394a0; font-size: 1.45rem; }
.topbar-heading h1 { overflow: hidden; margin: 0; color: #343541; font-size: .99rem; text-overflow: ellipsis; white-space: nowrap; }
.topbar-heading p { overflow: hidden; margin: 4px 0 0; color: #9697a2; font-size: .72rem; text-overflow: ellipsis; white-space: nowrap; }
.topbar-actions, .user-menu { display: flex; flex-shrink: 0; align-items: center; gap: 8px; }
.tab-button { border: 0; border-radius: 7px; padding: 8px 10px; color: #777986; background: transparent; font-size: .76rem; cursor: pointer; }
.tab-button.chosen { color: #405fae; background: #eaf0ff; font-weight: 750; }
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
.task-delete { display: grid; width: 30px; height: 30px; flex: 0 0 30px; place-items: center; border: 0; border-radius: 8px; color: #9aa2af; background: transparent; font-size: 1.2rem; cursor: pointer; }
.task-delete:hover { color: #b3485b; background: #fff0f1; }
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
.absence-view, .files-view, .github-view { max-width: 980px; width: 100%; margin: 0 auto; }
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
.notice-composer { grid-template-columns: 1fr; margin-top: 22px; border-color: #dfe5f3; background: #f7f9fe; }
.notice-composer > .section-kicker { grid-column: 1 / -1; }
.notice-composer .absence-detail, .notice-composer .absence-file { grid-column: auto; }
.notice-dates { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.notice-message { grid-template-columns: 38px minmax(0, 1fr); align-items: start; border-color: #e5eaf4; box-shadow: 0 3px 12px #31446a0a; }
.notice-avatar { color: #fff; background: linear-gradient(135deg, #537bd2, #8370d8); }
.notice-content { display: grid; min-width: 0; gap: 9px; }
.notice-content .absence-card-heading { align-items: flex-start; }
.notice-content .absence-card-heading time { text-align: right; }
.certificate-private { width: fit-content; border-radius: 999px; padding: 5px 8px; color: #596887; background: #eef2f8; font-size: .66rem; }
.files-view { max-width: 940px; }
.file-upload-card, .repo-upload-card { display: grid; gap: 14px; border: 1px solid #e2e7f1; border-radius: 14px; padding: 20px; background: linear-gradient(145deg, #f8faff, #f7f6ff); }
.file-upload-card { grid-template-columns: minmax(0, 1fr) auto; align-items: end; }
.file-upload-card > .section-kicker { grid-column: 1 / -1; }
.file-upload-card .field small, .repo-upload-card .field small { color: #858ca0; font-size: .68rem; font-weight: 400; }
.shared-files { display: grid; gap: 9px; margin-top: 20px; }
.shared-file-card { display: flex; min-width: 0; align-items: center; gap: 12px; border: 1px solid #e7ebf3; border-radius: 12px; padding: 12px; background: #fff; }
.file-icon { display: grid; width: 42px; height: 46px; flex: 0 0 42px; place-items: center; overflow: hidden; border-radius: 9px; color: #4d63ad; background: #edf1fc; font-size: .58rem; font-weight: 850; }
.shared-file-meta { display: grid; min-width: 0; flex: 1; gap: 4px; }
.shared-file-meta strong { overflow: hidden; color: #41485a; font-size: .8rem; text-overflow: ellipsis; white-space: nowrap; }
.shared-file-meta span { color: #878fa2; font-size: .68rem; }
.github-view { max-width: 1020px; }
.github-card { width: 100%; margin: 0 auto 18px; border-color: #e4e8f2; border-radius: 14px; background: linear-gradient(145deg, #fff, #f8f9ff); box-shadow: 0 8px 24px #25365f0c; }
.github-card h2, .repo-upload-card h2, .repository-grid h2 { color: #303a53; }
.github-card .section-kicker, .repo-upload-card .section-kicker, .repository-grid .section-kicker { color: #6578b8; }
.github-profile { flex-wrap: wrap; }
.github-profile a, .repository-card-heading a { color: #4c67bc; }
.button-secondary { color: #4f62a3; background: #edf1fc; }
.button-secondary:hover:not(:disabled) { color: #fff; background: #556fbd; }
.repo-upload-card { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: end; background: #f7f8fd; }
.repo-upload-card > div, .repo-upload-card > .field:nth-of-type(3), .repo-upload-card > .button { grid-column: 1 / -1; }
.repo-upload-card h2 { margin: 5px 0; font-size: 1.15rem; }
.repo-upload-card p { margin: 0; color: #858ca0; font-size: .76rem; line-height: 1.5; }
.repository-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 25px; }
.repository-grid > .section-title-row, .repository-grid > .empty-card { grid-column: 1 / -1; }
.repository-grid > .section-title-row { margin-bottom: 3px; }
.repository-card { display: grid; min-width: 0; gap: 13px; border: 1px solid #e3e8f2; border-radius: 12px; padding: 15px; background: #fff; box-shadow: 0 4px 15px #28395f0a; }
.repository-card-heading { display: flex; min-width: 0; align-items: center; gap: 10px; }
.repository-card-heading > div { display: grid; min-width: 0; gap: 4px; }
.repository-card-heading a { overflow: hidden; font-size: .78rem; font-weight: 750; text-decoration: none; text-overflow: ellipsis; white-space: nowrap; }
.repository-card-heading a:hover { text-decoration: underline; }
.repository-card-heading span:last-child, .repository-card-footer > span { color: #8790a3; font-size: .65rem; }
.repo-mark { display: grid; width: 34px; height: 34px; flex: 0 0 34px; place-items: center; border-radius: 10px; color: #5c63b8; background: #eff0fc; }
.repository-card > p { min-height: 2.4em; margin: 0; color: #656f82; font-size: .75rem; line-height: 1.5; }
.repository-card-footer { display: flex; align-items: center; justify-content: space-between; gap: 8px; border-top: 1px solid #edf0f6; padding-top: 10px; }
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
  .repository-grid { grid-template-columns: 1fr; }
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
  .notice-dates, .repo-upload-card { grid-template-columns: 1fr; }
  .repo-upload-card > div, .repo-upload-card > .field:nth-of-type(3), .repo-upload-card > .button { grid-column: auto; }
  .file-upload-card { grid-template-columns: 1fr; }
  .file-upload-card > .section-kicker { grid-column: auto; }
  .github-card { padding: 20px; }
  .github-profile { align-items: flex-start; }
  .github-profile > div { min-width: calc(100% - 60px); }
  .shared-file-card { flex-wrap: wrap; }
  .shared-file-card .button { margin-left: auto; }
  .notice-content .absence-card-heading time { text-align: left; }
  .day-cell { min-height: 72px; padding: 4px 2px; }
  .weekday { font-size: .61rem; }
  .calendar-event { font-size: .52rem; padding: 2px; }
  .agenda-form { grid-template-columns: 1fr 1fr; }
  .agenda-form .button { grid-column: 1 / -1; }
  .calendar-toolbar h2 { font-size: 1.16rem; }
}

:global(:root) {
  color-scheme: light;
  --ink: #222c3e;
  --ink-muted: #647086;
  --soft-muted: #8993a5;
  --line: #e4e8ef;
  --paper: #f4f6fa;
  --white: #fff;
  --blue: #486cbd;
  --violet: #7965ba;
  --sea: #438f85;
  --shadow-soft: 0 10px 30px #293b5812;
  font-family: Inter, "Segoe UI", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}

:global(body) { min-height: 100vh; background: #edf1f6; color: var(--ink); }
:global(button), :global(a), :global(input), :global(textarea), :global(select) {
  -webkit-tap-highlight-color: transparent;
}
:global(button) {
  transition:
    color .2s ease,
    background-color .2s ease,
    border-color .2s ease,
    box-shadow .22s ease,
    transform .22s cubic-bezier(.2,.8,.2,1),
    opacity .2s ease;
}
:global(button:not(:disabled):hover) { transform: translateY(-1px); }
:global(button:not(:disabled):active) { transform: translateY(0) scale(.98); }
:global(:focus-visible) { outline: 3px solid #7897e77a; outline-offset: 3px; }
:global(*) { scrollbar-color: #c8d1df transparent; scrollbar-width: thin; }

.app-shell { grid-template-columns: 266px minmax(0, 1fr); background: var(--paper); }
.channel-sidebar {
  z-index: 2;
  gap: 9px;
  padding: 23px 18px 16px;
  border-right: 1px solid #e3e7ef;
  background:
    radial-gradient(ellipse at 4% 0%, #e8edf8 0, transparent 38%),
    #f8f9fc;
}
.workspace-brand { display: flex; align-items: center; gap: 11px; margin: 0 0 25px; border: 0; padding: 0 4px; background: transparent; text-align: left; cursor: pointer; }
.workspace-brand .brand-mark { width: 44px; height: 44px; border-radius: 16px; background: linear-gradient(145deg, #4b76b8, #7868b8); box-shadow: 0 7px 17px #6379ae38; }
.workspace-brand:hover .brand-mark { transform: rotate(-7deg) scale(1.06); box-shadow: 0 10px 24px #6379ae55; }
.brand-copy { display: grid; gap: 3px; }
.brand-copy strong { color: #28354a; font-family: Georgia, "Times New Roman", serif; font-size: 1.3rem; letter-spacing: -.04em; }
.brand-copy small, .sidebar-caption { color: #8993a5; font-size: .6rem; font-weight: 800; letter-spacing: .14em; }
.sidebar-caption { padding: 0 10px; }
.workspace-nav { display: grid; gap: 5px; }
.side-link {
  position: relative;
  gap: 12px;
  min-height: 43px;
  margin-top: 0;
  border-radius: 10px;
  padding: 9px 11px;
  color: #667287;
  font-size: .82rem;
  font-weight: 550;
}
.side-link:hover { color: #3d5e9f; background: #edf1f7; }
.side-link:hover .side-link-icon { transform: translateY(-1px) scale(1.08); color: var(--blue); }
.side-link.active { color: #3c5ea1; background: #e9eef7; font-weight: 750; }
.side-link.active::before { position: absolute; inset: 9px auto 9px 0; width: 3px; border-radius: 4px; background: linear-gradient(#5380bd, #8270ba); content: ""; }
.side-link-icon { width: 22px; color: #8b96a8; transition: color .2s, transform .2s; }
.nav-count { display: grid; min-width: 20px; height: 20px; place-items: center; margin-left: auto; border-radius: 20px; color: #fff; background: #6482b8; font-size: .64rem; }
.team-section { display: flex; min-height: 0; flex: 1; flex-direction: column; margin-top: 15px; }
.team-title { margin-top: 0; padding: 0 8px; color: #8a95a7; }
.team-list { gap: 4px; margin-top: 8px; overflow: auto; }
.team-link { min-height: 40px; border-radius: 9px; padding: 6px 8px; color: #69758a; }
.team-link:hover, .team-link.active { color: #3e5e9a; background: #eaf0f8; }
.team-symbol { display: grid; width: 27px; height: 27px; flex: 0 0 27px; place-items: center; border: 1px solid #dfe6f0; border-radius: 9px; color: #5a719f; background: #fff; font-size: .67rem; font-weight: 800; }
.team-link.active .team-symbol { border-color: transparent; color: #fff; background: linear-gradient(145deg, #6387bd, #8273ba); }
.team-link small { color: #9ba4b3; }
.sidebar-empty { margin: 11px 9px; color: #858fa1; }
.create-server-link { min-height: 39px; margin: 7px 0 0; border: 1px dashed #d8deea; border-radius: 9px; padding: 8px 10px; color: #6179a4; background: #fff; font-size: .75rem; }
.create-server-link:hover { border-color: #aab8d1; background: #f2f5fa; }
.profile-card { flex: 0 0 auto; gap: 10px; margin-top: auto; border: 1px solid #e4e8ef; border-radius: 13px; padding: 11px 9px; background: #fff; box-shadow: 0 3px 13px #293b580a; }
.avatar { overflow: hidden; background: linear-gradient(145deg, #e6ecf6, #ece8f5); }
.avatar img { display: block; width: 100%; height: 100%; border-radius: inherit; object-fit: cover; }
.profile-avatar { cursor: pointer; }
.profile-copy { border: 0; padding: 0; background: transparent; text-align: left; cursor: pointer; }
.profile-copy strong { color: #344258; }
.profile-copy small { color: #8994a6; }
.logout-button:hover { color: #a85f69; background: #fff0f0; }
.main-panel { min-height: 0; background: #f4f6fa; }
.topbar { z-index: 1; min-height: 86px; border-color: #e5e9f0; padding: 15px clamp(18px, 3vw, 42px); box-shadow: 0 2px 8px #25344a06; }
.topbar-heading { gap: 15px; }
.top-icon { display: grid; width: 41px; height: 41px; flex: 0 0 41px; place-items: center; border: 1px solid #e2e7ef; border-radius: 14px; color: #5873a2; background: #f4f7fc; font-size: 1.08rem; }
.topbar-heading h1 { color: #273449; font-family: Georgia, "Times New Roman", serif; font-size: 1.2rem; letter-spacing: -.025em; }
.topbar-heading p { color: #8791a2; font-size: .73rem; }
.topbar-actions { gap: 5px; }
.tab-button { border-radius: 8px; padding: 9px 11px; color: #758196; }
.tab-button:hover { color: #3d5c94; background: #f0f3f8; }
.tab-button.chosen { color: #3f609b; background: #e9eef7; }
.invite-form input { border-color: #e0e5ed; border-radius: 8px; }
.top-profile { display: flex; align-items: center; gap: 9px; border: 0; padding: 4px 7px; color: #6b778a; background: transparent; font-size: .75rem; cursor: pointer; }
.top-profile:hover { color: #3c5e9b; }
.top-profile .avatar { width: 35px; height: 35px; }
.notification-button { border-color: #e5e9f0; color: #6078a1; }
.notification-button:hover { border-color: #c9d4e5; background: #f4f6fb; }
.content-scroll { padding: clamp(24px, 4vw, 48px) clamp(20px, 5vw, 64px) 56px; animation: settle-in .36s ease both; }
.content-scroll > * { animation: settle-in .42s ease both; }
.personal-heading h2, .calendar-toolbar h2, .task-create-card h2 { color: #29364b; font-family: Georgia, "Times New Roman", serif; font-weight: 600; }
.personal-heading p, .calendar-toolbar p { color: #818da0; }
.section-kicker { color: #6680a9; }
.field { color: #526075; }
.field input, .field select, .field textarea { border-color: #dfe5ee; border-radius: 10px; color: #29374b; background: #fff; transition: border-color .2s, box-shadow .2s, background .2s; }
.field input:hover, .field select:hover, .field textarea:hover { border-color: #c2ccdc; }
.field input:focus, .field select:focus, .field textarea:focus { border-color: #7691bd; box-shadow: 0 0 0 3px #e6ecf6; }
.button { border-radius: 10px; background: linear-gradient(120deg, #5277ae, #7569ad); box-shadow: 0 5px 13px #5974a52e; }
.button:hover:not(:disabled) { background: linear-gradient(120deg, #446a9f, #655996); box-shadow: 0 8px 18px #536b9e38; }
.button:active:not(:disabled) { box-shadow: 0 2px 6px #536b9e22; }
.button-light { border: 1px solid #e1e6ee; color: #5e6c80; background: #fff; box-shadow: none; }
.button-light:hover:not(:disabled) { border-color: #c6d0df; color: #405d8a; background: #f4f6f9; box-shadow: 0 4px 11px #293b5810; }
.button-secondary { border: 1px solid #dce3ef; color: #506894; background: #f2f5fa; box-shadow: none; }
.task-create-card, .agenda-card, .personal-create, .absence-create, .github-card, .task-row, .task-row-area, .profile-editor, .contact-invite-card, .person-card, .file-upload-card, .repo-upload-card, .repository-card {
  border-color: #e2e7ef;
  border-radius: 15px;
  box-shadow: var(--shadow-soft);
}
.task-create-card, .agenda-card { background: #fff; }
.task-row { background: #fff; transition: transform .2s, box-shadow .2s, border-color .2s; }
.task-row:hover { transform: translateY(-2px); border-color: #d6dfec; box-shadow: 0 9px 20px #293b5810; }
.task-check:hover { border-color: #6d83ad; }
.task-check.checked { background: #519188; }
.count-pill { color: #58729f; background: #edf1f7; }
.personal-create { background: #fff; }
.chat-panel { flex-direction: row; gap: 20px; padding: 20px clamp(18px, 3vw, 42px) 25px; }
.team-chat-column { display: flex; min-width: 0; min-height: 0; flex: 1; flex-direction: column; }
.chat-history { width: 100%; align-self: stretch; }
.chat-composer { width: 100%; align-self: stretch; border-color: #dfe5ee; border-radius: 14px; background: #fff; box-shadow: 0 5px 20px #293b580d; }
.chat-composer:focus-within { border-color: #839ac0; box-shadow: 0 0 0 3px #e8edf6, 0 7px 18px #293b580d; }
.team-calendar-card { display: flex; width: min(390px, 42%); min-width: 340px; min-height: 0; flex: 0 0 min(390px, 42%); flex-direction: column; gap: 15px; overflow: hidden; border: 1px solid #e0e6ef; border-radius: 17px; padding: 18px; background: #fff; box-shadow: var(--shadow-soft); }
.team-calendar-heading, .team-calendar-toolbar, .team-calendar-agenda-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.team-calendar-heading h2 { margin: 4px 0 0; color: #29364b; font-family: Georgia, "Times New Roman", serif; font-size: 1.12rem; }
.team-calendar-heading .tab-button { flex-shrink: 0; color: #55729f; background: #f1f5fa; }
.team-calendar-heading .tab-button:hover { background: #e9eff8; }
.team-calendar-toolbar > strong { color: #35435a; font-size: .88rem; text-transform: capitalize; }
.team-calendar-toolbar .month-button, .team-calendar-toolbar .today-button { min-width: 31px; height: 30px; }
.team-calendar-grid { display: grid; min-height: 255px; flex: 0 0 255px; grid-template-columns: repeat(7, minmax(0, 1fr)); grid-auto-rows: minmax(32px, 1fr); overflow: hidden; border: 1px solid #e3e8f0; border-radius: 12px; background: #fff; }
.team-calendar-weekday { display: grid; place-items: center; color: #8090a7; background: #f4f6fa; font-size: .69rem; font-weight: 750; }
.team-calendar-day { position: relative; display: flex; min-width: 0; align-items: center; justify-content: center; gap: 3px; border: 0; border-top: 1px solid #edf0f5; border-right: 1px solid #edf0f5; color: #526078; background: #fff; font-size: .74rem; cursor: pointer; }
.team-calendar-day:hover { background: #f0f4fa; }
.team-calendar-day.outside-month { color: #b1bac8; background: #fafbfd; }
.team-calendar-day.selected-day { z-index: 1; box-shadow: inset 0 0 0 2px #7690bd; background: #eef3fa; }
.team-calendar-day.today-cell > span { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 50%; color: #fff; background: linear-gradient(145deg, #4f7fae, #7771b5); }
.team-calendar-day small { display: grid; min-width: 16px; height: 16px; place-items: center; border-radius: 999px; padding: 0 3px; color: #fff; background: #6882af; font-size: .57rem; font-weight: 750; }
.team-calendar-agenda { display: flex; min-height: 0; flex: 1; flex-direction: column; gap: 10px; }
.team-calendar-agenda-heading { padding-bottom: 8px; border-bottom: 1px solid #edf0f5; }
.team-calendar-agenda-heading strong { color: #35435a; font-size: .78rem; }
.team-calendar-agenda-heading > span { color: #8793a5; font-size: .68rem; }
.team-calendar-task-list { display: grid; min-height: 0; gap: 6px; overflow-y: auto; }
.team-calendar-task { display: flex; min-width: 0; align-items: flex-start; gap: 9px; border-radius: 9px; padding: 8px; background: #f7f8fb; }
.team-calendar-task-dot { width: 9px; height: 9px; flex: 0 0 9px; margin-top: 4px; border-radius: 50%; background: #8393ac; }
.team-calendar-task-dot.urgencia-verde { background: #59a879; }
.team-calendar-task-dot.urgencia-amarillo { background: #d6a739; }
.team-calendar-task-dot.urgencia-rojo { background: #d66169; }
.team-calendar-task-dot.urgencia-neutral, .team-calendar-task-dot.urgencia-sin-fecha { background: #9aa4b2; }
.team-calendar-task > div { display: grid; min-width: 0; gap: 4px; }
.team-calendar-task strong { overflow: hidden; color: #46536a; font-size: .72rem; text-overflow: ellipsis; white-space: nowrap; }
.team-calendar-task strong.struck { color: #929baa; text-decoration: line-through; }
.team-calendar-task small { color: #8995a6; font-size: .64rem; text-transform: capitalize; }
.team-calendar-empty { margin: 0; color: #8995a6; font-size: .72rem; line-height: 1.5; }
.send-button { background: linear-gradient(140deg, #527ab5, #796bb2); transition: transform .2s, box-shadow .2s; }
.send-button:hover:not(:disabled) { transform: translateY(-2px) rotate(-5deg); box-shadow: 0 6px 13px #526e9f50; }
.message { transition: background .18s, transform .18s; }
.message:hover { background: #f1f4f8; transform: translateX(3px); }
.welcome-hash { background: linear-gradient(145deg, #5682ae, #8273b5); }
.day-cell { background: #fff; transition: background .18s, box-shadow .18s, transform .18s; }
.day-cell:hover { position: relative; z-index: 1; background: #f1f5fb; box-shadow: inset 0 0 0 1px #d6e0ef; }
.today-cell .day-number { background: linear-gradient(145deg, #4f7fae, #7771b5); }
.calendar-grid { border-color: #e2e7ef; }
.weekday { color: #738097; background: #f0f3f8; }
.month-button, .today-button { border-color: #e1e6ee; transition: transform .2s, background .2s, color .2s; }
.month-button:hover, .today-button:hover { color: #4a689c; background: #eef2f8; }
.github-card, .repo-upload-card, .repository-card { background: #fff; }
.github-profile a, .repository-card-heading a { color: #4e6eaa; }
.absence-view, .files-view, .github-view, .contacts-view, .profile-view { max-width: 1080px; }
.absence-list { gap: 12px; }
.absence-card, .shared-file-card { border-color: #e1e6ee; border-radius: 13px; transition: transform .2s, border-color .2s, box-shadow .2s; }
.absence-card:hover, .shared-file-card:hover { transform: translateY(-2px); border-color: #cfd9e8; box-shadow: 0 8px 20px #293b5810; }
.notice-avatar { background: linear-gradient(145deg, #5e88b8, #8875b6); }
.certificate-private { color: #6c778a; background: #eff2f6; }
.file-icon { color: #536b91; background: #edf1f7; }
.repository-card:hover, .person-card:hover { transform: translateY(-3px); border-color: #cbd6e5; box-shadow: 0 13px 26px #293b5815; }
.repo-mark { color: #6573a0; background: #f0f1f8; }
.notification-panel { border-color: #e2e7ef; border-radius: 14px; box-shadow: 0 18px 40px #25344a1c; }
.notification-item { background: #f5f7fa; }
.notification-item:hover { background: #eaf0f7; }
.empty-card { border-color: #d7dee9; color: #778398; background: #f9fafc; }
.modal-backdrop { background: #25334a66; backdrop-filter: blur(5px); }
.modal-card, .certificate-modal { border: 1px solid #e1e6ef; border-radius: 19px; box-shadow: 0 24px 80px #1d2c423d; }
.toast { border-radius: 12px; box-shadow: 0 12px 32px #293b5818; animation: toast-enter .28s ease both; }
.page-intro { margin: 2px 0 26px; }
.page-intro h2 { max-width: 720px; margin: 8px 0; color: #29364b; font-family: Georgia, "Times New Roman", serif; font-size: clamp(1.8rem, 3vw, 2.55rem); font-weight: 500; letter-spacing: -.045em; line-height: 1.14; }
.page-intro p { max-width: 610px; margin: 0; color: #7a879b; font-size: .86rem; line-height: 1.7; }
.profile-editor { display: grid; width: min(100%, 680px); gap: 23px; border: 1px solid var(--line); border-radius: 18px; padding: clamp(20px, 4vw, 34px); background: #fff; box-shadow: var(--shadow-soft); }
.profile-picture-field { display: flex; align-items: center; gap: 18px; border-bottom: 1px solid #edf0f4; padding-bottom: 23px; }
.profile-picture-preview { width: 90px; height: 90px; flex: 0 0 90px; border: 4px solid #f0f3f8; color: #526993; font-size: 1.7rem; box-shadow: 0 0 0 1px #dfe5ee; }
.profile-picture-copy { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.profile-picture-copy > strong { width: 100%; color: #344258; font-size: .9rem; }
.profile-picture-copy > span, .profile-save-row > span, .profile-editor .field small { color: #8490a2; font-size: .7rem; font-weight: 400; }
.upload-photo-button { position: relative; overflow: hidden; padding: 8px 11px; cursor: pointer; font-size: .72rem; }
.upload-photo-button input { position: absolute; width: 1px; height: 1px; overflow: hidden; opacity: 0; }
.text-button { border: 0; padding: 7px; color: #7b6f82; background: transparent; font-size: .72rem; cursor: pointer; }
.text-button:hover { color: #a04e63; }
.profile-save-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; border-top: 1px solid #edf0f4; padding-top: 18px; }
.contacts-intro { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.contacts-total { display: grid; min-width: 74px; height: 74px; place-content: center; border: 1px solid #e0e6ee; border-radius: 22px; color: #516b96; background: linear-gradient(145deg, #fff, #edf1f7); font-family: Georgia, "Times New Roman", serif; font-size: 1.6rem; text-align: center; }
.contacts-total small { color: #8490a2; font-family: Inter, sans-serif; font-size: .59rem; letter-spacing: .04em; }
.contact-invite-card { display: grid; grid-template-columns: 46px minmax(0, 1fr) auto; align-items: end; gap: 15px; border: 1px solid #e1e6ef; border-radius: 15px; padding: 18px; background: #fff; box-shadow: var(--shadow-soft); }
.invite-symbol { display: grid; width: 43px; height: 43px; place-items: center; border-radius: 14px; color: #56729e; background: #edf1f7; font-size: 1.3rem; }
.contact-section { margin-top: 32px; }
.contact-section .section-title-row { margin-bottom: 12px; }
.contact-section .section-title-row h2 { color: #334157; font-family: Georgia, "Times New Roman", serif; font-size: 1.15rem; font-weight: 600; }
.contact-card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px; }
.person-card { display: flex; min-width: 0; min-height: 98px; align-items: center; gap: 12px; border: 1px solid #e3e8f0; border-radius: 14px; padding: 14px; background: #fff; box-shadow: 0 5px 16px #293b5809; transition: transform .2s, border-color .2s, box-shadow .2s; }
.person-avatar { width: 46px; height: 46px; flex: 0 0 46px; color: #536b94; background: linear-gradient(145deg, #e8eef7, #eeeaf6); font-size: .95rem; }
.person-copy { display: grid; min-width: 0; flex: 1; gap: 3px; }
.person-copy strong { overflow: hidden; color: #354359; font-size: .79rem; text-overflow: ellipsis; white-space: nowrap; }
.person-copy > span { overflow: hidden; color: #768399; font-size: .66rem; text-overflow: ellipsis; white-space: nowrap; }
.person-copy small { color: #8492a5; font-size: .63rem; }
.pending-mark { flex: 0 0 auto; border-radius: 999px; padding: 6px 8px; color: #737f91; background: #f1f3f6; font-size: .62rem; }
.request-card { align-items: flex-start; }
.request-actions { display: flex; flex: 0 0 auto; flex-direction: column; gap: 6px; }
.request-actions .button-small { padding: 7px 10px; }
.remove-contact-button { flex: 0 0 30px; color: #8691a2; font-size: 1.25rem; }
.remove-contact-button:hover { color: #a44f60; background: #fff0f1; }
.contacts-empty { margin-top: 10px; padding: 30px 18px; }

@keyframes settle-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes toast-enter {
  from { opacity: 0; transform: translateY(-7px) scale(.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@media (max-width: 920px) {
  .app-shell { grid-template-columns: 224px minmax(0, 1fr); }
  .channel-sidebar { padding-inline: 14px; }
  .contact-card-grid { grid-template-columns: 1fr; }
}
@media (max-width: 680px) {
  .app-shell { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr); height: 100dvh; }
  .channel-sidebar { display: flex; flex-direction: row; gap: 11px; overflow-x: auto; border-right: 0; border-bottom: 1px solid #e1e6ef; padding: 9px 12px; }
  .workspace-brand { flex: 0 0 auto; gap: 7px; margin: 0 4px 0 0; }
  .workspace-brand .brand-mark { width: 36px; height: 36px; border-radius: 12px; font-size: 1rem; }
  .brand-copy strong { font-size: 1.02rem; }
  .brand-copy small, .sidebar-caption, .team-section, .profile-copy, .logout-button { display: none; }
  .workspace-nav { display: flex; min-width: 0; flex: 1; gap: 3px; overflow: auto; }
  .side-link { justify-content: center; min-width: 40px; min-height: 39px; gap: 0; margin: 0; padding: 7px; }
  .side-link > span:nth-child(2) { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
  .side-link-icon { width: 24px; font-size: 1.08rem; }
  .side-link.active::before { inset: auto 11px 0; width: auto; height: 2px; }
  .nav-count { position: absolute; top: 0; right: 0; min-width: 16px; height: 16px; font-size: .55rem; }
  .profile-card { flex: 0 0 auto; margin: 0; border: 0; padding: 0; background: transparent; box-shadow: none; }
  .profile-avatar { width: 35px; height: 35px; }
  .topbar { min-height: 72px; flex-wrap: wrap; padding: 9px 13px; }
  .topbar-heading { flex: 1; }
  .topbar-heading p { max-width: 58vw; }
  .topbar-actions { max-width: 100%; overflow-x: auto; }
  .invite-form { min-width: 235px; }
  .content-scroll { padding: 23px 15px 38px; }
  .contact-invite-card { grid-template-columns: 38px minmax(0, 1fr); gap: 11px; padding: 14px; }
  .contact-invite-card .button { grid-column: 1 / -1; }
  .invite-symbol { width: 38px; height: 38px; }
  .contacts-intro { align-items: flex-start; }
  .contacts-total { min-width: 62px; height: 62px; border-radius: 18px; font-size: 1.3rem; }
  .person-card { flex-wrap: wrap; padding: 12px; }
  .request-actions { width: 100%; flex-direction: row; padding-left: 58px; }
  .request-actions .button { flex: 1; }
  .profile-picture-field { align-items: flex-start; }
  .profile-picture-preview { width: 72px; height: 72px; flex-basis: 72px; }
  .profile-save-row { align-items: flex-start; flex-direction: column; }
  .profile-save-row .button { width: 100%; }
  .github-profile { align-items: flex-start; }
  .github-profile > div { min-width: calc(100% - 60px); }
  .shared-file-card { flex-wrap: wrap; }
  .shared-file-card .button { margin-left: auto; }
  .notice-content .absence-card-heading time { text-align: left; }
}
@media (max-width: 1100px) {
  .chat-panel { flex-direction: column; overflow-y: auto; }
  .team-chat-column { min-height: 320px; flex: 1 0 320px; }
  .team-calendar-card { width: 100%; min-width: 0; min-height: 465px; flex: 0 0 auto; }
}

:global(html[data-theme="negro"]) { color-scheme: dark; background: #11131b; }
:global(body[data-theme="negro"]) { background: #11131b; }
.content-scroll, .chat-panel { animation: settle-in .32s cubic-bezier(.2,.8,.2,1) both; }
.modal-backdrop { animation: backdrop-enter .2s ease both; }
.modal-card, .certificate-modal, .notification-panel { animation: settle-in .26s cubic-bezier(.2,.8,.2,1) both; }
.calendar-event, .day-cell, .agenda-card, .task-create-card, .modal-card {
  transition: background-color .24s ease, border-color .24s ease, color .24s ease, box-shadow .24s ease, transform .24s cubic-bezier(.2,.8,.2,1);
}
.app-shell[data-theme="negro"] { color: #e5e7ef; background: #11131b; }
.app-shell[data-theme="negro"] .channel-sidebar {
  border-color: #292d39;
  background: radial-gradient(ellipse at 4% 0%, #25233a 0, transparent 38%), #171923;
}
.app-shell[data-theme="negro"] .main-panel,
.app-shell[data-theme="negro"] .topbar,
.app-shell[data-theme="negro"] .content-scroll,
.app-shell[data-theme="negro"] .chat-panel { color: #e5e7ef; background: #11131b; }
.app-shell[data-theme="negro"] .topbar,
.app-shell[data-theme="negro"] .profile-card { border-color: #292d39; }
.app-shell[data-theme="negro"] .topbar-heading h1,
.app-shell[data-theme="negro"] .section-title-row h2,
.app-shell[data-theme="negro"] .personal-heading h2,
.app-shell[data-theme="negro"] .calendar-toolbar h2,
.app-shell[data-theme="negro"] .task-create-card h2,
.app-shell[data-theme="negro"] .github-card h2,
.app-shell[data-theme="negro"] .modal-card h2,
.app-shell[data-theme="negro"] .agenda-card h3 { color: #eef0f7; }
.app-shell[data-theme="negro"] .topbar-heading p,
.app-shell[data-theme="negro"] .personal-heading p,
.app-shell[data-theme="negro"] .user-menu,
.app-shell[data-theme="negro"] .section-kicker { color: #9ba3b5; }
.app-shell[data-theme="negro"] .side-link,
.app-shell[data-theme="negro"] .team-link,
.app-shell[data-theme="negro"] .top-profile { color: #aeb5c4; }
.app-shell[data-theme="negro"] .side-link:hover,
.app-shell[data-theme="negro"] .side-link.active,
.app-shell[data-theme="negro"] .team-link:hover,
.app-shell[data-theme="negro"] .team-link.active { color: #c4baff; background: #29263f; }
.app-shell[data-theme="negro"] .brand-copy strong,
.app-shell[data-theme="negro"] .profile-copy strong,
.app-shell[data-theme="negro"] .task-row-body strong,
.app-shell[data-theme="negro"] .absence-card-heading strong,
.app-shell[data-theme="negro"] .github-profile strong { color: #e2e5ef; }
.app-shell[data-theme="negro"] .task-create-card,
.app-shell[data-theme="negro"] .agenda-card,
.app-shell[data-theme="negro"] .personal-create,
.app-shell[data-theme="negro"] .absence-create,
.app-shell[data-theme="negro"] .github-card,
.app-shell[data-theme="negro"] .absence-card,
.app-shell[data-theme="negro"] .task-row,
.app-shell[data-theme="negro"] .notification-panel,
.app-shell[data-theme="negro"] .person-card,
.app-shell[data-theme="negro"] .file-upload-card,
.app-shell[data-theme="negro"] .repository-card,
.app-shell[data-theme="negro"] .profile-editor,
.app-shell[data-theme="negro"] .modal-card,
.app-shell[data-theme="negro"] .team-calendar-card { border-color: #2b3040; background-color: #191c27; }
.app-shell[data-theme="negro"] .task-row { border-bottom-color: #2b3040; }
.app-shell[data-theme="negro"] .task-row-body span,
.app-shell[data-theme="negro"] .task-state,
.app-shell[data-theme="negro"] .github-card > p,
.app-shell[data-theme="negro"] .absence-card p,
.app-shell[data-theme="negro"] .absence-card-heading span,
.app-shell[data-theme="negro"] .absence-card-heading time,
.app-shell[data-theme="negro"] .modal-card p { color: #a1a8b8; }
.app-shell[data-theme="negro"] .field { color: #c3c8d4; }
.app-shell[data-theme="negro"] .field input,
.app-shell[data-theme="negro"] .field select,
.app-shell[data-theme="negro"] .field textarea,
.app-shell[data-theme="negro"] .invite-form input,
.app-shell[data-theme="negro"] .chat-composer,
.app-shell[data-theme="negro"] .month-button,
.app-shell[data-theme="negro"] .today-button { border-color: #343a4c; color: #e5e7ef; background: #141721; }
.app-shell[data-theme="negro"] .field input::placeholder,
.app-shell[data-theme="negro"] .field textarea::placeholder { color: #788196; }
.app-shell[data-theme="negro"] .chat-composer input { color: #e5e7ef; }
.app-shell[data-theme="negro"] .calendar-grid,
.app-shell[data-theme="negro"] .team-calendar-grid { border-color: #303647; background: #191c27; }
.app-shell[data-theme="negro"] .weekday,
.app-shell[data-theme="negro"] .team-calendar-weekday { color: #aab2c2; background: #1b1f2c; }
.app-shell[data-theme="negro"] .day-cell,
.app-shell[data-theme="negro"] .team-calendar-day { border-color: #303647; color: #d8dce6; background: #141721; }
.app-shell[data-theme="negro"] .day-cell:hover,
.app-shell[data-theme="negro"] .day-cell.outside-month,
.app-shell[data-theme="negro"] .team-calendar-day.outside-month { background: #191c27; }
.app-shell[data-theme="negro"] .day-cell.outside-month .day-number { color: #747e91; }
.app-shell[data-theme="negro"] .notification-item { background: #202432; }
.app-shell[data-theme="negro"] .notification-item:hover { background: #2b2a41; }
.app-shell[data-theme="negro"] .notification-panel > strong,
.app-shell[data-theme="negro"] .notification-item b { color: #e2e5ef; }
.app-shell[data-theme="negro"] .notification-item small,
.app-shell[data-theme="negro"] .notification-empty { color: #a1a8b8; }
.app-shell[data-theme="negro"] .tab-button { color: #c2c8d6; }
.app-shell[data-theme="negro"] .tab-button.chosen { color: #c4baff; background: #29263f; }
.app-shell[data-theme="negro"] .empty-card { border-color: #343a4c; color: #a1a8b8; }
.app-shell[data-theme="negro"] .topbar .theme-control { color: #aeb5c4; }
.app-shell[data-theme="negro"] .topbar .theme-control select { border-color: #343a4c; color: #e5e7ef; background: #191c27; }
.app-shell[data-theme="negro"] .theme-control option { color: #e5e7ef; background: #191c27; }
.auth-page[data-theme="negro"] { background: #11131b; }
.auth-page[data-theme="negro"] .auth-form-wrap { background: #11131b; }
.auth-page[data-theme="negro"] .auth-form h2 { color: #eef0f7; }
.auth-page[data-theme="negro"] .auth-form-wrap .field { color: #c3c8d4; }
.auth-page[data-theme="negro"] .auth-form-wrap .field input { border-color: #343a4c; color: #e5e7ef; background: #191c27; }
.auth-page[data-theme="negro"] .auth-hint,
.auth-page[data-theme="negro"] .switch-auth { color: #a1a8b8; }
.app-shell[data-theme="negro"] {
  color: #e8edf6;
  background: #0c1220;
}
.app-shell[data-theme="negro"] .channel-sidebar {
  border-color: #26344a;
  background: radial-gradient(ellipse at 4% 0%, #202941 0, transparent 42%), #101929;
}
.app-shell[data-theme="negro"] .main-panel,
.app-shell[data-theme="negro"] .topbar,
.app-shell[data-theme="negro"] .content-scroll,
.app-shell[data-theme="negro"] .chat-panel {
  color: #e8edf6;
  background: #0c1220;
}
.app-shell[data-theme="negro"] .topbar,
.app-shell[data-theme="negro"] .profile-card { border-color: #26344a; }
.app-shell[data-theme="negro"] .brand-copy strong,
.app-shell[data-theme="negro"] .profile-copy strong,
.app-shell[data-theme="negro"] .task-row-body strong,
.app-shell[data-theme="negro"] .absence-card-heading strong,
.app-shell[data-theme="negro"] .github-profile strong,
.app-shell[data-theme="negro"] .person-copy strong,
.app-shell[data-theme="negro"] .shared-file-meta strong,
.app-shell[data-theme="negro"] .repository-card-heading strong,
.app-shell[data-theme="negro"] .team-calendar-task strong,
.app-shell[data-theme="negro"] .team-calendar-toolbar > strong,
.app-shell[data-theme="negro"] .team-calendar-agenda-heading strong,
.app-shell[data-theme="negro"] .chat-welcome h2,
.app-shell[data-theme="negro"] .message-meta strong,
.app-shell[data-theme="negro"] .message-body p,
.app-shell[data-theme="negro"] .profile-picture-copy > strong,
.app-shell[data-theme="negro"] .contacts-intro h2,
.app-shell[data-theme="negro"] .page-intro h2,
.app-shell[data-theme="negro"] .contact-section .section-title-row h2 {
  color: #e8edf6;
}
.app-shell[data-theme="negro"] .side-title,
.app-shell[data-theme="negro"] .sidebar-caption,
.app-shell[data-theme="negro"] .team-title,
.app-shell[data-theme="negro"] .brand-copy small,
.app-shell[data-theme="negro"] .team-link small,
.app-shell[data-theme="negro"] .profile-copy small,
.app-shell[data-theme="negro"] .topbar-heading p,
.app-shell[data-theme="negro"] .personal-heading p,
.app-shell[data-theme="negro"] .page-intro p,
.app-shell[data-theme="negro"] .user-menu,
.app-shell[data-theme="negro"] .section-kicker,
.app-shell[data-theme="negro"] .team-calendar-agenda-heading > span,
.app-shell[data-theme="negro"] .team-calendar-task small,
.app-shell[data-theme="negro"] .team-calendar-empty,
.app-shell[data-theme="negro"] .message-meta time,
.app-shell[data-theme="negro"] .chat-welcome p,
.app-shell[data-theme="negro"] .history-note,
.app-shell[data-theme="negro"] .personal-heading p,
.app-shell[data-theme="negro"] .absence-file small,
.app-shell[data-theme="negro"] .file-upload-card .field small,
.app-shell[data-theme="negro"] .repo-upload-card .field small,
.app-shell[data-theme="negro"] .profile-picture-copy > span,
.app-shell[data-theme="negro"] .profile-save-row > span,
.app-shell[data-theme="negro"] .profile-editor .field small,
.app-shell[data-theme="negro"] .person-copy > span,
.app-shell[data-theme="negro"] .person-copy small,
.app-shell[data-theme="negro"] .shared-file-meta span {
  color: #9cabc0;
}
.app-shell[data-theme="negro"] .side-link,
.app-shell[data-theme="negro"] .team-link,
.app-shell[data-theme="negro"] .top-profile { color: #b5c1d3; }
.app-shell[data-theme="negro"] .side-link:hover,
.app-shell[data-theme="negro"] .team-link:hover,
.app-shell[data-theme="negro"] .create-server-link:hover {
  color: #d2c8ff;
  background: #202941;
}
.app-shell[data-theme="negro"] .side-link.active,
.app-shell[data-theme="negro"] .team-link.active {
  color: #d2c8ff;
  background: #252b47;
}
.app-shell[data-theme="negro"] .side-link-icon { color: #9aa9c1; }
.app-shell[data-theme="negro"] .team-symbol,
.app-shell[data-theme="negro"] .top-icon {
  border-color: #33435b;
  color: #c3b7ff;
  background: #1b2639;
}
.app-shell[data-theme="negro"] .create-server-link {
  border-color: #3b4961;
  color: #c3b7ff;
  background: #151f30;
}
.app-shell[data-theme="negro"] .sidebar-empty,
.app-shell[data-theme="negro"] .task-row-body span,
.app-shell[data-theme="negro"] .task-state,
.app-shell[data-theme="negro"] .github-card > p,
.app-shell[data-theme="negro"] .absence-card p,
.app-shell[data-theme="negro"] .absence-card-heading span,
.app-shell[data-theme="negro"] .absence-card-heading time,
.app-shell[data-theme="negro"] .modal-card p,
.app-shell[data-theme="negro"] .person-copy small,
.app-shell[data-theme="negro"] .profile-picture-copy > span,
.app-shell[data-theme="negro"] .profile-save-row > span,
.app-shell[data-theme="negro"] .profile-editor .field small {
  color: #a9b5c7;
}
.app-shell[data-theme="negro"] .task-create-card,
.app-shell[data-theme="negro"] .agenda-card,
.app-shell[data-theme="negro"] .personal-create,
.app-shell[data-theme="negro"] .absence-create,
.app-shell[data-theme="negro"] .github-card,
.app-shell[data-theme="negro"] .absence-card,
.app-shell[data-theme="negro"] .task-row,
.app-shell[data-theme="negro"] .task-row-area,
.app-shell[data-theme="negro"] .notification-panel,
.app-shell[data-theme="negro"] .person-card,
.app-shell[data-theme="negro"] .contact-invite-card,
.app-shell[data-theme="negro"] .file-upload-card,
.app-shell[data-theme="negro"] .repo-upload-card,
.app-shell[data-theme="negro"] .shared-file-card,
.app-shell[data-theme="negro"] .repository-card,
.app-shell[data-theme="negro"] .profile-editor,
.app-shell[data-theme="negro"] .modal-card,
.app-shell[data-theme="negro"] .team-calendar-card {
  border-color: #2a3950;
  background-color: #151f30;
  box-shadow: 0 10px 30px #03081440;
}
.app-shell[data-theme="negro"] .task-row,
.app-shell[data-theme="negro"] .task-row-area { border-bottom-color: #2a3950; }
.app-shell[data-theme="negro"] .task-row:hover,
.app-shell[data-theme="negro"] .absence-card:hover,
.app-shell[data-theme="negro"] .shared-file-card:hover,
.app-shell[data-theme="negro"] .repository-card:hover,
.app-shell[data-theme="negro"] .person-card:hover {
  border-color: #465875;
  background-color: #19263a;
}
.app-shell[data-theme="negro"] .task-row-body strong.struck,
.app-shell[data-theme="negro"] .team-calendar-task strong.struck { color: #9aa8bc; }
.app-shell[data-theme="negro"] .field { color: #c5d0df; }
.app-shell[data-theme="negro"] .field input,
.app-shell[data-theme="negro"] .field select,
.app-shell[data-theme="negro"] .field textarea,
.app-shell[data-theme="negro"] .invite-form input,
.app-shell[data-theme="negro"] .chat-composer,
.app-shell[data-theme="negro"] .month-button,
.app-shell[data-theme="negro"] .today-button {
  border-color: #35465f;
  color: #e8edf6;
  background: #0f1929;
}
.app-shell[data-theme="negro"] .field input::placeholder,
.app-shell[data-theme="negro"] .field textarea::placeholder,
.app-shell[data-theme="negro"] .invite-form input::placeholder,
.app-shell[data-theme="negro"] .chat-composer input::placeholder { color: #8494ab; }
.app-shell[data-theme="negro"] .field input:focus,
.app-shell[data-theme="negro"] .field select:focus,
.app-shell[data-theme="negro"] .field textarea:focus,
.app-shell[data-theme="negro"] .chat-composer:focus-within {
  border-color: #9b8df0;
  box-shadow: 0 0 0 3px #8875e433;
}
.app-shell[data-theme="negro"] .chat-composer input { color: #e8edf6; }
.app-shell[data-theme="negro"] .button:not(.button-light):not(.button-secondary),
.app-shell[data-theme="negro"] .send-button {
  color: #fff;
  background: linear-gradient(120deg, #756bd6, #9880df);
  box-shadow: 0 5px 16px #665acb40;
}
.app-shell[data-theme="negro"] .button:not(.button-light):not(.button-secondary):hover:not(:disabled),
.app-shell[data-theme="negro"] .send-button:hover:not(:disabled) {
  background: linear-gradient(120deg, #8478e6, #a48ce9);
}
.app-shell[data-theme="negro"] .button-light,
.app-shell[data-theme="negro"] .button-secondary {
  border-color: #3a4a63;
  color: #c5d0df;
  background: #1a2639;
  box-shadow: none;
}
.app-shell[data-theme="negro"] .button-light:hover:not(:disabled),
.app-shell[data-theme="negro"] .button-secondary:hover:not(:disabled) {
  border-color: #586b89;
  color: #e7e3ff;
  background: #25334b;
}
.app-shell[data-theme="negro"] .calendar-grid,
.app-shell[data-theme="negro"] .team-calendar-grid {
  border-color: #2a3950;
  background: #151f30;
}
.app-shell[data-theme="negro"] .weekday,
.app-shell[data-theme="negro"] .team-calendar-weekday {
  color: #aab8cc;
  background: #1a2639;
}
.app-shell[data-theme="negro"] .day-cell,
.app-shell[data-theme="negro"] .team-calendar-day {
  border-color: #2a3950;
  color: #d6dfec;
  background: #101a2a;
}
.app-shell[data-theme="negro"] .day-cell:hover,
.app-shell[data-theme="negro"] .team-calendar-day:hover,
.app-shell[data-theme="negro"] .day-cell.outside-month,
.app-shell[data-theme="negro"] .team-calendar-day.outside-month {
  color: #9eacc0;
  background: #172337;
}
.app-shell[data-theme="negro"] .day-cell.outside-month .day-number { color: #8191a9; }
.app-shell[data-theme="negro"] .day-cell.selected-day,
.app-shell[data-theme="negro"] .team-calendar-day.selected-day {
  color: #e8e4ff;
  background: #252b47;
  box-shadow: inset 0 0 0 2px #9486e8;
}
.app-shell[data-theme="negro"] .day-number,
.app-shell[data-theme="negro"] .calendar-toolbar h2,
.app-shell[data-theme="negro"] .agenda-card h3,
.app-shell[data-theme="negro"] .team-calendar-heading h2 { color: #e8edf6; }
.app-shell[data-theme="negro"] .team-calendar-task { background: #1b293e; }
.app-shell[data-theme="negro"] .team-calendar-heading .tab-button {
  color: #d2c8ff;
  background: #252b47;
}
.app-shell[data-theme="negro"] .team-calendar-agenda-heading { border-bottom-color: #2a3950; }
.app-shell[data-theme="negro"] .notification-item { color: #e8edf6; background: #1b293e; }
.app-shell[data-theme="negro"] .notification-item:hover { background: #252b47; }
.app-shell[data-theme="negro"] .notification-panel > strong,
.app-shell[data-theme="negro"] .notification-item b { color: #e8edf6; }
.app-shell[data-theme="negro"] .notification-item small,
.app-shell[data-theme="negro"] .notification-empty { color: #a9b5c7; }
.app-shell[data-theme="negro"] .tab-button { color: #c5d0df; }
.app-shell[data-theme="negro"] .tab-button:hover,
.app-shell[data-theme="negro"] .tab-button.chosen { color: #d2c8ff; background: #252b47; }
.app-shell[data-theme="negro"] .count-pill,
.app-shell[data-theme="negro"] .pending-mark,
.app-shell[data-theme="negro"] .certificate-private {
  color: #c9c3f5;
  background: #252b47;
}
.app-shell[data-theme="negro"] .urgencia-verde { color: #8fe0ad; background: #18352d; }
.app-shell[data-theme="negro"] .urgencia-amarillo { color: #f0cf7d; background: #3b321d; }
.app-shell[data-theme="negro"] .urgencia-rojo { color: #ffa4a8; background: #3c252e; }
.app-shell[data-theme="negro"] .urgencia-neutral,
.app-shell[data-theme="negro"] .urgencia-sin-fecha { color: #bdc7d5; background: #263348; }
.app-shell[data-theme="negro"] .calendar-event { color: #e5e0ff; background: #35305a; }
.app-shell[data-theme="negro"] .github-profile,
.app-shell[data-theme="negro"] .profile-picture-field { border-color: #2a3950; }
.app-shell[data-theme="negro"] .github-profile a,
.app-shell[data-theme="negro"] .repository-card-heading a,
.app-shell[data-theme="negro"] .text-button { color: #b9adff; }
.app-shell[data-theme="negro"] .github-avatar,
.app-shell[data-theme="negro"] .file-icon,
.app-shell[data-theme="negro"] .repo-mark,
.app-shell[data-theme="negro"] .person-avatar,
.app-shell[data-theme="negro"] .invite-symbol {
  color: #c8c0ff;
  background: #252b47;
}
.app-shell[data-theme="negro"] .profile-picture-preview {
  border-color: #25334a;
  color: #c8c0ff;
  box-shadow: 0 0 0 1px #40516d;
}
.app-shell[data-theme="negro"] .empty-card {
  border-color: #35465f;
  color: #a9b5c7;
  background: #111b2b;
}
.app-shell[data-theme="negro"] .toast {
  border-color: #3c4c66;
  color: #e8edf6;
  background: #19263a;
}
.app-shell[data-theme="negro"] .toast-error {
  border-color: #74414c;
  color: #ffd4d5;
  background: #38232c;
}
.app-shell[data-theme="negro"] .modal-backdrop { background: #050914b8; }
.app-shell[data-theme="negro"] .modal-card,
.app-shell[data-theme="negro"] .certificate-modal {
  border-color: #34445d;
  background: #151f30;
  box-shadow: 0 24px 80px #030814a6;
}
.app-shell[data-theme="negro"] .modal-close { color: #a9b5c7; }
.app-shell[data-theme="negro"] .modal-close:hover { color: #e8edf6; background: #25334b; }
.app-shell[data-theme="negro"] .topbar .theme-control { color: #c5d0df; }
.app-shell[data-theme="negro"] .topbar .theme-control select {
  border-color: #35465f;
  color: #e8edf6;
  background: #151f30;
}
.app-shell[data-theme="negro"] .theme-control option {
  color: #e8edf6;
  background: #151f30;
}
.auth-page[data-theme="negro"] { background: #0c1220; }
.auth-page[data-theme="negro"] .auth-decoration {
  background:
    radial-gradient(ellipse at 78% 22%, #6557a8 0, transparent 40%),
    linear-gradient(150deg, #111a30, #202c4a 55%, #3b345f);
}
.auth-page[data-theme="negro"] .auth-form-wrap { background: #0c1220; }
.auth-page[data-theme="negro"] .auth-form h2 { color: #e8edf6; }
.auth-page[data-theme="negro"] .auth-form-wrap .field { color: #c5d0df; }
.auth-page[data-theme="negro"] .auth-form-wrap .field input,
.auth-page[data-theme="negro"] .auth-form-wrap .field select,
.auth-page[data-theme="negro"] .auth-form-wrap .field textarea {
  border-color: #35465f;
  color: #e8edf6;
  background: #151f30;
}
.auth-page[data-theme="negro"] .auth-form-wrap .field input::placeholder,
.auth-page[data-theme="negro"] .auth-form-wrap .field textarea::placeholder { color: #8494ab; }
.auth-page[data-theme="negro"] .auth-theme-control { color: #ded7ff; }
.auth-page[data-theme="negro"] .auth-theme-control select {
  border-color: #ffffff55;
  color: #fff;
  background: #111a30aa;
}
.auth-page[data-theme="negro"] .auth-theme-control option { color: #e8edf6; background: #151f30; }
.app-shell[data-theme="violeta"] .side-link.active,
.app-shell[data-theme="violeta"] .team-link.active { color: #6552c4; background: #efedff; }
.app-shell[data-theme="violeta"] .button { background: linear-gradient(120deg, #6556cf, #8b66d8); }
.app-shell[data-theme="violeta"] .button:hover:not(:disabled) { background: linear-gradient(120deg, #5848c1, #7956c9); }

@keyframes art-float {
  0%, 100% { transform: translateY(0) rotate(-1deg); }
  50% { transform: translateY(-9px) rotate(1deg); }
}
@keyframes art-float-side {
  0%, 100% { transform: translateY(0) rotate(0); }
  50% { transform: translateY(-11px) rotate(-3deg); }
}
@keyframes orbit-turn { to { transform: rotate(360deg); } }
@keyframes backdrop-enter {
  from { opacity: 0; }
  to { opacity: 1; }
}
@media (max-width: 680px) {
  .auth-brand { gap: 8px; }
  .auth-art { right: 10px; bottom: 10px; width: 115px; opacity: .42; }
  .app-theme-control > span { display: none; }
  .app-theme-control select { max-width: 80px; padding: 7px 16px 7px 6px; }
}
@media (prefers-reduced-motion: reduce) {
  :global(*), :global(*::before), :global(*::after) {
    scroll-behavior: auto !important;
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
  }
}
</style>
