// pages/Index.ets
import router from '@ohos.router';
import preferences from '@ohos.data.preferences';
import http from '@ohos.net.http';



const BASE_URL = 'http://1.95.65.51:8080';


interface WebSocketMessage {
  deviceId: string;
  deviceTs: number;
  serverTime: string;
  gesture: string;
  confidence: number;
  battery: number;
  emg: number[][];   // 10包 x 8通道
  acc: number[];
  gyro: number[];
  angle: number[];
}

// 定义 HTTP 请求头类型
interface HttpHeaders {
  'Content-Type': string;
  'Accept': string;
}


interface ApiResponse {
  message: string;
  data?: string; // JWT token string
  token?: string; // Deprecated
}

@Entry
@Component
struct Index {
  @State isLoggedIn: boolean = false;
  @State backendMessage: string = '';
  @State username: string = '';
  @State password: string = '';
  @State registerUsername: string = '';
  @State registerPassword: string = '';
  @State confirmPassword: string = '';
  @State activeTab: string = 'login'; // 'login' 或 'register'
  @State agreeTerms: boolean = false;



  build() {
    Column() {
      this.LoginPage()
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#FFFFFF');
  }

  @Builder
  LoginPage() {
    Column() {
      // 显示后端消息（如错误提示）
      if (this.backendMessage) {
        Text(this.backendMessage)
          .fontSize(14)
          .fontColor('#EF4444')
          .margin({ bottom: 8 });
      }

      // Logo和标题区域
      Column() {
        Image($r('app.media.robot4'))
          .width(80)
          .height(80)
          .borderRadius(40)
          .margin({ bottom: 16 });

        Text('仿生机械臂')
          .fontSize(28)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1E40AF')
          .margin({ bottom: 8 });

        Text('智能控制，精准抓握')
          .fontSize(14)
          .fontColor('#6B7280');
      }
      .width('100%')
      .padding({ top: 30, bottom: 20 })
      .alignItems(HorizontalAlign.Center);

      // 登录/注册切换按钮（左右布局）
      Row() {
        Button('登录')
          .width('50%')
          .height(48)
          .backgroundColor(this.activeTab === 'login' ? '#1E40AF' : '#F3F4F6')
          .fontColor(this.activeTab === 'login' ? '#FFFFFF' : '#4B5563')
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .borderRadius(24)
          .onClick(() => {
            this.activeTab = 'login';
            this.backendMessage = '';
          });

        Button('注册')
          .width('50%')
          .height(48)
          .backgroundColor(this.activeTab === 'register' ? '#1E40AF' : '#F3F4F6')
          .fontColor(this.activeTab === 'register' ? '#FFFFFF' : '#4B5563')
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .borderRadius(24)
          .onClick(() => {
            this.activeTab = 'register';
            this.backendMessage = '';
          });
      }
      .width('100%')
      .backgroundColor('#F3F4F6')
      .borderRadius(24)
      .padding(4)
      .margin({ bottom: 20 });

      // 登录或注册表单
      if (this.activeTab === 'login') {
        this.LoginForm();
      } else {
        this.RegisterForm();
      }
    }
    .width('100%')
    .height('100%')
    .padding({ left: 24, right: 24 });
  }

  @Builder
  LoginForm() {
    Column({ space: 20 }) {
      // 用户名输入框
      Column() {
        Text('用户名')
          .fontSize(14)
          .fontColor('#4B5563')
          .width('100%')
          .margin({ bottom: 8 });

        TextInput({
          placeholder: '请输入用户名',
          text: this.username
        })
          .width('100%')
          .height(48)
          .backgroundColor('#F9FAFB')
          .placeholderColor('#9CA3AF')
          .fontColor('#1F2937')
          .borderRadius(12)
          .border({ width: 1, color: '#E5E7EB' })
          .padding({ left: 16 })
          .onChange((value: string) => {
            this.username = value;
          });
      }
      .width('100%');

      // 密码输入框
      Column() {
        Text('密码')
          .fontSize(14)
          .fontColor('#4B5563')
          .width('100%')
          .margin({ bottom: 8 });

        TextInput({
          placeholder: '请输入密码',
          text: this.password
        })
          .width('100%')
          .height(48)
          .backgroundColor('#F9FAFB')
          .placeholderColor('#9CA3AF')
          .fontColor('#1F2937')
          .type(InputType.Password)
          .borderRadius(12)
          .border({ width: 1, color: '#E5E7EB' })
          .padding({ left: 16 })
          .onChange((value: string) => {
            this.password = value;
          });
      }
      .width('100%');

      // 记住密码和忘记密码
      Row() {
        Row() {
          Toggle({ type: ToggleType.Checkbox, isOn: false })
            .width(20)
            .height(20);
          Text('记住密码')
            .fontSize(14)
            .fontColor('#6B7280')
            .margin({ left: 4 });
        }

        Text('忘记密码？')
          .fontSize(14)
          .fontColor('#1E40AF')
          .onClick(() => {
            this.backendMessage = '请联系管理员重置密码';
          });
      }
      .width('100%')
      .justifyContent(FlexAlign.SpaceBetween);

      // 登录按钮
      Button('登录')
        .width('100%')
        .height(50)
        .backgroundColor('#1E40AF')
        .fontColor('#FFFFFF')
        .fontSize(18)
        .fontWeight(FontWeight.Medium)
        .borderRadius(25)
        .margin({ top: 20 })
        .onClick(() => {
          this.handleLogin();
        });
    }
    .width('100%');
  }

  @Builder
  RegisterForm() {
    Column({ space: 20 }) {
      // 用户名输入框
      Column() {
        Text('用户名')
          .fontSize(14)
          .fontColor('#4B5563')
          .width('100%')
          .margin({ bottom: 8 });

        TextInput({
          placeholder: '请输入用户名',
          text: this.registerUsername
        })
          .width('100%')
          .height(48)
          .backgroundColor('#F9FAFB')
          .placeholderColor('#9CA3AF')
          .fontColor('#1F2937')
          .borderRadius(12)
          .border({ width: 1, color: '#E5E7EB' })
          .padding({ left: 16 })
          .onChange((value: string) => {
            this.registerUsername = value;
          });
      }
      .width('100%');

      // 密码输入框
      Column() {
        Text('密码')
          .fontSize(14)
          .fontColor('#4B5563')
          .width('100%')
          .margin({ bottom: 8 });

        TextInput({
          placeholder: '请输入密码',
          text: this.registerPassword
        })
          .width('100%')
          .height(48)
          .backgroundColor('#F9FAFB')
          .placeholderColor('#9CA3AF')
          .fontColor('#1F2937')
          .type(InputType.Password)
          .borderRadius(12)
          .border({ width: 1, color: '#E5E7EB' })
          .padding({ left: 16 })
          .onChange((value: string) => {
            this.registerPassword = value;
          });
      }
      .width('100%');

      // 确认密码输入框
      Column() {
        Text('确认密码')
          .fontSize(14)
          .fontColor('#4B5563')
          .width('100%')
          .margin({ bottom: 8 });

        TextInput({
          placeholder: '请再次输入密码',
          text: this.confirmPassword
        })
          .width('100%')
          .height(48)
          .backgroundColor('#F9FAFB')
          .placeholderColor('#9CA3AF')
          .fontColor('#1F2937')
          .type(InputType.Password)
          .borderRadius(12)
          .border({ width: 1, color: '#E5E7EB' })
          .padding({ left: 16 })
          .onChange((value: string) => {
            this.confirmPassword = value;
          });
      }
      .width('100%');

      // 用户协议
      Row() {
        Toggle({ type: ToggleType.Checkbox, isOn: this.agreeTerms })
          .width(20)
          .height(20)
          .onChange((isOn: boolean) => {
            this.agreeTerms = isOn;
          });

        Text('我已阅读并同意')
          .fontSize(14)
          .fontColor('#6B7280')
          .margin({ left: 4 });

        Text('《用户协议》')
          .fontSize(14)
          .fontColor('#1E40AF')
          .onClick(() => {
            this.backendMessage = '用户协议内容';
          });

        Text('和')
          .fontSize(14)
          .fontColor('#6B7280');

        Text('《隐私政策》')
          .fontSize(14)
          .fontColor('#1E40AF')
          .onClick(() => {
            this.backendMessage = '隐私政策内容';
          });
      }
      .width('100%')
      .justifyContent(FlexAlign.Center);

      // 注册按钮
      Button('注册')
        .width('100%')
        .height(50)
        .backgroundColor('#1E40AF')
        .fontColor('#FFFFFF')
        .fontSize(18)
        .fontWeight(FontWeight.Medium)
        .borderRadius(25)
        .margin({ top: 10 })
        .onClick(() => {
          this.handleRegister();
        });
    }
    .width('100%');
  }

  handleLogin() {
    if (!this.username || !this.password) {
      this.backendMessage = '请输入用户名和密码';
      return;
    }

    const url = `${BASE_URL}/auth/login`;
    const httpRequest = http.createHttp();

    const requestHeaders: HttpHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };

    const requestBody = JSON.stringify({
      username: this.username,
      password: this.password
    });

    httpRequest.request(
      url,
      {
        method: http.RequestMethod.POST,
        header: requestHeaders,
        extraData: requestBody,
        connectTimeout: 10000,
        readTimeout: 10000
      },
      (err, data) => {
        httpRequest.destroy();
        if (err) {
          console.error('登录请求失败:', JSON.stringify(err));
          // 显示具体的网络错误信息
          this.backendMessage = '网络错误: ' + JSON.stringify(err);
          return;
        }

        let responseText = '';
        if (data.result instanceof ArrayBuffer) {
          const uint8Array = new Uint8Array(data.result);
          responseText = String.fromCharCode(...uint8Array);
        } else if (typeof data.result === 'string') {
          responseText = data.result;
        }

        console.info('登录响应:', responseText); // 打印完整响应

        try {
          const res = JSON.parse(responseText) as ApiResponse;
          // 后端返回结构 { message: "...", data: "TOKEN..." }
          // 兼容旧接口 (res.token) 和新接口 (res.data)
          const token = res.data || res.token;

          if (data.responseCode === 200 && token) {
            console.info('登录成功，token:', token);

            // ✅ 保存 token 到本地存储
            const context = getContext(this) as Context; // ✅ 推荐
            preferences.getPreferences(context, 'login_prefs', (err, prefs) => {
              if (err) {
                console.error('保存 token 失败:', err);
                this.backendMessage = '登录状态保存失败，请重试';
                return;
              }
              prefs.putSync('auth_token', token);
              prefs.flushSync(); // 立即写入磁盘

              // ✅ 保存成功后再跳转
              router.replaceUrl({ url: 'pages/HomePage' });
            });
          } else {
            this.backendMessage = res.message || '登录失败';
          }
        } catch (e) {
          console.error('解析响应失败:', e);
          this.backendMessage = 'Login格式错误: ' + responseText.substring(0, 100);
        }
      }
    );
  }

  handleRegister() {
    if (!this.registerUsername || !this.registerPassword || !this.confirmPassword) {
      this.backendMessage = '请填写完整信息';
      return;
    }

    if (this.registerPassword !== this.confirmPassword) {
      this.backendMessage = '两次输入的密码不一致';
      return;
    }

    if (!this.agreeTerms) {
      this.backendMessage = '请同意用户协议和隐私政策';
      return;
    }

    const url = `${BASE_URL}/auth/register`;
    const httpRequest = http.createHttp();

    const requestHeaders: HttpHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };

    const requestBody = JSON.stringify({
      username: this.registerUsername,
      password: this.registerPassword
    });

    httpRequest.request(
      url,
      {
        method: http.RequestMethod.POST,
        header: requestHeaders,
        extraData: requestBody,
        connectTimeout: 10000,
        readTimeout: 10000
      },
      (err, data) => {
        httpRequest.destroy();
        if (err) {
          console.error('注册请求失败:', JSON.stringify(err));
          this.backendMessage = '网络错误: ' + JSON.stringify(err);
          return;
        }

        let responseText = '';
        if (data.result instanceof ArrayBuffer) {
          const uint8Array = new Uint8Array(data.result);
          responseText = String.fromCharCode(...uint8Array);
        } else if (typeof data.result === 'string') {
          responseText = data.result;
        }

        console.info('注册响应:', responseText);

        try {
          const res = JSON.parse(responseText) as ApiResponse;
          if (data.responseCode === 200) {
            console.info('注册成功:', res);
            this.backendMessage = '注册成功！';
            this.activeTab = 'login';
          } else {
            this.backendMessage = res.message || '注册失败';
          }
        } catch (e) {
          console.error('解析响应失败:', e);
          this.backendMessage = 'Reg格式错误: ' + responseText.substring(0, 50);
        }
      }
    );
  }

}