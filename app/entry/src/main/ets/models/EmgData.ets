export interface GestureEvent {
  gesture: string;
  confidence?: number;
  timestamp?: number;
}

export class EmgData {
  deviceId?: string;
  gesture?: string;
  confidence?: number;
  battery?: number;
  emg?: number[][]; // 2D: frames x channels
  acc?: number[];   // [x, y, z]
  gyro?: number[];  // [x, y, z]
  angle?: number[]; // [roll, pitch, yaw]
  timestamp?: number;

  constructor(init?: Partial<EmgData>) {
    if (!init) {
      return;
    }
    this.deviceId = init.deviceId;
    this.gesture = init.gesture;
    this.confidence = init.confidence;
    this.battery = init.battery;
    this.emg = init.emg;
    this.acc = init.acc;
    this.gyro = init.gyro;
    this.angle = init.angle;
    this.timestamp = init.timestamp;
  }
}
