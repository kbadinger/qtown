import * as grpc from "@grpc/grpc-js";
import * as protoLoader from "@grpc/proto-loader";
import path from "path";
import { fileURLToPath } from "url";
import pino from "pino";

const logger = pino({ name: "grpc-clients" });

// ---------------------------------------------------------------------------
// Proto loading
// ---------------------------------------------------------------------------
// Proto files should live in /protos relative to the project root.
// Paths are resolved relative to this file.

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROTO_BASE = path.resolve(__dirname, "../../protos");

const LOADER_OPTIONS: protoLoader.Options = {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
};

function loadPackage(protoFile: string): grpc.GrpcObject {
  const definition = protoLoader.loadSync(path.join(PROTO_BASE, protoFile), LOADER_OPTIONS);
  return grpc.loadPackageDefinition(definition);
}

// ---------------------------------------------------------------------------
// Client factory helpers
// ---------------------------------------------------------------------------

/**
 * Creates a gRPC channel with sensible defaults and exponential back-off.
 * Returns the underlying `grpc.Channel` options that can be shared across stubs.
 */
function makeChannelOptions(): grpc.ChannelOptions {
  return {
    "grpc.keepalive_time_ms": 10_000,
    "grpc.keepalive_timeout_ms": 5_000,
    "grpc.keepalive_permit_without_calls": 1,
    "grpc.enable_retries": 1,
    "grpc.service_config": JSON.stringify({
      methodConfig: [
        {
          name: [{}],
          retryPolicy: {
            maxAttempts: 5,
            initialBackoff: "0.5s",
            maxBackoff: "30s",
            backoffMultiplier: 2,
            retryableStatusCodes: ["UNAVAILABLE", "RESOURCE_EXHAUSTED"],
          },
        },
      ],
    }),
  };
}

// ---------------------------------------------------------------------------
// Exported client constructors
// ---------------------------------------------------------------------------

/**
 * town-core — NPC state, neighbourhood data.
 * gRPC endpoint: localhost:50050
 */
export function createTownCoreClient(): grpc.Client {
  const pkg = loadPackage("town_core.proto");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const TownCore = (pkg as any).qtown?.TownCoreService as typeof grpc.Client;

  if (!TownCore) {
    logger.warn("town_core.proto not found — returning a generic channel stub");
    return new grpc.Client("localhost:50050", grpc.credentials.createInsecure(), makeChannelOptions());
  }

  const client = new TownCore(
    "localhost:50050",
    grpc.credentials.createInsecure(),
    makeChannelOptions()
  );

  logger.info("TownCore gRPC client created (localhost:50050)");
  return client;
}

/**
 * market-district — Order book, trade history.
 * gRPC endpoint: localhost:50051
 */
export function createMarketClient(): grpc.Client {
  const pkg = loadPackage("market_district.proto");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Market = (pkg as any).qtown?.MarketService as typeof grpc.Client;

  if (!Market) {
    logger.warn("market_district.proto not found — returning a generic channel stub");
    return new grpc.Client("localhost:50051", grpc.credentials.createInsecure(), makeChannelOptions());
  }

  const client = new Market(
    "localhost:50051",
    grpc.credentials.createInsecure(),
    makeChannelOptions()
  );

  logger.info("Market gRPC client created (localhost:50051)");
  return client;
}

/**
 * fortress — Validation, governance, and rules engine.
 * gRPC endpoint: localhost:50052
 */
export function createFortressClient(): grpc.Client {
  const pkg = loadPackage("fortress.proto");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Fortress = (pkg as any).qtown?.FortressService as typeof grpc.Client;

  if (!Fortress) {
    logger.warn("fortress.proto not found — returning a generic channel stub");
    return new grpc.Client("localhost:50052", grpc.credentials.createInsecure(), makeChannelOptions());
  }

  const client = new Fortress(
    "localhost:50052",
    grpc.credentials.createInsecure(),
    makeChannelOptions()
  );

  logger.info("Fortress gRPC client created (localhost:50052)");
  return client;
}
