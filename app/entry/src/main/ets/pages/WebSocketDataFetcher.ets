// //WebSocketDataFetcher.ets
// import webSocket from '@ohos.net.webSocket';
// import { BusinessError } from '@ohos.base';
//
// export interface WebSocketMessage {
//   deviceId: string;
//   deviceTs: number;
//   serverTime: string;
//   gesture: string;
//   confidence: number;
//   battery: number;
//   emg: number[][];
//   acc: number[];
//   gyro: number[];
//   angle: number[];
// }
//
// type OnDataReceived = (data: WebSocketMessage) => void;
// type OnErrorOccurred = (error: string) => void;
//
// @Component
// export struct WebSocketDataFetcher {
//   private url: string = 'ws://1.95.65.51:8080/ws/app';
//   private ws: webSocket.WebSocket | null = null;
//
//   // 👇 使用普通字段，不要用 readonly 或 auto-bind
//   // 替换原来的 private 字段声明
//   onData: OnDataReceived | undefined = undefined;
//   onError: OnErrorOccurred | undefined = undefined;
//
//
//
//   aboutToAppear() {
//     this.connect();
//   }
//
//   aboutToDisappear() {
//     this.disconnect();
//   }
//
//   private connect() {
//     if (this.ws) return;
//
//     const ws = webSocket.createWebSocket();
//     this.ws = ws;
//
//     ws.connect(this.url, (err: BusinessError) => {
//       if (err) {
//         this.onError?.(`连接失败: ${err.message}`);
//         return;
//       }
//     });
//
//     ws.on('open', (err: BusinessError) => {
//       if (err) {
//         this.onError?.(`打开失败: ${err.message}`);
//         return;
//       }
//       ws.send('{"action":"get_latest"}', (sendErr: BusinessError) => {
//         if (sendErr) {
//           console.warn('发送 get_latest 失败:', sendErr.message);
//         }
//       });
//     });
//
//     ws.on('message', (err: BusinessError, data: string | ArrayBuffer) => {
//       if (err) {
//         this.onError?.(`接收消息出错: ${err.message}`);
//         return;
//       }
//
//       let rawMsg = '';
//       try {
//         if (typeof data === 'string') {
//           rawMsg = data;
//         } else if (data instanceof ArrayBuffer) {
//           const uint8 = new Uint8Array(data);
//           rawMsg = String.fromCharCode(...uint8);
//         }
//
//         const json = JSON.parse(rawMsg) as WebSocketMessage;
//         this.onData?.(json); // ✅ 发送数据
//       } catch (e) {
//         const error = e as Error;
//         this.onError?.(`解析失败: ${error.message} | 原始: ${rawMsg.substring(0, 50)}...`);
//       }
//     });
//
//     ws.on('error', (err: BusinessError) => {
//       this.onError?.(`WebSocket 错误: ${err.message}`);
//     });
//
//     ws.on('close', (err: BusinessError, result: webSocket.CloseResult) => {
//       console.info('WebSocket closed, code:', result?.code);
//       this.ws = null;
//     });
//   }
//
//   private disconnect() {
//     if (this.ws) {
//       this.ws.close((err: BusinessError) => {
//         if (err) {
//           console.error('关闭 WebSocket 出错:', err.message);
//         }
//       });
//       this.ws = null;
//     }
//   }
//
//   build() {
//     Column() {}
//   }
// }