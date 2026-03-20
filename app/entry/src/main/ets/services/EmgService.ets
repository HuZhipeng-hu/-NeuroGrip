import { EmgData } from '../models/EmgData';

export class EmgService {
  onDataReceived: (data: EmgData) => void = () => {};
  onConnectionChanged: (connected: boolean) => void = () => {};

  connect() {
    // 占位：实际实现应创建 WebSocket/HTTP 连接并拉取数据
    // 这里模拟连接成功事件
    setTimeout(() => {
      this.onConnectionChanged(true);
      this.onDataReceived(new EmgData());
    }, 300);
  }

  disconnect() {
    this.onConnectionChanged(false);
  }
}
