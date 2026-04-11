// BFF proxy: GET /api/market/orderbook?resource=wood → Cartographer GraphQL

interface OrderBookQueryResult {
  orderBook: {
    resourceType: string
    lastPrice: number
    volume24h: number
    bids: Array<{ price: number; quantity: number; totalQuantity: number }>
    asks: Array<{ price: number; quantity: number; totalQuantity: number }>
    priceHistory: Array<{ tick: number; price: number; timestamp: string }>
  } | null
}

const ORDER_BOOK_QUERY = `
  query GetOrderBook($resourceType: String!) {
    orderBook(resourceType: $resourceType) {
      resourceType lastPrice volume24h
      bids { price quantity totalQuantity }
      asks { price quantity totalQuantity }
      priceHistory(limit: 100) {
        tick price timestamp
      }
    }
  }
`

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const cartographerUrl = config.cartographerUrl as string

  const query = getQuery(event)
  const resourceType = query.resource as string | undefined

  if (!resourceType) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Bad Request',
      message: 'Query param "resource" is required (e.g. ?resource=wood)',
    })
  }

  try {
    const response = await $fetch<{ data: OrderBookQueryResult; errors?: Array<{ message: string }> }>(
      `${cartographerUrl}/graphql`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: {
          query: ORDER_BOOK_QUERY,
          variables: { resourceType },
        },
      }
    )

    if (response.errors?.length) {
      const errorMsg = response.errors.map((e) => e.message).join('; ')
      throw createError({
        statusCode: 422,
        statusMessage: 'Upstream GraphQL Error',
        message: errorMsg,
      })
    }

    if (!response.data.orderBook) {
      throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
        message: `Order book for resource "${resourceType}" not found`,
      })
    }

    return response.data.orderBook
  } catch (err) {
    if ((err as { statusCode?: number }).statusCode) throw err
    const message = err instanceof Error ? err.message : 'Upstream error'
    console.error('[server/api/market/orderbook] proxy error:', message)
    throw createError({
      statusCode: 502,
      statusMessage: 'Bad Gateway',
      message: `Failed to fetch order book: ${message}`,
    })
  }
})
