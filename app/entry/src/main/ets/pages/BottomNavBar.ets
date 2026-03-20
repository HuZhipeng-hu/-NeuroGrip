import router from '@ohos.router';

@Component
export  struct BottomNavBar {
  @Prop currentIndex: number;

  build() {
    Row({ space: 40 }) {
      NavItem({
        icon: '🏠',
        label: '首页',
        isSelected: this.currentIndex === 0,
        onTap: () => {
          if (this.currentIndex !== 0) {
            router.pushUrl({ url: 'pages/HomePage' });
          }
        }
      });

      NavItem({
        icon: '💪',
        label: '训练',
        isSelected: this.currentIndex === 1,
        onTap: () => {
          if (this.currentIndex !== 1) {
            router.pushUrl({ url: 'pages/Training' });
          }
        }
      });

      NavItem({
        icon: '📊',
        label: '数据',
        isSelected: this.currentIndex === 2,
        onTap: () => {
          if (this.currentIndex !== 2) {
            router.pushUrl({ url: 'pages/Data' });
            console.log('Data page not implemented yet');
          }
        }
      });

      NavItem({
        icon: '👤',
        label: '我的',
        isSelected: this.currentIndex === 3,
        onTap: () => {
          if (this.currentIndex !== 3) {
            router.pushUrl({ url: 'pages/Profile' });
          }
        }
      });
    }
    .width('100%')
    .height(60)
    .justifyContent(FlexAlign.SpaceAround)
    .alignItems(VerticalAlign.Center)
    .backgroundColor('#FFFFFF')
    .border({ width: { top: 1 }, color: { top: '#E5E7EB' } })
    .padding({ top: 8, bottom: 8 });
  }
}
// ========== NavItem ==========
@Component
struct NavItem {
  @Prop icon: string;
  @Prop label: string;
  @Prop isSelected: boolean;
  private onTap: () => void = () => {};

  build() {
    Column({ space: 4 }) {
      Text(this.icon)
        .fontSize(this.isSelected ? 26 : 24)
        .fontColor(this.isSelected ? '#3B82F6' : '#9CA3AF');

      Text(this.label)
        .fontSize(12)
        .fontColor(this.isSelected ? '#3B82F6' : '#9CA3AF');
    }
    .onClick(() => {
      this.onTap();
    });
  }
}