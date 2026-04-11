import { start } from "./server.js";

// Entry point — delegate everything to server.ts
start().catch((err: unknown) => {
  console.error("[tavern] Fatal startup error:", err);
  process.exit(1);
});
