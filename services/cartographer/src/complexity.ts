// ============================================================================
// Query Complexity Analysis
// ============================================================================
//
// Limits are enforced in the Apollo Server plugin (server.ts) before
// execution. We define costs here and export the validator.

export const COMPLEXITY_CONFIG = {
  /** Reject queries exceeding this depth */
  maxDepth: 5,
  /** Reject queries exceeding this total complexity score */
  maxComplexity: 1000,
} as const;

// Per-field complexity costs
export const FIELD_COSTS: Record<string, number> = {
  // Query root fields
  "Query.npcs": 5,       // base cost per call — multiplied by limit arg
  "Query.npc": 1,
  "Query.worldState": 2,
  "Query.orderBook": 3,
  "Query.orders": 5,
  "Query.newspaper": 2,
  "Query.newspapers": 5,
  "Query.leaderboard": 3,
  "Query.searchHistory": 10,
  "Query.npcDecisionTrace": 5,

  // NPC nested fields
  "NPC.orders": 10,
  "NPC.dialogues": 10,
  "NPC.recentEvents": 5,
  "NPC.leaderboardRanks": 3,
  "NPC.decisionTrace": 8,

  // Subscription fields
  "Subscription.eventStream": 1,
  "Subscription.priceUpdates": 1,
};

// ============================================================================
// Depth analysis
// ============================================================================

export interface ComplexityResult {
  depth: number;
  score: number;
  errors: string[];
}

/**
 * Recursively calculates the depth and complexity score of a selection set.
 * `selectionSet` follows the GraphQL AST shape.
 */
export function analyzeComplexity(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  document: any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  variables: Record<string, any> = {}
): ComplexityResult {
  const errors: string[] = [];
  let maxDepth = 0;
  let totalScore = 0;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function visitSelections(selections: any[], parentType: string, depth: number): void {
    if (depth > maxDepth) maxDepth = depth;

    for (const selection of selections ?? []) {
      if (selection.kind !== "Field") continue;

      const fieldName = selection.name?.value as string;
      const qualifiedName = `${parentType}.${fieldName}`;
      const baseCost = FIELD_COSTS[qualifiedName] ?? 1;

      // Multiply base cost by limit argument when present
      const limitArg = selection.arguments?.find(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (a: any) => a.name?.value === "limit"
      );
      let multiplier = 1;
      if (limitArg) {
        const argValue = limitArg.value;
        if (argValue?.kind === "IntValue") {
          multiplier = parseInt(argValue.value as string, 10);
        } else if (argValue?.kind === "Variable") {
          const varName = argValue.name?.value as string;
          multiplier = Number(variables[varName] ?? 10);
        }
      }

      totalScore += baseCost * multiplier;

      if (selection.selectionSet) {
        visitSelections(
          selection.selectionSet.selections,
          fieldName.charAt(0).toUpperCase() + fieldName.slice(1),
          depth + 1
        );
      }
    }
  }

  for (const def of document.definitions ?? []) {
    if (def.kind === "OperationDefinition") {
      visitSelections(def.selectionSet?.selections ?? [], "Query", 1);
    }
  }

  if (maxDepth > COMPLEXITY_CONFIG.maxDepth) {
    errors.push(
      `Query depth ${maxDepth} exceeds maximum allowed depth ${COMPLEXITY_CONFIG.maxDepth}`
    );
  }

  if (totalScore > COMPLEXITY_CONFIG.maxComplexity) {
    errors.push(
      `Query complexity ${totalScore} exceeds maximum allowed complexity ${COMPLEXITY_CONFIG.maxComplexity}`
    );
  }

  return { depth: maxDepth, score: totalScore, errors };
}
