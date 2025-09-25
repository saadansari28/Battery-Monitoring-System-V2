#include <Wire.h>
#include <Adafruit_INA219.h>
#include <OneWire.h>
#include <DallasTemperature.h>

Adafruit_INA219 ina219;

// DS18B20 Temperature
#define ONE_WIRE_BUS 2   // DS18B20 data pin to D2
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// Battery reference values
float fullVoltage = 9.0;   // Full battery voltage
float emptyVoltage = 6.0;  // Empty battery voltage
int cycleCount = 0;
bool discharged = false;

void setup(void) {
  Serial.begin(9600);
  ina219.begin();
  sensors.begin();
}

void loop(void) {
  // Read INA219
  float busVoltage = ina219.getBusVoltage_V();
  float current_mA = ina219.getCurrent_mA();
  float power_mW = ina219.getPower_mW();

  // Read DS18B20
  sensors.requestTemperatures();
  float temperatureC = sensors.getTempCByIndex(0);

  // Calculate SOC (%)
  float soc = ((busVoltage - emptyVoltage) / (fullVoltage - emptyVoltage)) * 100.0;
  if (soc > 100) soc = 100;
  if (soc < 0) soc = 0;

  // Estimate SOH (simple: compare full voltage with rated full voltage)
  float soh = (busVoltage / fullVoltage) * 100.0;
  if (soh > 100) soh = 100;

  // Count cycles (discharge → charge)
  if (soc < 20 && !discharged) {
    discharged = true;
  }
  if (soc > 80 && discharged) {
    cycleCount++;
    discharged = false;
  }

  // Send all data to Serial
  Serial.print(busVoltage); Serial.print(",");
  Serial.print(current_mA); Serial.print(",");
  Serial.print(power_mW); Serial.print(",");
  Serial.print(temperatureC); Serial.print(",");
  Serial.print(soc); Serial.print(",");
  Serial.print(soh); Serial.print(",");
  Serial.println(cycleCount);

  delay(1000); // 1 second delay
}
