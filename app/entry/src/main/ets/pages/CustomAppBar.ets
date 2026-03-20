// components/CustomAppBar.ets

import router from '@ohos.router';

@Component
export struct CustomAppBar {
  @Prop title: string;
  private onBack?: () => void;
  @Prop showSettings: boolean = true;

  build() {
    Row() {
      // 左侧：返回按钮
      Row() {
        Text('‹')
          .fontSize(28)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1E40AF')
          .margin({ right: 8 })
        Text('返回')
          .fontSize(18)
          .fontColor('#1E40AF')
          .margin({top:4 })
      }
      .onClick(() => {
        if (this.onBack) {
          this.onBack();
        }
      })
      .visibility(this.onBack ? Visibility.Visible : Visibility.None)

      .visibility(this.onBack ? Visibility.Visible : Visibility.Hidden)

      Blank()

      // 中间：标题
      Text(this.title)
        .fontSize(20)
        .fontWeight(FontWeight.Bold)
        .fontColor('#1E40AF')

      Blank()
      Text('⚙️')
        .fontSize(20)
        .width(40)
        .height(40)
        .textAlign(TextAlign.Center)
        .visibility(this.showSettings ? Visibility.Visible : Visibility.Hidden)
        .onClick(() => {
          router.pushUrl({
            url: 'pages/Settings'
          });
        });
    }
    .width('100%')
    .height(56)
    .padding({ left: 16, right: 16 })
    .justifyContent(FlexAlign.SpaceBetween)
    .alignItems(VerticalAlign.Center)
    .backgroundColor(Color.White)
    .border({ width: { bottom: 0.5 }, color: '#E5E7EB' })
  }
}
