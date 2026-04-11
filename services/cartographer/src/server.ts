import http from "http";
import { ApolloServer } from "@apollo/server";
import { expressMiddleware } from "@apollo/server/express4";
import { ApolloServerPluginDrainHttpServer } from "@apollo/server/plugin/drainHttpServer";
import express from "express";
import { useServer } from "graphql-ws/lib/use/ws";
import { WebSocketServer } from "ws";
import { makeExecutableSchema } from "@graphql-tools/schema";
import pino from "pino";
import { typeDefs } from "./schema/typeDefs.js";
import { resolvers } from "./resolvers.js";
import type { ResolverContext } from "./resolvers.js";
import {
  createTownCoreClient,
  createMarketDistrictClient,
  createAcademyClient,
  createFortressClient,
} from "./grpc-clients.js";
import { createDataLoaders } from "./dataloaders.js";
import { createRedisCache } from "./cache.js";
import { analyzeComplexity } from "./complexity.js";

// ============================================================================
// Config
// ============================================================================

const logger = pino({ name: "cartographer-server" });
const PORT = parseInt(process.env["PORT"] ?? "4000", 10);
const REDIS_URL = process.env["REDIS_URL"] ?? "redis://localhost:6379";

// ============================================================================
// Bootstrap
// ============================================================================

async function main(): Promise<void> {
  // --------------------------------------------------------------------------
  // gRPC clients (long-lived — shared across requests)
  // --------------------------------------------------------------------------
  const townCoreClient = createTownCoreClient();
  const marketDistrictClient = createMarketDistrictClient();
  const academyClient = createAcademyClient();
  const fortressClient = createFortressClient();

  // --------------------------------------------------------------------------
  // Redis cache (shared — connection pooled)
  // --------------------------------------------------------------------------
  const redisCache = createRedisCache(REDIS_URL);

  // --------------------------------------------------------------------------
  // GraphQL schema
  // --------------------------------------------------------------------------
  const schema = makeExecutableSchema({ typeDefs, resolvers });

  // --------------------------------------------------------------------------
  // HTTP server
  // --------------------------------------------------------------------------
  const app = express();
  app.use(express.json());
  const httpServer = http.createServer(app);

  // --------------------------------------------------------------------------
  // WebSocket server for GraphQL subscriptions (graphql-ws protocol)
  // --------------------------------------------------------------------------
  const wsServer = new WebSocketServer({
    server: httpServer,
    path: "/graphql",
  });

  // graphql-ws integration: creates per-connection context
  const wsServerCleanup = useServer(
    {
      schema,
      context: (): ResolverContext => ({
        townCoreClient,
        marketDistrictClient,
        academyClient,
        fortressClient,
        redisCache,
        dataLoaders: createDataLoaders(
          townCoreClient,
          marketDistrictClient,
          academyClient
        ),
      }),
    },
    wsServer
  );

  // --------------------------------------------------------------------------
  // Apollo Server
  // --------------------------------------------------------------------------
  const server = new ApolloServer<ResolverContext>({
    schema,
    introspection: process.env["NODE_ENV"] !== "production",
    plugins: [
      // Graceful HTTP server drain on stop
      ApolloServerPluginDrainHttpServer({ httpServer }),
      // Graceful WS server drain on stop
      {
        async serverWillStart() {
          return {
            async drainServer() {
              await wsServerCleanup.dispose();
            },
          };
        },
      },
      // Query complexity analysis plugin
      {
        async requestDidStart({ request }) {
          const start = Date.now();
          logger.debug({ operationName: request.operationName }, "GraphQL request started");
          return {
            async didResolveDocument({ document, request: req }) {
              const result = analyzeComplexity(document, req.variables ?? {});
              if (result.errors.length > 0) {
                logger.warn(
                  { errors: result.errors, score: result.score, depth: result.depth },
                  "Query complexity limit exceeded"
                );
                // Throw to abort execution
                throw new Error(result.errors.join("; "));
              }
              logger.debug(
                { score: result.score, depth: result.depth },
                "Query complexity OK"
              );
            },
            async willSendResponse({ response }) {
              logger.debug(
                {
                  operationName: request.operationName,
                  durationMs: Date.now() - start,
                },
                "GraphQL request completed"
              );
              // Suppress unused variable warning
              void response;
            },
          };
        },
      },
    ],
  });

  await server.start();
  logger.info("Apollo Server started");

  // --------------------------------------------------------------------------
  // Routes
  // --------------------------------------------------------------------------

  // Health check
  app.get("/health", (_req, res) => {
    res.json({ status: "ok", service: "cartographer", port: PORT });
  });

  // GraphQL endpoint (HTTP + WebSocket upgrade handled on same path)
  app.use(
    "/graphql",
    expressMiddleware(server, {
      context: async (): Promise<ResolverContext> => ({
        townCoreClient,
        marketDistrictClient,
        academyClient,
        fortressClient,
        redisCache,
        // Per-request DataLoaders — fresh instance per request for correct cache scoping
        dataLoaders: createDataLoaders(
          townCoreClient,
          marketDistrictClient,
          academyClient
        ),
      }),
    })
  );

  // --------------------------------------------------------------------------
  // Start listening
  // --------------------------------------------------------------------------
  await new Promise<void>((resolve) =>
    httpServer.listen({ port: PORT, host: "0.0.0.0" }, resolve)
  );

  logger.info(
    { port: PORT },
    `Cartographer GraphQL server ready at http://0.0.0.0:${PORT}/graphql`
  );
  logger.info(
    { port: PORT },
    `WebSocket subscriptions at ws://0.0.0.0:${PORT}/graphql`
  );
  logger.info(`Health endpoint at http://0.0.0.0:${PORT}/health`);

  // --------------------------------------------------------------------------
  // Graceful shutdown
  // --------------------------------------------------------------------------

  async function shutdown(signal: string): Promise<void> {
    logger.info({ signal }, "Shutdown signal received");
    try {
      await server.stop();
      townCoreClient.close();
      marketDistrictClient.close();
      academyClient.close();
      fortressClient.close();
      redisCache.disconnect();
      logger.info("Cartographer shut down cleanly");
      process.exit(0);
    } catch (err) {
      logger.error({ err }, "Error during shutdown");
      process.exit(1);
    }
  }

  process.on("SIGTERM", () => {
    shutdown("SIGTERM").catch((err) => {
      logger.error({ err }, "Shutdown failed");
      process.exit(1);
    });
  });
  process.on("SIGINT", () => {
    shutdown("SIGINT").catch((err) => {
      logger.error({ err }, "Shutdown failed");
      process.exit(1);
    });
  });
}

// ============================================================================
// Entry point
// ============================================================================

main().catch((err: unknown) => {
  console.error("[cartographer] Fatal startup error:", err);
  process.exit(1);
});
