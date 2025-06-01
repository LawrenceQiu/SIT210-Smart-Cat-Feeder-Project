/*
  weight_server.ino
  -----------------
  Uses secrets.h for Wi-Fi credentials.
  - Serial: type a number to set currentWeight.
  - HTTP GET /weight → returns {"weight":<currentWeight>}.
*/

#include "secrets.h"        // SSID & PASS  here
#include <WiFiNINA.h>

WiFiServer server(80);
float currentWeight = 0.0;   // grams, updated via Serial

void setup() {
  Serial.begin(9600);
  while(!Serial);

  // Connect to Wi-Fi
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi connected");
  Serial.print("Server IP: ");
  Serial.println(WiFi.localIP());

  // Start HTTP server
  server.begin();
  Serial.println("HTTP server started on port 80");
  Serial.println("Serial commands:");
  Serial.println("  <number> → set simulated weight (g)");
  Serial.println("  GET /weight → returns JSON");
}

void loop() {
  // A) Update currentWeight from Serial
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    currentWeight = line.toFloat();
    Serial.print("Weight set to: ");
    Serial.print(currentWeight, 3);
    Serial.println(" g");
  }

  // B) Handle HTTP requests
  WiFiClient client = server.available();
  if (client) {
    String request = client.readStringUntil('\r');
    client.flush();
    if (request.indexOf("GET /weight") >= 0) {
      // send 200 + JSON
      client.print(
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        "Connection: close\r\n\r\n"
      );
      client.print("{\"weight\":");
      client.print(currentWeight, 3);
      client.print("}");
    } else {
      // 404 otherwise
      client.print(
        "HTTP/1.1 404 Not Found\r\n"
        "Connection: close\r\n\r\n"
      );
    }
    delay(1);
    client.stop();
  }
}
