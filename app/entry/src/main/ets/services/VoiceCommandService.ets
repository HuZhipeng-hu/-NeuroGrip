import abilityAccessCtrl from '@ohos.abilityAccessCtrl';
import common from '@ohos.app.ability.common';
import promptAction from '@ohos.promptAction';
import router from '@ohos.router';

const DEFAULT_WAKE_WORD = '小臂助手';
const COMMAND_WINDOW_MS = 8000;

class VoiceCommandService {
  private isListening: boolean = false;
  private wakeWord: string = DEFAULT_WAKE_WORD;
  private wakeActive: boolean = false;
  private wakeTimer: number = -1;

  async start(context: common.UIAbilityContext, wakeWord?: string): Promise<void> {
    if (this.isListening) {
      return;
    }

    if (wakeWord && wakeWord.trim().length > 0) {
      this.wakeWord = wakeWord.trim();
    }

    const granted = await this.ensureMicPermission(context);
    if (!granted) {
      promptAction.showToast({ message: '语音控制需要麦克风权限' });
      return;
    }

    this.isListening = true;
    this.updateAppStorage('voice_listening', true);
    promptAction.showToast({ message: '语音控制已开启（等待云端 ASR 接入）' });
  }

  stop(): void {
    this.isListening = false;
    this.wakeActive = false;
    this.clearWakeTimer();
    this.updateAppStorage('voice_listening', false);
  }

  submitRecognizedText(text: string): void {
    if (!this.isListening) {
      return;
    }
    if (text.trim().length === 0) {
      return;
    }
    this.updateAppStorage('voice_last_text', text);
    this.handleRecognizedText(text);
  }

  private async ensureMicPermission(context: common.UIAbilityContext): Promise<boolean> {
    try {
      const atManager = abilityAccessCtrl.createAtManager();
      const result = await atManager.requestPermissionsFromUser(context, [
        'ohos.permission.MICROPHONE'
      ]);
      return result.authResults.every((status: number) => status === 0);
    } catch (e) {
      console.error('requestPermissionsFromUser failed:', JSON.stringify(e));
      return false;
    }
  }

  private handleRecognizedText(text: string): void {
    const normalized = this.normalize(text);
    const normalizedWake = this.normalize(this.wakeWord);

    if (!this.wakeActive) {
      if (normalized.includes(normalizedWake)) {
        this.activateWakeWindow();
        promptAction.showToast({ message: '已唤醒，请说指令' });
      }
      return;
    }

    this.wakeActive = false;
    this.clearWakeTimer();

    const action = this.matchCommand(normalized);
    if (!action) {
      promptAction.showToast({ message: '未识别指令' });
      return;
    }

    this.updateAppStorage('voice_last_command', action);

    switch (action) {
      case 'location':
        router.pushUrl({ url: 'pages/Location' });
        promptAction.showToast({ message: '打开定位' });
        break;
      case 'gesture':
        router.pushUrl({ url: 'pages/Training' });
        promptAction.showToast({ message: '打开手势录入' });
        break;
      case 'model':
        router.pushUrl({ url: 'pages/ModelManagePage' });
        promptAction.showToast({ message: '打开模型更新' });
        break;
      default:
        break;
    }
  }

  private activateWakeWindow(): void {
    this.wakeActive = true;
    this.clearWakeTimer();
    this.wakeTimer = setTimeout(() => {
      this.wakeActive = false;
    }, COMMAND_WINDOW_MS) as number;
  }

  private clearWakeTimer(): void {
    if (this.wakeTimer !== -1) {
      clearTimeout(this.wakeTimer);
      this.wakeTimer = -1;
    }
  }

  private matchCommand(text: string): 'location' | 'gesture' | 'model' | '' {
    if (text.includes('查看设备位置') || text.includes('查看位置') || text.includes('定位') || text.includes('打开定位')) {
      return 'location';
    }
    if (text.includes('录入手势') || text.includes('手势录入') || text.includes('录制手势') || text.includes('开始录入')) {
      return 'gesture';
    }
    if (text.includes('模型更新') || text.includes('更新模型') || text.includes('模型管理') || text.includes('模型升级')) {
      return 'model';
    }
    return '';
  }

  private normalize(text: string): string {
    return text
      .toLowerCase()
      .replace(/\s+/g, '')
      .replace(/[\uFF0C\u3002\uFF1F\uFF01\uFF1B\uFF1A,\.!?;:]/g, '');
  }

  private updateAppStorage(key: string, value: string | boolean): void {
    try {
      AppStorage.SetOrCreate(key, value);
    } catch (e) {
      // ignore
    }
  }
}

export const voiceCommandService = new VoiceCommandService();
