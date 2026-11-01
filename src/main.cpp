#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <math.h>
#include <stdio.h>

// ---- ASSIGNMENTS: Member 1 (math), Member 2 (input/UI), Member 3 (testing) ----
static const uint8_t PIN_MASS = 32;
static const uint8_t PIN_RISE = 33;
static const uint8_t PIN_RUN  = 34;
static const uint8_t PIN_MU   = 35;
static const uint8_t PIN_PREV = 26;
static const uint8_t PIN_NEXT = 25;
static const double G = 9.81;
static const double MIN_RUN_M = 0.50;       // declared model search bound
static const int N_CANDIDATES = 101;        // discrete grid (not continuous optimum)
static const double MAX_MASS_KG = 500.0;
static const double MAX_RISE_M = 10.0;
static const double MAX_RUN_M = 100.0;
static const double MAX_MU = 1.0;
LiquidCrystal_I2C lcd(0x27, 20, 4);

struct Inputs {
  double massKg;
  double riseM;
  double maxRunM;
  double muK;
};

struct Calculation {
  double runM;
  double slopeLengthM;
  double angleDeg;
  double gravityParallelN;
  double normalN;
  double kineticFrictionN;
  double appliedForceN;
  double workJ;
};

Inputs inputs = {30.0, 0.60, 4.00, 0.03};
Calculation best = {};
Calculation lowestWork = {};
String lineBuffer = "";
bool serialOverride = false;
int screenIndex = 0;
int oldPrev = HIGH;
int oldNext = HIGH;
unsigned long lastButton = 0;
unsigned long lastRefresh = 0;

bool validInputs(const Inputs &s) {
  return isfinite(s.massKg) && isfinite(s.riseM) &&
         isfinite(s.maxRunM) && isfinite(s.muK) &&
         s.massKg > 0 && s.massKg <= MAX_MASS_KG &&
         s.riseM > 0 && s.riseM <= MAX_RISE_M &&
         s.maxRunM >= MIN_RUN_M && s.maxRunM <= MAX_RUN_M &&
         s.muK >= 0 && s.muK <= MAX_MU;
}

// Core Newtonian mechanics, for an already-sliding block at constant speed.
Calculation calculateAtRun() {
 
}

// For a fixed height, enumerate 101 horizontal runs in [MIN_RUN_M,maxRunM].
// Choose lowest force, not necessarily shortest length or least work.
void optimize() {
  
}

// ------- Virtual controls -------
double analogRange(int pin, double minValue, double maxValue) {
  int raw = analogRead(pin);
  raw = constrain(raw, 0, 4095);
  return minValue + (maxValue - minValue) * (double(raw) / 4095.0);
}


//-------------------------------Christian------------------------------------
void refreshKnobs() {
  
}

void putLine(int row, String text) {
  // Exactly one 20-character screen line; prevents LCD stale characters.
  while (text.length() < 20) text += " ";
  lcd.setCursor(0, row);
  lcd.print(text.substring(0, 20));
}

//-------------------------------Christian------------------------------------
void showScreen() {
 
}

// ------- Evidence output (for Chapter 4 numerical validation) -------
void printSingle(const Calculation &c) {
  Serial.printf("Run %.4f m | Length %.4f m | Angle %.4f deg\n", c.runM, c.slopeLengthM, c.angleDeg);
  Serial.printf("Parallel %.4f N | Normal %.4f N | Friction %.4f N\n", c.gravityParallelN, c.normalN, c.kineticFrictionN);
  Serial.printf("REQUIRED FORCE %.4f N | WORK %.4f J\n", c.appliedForceN, c.workJ);
}


//-------------------------------Ace------------------------------------
void printComparison() {
 
}


//-------------------------------Christian------------------------------------
void printCSV() {
  
}



//-------------------------------Cedric------------------------------------
void selfTest() {
  // TODO member 3: expand to >= 12 independent comparison tests.
 
}

void help() {
  Serial.println("RAMPFORCE / SERIAL COMMANDS");
  Serial.println("SET m h maxRun mu   - exact parameters; ex: SET 30 0.60 4 0.03");
  Serial.println("CALC m h run mu     - calculate one ramp; ex: CALC 30 0.60 2 0.03");
  Serial.println("RUN                 - compare 5 ramps and report best of 101");
  Serial.println("CSV                 - export 101 comparison rows");
  Serial.println("SELFTEST            - run three preliminary checks");
  Serial.println("KNOBS               - resume interactive virtual knob inputs");
  Serial.println("HELP                - show instructions");
}


//-------------------------------Cedric------------------------------------
void handleCommand(String cmd) {
  
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  analogReadResolution(12);
  pinMode(PIN_PREV, INPUT_PULLUP);
  pinMode(PIN_NEXT, INPUT_PULLUP);
  optimize(inputs, best, lowestWork);
  help();
  showScreen();
}

void loop() {
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\r' || ch == '\n') {
      handleCommand(lineBuffer);
      lineBuffer = "";
    } else if (lineBuffer.length() < 120) {
      lineBuffer += ch;
    }
  }

  int prev = digitalRead(PIN_PREV);
  int next = digitalRead(PIN_NEXT);
  if (millis() - lastButton > 180) {
    if (prev == LOW && oldPrev == HIGH) {
      screenIndex = (screenIndex + 4) % 5;
      showScreen();
      lastButton = millis();
    } else if (next == LOW && oldNext == HIGH) {
      screenIndex = (screenIndex + 1) % 5;
      showScreen();
      lastButton = millis();
    }
  }
  oldPrev = prev;
  oldNext = next;

  if (millis() - lastRefresh >= 500) {
    lastRefresh = millis();
    refreshKnobs();
    optimize(inputs, best, lowestWork);
    showScreen();
  }
}
