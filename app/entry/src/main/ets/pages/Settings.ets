// pages/Setting.ets

import router from '@ohos.router';
import promptAction from '@ohos.promptAction';
import { CustomAppBar } from './CustomAppBar';
import preferences from '@ohos.data.preferences';

@Entry
@Component
struct Setting {
  build() {
    Column() {
      CustomAppBar({ title: '系统设置', onBack: () => router.back(), showSettings: false })

      List({ space: 12 }) {
        ListItem() {
          SectionTitle({ title: '功能' })
        }
        .enabled(false)

        ListItem() {
          SettingItem({
            icon: '✋',
            title: '手势自定义',
            desc: '设置常用手势命令',
            color: '#4F46E5',
            onTap: () => { // 👈 添加这一段
              AlertDialog.show({ message: '请前往“训练”页面录制新手势' });
            }
          });
        }

        ListItem() {
          SettingItem({
            icon: '🔄',
            title: '数据同步',
            desc: '云端备份配置',
            extra: '自动',
            color: '#DC2626',
            onTap: () => { // 👈 添加这一段
              AlertDialog.show({ message: '数据会自动同步' });
            }
          });
        }

        // ===== 帮助与支持分组 =====
        ListItem() {
          SectionTitle({ title: '帮助与支持' })
        }
        .enabled(false)

        ListItem() {
          SettingItem({
            icon: '📖',
            title: '使用指南',
            desc: '详细操作教程',
            color: '#7C3AED',
            onTap: () => { // 👈 添加这一段
              AlertDialog.show({ message: '请参考说明文档' });
            }
          });
        }

        ListItem() {
          SettingItem({
            icon: '📞',
            title: '联系客服',
            desc: '技术支持服务',
            color: '#EA580C',
            onTap: () => { // 👈 添加这一段
              AlertDialog.show({ message: '请联系工作人员' });
            }
          });
        }

        ListItem() {
          SettingItem({
            icon: 'ℹ️',
            title: '关于我们',
            desc: 'NeuroGripPro v1.0',
            color: '#64748B',
            onTap: () => { // 👈 添加这一段
              AlertDialog.show({ message: 'NeuroGripPro v1.0\n\n© 2026 ICT Team' })
            }
          });
        }

        // ===== 系统分组 =====
        ListItem() {
          SectionTitle({ title: '系统' })
        }
        .enabled(false)

        // ✅ 新增：退出登录项
        ListItem() {
          SettingItem({
            icon: '🚪',
            title: '退出登录',
            desc: '退出当前账号',
            color: '#EF4444',
            isDestructive: true
          });
        }
      }
      .width('100%')
      .layoutWeight(1)
      .padding({ top: 8, left: 16, right: 16, bottom: 20 })
      .backgroundColor('#F8FAFC')
      .scrollBar(BarState.Off)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F8FAFC')
  }
}

// ========== SectionTitle 组件  ==========
@Component
struct SectionTitle {
  @Prop title: string;

  build() {
    Text(this.title)
      .fontSize(14)
      .fontWeight(FontWeight.Medium)
      .fontColor('#475569')
      .margin({ top: 8, bottom: 8 })
      .padding({ left: 4 })
      .width('100%');
  }
}

// ========== SettingItem 组件 ==========
@Component
struct SettingItem {
  @Prop icon: string;
  @Prop title: string;
  @Prop desc: string;
  @Prop extra?: string;
  @Prop color: ResourceColor;
  @Prop isDestructive?: boolean = false;
  private onTap?: () => void;

  build() {
    Row({ space: 16 }) {
      // 图标
      Text(this.icon)
        .fontSize(24)
        .width(40)
        .height(40)
        .textAlign(TextAlign.Center)
        .borderRadius(20)
        .backgroundColor(this.color + '15')
        .fontColor(this.color)

      // 文字和额外信息区域
      Flex({ direction: FlexDirection.Column, justifyContent: FlexAlign.Start }) {
        Text(this.title)
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .fontColor(this.isDestructive ? '#EF4444' : '#1E293B')
          .margin({ bottom: 4 });

        Row() {
          Text(this.desc)
            .fontSize(13)
            .fontColor(this.isDestructive ? '#F87171' : '#64748B')
            .layoutWeight(1);

          if (this.extra) {
            Text(this.extra)
              .fontSize(12)
              .fontColor('#059669')
              .padding({ left: 8, right: 8, top: 3, bottom: 3 })
              .backgroundColor('#ECFDF5')
              .borderRadius(10)
              .margin({ left: 8 });
          }
        }
        .alignItems(VerticalAlign.Center);
      }
      .layoutWeight(1);

      if (!this.isDestructive) {
        Text('›')
          .fontSize(28)
          .fontColor('#CBD5E1')
          .fontWeight(FontWeight.Lighter)
          .width(20)
          .textAlign(TextAlign.End);
      }
    }
    .padding({ top: 16, bottom: 16, left: 20, right: 20 })
    .backgroundColor('#FFFFFF')
    .borderRadius(16)
    .shadow({
      radius: 8,
      color: '#00000010',
      offsetX: 0,
      offsetY: 2
    })
    .onClick(() => {
      if (this.isDestructive) {
        // 退出登录的点击逻辑
        this.showLogoutDialog();
      } else if (this.onTap) { // 👈 判断并调用 onTap
        this.onTap();          // 👈 执行传入的弹窗逻辑
      }
    })
    .alignItems(VerticalAlign.Center)
    .width('100%')
    .animation({
      duration: 150,
      curve: Curve.EaseInOut
    })
    .stateStyles({
      normal: {
        .scale({ x: 1.0, y: 1.0 })
      },
      pressed: {
        .scale({ x: 0.98, y: 0.98 })
      }
    })
  }

  // ✅ 新增：显示退出登录确认对话框
  private showLogoutDialog() {
    AlertDialog.show({
      title: '确认退出',
      message: '您确定要退出当前账号吗？',
      primaryButton: {
        value: '取消',
        action: () => {
          console.info('User cancelled logout');
        }
      },
      secondaryButton: {
        value: '退出',
        fontColor: '#EF4444', // ✅ 按钮文字也用红色
        action: () => {
          console.info('User confirmed logout');

          // ✅ 获取上下文（用于访问 preferences）
          const context = getContext(this) as Context;

          // ✅ 打开偏好设置
          preferences.getPreferences(context, 'login_prefs', (err, prefs) => {
            if (err) {
              console.error('获取 preferences 失败:', err);
              promptAction.showToast({ message: '退出失败，请重试' });
              return;
            }

            // ✅ 删除 token
            prefs.deleteSync('auth_token');
            prefs.flushSync(); // 立即写入磁盘

            // ✅ 跳转到登录页
            router.replaceUrl({ url: 'pages/Index' });

            promptAction.showToast({ message: '已退出登录' });
          });
        }
      }
    });
  }
}





























