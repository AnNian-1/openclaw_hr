// ============================================================
// WebSocket Bridge Protocol — 入站 JSON 消息类型定义
// ============================================================

// ------ 入站消息（用户服务 → 插件） ------

/** 单条消息对象（支持文本与图片） */
export interface MessageObject {
  /** 角色：user / agent */
  role: "user" | "agent";
  /** 消息类型：text / image */
  type: "text" | "image";
  /** 消息内容：type 为 text 时不可为空 */
  text?: string;
  /** 图片地址：type 为 image 时不可为空 */
  image_url?: string;
}

/** 用户服务推送的消息 */
export interface WsBridgeRequest {
  /** 消息内容（消息对象数组） */
  messages: MessageObject[];
  /** 唯一请求 ID，用于关联响应 */
  requestId: string;
  /** 可选：会话 key，用于多轮对话持久化 */
  sessionKey?: string;
  /** 可选：历史消息，由调用方维护（当前桥接层保持兼容但不消费） */
  history?: Array<{
    role: "user" | "assistant" | "system";
    content: string;
  }>;
}

/** 取消正在进行的请求 */
export interface WsBridgeCancel {
  type: "cancel";
  requestId: string;
}

export type InboundMessage = WsBridgeRequest | WsBridgeCancel;

// ------ 设备工具调用帧（插件 → 设备） ------

/** 设备工具调用对象 */
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

/** 工具调用帧：通知设备执行设备命令 */
export interface WsBridgeToolCallFrame {
  event: "message";
  data: {
    role: "agent";
    message_id: string;
    agent_id: string;
    is_finish: false;
    type: "tool_call";
    tool_call: DeviceToolCall;
  };
}
