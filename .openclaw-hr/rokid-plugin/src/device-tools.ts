// ============================================================
// 设备工具定义与注册 — 向 OpenClaw 注册拍照/导航/日程/退出等设备命令工具
// ============================================================

/** 设备工具调用对象，通过 WebSocket 下发给设备 */
export interface DeviceToolCall {
  /** 命令：take_photo | take_navigation | notify_agent_off | control_calendar */
  command: string;
  /** 动作（导航：open/close，日程：create） */
  action?: string;
  /** 导航目的地名称 */
  poi_name?: string;
  /** 导航类型：0 驾车、1 步行、2 骑行 */
  navi_type?: string;
  /** 日程标题 */
  title?: string;
  /** 日程开始时间 */
  start_time?: string;
  /** 日程结束时间 */
  end_time?: string;
}

/** 工具执行时调用的回调，由 ws-bridge-service 注册，用于直接发送工具帧 */
let _toolCallHandler: ((toolCall: DeviceToolCall) => void) | null = null;

/**
 * 注册工具调用回调。
 * ws-bridge-service 在每次 dispatch 前注册，dispatch 结束后清除。
 */
export function setToolCallHandler(handler: ((toolCall: DeviceToolCall) => void) | null) {
  _toolCallHandler = handler;
}

/**
 * 触发工具调用回调（由各工具 execute() 内部调用）
 */
export function emitToolCall(toolCall: DeviceToolCall) {
  _toolCallHandler?.(toolCall);
}

/**
 * 创建设备工具数组，供 api.registerTool() 注册到 OpenClaw
 */
export function createDeviceTools() {
  return [
    {
      name: "take_photo",
      description: '向设备下发拍照命令。当用户要求拍照、拍摄、截图、看看周围、看看这个、拍一下，或用户提到图片但实际并未提供图片（如"这张照片怎么样""帮我看看这个"），或用户想要记录眼前画面时调用。',
      parameters: {
        type: "object" as const,
        properties: {},
        required: [] as string[],
      },
      execute: async () => {
        emitToolCall({ command: "take_photo" });
        return "拍照命令已发送";
      },
    },
    {
      name: "take_navigation",
      description:
        '向设备下发导航命令。当用户想去某个地方、从A到B、问怎么走、问路线、提到开车/步行/骑行去某处、想回家、想去某个地点时调用。必须从用户描述中提取目的地填入 poi_name 参数，action 设为 "open"。如用户提到交通方式则设置 navi_type（驾车=0，步行=1，骑行=2）。如用户要求关闭/停止导航，action 设为 "close"。',
      parameters: {
        type: "object" as const,
        properties: {
          action: {
            type: "string",
            enum: ["open", "close"],
            description: "导航动作：open 打开导航，close 关闭导航",
          },
          poi_name: {
            type: "string",
            description: '导航目的地名称，例如"西湖"、"杭州东站"',
          },
          navi_type: {
            type: "string",
            enum: ["0", "1", "2"],
            description: "导航类型：0 驾车、1 步行、2 骑行",
          },
        },
        required: ["action", "poi_name"],
      },
      execute: async (args: { action: string; poi_name: string; navi_type?: string }) => {
        if (!args.action || !args.poi_name) {
          return "错误：缺少必要参数，action 和 poi_name 为必填项。请从用户描述中提取目的地填入 poi_name，并将 action 设为 open 或 close。";
        }
        emitToolCall({
          command: "take_navigation",
          action: args.action,
          poi_name: args.poi_name,
          ...(args.navi_type ? { navi_type: args.navi_type } : {}),
        });
        return "导航命令已发送";
      },
    },
    {
      name: "control_calendar",
      description:
        '向设备下发创建日程命令。当用户想设置日程、提醒、闹钟、备忘、约会、会议安排，或提到某个时间要做某事时调用。必须从用户描述中提取日程标题填入 title，提取时间填入 start_time（ISO 8601 格式），action 设为 "create"。',
      parameters: {
        type: "object" as const,
        properties: {
          action: {
            type: "string",
            enum: ["create"],
            description: "日程动作：create 创建日程",
          },
          title: {
            type: "string",
            description: "日程标题",
          },
          start_time: {
            type: "string",
            description: "日程开始时间，ISO 8601 格式",
          },
          end_time: {
            type: "string",
            description: "日程结束时间，ISO 8601 格式（可选）",
          },
        },
        required: ["action", "title", "start_time"],
      },
      execute: async (args: { action: string; title: string; start_time: string; end_time?: string }) => {
        if (!args.action || !args.title || !args.start_time) {
          return "错误：缺少必要参数，action、title 和 start_time 为必填项。请从用户描述中提取日程标题和时间信息。";
        }
        emitToolCall({
          command: "control_calendar",
          action: args.action,
          title: args.title,
          start_time: args.start_time,
          ...(args.end_time ? { end_time: args.end_time } : {}),
        });
        return "日程命令已发送";
      },
    },
    {
      name: "notify_agent_off",
      description: '向设备下发退出命令。当用户说退出、结束、关闭、不聊了、拜拜、再见时调用。',
      parameters: {
        type: "object" as const,
        properties: {},
        required: [] as string[],
      },
      execute: async () => {
        emitToolCall({ command: "notify_agent_off" });
        return "退出命令已发送";
      },
    },
  ];
}
