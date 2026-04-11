import { ApolloServer } from "@apollo/server";
import { startStandaloneServer } from "@apollo/server/standalone";
import { createServer } from "http";
import pino from "pino";
import { typeDefs } from "./schema.js";
import { resolvers, type ResolverContext } from "./resolvers.js";
import { createTownCoreClient, createMarketClient, createFortressClient } from "./grpc-clients.js";
import { createDataloaders } from "./dataloaders.js";

// ---------------------------------------------------------------------------
// Logger
// ---------------------------------------------------------------------------
const logger = pino({ name: "cartographer" });

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PORT = parseInt(process.env["PORT"] ?? "4000", 10);

// ---------------------------------------------------------------------------
// gRPC clients (long-lived — shared across requests)
// ---------------------------------------------------------------------------
const townCoreClient = createTownCoreClient();
const marketClient = createMarketClient();
const fortressClient = createFortressClient();

// ---------------------------------------------------------------------------
// Apollo Server
// ---------------------------------------------------------------------------
const server = new ApolloServer<ResolverContext>({
  typeDefs,
  resolvers,
  // Apollo Studio introspection is enabled by default in non-production
  introspection: process.env["NODE_ENV"] !== "production",
  plugins: [
    {
      async requestDidStart({ request }) {
        const start = Date.now();
        logger.debug({ operationName: request.operationName }, "GraphQL request started");
        return {
          async willSendResponse({ response }) {
            logger.debug(
              {
                operationName: request.operationName,
                durationMs: Date.now() - start,
                errors: response.body.kind === "single" ? response.body.singleResult.errors : [],
              },
              "GraphQL request completed"
            );
          },
        };
      },
    },
  ],
});

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------

async function start(): Promise<void> {
  try {
    const { url } = await startStandaloneServer(server, {
      listen: { port: PORT },
      context: async (): Promise<ResolverContext> => {
        // DataLoaders are created per-request to ensure correct batching scope
        return {
          townCoreClient,
          marketClient,
          fortressClient,
          dataloaders: createDataloaders(townCoreClient, marketClient),
        };
      },
    });

    logger.info({ url }, "Cartographer GraphQL server ready");

    // ---------------------------------------------------------------------------
    // /health endpoint
    // ---------------------------------------------------------------------------
    // startStandaloneServer wraps Apollo in its own HTTP server; for a dedicated
    // health route we spin up a lightweight plain HTTP server on a sidecar port.
    const healthPort = PORT + 1; // e.g. 4001
    const healthServer = createServer((req, res) => {
      if (req.url === "/health" && req.method === "GET") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", service: "cartographer" }));
      } else {
        res.writeHead(404);
        res.end();
      }
    });

    healthServer.listen(healthPort, () => {
      logger.info({ port: healthPort }, "Health endpoint listening");
    });

    // Store references for shutdown
    _healthServer = healthServer;
  } catch (err) {
    logger.fatal({ err }, "Failed to start Cartographer");
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------

let _healthServer: ReturnType<typeof createServer> | null = null;

async function shutdown(signal: string): Promise<void> {
  logger.info({ signal }, "Shutdown signal received");
  try {
    await server.stop();

    if (_healthServer) {
      await new Promise<void>((resolve, reject) =>
        _healthServer!.close((err) => (err ? reject(err) : resolve()))
      );
    }

    townCoreClient.close();
    marketClient.close();
    fortressClient.close();

    logger.info("Cartographer shut down cleanly");
    process.exit(0);
  } catch (err) {
    logger.error({ err }, "Error during shutdown");
    process.exit(1);
  }
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
start();
