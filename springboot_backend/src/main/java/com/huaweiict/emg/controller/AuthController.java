package com.huaweiict.emg.controller;

import com.huaweiict.emg.dto.ApiResponse;
import com.huaweiict.emg.dto.AuthRequest;
import com.huaweiict.emg.service.AuthService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/auth")
public class AuthController {

    @Autowired
    private AuthService authService;

    @PostMapping("/register")
    public ApiResponse register(@RequestBody AuthRequest request) {
        return authService.register(request);
    }

    @PostMapping("/login")
    public ApiResponse login(@RequestBody AuthRequest request) {
        return authService.login(request);
    }

    @GetMapping("/hello")
    public String hello(){
        return "hello";
    }

}
