/**
 * memL - OpenClaw Memory Plugin
 * 
 * Provides cloud-based persistent memory via memL service.
 */

import { Type } from "@sinclair/typebox";

interface MemLConfig {
  apiUrl: string;
  apiKey: string;
  autoInject?: boolean;
  maxMemories?: number;
}

interface Memory {
  id: string;
  text: string;
  tags: string[];
  meta: Record<string, unknown>;
  created: string;
  updated: string;
  score?: number;
}

interface MemLResponse {
  ok: boolean;
  data?: Memory | { total: number; results: Memory[] } | Record<string, unknown>;
  error?: { code: string; message: string };
}

async function memLRequest(
  config: MemLConfig,
  method: string,
  path: string,
  body?: unknown
): Promise<MemLResponse> {
  const url = `${config.apiUrl}${path}`;
  const headers: Record<string, string> = {
    "Authorization": `Bearer ${config.apiKey}`,
    "Content-Type": "application/json",
  };

  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  return response.json();
}

export default function register(api: any) {
  const logger = api.logger.child({ plugin: "memL" });

  // Get config helper
  function getConfig(): MemLConfig | null {
    const cfg = api.config?.plugins?.entries?.meml?.config;
    if (!cfg?.apiUrl || !cfg?.apiKey) {
      return null;
    }
    return {
      apiUrl: cfg.apiUrl,
      apiKey: cfg.apiKey,
      autoInject: cfg.autoInject ?? true,
      maxMemories: cfg.maxMemories ?? 10,
    };
  }

  // ========================================
  // Agent Tools
  // ========================================

  // memory_store - Store a new memory
  api.registerTool({
    name: "memory_store",
    description: "Store a memory to the cloud memory service. Use this to persist important information about the user, decisions, preferences, or context that should be remembered across sessions.",
    parameters: Type.Object({
      text: Type.String({ description: "The memory content to store" }),
      tags: Type.Optional(Type.Array(Type.String(), { description: "Tags for categorizing this memory" })),
      meta: Type.Optional(Type.Record(Type.String(), Type.Any(), { description: "Optional metadata" })),
    }),
    async execute(_id: string, params: { text: string; tags?: string[]; meta?: Record<string, unknown> }) {
      const config = getConfig();
      if (!config) {
        return { content: [{ type: "text", text: "Error: memL plugin not configured. Set apiUrl and apiKey in plugins.entries.meml.config" }] };
      }

      try {
        const result = await memLRequest(config, "POST", "/memory", {
          text: params.text,
          tags: params.tags ?? [],
          meta: params.meta ?? {},
        });

        if (!result.ok) {
          return { content: [{ type: "text", text: `Error: ${result.error?.message || "Unknown error"}` }] };
        }

        const memory = result.data as Memory;
        return {
          content: [{
            type: "text",
            text: `Memory stored successfully.\nID: ${memory.id}\nText: ${memory.text}\nTags: ${memory.tags.join(", ") || "none"}`,
          }],
        };
      } catch (err: any) {
        return { content: [{ type: "text", text: `Error storing memory: ${err.message}` }] };
      }
    },
  });

  // memory_search - Search memories
  api.registerTool({
    name: "memory_search",
    description: "Search memories using semantic search. Finds memories that are semantically similar to the query, not just keyword matches.",
    parameters: Type.Object({
      q: Type.String({ description: "The search query (semantic search)" }),
      tags: Type.Optional(Type.Array(Type.String(), { description: "Filter by tags" })),
      tag_mode: Type.Optional(Type.String({ description: "Tag filter mode: 'any' or 'all'" })),
      limit: Type.Optional(Type.Number({ description: "Maximum results to return (default 10)" })),
    }),
    async execute(_id: string, params: { q: string; tags?: string[]; tag_mode?: string; limit?: number }) {
      const config = getConfig();
      if (!config) {
        return { content: [{ type: "text", text: "Error: memL plugin not configured" }] };
      }

      try {
        const queryParams = new URLSearchParams();
        queryParams.set("q", params.q);
        if (params.tags?.length) {
          params.tags.forEach(t => queryParams.append("tags", t));
        }
        if (params.tag_mode) {
          queryParams.set("tag_mode", params.tag_mode);
        }
        if (params.limit) {
          queryParams.set("limit", String(params.limit));
        }

        const result = await memLRequest(config, "GET", `/memory?${queryParams}`);

        if (!result.ok) {
          return { content: [{ type: "text", text: `Error: ${result.error?.message || "Unknown error"}` }] };
        }

        const data = result.data as { total: number; results: Memory[] };
        
        if (data.results.length === 0) {
          return { content: [{ type: "text", text: "No memories found matching the query." }] };
        }

        const lines = [`Found ${data.total} memory(ies):`, ""];
        for (const mem of data.results) {
          const score = mem.score ? ` (score: ${mem.score.toFixed(3)})` : "";
          lines.push(`[${mem.id}]${score}`);
          lines.push(`  ${mem.text}`);
          if (mem.tags.length > 0) {
            lines.push(`  Tags: ${mem.tags.join(", ")}`);
          }
          lines.push("");
        }

        return { content: [{ type: "text", text: lines.join("\n") }] };
      } catch (err: any) {
        return { content: [{ type: "text", text: `Error searching memories: ${err.message}` }] };
      }
    },
  });

  // memory_get - Get a specific memory by ID
  api.registerTool({
    name: "memory_get",
    description: "Retrieve a specific memory by its ID.",
    parameters: Type.Object({
      id: Type.String({ description: "The memory ID" }),
    }),
    async execute(_id: string, params: { id: string }) {
      const config = getConfig();
      if (!config) {
        return { content: [{ type: "text", text: "Error: memL plugin not configured" }] };
      }

      try {
        const result = await memLRequest(config, "GET", `/memory/${params.id}`);

        if (!result.ok) {
          return { content: [{ type: "text", text: `Error: ${result.error?.message || "Memory not found"}` }] };
        }

        const mem = result.data as Memory;
        const lines = [
          `Memory [${mem.id}]`,
          `Text: ${mem.text}`,
          `Tags: ${mem.tags.join(", ") || "none"}`,
          `Created: ${mem.created}`,
          `Updated: ${mem.updated}`,
        ];
        if (Object.keys(mem.meta).length > 0) {
          lines.push(`Meta: ${JSON.stringify(mem.meta)}`);
        }

        return { content: [{ type: "text", text: lines.join("\n") }] };
      } catch (err: any) {
        return { content: [{ type: "text", text: `Error getting memory: ${err.message}` }] };
      }
    },
  });

  // memory_update - Update a memory
  api.registerTool({
    name: "memory_update",
    description: "Update an existing memory. Only provided fields will be updated.",
    parameters: Type.Object({
      id: Type.String({ description: "The memory ID to update" }),
      text: Type.Optional(Type.String({ description: "New text content" })),
      tags: Type.Optional(Type.Array(Type.String(), { description: "New tags" })),
      meta: Type.Optional(Type.Record(Type.String(), Type.Any(), { description: "New metadata" })),
    }),
    async execute(_id: string, params: { id: string; text?: string; tags?: string[]; meta?: Record<string, unknown> }) {
      const config = getConfig();
      if (!config) {
        return { content: [{ type: "text", text: "Error: memL plugin not configured" }] };
      }

      try {
        const body: Record<string, unknown> = {};
        if (params.text !== undefined) body.text = params.text;
        if (params.tags !== undefined) body.tags = params.tags;
        if (params.meta !== undefined) body.meta = params.meta;

        const result = await memLRequest(config, "PATCH", `/memory/${params.id}`, body);

        if (!result.ok) {
          return { content: [{ type: "text", text: `Error: ${result.error?.message || "Unknown error"}` }] };
        }

        const mem = result.data as Memory;
        return {
          content: [{
            type: "text",
            text: `Memory updated.\nID: ${mem.id}\nText: ${mem.text}\nTags: ${mem.tags.join(", ") || "none"}`,
          }],
        };
      } catch (err: any) {
        return { content: [{ type: "text", text: `Error updating memory: ${err.message}` }] };
      }
    },
  });

  // memory_delete - Delete a memory
  api.registerTool({
    name: "memory_delete",
    description: "Delete a memory by its ID. This is permanent and cannot be undone.",
    parameters: Type.Object({
      id: Type.String({ description: "The memory ID to delete" }),
    }),
    async execute(_id: string, params: { id: string }) {
      const config = getConfig();
      if (!config) {
        return { content: [{ type: "text", text: "Error: memL plugin not configured" }] };
      }

      try {
        const result = await memLRequest(config, "DELETE", `/memory/${params.id}`);

        if (!result.ok) {
          return { content: [{ type: "text", text: `Error: ${result.error?.message || "Unknown error"}` }] };
        }

        return { content: [{ type: "text", text: `Memory ${params.id} deleted.` }] };
      } catch (err: any) {
        return { content: [{ type: "text", text: `Error deleting memory: ${err.message}` }] };
      }
    },
  });

  // ========================================
  // Lifecycle Hook: Auto-inject memories
  // ========================================

  api.on(
    "before_prompt_build",
    async (event: string, ctx: any) => {
      const config = getConfig();
      
      // Skip if not configured or auto-inject disabled
      if (!config || config.autoInject === false) {
        return {};
      }

      // Get the last user message to search for relevant memories
      const messages = ctx?.messages || [];
      const lastUserMessage = [...messages].reverse().find((m: any) => m.role === "user");
      
      if (!lastUserMessage?.content) {
        return {};
      }

      // Extract text from message
      let queryText = "";
      if (typeof lastUserMessage.content === "string") {
        queryText = lastUserMessage.content;
      } else if (Array.isArray(lastUserMessage.content)) {
        for (const part of lastUserMessage.content) {
          if (part.type === "text") {
            queryText = part.text;
            break;
          }
        }
      }

      if (!queryText || queryText.length < 5) {
        return {};
      }

      try {
        // Search for relevant memories
        const queryParams = new URLSearchParams();
        queryParams.set("q", queryText.slice(0, 500)); // Limit query length
        queryParams.set("limit", String(config.maxMemories || 10));

        const result = await memLRequest(config, "GET", `/memory?${queryParams}`);

        if (!result.ok || !result.data) {
          logger.debug("Memory search failed, skipping injection");
          return {};
        }

        const data = result.data as { total: number; results: Memory[] };
        
        if (data.results.length === 0) {
          return {};
        }

        // Build context from memories
        const memoryLines = [
          "📚 Relevant memories from previous conversations:",
          "",
        ];

        for (const mem of data.results) {
          memoryLines.push(`• ${mem.text}`);
          if (mem.tags.length > 0) {
            memoryLines.push(`  (tags: ${mem.tags.join(", ")})`);
          }
        }

        memoryLines.push("");
        memoryLines.push("Use these memories to provide contextually relevant responses.");
        memoryLines.push("---");
        memoryLines.push("");

        logger.info(`Injected ${data.results.length} relevant memories`);
        
        return {
          prependContext: memoryLines.join("\n"),
        };
      } catch (err: any) {
        logger.warn(`Failed to inject memories: ${err.message}`);
        return {};
      }
    },
    { priority: 100 } // Run early so memories are prepended
  );

  logger.info("memL plugin loaded");
}
