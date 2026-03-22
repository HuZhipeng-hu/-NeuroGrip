# 华为云 ECS 部署指南

> **目标服务器**：ECS `1.95.65.51`（Ubuntu 22.04）  
> **数据库**：RDS MySQL `1.94.234.114:3306`，库名 `ict_db`  
> **服务端口**：`8080`

---

## 一、编译与打包策略

### 1.1 推荐：在云端编译（无需本地 JDK/Maven）

1) 将后端源码上传到 ECS：

```bash
# 在本地执行（包含整个 springboot_backend 目录）
scp -r springboot_backend root@1.95.65.51:/opt/emg/
```

2) SSH 登录 ECS 安装构建环境：

```bash
ssh root@1.95.65.51
apt update
apt install -y openjdk-11-jdk-headless maven
java -version
mvn -version
```

3) 在 ECS 上编译：

```bash
cd /opt/emg/springboot_backend
mvn clean package -DskipTests
```

编译完成后 JAR 位于 `target/emg-backend-1.0.0.jar`。

### 1.2 如需本地编译（可选）

仍可在本地安装 JDK/Maven 并执行同样的 `mvn clean package -DskipTests`，再上传 JAR。

---

## 二、上传到 ECS 服务器

### 2.1 上传源码（云端编译场景）

- PowerShell：`scp -r springboot_backend root@1.95.65.51:/opt/emg/`
- WinSCP：连接后直接拖拽整个 `springboot_backend` 目录到 `/opt/emg/`

### 2.2 上传已编译 JAR（本地编译场景）

- PowerShell：`scp target/emg-backend-1.0.0.jar root@1.95.65.51:/opt/emg/`
- WinSCP：拖拽 `emg-backend-1.0.0.jar` 到 `/opt/emg/`

---

## 三、ECS 服务器初始化

### 3.1 SSH 登录服务器

```bash
ssh root@1.95.65.51
# 或使用私钥
ssh -i <your-key.pem> root@1.95.65.51
```

### 3.2 安装 JDK 11 与 Maven（云端编译需要）

```bash
apt update
apt install -y openjdk-11-jdk-headless maven

# 验证
java -version
# 输出应包含：openjdk version "11"
```

### 3.3 创建工作目录

```bash
# 创建应用目录结构
mkdir -p /opt/emg/training
mkdir -p /opt/emg/models
mkdir -p /opt/emg/logs

# 设置权限
chmod 755 /opt/emg
```

---

## 四、配置应用

### 4.1 上传配置文件（可选：覆盖 JAR 内的配置）

如需在服务器上使用独立配置文件（推荐生产环境使用），在 `/opt/emg/` 创建 `application.yml`：

```bash
cat > /opt/emg/application.yml << 'EOF'
server:
  port: 8080

spring:
  application:
    name: emg-backend
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://1.94.234.114:3306/ict_db?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true
    username: root
    password: xzhAa120119110
    type: com.alibaba.druid.pool.DruidDataSource
    druid:
      initial-size: 5
      min-idle: 5
      max-active: 20
      max-wait: 60000

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true

training:
  workspace: /opt/emg/training
  python:
    executable: python3
  script:
    path: /opt/emg/scripts/training_server.py

model:
  storage:
    path: /opt/emg/models

logging:
  file:
    name: /opt/emg/logs/emg-backend.log
  level:
    root: INFO
    com.huaweiict: DEBUG
EOF
```

> 如果在云端编译，执行 `mvn clean package -DskipTests` 前可先放好此配置，方便直接运行。

---

## 五、创建 systemd 服务（开机自启）

```bash
cat > /etc/systemd/system/emg-backend.service << 'EOF'
[Unit]
Description=EMG Backend Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/emg
ExecStart=/usr/bin/java -jar /opt/emg/emg-backend-1.0.0.jar \
  --spring.config.location=file:/opt/emg/application.yml
ExecStop=/bin/kill -SIGTERM $MAINPID
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=emg-backend
Environment=JAVA_OPTS=-Xmx512m -Xms256m

[Install]
WantedBy=multi-user.target
EOF
```

启用并启动服务：

```bash
systemctl daemon-reload
systemctl enable emg-backend
systemctl start emg-backend




mvn clean package -DskipTests
java -jar target/emg-backend-1.0.0.jar
```

---

## 六、配置防火墙（安全组）

### 6.1 Ubuntu UFW 防火墙

```bash
ufw allow 22/tcp    # SSH
ufw allow 8080/tcp  # Spring Boot
ufw enable
ufw status
```

### 6.2 华为云控制台安全组（必须！）

登录华为云控制台 → ECS → 找到实例 `1.95.65.51` → **安全组** → **添加入方向规则**：

| 协议 | 端口 | 来源    | 说明            |
|------|------|---------|-----------------|
| TCP  | 8080 | 0.0.0.0/0 | Spring Boot API |
| TCP  | 22   | 你的 IP | SSH 管理       |

> **WebSocket** 使用 HTTP 升级协议，8080 端口已涵盖，无需额外开放。

---

## 七、启动验证

### 7.1 检查服务状态

```bash
# 查看运行状态
systemctl status emg-backend

# 实时日志
journalctl -u emg-backend -f

# 或查看日志文件
tail -f /opt/emg/logs/emg-backend.log
```

### 7.2 接口联通性测试

```bash
# 在服务器本地测试
curl http://localhost:8080/api/training/tasks

# 从外部测试（将下面替换为你的电脑执行）
curl http://1.95.65.51:8080/api/training/tasks
```

期望响应：
```json
{"code":200,"data":[]}
```

### 7.3 WebSocket 连接测试

使用 Python 脚本在本机测试（需要安装 websockets 库）：

```python
import asyncio
import websockets

async def test():
    uri = "ws://1.95.65.51:8080/ws/app"
    async with websockets.connect(uri) as ws:
        print("WebSocket 连接成功！")
        msg = await asyncio.wait_for(ws.recv(), timeout=3)
        print("收到消息:", msg)

asyncio.run(test())
```

---

## 八、版本更新流程

当代码修改后，重新部署步骤：

```bash
# Step 1：本地重新打包
mvn clean package -DskipTests

# Step 2：上传新 JAR
scp target/emg-backend-1.0.0.jar root@1.95.65.51:/opt/emg/

# Step 3：重启服务
ssh root@1.95.65.51 "systemctl restart emg-backend"

# Step 4：检查日志
ssh root@1.95.65.51 "journalctl -u emg-backend -n 50"
```

---

## 九、常见问题排查

### 9.1 启动失败 - 数据库连接失败

```
Failed to obtain JDBC Connection
```

**排查步骤：**
```bash
# 1. 在 ECS 上测试 RDS 连通性
telnet 1.94.234.114 3306

# 2. 检查 RDS 安全组是否允许 ECS 的内网 IP 访问
# 3. 确认密码正确
mysql -h 1.94.234.114 -u root -p ict_db
```

### 9.2 端口 8080 无法访问

```bash
# 检查端口是否监听
ss -tlnp | grep 8080

# 检查 UFW 规则
ufw status

# 检查华为云安全组控制台（最常见问题！）
```

### 9.3 WebSocket 连接被拒绝

WebSocket 需要 Spring Boot 的 WebSocket 配置允许跨域，检查 `WebSocketConfig.java`：

```java
@Bean
public WebMvcConfigurer corsConfigurer() {
    return new WebMvcConfigurer() {
        @Override
        public void addCorsMappings(CorsRegistry registry) {
            registry.addMapping("/**").allowedOrigins("*");
        }
    };
}
```

### 9.4 内存不足（OOM）

```bash
# 查看内存使用
free -h

# 适当调整 JVM 参数（编辑 service 文件）
Environment=JAVA_OPTS=-Xmx256m -Xms128m
systemctl daemon-reload && systemctl restart emg-backend
```

---

## 十、完整部署检查清单

- [ ] 本地 `mvn clean package -DskipTests` 成功，无编译错误
- [ ] JAR 包已上传至 `/opt/emg/emg-backend-1.0.0.jar`
- [ ] JDK 11 已安装（`java -version`）
- [ ] `/opt/emg/application.yml` 配置了正确的 DB 地址和密码
- [ ] systemd 服务已创建并启用（`systemctl enable emg-backend`）
- [ ] 华为云安全组已开放 8080 端口
- [ ] `curl http://1.95.65.51:8080/api/training/tasks` 返回 200
- [ ] WebSocket `ws://1.95.65.51:8080/ws/app` 连接成功

编译：mvn clean package -DskipTests

后端运行：nohup java -jar ./target/emg-backend-1.0.0.jar > stdout.log 2> stderr.log &

查找pid：ps -ef | grep emg-backend

停止：kill -15 12345
