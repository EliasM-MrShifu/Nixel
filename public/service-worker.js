self.addEventListener('push', (event) => {
  if (!event.data) return

  let payload
  try {
    payload = event.data.json()
  } catch {
    payload = { title: 'Nexo', body: event.data.text() }
  }

  event.waitUntil(
    self.registration.showNotification(payload.title || 'Nexo', {
      body: payload.body || 'Hay una actualización en tu equipo.',
      tag: `nexo-${payload.id || 'update'}`,
      data: { url: payload.url || '/' },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const destination = new URL(event.notification.data?.url || '/', self.location.origin).href
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const openClient = clients.find((client) => client.url.startsWith(self.location.origin))
      if (openClient) {
        return openClient.navigate(destination).then(() => openClient.focus())
      }
      return self.clients.openWindow(destination)
    }),
  )
})
