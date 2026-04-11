import type * as grpc from "@grpc/grpc-js";
import type { RedisCache } from "./cache.js";
import type { DataLoaders } from "./types.js";

// ============================================================================
// GraphQL resolver context
// ============================================================================
// Extracted to a standalone file to avoid circular imports between
// resolvers.ts and resolvers/npc.ts.

export interface ResolverContext {
  townCoreClient: grpc.Client;
  marketDistrictClient: grpc.Client;
  academyClient: grpc.Client;
  fortressClient: grpc.Client;
  redisCache: RedisCache;
  dataLoaders: DataLoaders;
}
