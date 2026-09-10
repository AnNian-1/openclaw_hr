// ============================================================
// WebSocket Bridge 核心服务
// 管理 WebSocket 客户端连接、消息路由、并发请求、自动重连
// ============================================================

import type { OpenClawConfig, PluginRuntime, ReplyPayload } from "openclaw/plugin-sdk";
import WebSocket from "ws";
import type { WsBridgeRequest, MessageObject } from "./protocol.js";
import { type DeviceToolCall, setToolCallHandler } from "./device-tools.js";

/** WebSocket Bridge 服务的完整配置 */
export interface WsBridgeConfig {
  /** WebSocket 服务端地址 */
  wsUrl: string;
  /** 设备鉴权 linkCode */
  linkCode: string;
  /** 设备鉴权 linkSecret */
  linkSecret: string;
  /** 断线重连最大次数 */
  reconnectMaxRetries: number;
  /** 断线重连基础延迟（毫秒） */
  reconnectBaseDelayMs: number;
  /** OpenClaw 运行时上下文 */
  openclaw: {
    /** 动态获取最新全局配置的函数 */
    getCfg: () => OpenClawConfig;
    /** 当前账号 ID */
    accountId?: string | null;
    /** 通道 ID */
    channelId: string;
    /** 通道运行时实例 */
    channelRuntime: PluginRuntime["channel"];
  };
}

/** 流式消息帧：向客户端推送一段增量回复文本 */
interface WsBridgeMessageFrame {
  event: "message";
  data: {
    role: "agent";
    message_id: string;
    agent_id: string;
    answer_stream: string;
    is_finish: false;
    type: "answer";
  };
}

/** 完成帧：通知客户端本次请求的流式回复已全部发送完毕 */
interface WsBridgeDoneFrame {
  event: "done";
  data: {
    role: "agent";
    message_id: string;
    agent_id: string;
    answer_stream: "";
    is_finish: true;
    type: "answer";
  };
}

/** 错误帧：向客户端报告处理失败 */
interface WsBridgeErrorFrame {
  type: "error";
  requestId: string;
  code: string;
  message: string;
}

/** 连接状态帧 */
interface WsBridgeStatusFrame {
  type: "status";
  connected: boolean;
}

/** 工具调用帧：通知设备执行设备命令（done 事件，is_finish=true） */
interface WsBridgeToolCallFrame {
  event: "done";
  data: {
    role: "agent";
    message_id: string;
    agent_id: string;
    is_finish: true;
    type: "tool_call";
    tool_call: DeviceToolCall;
  };
}

/** 所有可下行的帧类型联合 */
type OutboundFrame =
  | WsBridgeMessageFrame
  | WsBridgeDoneFrame
  | WsBridgeErrorFrame
  | WsBridgeStatusFrame
  | WsBridgeToolCallFrame;

/**
 * 拼接完整的 WebSocket 连接地址
 */
function buildWsUrl(config: WsBridgeConfig): string {
  const url = new URL(config.wsUrl);
  url.searchParams.set("linkCode", config.linkCode);
  url.searchParams.set("linkSecret", config.linkSecret);
  return url.toString();
}

interface Logger {
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
}

function backoffDelay(attempt: number, baseMs: number, maxMs = 30000): number {
  const delay = baseMs * Math.pow(2, attempt);
  const jitter = Math.random() * baseMs;
  return Math.min(delay + jitter, maxMs);
}

function normalizeAccountId(accountId?: string | null, linkCode?: string): string {
  const trimmed = typeof accountId === "string" ? accountId.trim() : "";
  return trimmed || (linkCode ?? "");
}

function normalizeTextPayload(payload: ReplyPayload): string {
  return typeof payload.text === "string" ? payload.text : "";
}

/**
 * 创建并返回 WebSocket Bridge 服务实例
 */
export function createWsBridgeService(config: WsBridgeConfig, logger: Logger) {
  let ws: WebSocket | null = null;
  let reconnectAttempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  /** 内部请求自增 ID */
  let nextInternalId = 0;
  /** 正在处理的请求集合，key 为内部自增 ID */
  const activeRequests = new Map<number, { requestId: string; ctrl: AbortController; agentId: string }>();
  /** 每个 requestId 的最新内部 ID，用于判断当前请求是否仍为最新 */
  const latestInternalIdByRequestId = new Map<string, number>();
  /** 正在执行的 dispatch Promise，key 为 internalId，用于等待旧请求真正结束 */
  const pendingDispatches = new Map<number, Promise<void>>();

  const accountId = normalizeAccountId(config.openclaw.accountId, config.linkCode);
  const rt = config.openclaw.channelRuntime;
  const getCfg = config.openclaw.getCfg;
  const channelId = config.openclaw.channelId;

  function sendWs(msg: OutboundFrame) {
    if (ws?.readyState === WebSocket.OPEN) {
      const raw = JSON.stringify(msg);
      logger.info(`[rokid-openclaw-bridge] >>> SEND: ${raw}`);
      ws.send(raw);
    }
  }

  function sendStreamChunk(requestId: string, agentId: string, delta: string) {
    if (!delta) return;
    sendWs({
      event: "message",
      data: {
        role: "agent",
        message_id: requestId,
        agent_id: agentId,
        answer_stream: delta,
        is_finish: false,
        type: "answer",
      },
    });
  }

  function sendDone(requestId: string, agentId: string) {
    sendWs({
      event: "done",
      data: {
        role: "agent",
        message_id: requestId,
        agent_id: agentId,
        answer_stream: "",
        is_finish: true,
        type: "answer",
      },
    });
  }

  function sendToolCall(requestId: string, agentId: string, toolCall: DeviceToolCall) {
    sendWs({
      event: "done",
      data: {
        role: "agent",
        message_id: requestId,
        agent_id: agentId,
        is_finish: true,
        type: "tool_call",
        tool_call: toolCall,
      },
    });
  }

  function handleMessage(raw: string) {
    let msg: unknown;
    try {
      msg = JSON.parse(raw);
    } catch {
      logger.warn(`[rokid-openclaw-bridge] Invalid JSON received: ${raw.slice(0, 200)}`);
      return;
    }

    if (!msg || typeof msg !== "object") return;
    const parsed = msg as Record<string, unknown>;

    if (parsed.type === "cancel" && typeof parsed.requestId === "string") {
      handleCancel(parsed.requestId);
      return;
    }

    // 兼容两种字段名：messages/requestId（RCS 服务端转发）和 message/message_id（HTTP 透传）
    const messages = parsed.messages ?? parsed.message;
    const requestId = parsed.requestId ?? parsed.message_id;

    if (Array.isArray(messages) && typeof requestId === "string") {
      void handleChatRequest({ messages, requestId, sessionKey: parsed.sessionKey as string | undefined, history: parsed.history as any } as WsBridgeRequest);
      return;
    }

    logger.warn(`[rokid-openclaw-bridge] Unrecognized message: ${raw.slice(0, 200)}`);
  }

  /**
   * 判断当前 internalId 是否仍是该 requestId 的最新请求
   */
  function isStaleRequest(requestId: string, internalId: number): boolean {
    return latestInternalIdByRequestId.get(requestId) !== internalId;
  }

  async function handleChatRequest(request: WsBridgeRequest) {
    // 打断：中止所有进行中的旧请求，确保同一时间只处理最新请求
    const waitList: Promise<void>[] = [];
    for (const [prevId, entry] of activeRequests) {
      if (entry.requestId !== request.requestId) {
        sendDone(entry.requestId, entry.agentId);
      }
      entry.ctrl.abort();
      activeRequests.delete(prevId);
      logger.info(`[rokid-openclaw-bridge] Interrupted previous request ${entry.requestId} by new request ${request.requestId}`);
      const pending = pendingDispatches.get(prevId);
      if (pending) {
        waitList.push(pending);
      }
    }

    // 等待所有被打断的旧请求真正结束
    if (waitList.length > 0) {
      logger.info(`[rokid-openclaw-bridge] Waiting for ${waitList.length} aborted request(s) to finish before starting ${request.requestId}`);
      await Promise.allSettled(waitList);
    }

    const abortCtrl = new AbortController();
    const internalId = nextInternalId++;
    logger.info(`[rokid-openclaw-bridge] New request registered: requestId=${request.requestId}, internalId=${internalId}`);
    activeRequests.set(internalId, { requestId: request.requestId, ctrl: abortCtrl, agentId: "" });
    latestInternalIdByRequestId.set(request.requestId, internalId);

    const dispatchPromise = handleChatRequestWithRuntime(request, abortCtrl, internalId)
      .catch(() => {})
      .finally(() => {
        pendingDispatches.delete(internalId);
      });
    pendingDispatches.set(internalId, dispatchPromise);

    try {
      await dispatchPromise;
    } finally {
      logger.info(`[rokid-openclaw-bridge] Request finished: requestId=${request.requestId}, internalId=${internalId}, aborted=${abortCtrl.signal.aborted}, stale=${isStaleRequest(request.requestId, internalId)}`);
      activeRequests.delete(internalId);
      if (latestInternalIdByRequestId.get(request.requestId) === internalId) {
        latestInternalIdByRequestId.delete(request.requestId);
      }
    }
  }

  async function handleChatRequestWithRuntime(
    request: WsBridgeRequest,
    abortCtrl: AbortController,
    internalId: number
  ) {
    let lastPartialText = "";
    let partialStreamed = false;
    let finalFallbackText = "";
    let toolCallEmitted = false;

    try {
      const cfg = getCfg();

      const route = rt.routing.resolveAgentRoute({
        cfg,
        channel: channelId,
        accountId,
        peer: { kind: "direct", id: accountId },
      });

      // 路由解析完成后，将 agentId 写入 activeRequests
      for (const [, entry] of activeRequests) {
        if (entry.ctrl === abortCtrl) {
          entry.agentId = route.agentId;
          break;
        }
      }

      const sessionKey = request.sessionKey ?? route.sessionKey;
      const storePath = rt.session.resolveStorePath(cfg.session?.store, {
        agentId: route.agentId,
      });
      const previousTimestamp = rt.session.readSessionUpdatedAt({
        storePath,
        sessionKey,
      });

      // 解析 MessageObject[] messages：提取文本和图片
      const rawBody = request.messages
        .filter((m: MessageObject) => m.type === "text" && m.text)
        .map((m: MessageObject) => m.text)
        .join("\n");
      const imageUrls = request.messages
        .filter((m: MessageObject) => m.type === "image" && m.image_url)
        .map((m: MessageObject) => m.image_url!);

      const body = rt.reply.formatAgentEnvelope({
        channel: "WebSocket Bridge",
        from: accountId,
        timestamp: Date.now(),
        envelope: rt.reply.resolveEnvelopeFormatOptions(cfg),
        body: rawBody,
        previousTimestamp,
      });

      const ctxPayload = rt.reply.finalizeInboundContext({
        Body: body,
        BodyForAgent: rawBody,
        RawBody: rawBody,
        CommandBody: rawBody,
        From: `rokid-openclaw-bridge:${accountId}`,
        To: `rokid-openclaw-bridge:${accountId}`,
        SessionKey: sessionKey,
        AccountId: route.accountId,
        ChatType: "direct",
        ConversationLabel: accountId,
        SenderName: accountId,
        SenderId: accountId,
        Provider: channelId,
        Surface: channelId,
        MessageSid: `${request.requestId}_${internalId}`,
        Timestamp: Date.now(),
        MediaUrl: imageUrls[0],
        MediaUrls: imageUrls.length > 0 ? imageUrls : undefined,
        MediaPath: imageUrls[0],
        MediaPaths: imageUrls.length > 0 ? imageUrls : undefined,
        MediaType: imageUrls.length > 0 ? "image/jpeg" : undefined,
        MediaTypes: imageUrls.length > 0 ? imageUrls.map(() => "image/jpeg") : undefined,
        OriginatingChannel: channelId,
        OriginatingTo: `rokid-openclaw-bridge:${accountId}`,
      });

      await rt.session.recordInboundSession({
        storePath,
        sessionKey: ctxPayload.SessionKey ?? route.sessionKey,
        ctx: ctxPayload,
        updateLastRoute: {
          sessionKey: route.mainSessionKey,
          channel: channelId,
          to: `rokid-openclaw-bridge:${accountId}`,
          accountId: route.accountId,
        },
        onRecordError: (err: unknown) => {
          logger.warn(`[rokid-openclaw-bridge] Failed to record inbound session: ${String(err)}`);
        },
      });

      // 注册工具调用回调，工具 execute() 触发时直接发送工具帧
      logger.info(`[rokid-openclaw-bridge] Dispatching reply: requestId=${request.requestId}, internalId=${internalId}`);
      setToolCallHandler((toolCall) => {
        logger.info(`[rokid-openclaw-bridge] Tool call sent to device: ${JSON.stringify(toolCall)}`);
        // 工具调用直接发送 done 帧（is_finish=true）并终止后续流式输出
        toolCallEmitted = true;
        sendToolCall(request.requestId, route.agentId, toolCall);
        abortCtrl.abort();
      });

      try {
        await rt.reply.dispatchReplyWithBufferedBlockDispatcher({
          ctx: ctxPayload,
          cfg,
          dispatcherOptions: {
            responsePrefix: "",
            deliver: async (payload, _info) => {
              if (abortCtrl.signal.aborted) return;
              if (isStaleRequest(request.requestId, internalId)) return;
              if (payload.isReasoning) return;
              const text = normalizeTextPayload(payload);
              if (!text) return;
              if (partialStreamed) return;
              finalFallbackText = text;
            },
            onError: (err) => {
              logger.error(`[rokid-openclaw-bridge] Dispatch delivery error: ${String(err)}`);
            },
          },
          replyOptions: {
            abortSignal: abortCtrl.signal,
            disableBlockStreaming: true,
            onPartialReply: async (payload) => {
              if (abortCtrl.signal.aborted) return;
              if (isStaleRequest(request.requestId, internalId)) return;
              if (payload.isReasoning) return;
              const rawText = normalizeTextPayload(payload);
              if (!rawText) return;
              const text = rawText.trim();
              if (!text) return;
              const delta = text.startsWith(lastPartialText) ? text.slice(lastPartialText.length) : text;
              lastPartialText = text;
              if (!delta) return;
              partialStreamed = true;
              sendStreamChunk(request.requestId, route.agentId, delta);
            },
          },
        });
      } finally {
        setToolCallHandler(null);
      }

      if (!toolCallEmitted && !abortCtrl.signal.aborted && !isStaleRequest(request.requestId, internalId)) {
        if (!partialStreamed && finalFallbackText) {
          const cleaned = finalFallbackText.trim();
          if (cleaned) {
            sendStreamChunk(request.requestId, route.agentId, cleaned);
          }
        }
        sendDone(request.requestId, route.agentId);
      }
    } catch (err: unknown) {
      if (toolCallEmitted || abortCtrl.signal.aborted || isStaleRequest(request.requestId, internalId)) return;
      const message = err instanceof Error ? err.message : String(err);
      logger.error(`[rokid-openclaw-bridge] OpenClaw dispatch failed for ${request.requestId}: ${message}`);
      sendWs({
        type: "error",
        requestId: request.requestId,
        code: "DISPATCH_ERROR",
        message,
      });
    }
  }

  function handleCancel(requestId: string) {
    for (const [id, entry] of activeRequests) {
      if (entry.requestId === requestId) {
        entry.ctrl.abort();
        activeRequests.delete(id);
        logger.info(`[rokid-openclaw-bridge] Request ${requestId} cancelled`);
        return;
      }
    }
  }

  function connect() {
    if (stopped) return;

    const fullWsUrl = buildWsUrl(config);
    logger.info(
      `[rokid-openclaw-bridge] Connecting to ${fullWsUrl} (attempt ${reconnectAttempt + 1})`
    );

    ws = new WebSocket(fullWsUrl);

    ws.on("open", () => {
      reconnectAttempt = 0;
      logger.info(`[rokid-openclaw-bridge] Connected to ${config.wsUrl}`);
      sendWs({ type: "status", connected: true });
    });

    ws.on("message", (data) => {
      const raw = data.toString();
      logger.info(`[rokid-openclaw-bridge] <<< RECV: ${raw.slice(0, 500)}`);
      handleMessage(raw);
    });

    ws.on("close", (code, reason) => {
      logger.warn(
        `[rokid-openclaw-bridge] Disconnected (code=${code}, reason=${reason.toString()})`
      );
      scheduleReconnect();
    });

    ws.on("error", (err) => {
      logger.error(`[rokid-openclaw-bridge] WebSocket error: ${err.message}`);
    });
  }

  function scheduleReconnect() {
    if (stopped) return;

    if (reconnectAttempt >= config.reconnectMaxRetries) {
      logger.error(
        `[rokid-openclaw-bridge] Max reconnect retries (${config.reconnectMaxRetries}) exhausted. Giving up.`
      );
      return;
    }

    const delay = backoffDelay(reconnectAttempt, config.reconnectBaseDelayMs);
    reconnectAttempt++;
    logger.info(`[rokid-openclaw-bridge] Reconnecting in ${Math.round(delay)}ms...`);

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  return {
    id: "rokid-openclaw-bridge",

    async start() {
      stopped = false;
      connect();
    },

    async stop() {
      stopped = true;

      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }

      for (const [id, entry] of activeRequests) {
        entry.ctrl.abort();
        activeRequests.delete(id);
      }

      if (ws) {
        ws.removeAllListeners();
        if (ws.readyState === WebSocket.OPEN) {
          ws.close(1000, "Plugin stopping");
        }
        ws = null;
      }

      logger.info("[rokid-openclaw-bridge] Service stopped");
    },
  };
}
