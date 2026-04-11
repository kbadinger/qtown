import * as grpc from "@grpc/grpc-js";
import * as protoLoader from "@grpc/proto-loader";
import path from "path";
import { fileURLToPath } from "url";
import pino from "pino";

const logger = pino({ name: "grpc-clients" });

// ============================================================================
// Proto loading
// ============================================================================

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROTO_BASE = path.resolve(__dirname, "../../protos");

const LOADER_OPTIONS: protoLoader.Options = {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
};

function tryLoadPackage(protoFile: string): grpc.GrpcObject | null {
  try {
    const definition = protoLoader.loadSync(
      path.join(PROTO_BASE, protoFile),
      LOADER_OPTIONS
    );
    return grpc.loadPackageDefinition(definition);
  } catch {
    logger.warn({ protoFile }, "Proto file not found — using generic stub");
    return null;
  }
}

// ============================================================================
// Channel options
// ============================================================================

/**
 * Shared channel options: keepalive, retry policy with 2-attempt limit
 * and 5 s deadline propagated per call via metadata/deadline argument.
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
          timeout: "5s",
          retryPolicy: {
            maxAttempts: 3,
            initialBackoff: "0.5s",
            maxBackoff: "10s",
            backoffMultiplier: 2,
            retryableStatusCodes: ["UNAVAILABLE", "RESOURCE_EXHAUSTED"],
          },
        },
      ],
    }),
  };
}

// ============================================================================
// Generic client factory
// ============================================================================

function makeClient(
  protoFile: string,
  servicePath: string,
  address: string
): grpc.Client {
  const pkg = tryLoadPackage(protoFile);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ServiceCtor = pkg ? (pkg as any)[servicePath] as typeof grpc.Client | undefined : undefined;

  if (!ServiceCtor) {
    logger.warn(
      { protoFile, servicePath, address },
      "Service constructor not found — using generic channel client"
    );
    return new grpc.Client(
      address,
      grpc.credentials.createInsecure(),
      makeChannelOptions()
    );
  }

  const client = new ServiceCtor(
    address,
    grpc.credentials.createInsecure(),
    makeChannelOptions()
  );
  logger.info({ address, service: servicePath }, "gRPC client created");
  return client;
}

// ============================================================================
// Exported client constructors
// ============================================================================

/**
 * town-core — NPC state, neighbourhood data, world state.
 * gRPC endpoint: localhost:50051
 */
export function createTownCoreClient(): grpc.Client {
  return makeClient(
    "town_core.proto",
    "qtown.TownCoreService",
    process.env["TOWN_CORE_ADDR"] ?? "localhost:50051"
  );
}

/**
 * market-district — Order book, trade history, price updates.
 * gRPC endpoint: localhost:50052
 */
export function createMarketDistrictClient(): grpc.Client {
  return makeClient(
    "market_district.proto",
    "qtown.MarketDistrictService",
    process.env["MARKET_DISTRICT_ADDR"] ?? "localhost:50052"
  );
}

/**
 * academy — Newspaper generation, NPC decision traces.
 * gRPC endpoint: localhost:50053
 */
export function createAcademyClient(): grpc.Client {
  return makeClient(
    "academy.proto",
    "qtown.AcademyService",
    process.env["ACADEMY_ADDR"] ?? "localhost:50053"
  );
}

/**
 * fortress — Governance, validation, crime records.
 * gRPC endpoint: localhost:50054
 */
export function createFortressClient(): grpc.Client {
  return makeClient(
    "fortress.proto",
    "qtown.FortressService",
    process.env["FORTRESS_ADDR"] ?? "localhost:50054"
  );
}

// ============================================================================
// gRPC unary call helper
// ============================================================================

/**
 * Wraps a gRPC unary call in a Promise.
 * Injects a 5 s deadline on every call.
 */
export function grpcUnary<TRequest, TResponse>(
  client: grpc.Client,
  method: string,
  request: TRequest
): Promise<TResponse> {
  return new Promise((resolve, reject) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fn = (client as any)[method] as
      | ((
          req: TRequest,
          meta: grpc.Metadata,
          opts: grpc.CallOptions,
          cb: (err: grpc.ServiceError | null, res: TResponse) => void
        ) => void)
      | undefined;

    if (typeof fn !== "function") {
      reject(new Error(`gRPC method "${method}" not found on client`));
      return;
    }

    const meta = new grpc.Metadata();
    const deadline = new Date(Date.now() + 5_000);

    fn.call(
      client,
      request,
      meta,
      { deadline },
      (err: grpc.ServiceError | null, response: TResponse) => {
        if (err) {
          logger.warn({ method, code: err.code, message: err.message }, "gRPC call error");
          reject(err);
        } else {
          resolve(response);
        }
      }
    );
  });
}
