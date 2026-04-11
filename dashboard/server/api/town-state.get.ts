// BFF proxy: GET /api/town-state → town-core /api/world

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const townCoreUrl = config.townCoreUrl as string

  try {
    const data = await $fetch(`${townCoreUrl}/api/world`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        // Forward any auth headers if present
        ...(getHeader(event, 'authorization')
          ? { authorization: getHeader(event, 'authorization') as string }
          : {}),
      },
    })

    return data
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Upstream error'
    console.error('[server/api/town-state] proxy error:', message)

    throw createError({
      statusCode: 502,
      statusMessage: 'Bad Gateway',
      message: `Failed to fetch town state from upstream: ${message}`,
    })
  }
})
