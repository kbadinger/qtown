import http from "http";
import { ApolloServer } from "@apollo/server";
import { expressMiddleware } from "@apollo/server/express4";
import { ApolloServerPluginDrainHttpServer } from "@apollo/server/plugin/drainHttpServer";
import express from "express";
import { typeDefs } from "./schema/typeDefs.js";
import { npcResolvers, createLoaders } from "./resolvers/npc.js";
import type { ResolverContext } from "./resolvers/npc.js";

const PORT = parseInt(process.env["PORT"] ?? "4000", 10);

async function main(): Promise<void> {
  const app = express();
  const httpServer = http.createServer(app);

  // ---- Apollo Server --------------------------------------------------------

  const server = new ApolloServer<ResolverContext>({
    typeDefs,
    resolvers: [npcResolvers],
    plugins: [ApolloServerPluginDrainHttpServer({ httpServer })],
    introspection: true,
  });

  await server.start();
  console.log("[cartographer] Apollo Server started");

  // ---- Middleware -----------------------------------------------------------

  app.use(express.json());

  // Health check (no auth required).
  app.get("/health", (_req, res) => {
    res.json({ status: "ok", service: "cartographer" });
  });

  // GraphQL endpoint — per-request context creates fresh DataLoaders so that
  // cache is scoped to a single request (standard DataLoader pattern).
  app.use(
    "/graphql",
    expressMiddleware(server, {
      context: async (): Promise<ResolverContext> => ({
        loaders: createLoaders(),
      }),
    })
  );

  // ---- Start ---------------------------------------------------------------

  await new Promise<void>((resolve) =>
    httpServer.listen({ port: PORT }, resolve)
  );

  console.log(`[cartographer] GraphQL server ready at http://0.0.0.0:${PORT}/graphql`);
  console.log(`[cartographer] Health endpoint at http://0.0.0.0:${PORT}/health`);
}

// Graceful shutdown
process.on("SIGINT", () => {
  console.log("[cartographer] SIGINT received, shutting down");
  process.exit(0);
});
process.on("SIGTERM", () => {
  console.log("[cartographer] SIGTERM received, shutting down");
  process.exit(0);
});

main().catch((err) => {
  console.error("[cartographer] fatal error:", err);
  process.exit(1);
});
