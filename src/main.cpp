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
// Updates input variables from potentiometers unless serial override is active
void refreshKnobs() {
  if (serialOverride) return;

  inputs.massKg  = analogRange(PIN_MASS, 1.0, MAX_MASS_KG);
  inputs.riseM   = analogRange(PIN_RISE, 0.1, MAX_RISE_M);
  inputs.maxRunM = analogRange(PIN_RUN, MIN_RUN_M, MAX_RUN_M);
  inputs.muK     = analogRange(PIN_MU, 0.0, MAX_MU);
}

// Clears line and displays a 20-character string on the LCD
void putLine(int row, String text) {
  while (text.length() < 20) text += " ";
  lcd.setCursor(0, row);
  lcd.print(text);
}

//-------------------------------Christian------------------------------------
// Displays the current menu page based on screenIndex
void showScreen() {
  if (!validInputs(inputs)) {
    putLine(0, "   INPUT ERROR!   ");
    putLine(1, "Out of valid bounds");
    putLine(2, "Check potentiomtr");
    putLine(3, "or serial inputs  ");
    return;
  }

  switch (screenIndex) {
    case 0: // Inputs Overview
      putLine(0, "=== RAMP INPUTS ===");
      putLine(1, "Mass:   " + String(inputs.massKg, 1) + " kg");
      putLine(2, "Rise:   " + String(inputs.riseM, 2) + " m");
      putLine(3, "Run:" + String(inputs.maxRunM, 2) + "m | u:" + String(inputs.muK, 2));
      break;

    case 1: // Best (Min) Force Result
      putLine(0, "== MIN FORCE OPT ==");
      putLine(1, "Run:" + String(best.runM, 2) + "m Deg:" + String(best.angleDeg, 1));
      putLine(2, "Force:  " + String(best.appliedForceN, 2) + " N");
      putLine(3, "Work:   " + String(best.workJ, 2) + " J");
      break;

    case 2: // Lowest Work Result
      putLine(0, "== MIN WORK OPT ==");
      putLine(1, "Run:" + String(lowestWork.runM, 2) + "m Deg:" + String(lowestWork.angleDeg, 1));
      putLine(2, "Force:  " + String(lowestWork.appliedForceN, 2) + " N");
      putLine(3, "Work:   " + String(lowestWork.workJ, 2) + " J");
      break;

    case 3: // Force Breakdown
      putLine(0, "== FORCE VECTORS ==");
      putLine(1, "F_par:  " + String(best.gravityParallelN, 2) + " N");
      putLine(2, "Normal: " + String(best.normalN, 2) + " N");
      putLine(3, "Fric:   " + String(best.kineticFrictionN, 2) + " N");
      break;

    case 4: // Geometry Breakdown
      putLine(0, "== RAMP GEOMETRY ==");
      putLine(1, "Length: " + String(best.slopeLengthM, 2) + " m");
      putLine(2, "Run:    " + String(best.runM, 2) + " m");
      putLine(3, "Angle:  " + String(best.angleDeg, 2) + " deg");
      break;

    default:
      screenIndex = 0;
      break;
  }
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
// Exports all 101 candidate calculations to Serial in CSV format
void printCSV() {
  if (!validInputs(inputs)) {
    Serial.println("Error: Invalid inputs.");
    return;
  }

  Serial.println("Index,Run_m,SlopeLen_m,Angle_deg,F_Parallel_N,F_Normal_N,F_Friction_N,AppliedForce_N,Work_J");

  double step = (inputs.maxRunM - MIN_RUN_M) / (N_CANDIDATES - 1);

  for (int i = 0; i < N_CANDIDATES; i++) {
    double run = MIN_RUN_M + (i * step);
    Calculation c = calculateAtRun(run);

    Serial.println(String(i + 1) + "," + c.runM + "," + c.slopeLengthM + "," + 
                   c.angleDeg + "," + c.gravityParallelN + "," + c.normalN + "," + 
                   c.kineticFrictionN + "," + c.appliedForceN + "," + c.workJ);
  }
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
