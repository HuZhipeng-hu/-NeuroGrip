import router from '@ohos.router';
import preferences from '@ohos.data.preferences';
import promptAction from '@ohos.promptAction';
import common from '@ohos.app.ability.common';
import { CustomAppBar } from './CustomAppBar';
import { voiceCommandService } from '../services/VoiceCommandService';

@Entry
@Component
struct VoiceControlPage {
  @State voiceEnabled: boolean = false;
  @State wakeWord: string = '小臂助手';

  aboutToAppear() {
    this.loadVoicePrefs();
  }

  build() {
    Column() {
      CustomAppBar({ title: '语音控制', onBack: () => router.back(), showSettings: false })

      Scroll() {
        Column({ space: 12 }) {
          this.buildStatusCard();
          this.buildWakeWordCard();
          this.buildHelpCard();
        }
        .width('100%')
        .padding({ left: 16, right: 16, top: 12, bottom: 20 })
      }
      .layoutWeight(1)
      .scrollBar(BarState.Off)
      .backgroundColor('#F8FAFC')
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F8FAFC');
  }

  @Builder
  private buildStatusCard() {
    Column({ space: 8 }) {
      Row() {
        Text('状态')
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
        Blank();
        Text(this.voiceEnabled ? '已开启' : '已关闭')
          .fontSize(14)
          .fontColor(this.voiceEnabled ? '#10B981' : '#6B7280')
      }

      Text(this.voiceEnabled ? '已唤醒后可说指令' : '开启后说出唤醒词')
        .fontSize(13)
        .fontColor('#6B7280')

      Button(this.voiceEnabled ? '关闭语音控制' : '开启语音控制')
        .width('100%')
        .height(44)
        .backgroundColor(this.voiceEnabled ? '#EF4444' : '#1E40AF')
        .fontColor('#FFFFFF')
        .onClick(() => {
          this.toggleVoiceControl();
        })
    }
    .width('100%')
    .padding(16)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
  }

  @Builder
  private buildWakeWordCard() {
    Column({ space: 8 }) {
      Text('唤醒词')
        .fontSize(16)
        .fontWeight(FontWeight.Medium)

      TextInput({ text: this.wakeWord, placeholder: '例如：小臂助手' })
        .height(44)
        .backgroundColor('#F9FAFB')
        .borderRadius(8)
        .padding({ left: 12 })
        .onChange((val: string) => {
          this.wakeWord = val;
        })

      Button('保存唤醒词')
        .width('100%')
        .height(40)
        .backgroundColor('#10B981')
        .fontColor('#FFFFFF')
        .onClick(() => {
          this.saveWakeWord();
        })
    }
    .width('100%')
    .padding(16)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
  }

  @Builder
  private buildHelpCard() {
    Column({ space: 8 }) {
      Text('可用指令示例')
        .fontSize(16)
        .fontWeight(FontWeight.Medium)

      Text('查看设备位置 / 定位 / 打开定位')
        .fontSize(13)
        .fontColor('#6B7280')

      Text('录入手势 / 手势录入 / 录制手势')
        .fontSize(13)
        .fontColor('#6B7280')

      Text('模型更新 / 模型管理 / 更新模型')
        .fontSize(13)
        .fontColor('#6B7280')
    }
    .width('100%')
    .padding(16)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
  }

  private loadVoicePrefs(): void {
    const context = getContext(this) as common.UIAbilityContext;
    preferences.getPreferences(context, 'voice_prefs', (err, prefs) => {
      if (err || !prefs) {
        return;
      }
      this.voiceEnabled = Boolean(prefs.getSync('voice_enabled', false));
      this.wakeWord = String(prefs.getSync('voice_wake_word', '小臂助手')) || '小臂助手';
    });
  }

  private saveWakeWord(): void {
    const trimmed = this.wakeWord.trim();
    if (trimmed.length === 0) {
      promptAction.showToast({ message: '唤醒词不能为空' });
      return;
    }

    this.wakeWord = trimmed;
    const context = getContext(this) as common.UIAbilityContext;
    preferences.getPreferences(context, 'voice_prefs', (err, prefs) => {
      if (err || !prefs) {
        promptAction.showToast({ message: '保存失败' });
        return;
      }
      prefs.putSync('voice_wake_word', this.wakeWord);
      prefs.flushSync();
      promptAction.showToast({ message: `已保存唤醒词：${this.wakeWord}` });

      if (this.voiceEnabled) {
        voiceCommandService.start(context, this.wakeWord);
      }
    });
  }

  private toggleVoiceControl(): void {
    const nextValue = !this.voiceEnabled;
    this.voiceEnabled = nextValue;

    const context = getContext(this) as common.UIAbilityContext;
    preferences.getPreferences(context, 'voice_prefs', (err, prefs) => {
      if (err || !prefs) {
        promptAction.showToast({ message: '语音设置保存失败' });
        return;
      }
      prefs.putSync('voice_enabled', nextValue);
      prefs.putSync('voice_wake_word', this.wakeWord);
      prefs.flushSync();

      if (nextValue) {
        voiceCommandService.start(context, this.wakeWord);
        promptAction.showToast({ message: `语音控制已开启（唤醒词：${this.wakeWord}）` });
      } else {
        voiceCommandService.stop();
        promptAction.showToast({ message: '语音控制已关闭' });
      }
    });
  }
}
