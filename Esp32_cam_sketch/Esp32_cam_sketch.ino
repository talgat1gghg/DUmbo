#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include "esp_camera.h"

// ---  WI-FI settings ---
const char* ssid = "WI-FI name";
const char* password = "WI-FI password";

// ---  I2C and PCA9685 settings ---
#define I2C_SDA 15
#define I2C_SCL 14

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

// Pulse range for servo drives EMAX (500-2400 мкс)
#define SERVOMIN  102 
#define SERVOMAX  491 

// --- ПИНЫ КАМЕРЫ (AI-THINKER ESP32-CAM) ---
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WebServer server(80);

int angleToPulse(int angle) {
  return map(angle, 0, 180, SERVOMIN, SERVOMAX);
}

// --- 1. endpoint for controlling servos (/servo) ---
void handleServo() {
  if (server.hasArg("angle")) {
    int angle = server.arg("angle").toInt();
    angle = constrain(angle, 0, 180);

    int channel = 0;
    if (server.hasArg("channel")) {
      channel = server.arg("channel").toInt();
      channel = constrain(channel, 0, 15);
    }

    int pulse = angleToPulse(angle);
    pwm.setPWM(channel, 0, pulse);

    server.send(200, "text/plain", "Channel " + String(channel) + " angle set to " + String(angle));
  } else {
    server.send(400, "text/plain", "Missing 'angle' parameter");
  }
}

// --- 2. endpoint to capture a picture (/capture) ---
void handleCapture() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }

  // Sending a JPEG image directly in response to an HTTP request.
  server.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb); // Freeing the frame buffer
}

void setup() {
  Serial.begin(115200);

  // 1. initializing I2C for PCA9685
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setTimeOut(1000); // protectic I2C from freezing
  
  pwm.begin();
  pwm.setOscillatorFrequency(27000000);
  pwm.setPWMFreq(50);

  // 2. initializing camera matrix
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Resolution VGA (640x480) 
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12; // 10-12 good quality without having a big size
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  // 3. connecting to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWi-Fi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // 4. Server route registration
  server.on("/servo", handleServo);
  server.on("/capture", handleCapture);
  
  server.begin();
}

void loop() {
  server.handleClient();
}
