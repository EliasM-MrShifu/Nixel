# Aplicaion

This template should help get you started developing with Vue 3 in Vite.

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Type-Check, Compile and Minify for Production

```sh
npm run build
```

## Conectar con la base de datos

La interfaz usa la API Python de la carpeta `BaseDeDatos` y una base MySQL llamada
`aplicacion`. Configura `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER` y `MYSQL_PASSWORD`
según tu servidor MySQL y abre dos terminales desde la carpeta del proyecto:

1. Instala el conector una vez con `python -m pip install -r .\BaseDeDatos\requirements.txt`
   y luego inicia el backend con `.\BaseDeDatos\iniciar.ps1`.
2. En la otra terminal, entra en `Aplicaion` y ejecuta `npm run dev`.

Vite reenvía las solicitudes `/api` a `http://127.0.0.1:5000`. El backend crea la base
MySQL `aplicacion` al iniciar si aún no existe. Los cambios hechos en MySQL se reflejan
en la interfaz en unos segundos. Consulta `..\BaseDeDatos\README.md` para más
instrucciones y endpoints.
