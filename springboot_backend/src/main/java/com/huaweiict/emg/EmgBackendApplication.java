package com.huaweiict.emg;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@MapperScan("com.huaweiict.emg.mapper")
@EnableScheduling
@EnableAsync
public class EmgBackendApplication {
    public static void main(String[] args) {
        SpringApplication.run(EmgBackendApplication.class, args);
    }
}
