# scripts/generate_products_catalog.py
"""
Génère un catalogue produits synthétique (data/knowledge_base/ecommerce/produits.csv)
pour Liss Strike, boutique tunisienne d'électronique/maker.

⚠️ IMPORTANT : tous les produits sont générés par COMBINATOIRE (valeur x
puissance x tolérance x packaging, longueur x couleur x densité, etc.) —
exactement comme le fait un vrai distributeur de composants électroniques
(Mouser, DigiKey...) qui a des dizaines de milliers de références issues
des mêmes familles de produits déclinées en variantes. RIEN n'est copié
d'un site existant : les références, prix et descriptions sont inventés/
calculés par ce script, à des fins de démo/tests uniquement.

Usage :
    ./venv/Scripts/python.exe scripts/generate_products_catalog.py
"""

import csv
import random
from itertools import product
from pathlib import Path

random.seed(42)  # reproductible

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "knowledge_base" / "ecommerce" / "produits.csv"

rows = []
sku_counters = {}


def add_row(categorie, code, nom, prix, caracteristiques, description, dispo_weights=(78, 10, 7, 5)):
    sku_counters[code] = sku_counters.get(code, 0) + 1
    sku = f"LS-{code}-{sku_counters[code]:06d}"
    disponibilite = random.choices(
        ["en stock", "stock faible", "rupture de stock", "sur commande"],
        weights=dispo_weights,
    )[0]
    prix = round(prix * random.uniform(0.97, 1.05), 2)  # légère variation réaliste
    rows.append({
        "sku": sku,
        "nom": nom,
        "categorie": categorie,
        "prix_dt": prix,
        "disponibilite": disponibilite,
        "caracteristiques": caracteristiques,
        "description": description,
    })


# ============================================================
# CARTES PROGRAMMABLES (code CP)
# ============================================================
arduino_models = ["Uno R3", "Nano", "Mega 2560", "Micro", "Leonardo", "Pro Mini", "Due", "Uno R4 Minima"]
for modele in arduino_models:
    for variante in ["original", "compatible (clone)"]:
        prix = 65 if "original" in variante else 32
        add_row("Cartes Programmables", "CP",
                f"Carte Arduino {modele} ({variante})",
                prix + arduino_models.index(modele) * 4,
                f"Microcontrôleur AVR/SAM selon modèle, variante {variante}",
                f"Carte de développement Arduino {modele}, {variante}, idéale pour prototypage électronique.")

esp_models = ["ESP32 DevKitC", "ESP32-S3", "ESP32-C3", "ESP8266 NodeMCU", "ESP8266 Wemos D1 Mini", "ESP32-CAM"]
for modele in esp_models:
    for memoire in ["4MB Flash", "8MB Flash"]:
        add_row("Cartes Programmables", "CP",
                f"Module {modele} ({memoire})",
                40 + esp_models.index(modele) * 5,
                f"WiFi 802.11 b/g/n, Bluetooth (selon modèle), {memoire}",
                f"Carte {modele} pour projets IoT connectés, {memoire} de stockage.")

stm32_models = ["STM32F103C8T6 Blue Pill", "STM32F401 Black Pill", "STM32F411", "STM32F407 Discovery", "STM32L152 Nucleo"]
for modele in stm32_models:
    add_row("Cartes Programmables", "CP", f"Carte {modele}", 28 + stm32_models.index(modele) * 15,
            "ARM Cortex-M, plusieurs Ko de RAM/Flash selon modèle",
            f"Carte de développement {modele}, performance supérieure à Arduino Uno.")

rpi_models = ["Zero", "Zero W", "3 Model B+", "4 Model B (2Go)", "4 Model B (4Go)", "4 Model B (8Go)", "5 (4Go)", "5 (8Go)"]
for modele in rpi_models:
    add_row("Cartes Programmables", "CP", f"Raspberry Pi {modele}", 45 + rpi_models.index(modele) * 40,
            "Mini-ordinateur monocarte, WiFi/Bluetooth selon modèle",
            f"Raspberry Pi {modele} pour projets avancés (serveur, robotique, vision).")

for modele in ["Teensy 3.2", "Teensy 4.0", "Teensy 4.1", "BBC micro:bit v2", "Adafruit Circuit Playground",
               "FPGA iCEstick Lattice", "FPGA Basys 3", "PIC18F4550 dev board", "PIC16F877A dev board"]:
    add_row("Cartes Programmables", "CP", f"Carte {modele}", random.randint(40, 220),
            "Voir fiche technique constructeur", f"Carte de développement {modele}.")

# ============================================================
# MODULES (code MO)
# ============================================================
for canaux in [1, 2, 4, 8, 16, 32]:
    for tension in ["5V", "12V", "24V"]:
        add_row("Modules", "MO", f"Module relais {canaux} canal(aux) {tension}",
                4 + canaux * 1.4, f"{canaux} relais, alimentation {tension}, optocouplé",
                f"Permet de piloter {canaux} appareil(s) électrique(s) depuis une carte programmable.")

conv_refs = ["LM2596 step-down", "MP1584 step-down", "XL6009 step-up", "MT3608 step-up", "SEPIC buck-boost",
             "TPS5430", "LM2577 step-up", "XL4015 step-down 5A"]
for ref in conv_refs:
    for plage in ["3-30V ajustable", "3-40V ajustable", "sortie fixe 5V", "sortie fixe 12V", "sortie fixe 3.3V"]:
        add_row("Modules", "MO", f"Convertisseur DC-DC {ref} ({plage})", random.uniform(6, 18),
                f"Module {ref}, {plage}", f"Régulateur de tension {ref} pour adapter une source d'alimentation.")

for ref, desc in [("HC-05", "Bluetooth 2.0 maître/esclave"), ("HC-06", "Bluetooth 2.0 esclave"),
                   ("HM-10 BLE", "Bluetooth Low Energy 4.0"), ("JDY-31", "Bluetooth 2.0 économique"),
                   ("ESP-01", "WiFi UART"), ("ESP-01S", "WiFi UART amélioré"),
                   ("NRF24L01", "RF 2.4GHz"), ("NRF24L01+PA+LNA", "RF 2.4GHz longue portée"),
                   ("RF433MHz TX", "émetteur RF 433MHz"), ("RF433MHz RX", "récepteur RF 433MHz"),
                   ("LoRa SX1278 433MHz", "longue portée basse consommation"),
                   ("LoRa SX1276 868MHz", "longue portée basse consommation"),
                   ("RTC DS1307", "horloge temps réel"), ("RTC DS3231", "horloge temps réel haute précision"),
                   ("SD Card Reader SPI", "lecteur carte microSD"),
                   ("PAM8403", "amplificateur audio class D 2x3W"),
                   ("LM386", "amplificateur audio mono"),
                   ("MAX485 RS485", "communication industrielle"),
                   ("MCP2515 CAN Bus", "communication CAN bus")]:
    add_row("Modules", "MO", f"Module {ref}", random.uniform(7, 45), desc, f"Module {ref} — {desc}.")

driver_refs = ["L298N", "L293D", "A4988", "DRV8825", "TB6600", "ULN2003", "TB6612FNG", "BTS7960"]
for ref in driver_refs:
    for config in ["1 moteur", "2 moteurs", "pilotage pas-à-pas"]:
        add_row("Modules", "MO", f"Driver moteur {ref} ({config})", random.uniform(8, 55),
                f"Driver {ref}", f"Module de pilotage moteur {ref}, {config}.")

# ============================================================
# CAPTEURS (code CA)
# ============================================================
capteurs_base = [
    ("DHT11", "Température/humidité, ±2°C, ±5%"), ("DHT22", "Température/humidité, ±0.5°C, ±2%"),
    ("MQ-2", "Gaz : fumée, GPL, propane"), ("MQ-3", "Gaz : alcool"), ("MQ-4", "Gaz : méthane"),
    ("MQ-5", "Gaz : GPL, gaz naturel"), ("MQ-6", "Gaz : GPL, butane"), ("MQ-7", "Gaz : monoxyde de carbone"),
    ("MQ-8", "Gaz : hydrogène"), ("MQ-135", "Qualité de l'air : CO2, ammoniac, benzène"),
    ("HC-SR04", "Distance ultrason 2cm-4m"), ("VL53L0X", "Distance laser ToF"),
    ("Sharp GP2Y0A21", "Distance infrarouge 10-80cm"),
    ("HC-SR501 PIR", "Mouvement infrarouge passif"), ("RCWL-0516", "Mouvement micro-ondes"),
    ("LDR photorésistance", "Luminosité"), ("BH1750", "Luminosité numérique I2C"),
    ("TSL2561", "Luminosité numérique haute précision"),
    ("Capteur son KY-038", "Détection sonore"), ("Microphone MAX9814", "Amplification audio"),
    ("ACS712-5A", "Courant AC/DC ±5A"), ("ACS712-20A", "Courant AC/DC ±20A"), ("ACS712-30A", "Courant AC/DC ±30A"),
    ("BMP180", "Pression atmosphérique"), ("BMP280", "Pression + température"),
    ("BME280", "Pression + température + humidité"), ("BME680", "Pression + température + humidité + qualité air"),
    ("TCS3200", "Couleur (RGB)"), ("TCS34725", "Couleur numérique I2C"),
    ("TTP223 tactile", "Bouton tactile capacitif"), ("Capteur pluie FC-37", "Détection de pluie"),
    ("Capteur humidité sol", "Humidité du sol pour arrosage automatique"),
    ("Capteur pH analogique", "Mesure de pH liquide"), ("Capteur turbidité", "Qualité de l'eau"),
    ("Capteur flamme IR", "Détection de flamme"), ("Capteur vibration SW-420", "Détection de choc/vibration"),
    ("Cellule de charge + HX711", "Pesage précis (balance)"),
    ("MPU6050", "Accéléromètre + gyroscope 6 axes"), ("MPU9250", "Accéléromètre + gyroscope + magnétomètre 9 axes"),
    ("GY-521", "Module MPU6050 pré-monté"), ("GPS NEO-6M", "Positionnement GPS"), ("GPS NEO-M8N", "Positionnement GPS haute précision"),
    ("Capteur effet Hall A3144", "Détection magnétique"), ("Interrupteur à bille (tilt)", "Détection d'inclinaison"),
    ("Capteur d'empreinte digitale", "Biométrie"), ("Module RFID RC522", "Lecture/écriture RFID 13.56MHz"),
    ("Module lecteur code-barres", "Scan code-barres"), ("MAX30100", "Fréquence cardiaque + oxymètre"),
    ("MAX30102", "Fréquence cardiaque + oxymètre amélioré"),
    ("Capteur NPK sol", "Azote/Phosphore/Potassium du sol"), ("Capteur UV index ML8511", "Index UV"),
    ("Capteur poussière PM2.5 (GP2Y1010)", "Qualité de l'air, particules fines"),
    ("Débitmètre YF-S201", "Débit d'eau"), ("Pince de courant SCT-013", "Mesure de courant non-intrusive"),
    ("Cellule de charge 5kg + HX711", "Pesage jusqu'à 5kg"), ("Cellule de charge 20kg + HX711", "Pesage jusqu'à 20kg"),
    ("Thermocouple type K + MAX6675", "Température haute (jusqu'à 1000°C)"),
    ("Récepteur infrarouge IR", "Réception télécommande IR"), ("Émetteur infrarouge IR", "Émission signal IR"),
    ("Capteur suiveur de ligne (line follower)", "Suivi de ligne pour robot"),
    ("Capteur évitement d'obstacle IR", "Détection d'obstacle proximité"),
    ("Baromètre/altimètre numérique", "Pression atmosphérique + altitude"),
    ("Anémomètre (capteur de vent)", "Vitesse du vent"), ("Capteur de niveau d'eau", "Niveau de liquide"),
]
for ref, desc in capteurs_base:
    for variante in ["module complet", "capteur seul (nu)", "breakout board"]:
        add_row("Capteurs", "CA", f"Capteur {ref} ({variante})", random.uniform(6, 60),
                desc, f"Capteur {ref} — {desc}. Livré en version {variante}.")

# ============================================================
# MOTEURS & ROUES (code MR)
# ============================================================
for modele, couple in [("SG90", "1.8kg/cm"), ("MG90S", "2.2kg/cm"), ("MG996R", "10kg/cm"),
                        ("DS3218", "20kg/cm"), ("Servo continu FS90R", "1.5kg/cm"), ("Servo étanche DS3218MG", "20kg/cm")]:
    add_row("Moteurs & Roues", "MR", f"Servomoteur {modele}", random.uniform(9, 55),
            f"Couple {couple}, rotation 0-180° (sauf continu)", f"Servomoteur {modele}, couple {couple}.")

for modele in ["28BYJ-48 + ULN2003", "NEMA17 0.9°", "NEMA17 1.8°", "NEMA23", "NEMA14 mini"]:
    for courant in ["1A", "1.5A", "2A", "2.5A"]:
        add_row("Moteurs & Roues", "MR", f"Moteur pas-à-pas {modele} ({courant})", random.uniform(10, 65),
                f"Angle de pas selon modèle, courant {courant}", f"Moteur pas-à-pas {modele}, courant nominal {courant}.")

for voltage in ["3V", "6V", "9V", "12V", "24V"]:
    for rpm in ["low RPM (geared)", "medium RPM", "high RPM"]:
        add_row("Moteurs & Roues", "MR", f"Moteur DC {voltage} ({rpm})", random.uniform(5, 25),
                f"Alimentation {voltage}, {rpm}", f"Moteur à courant continu {voltage}, {rpm}.")

for diam in [40, 42, 48, 60, 65, 66, 70, 80, 100, 120]:
    for matiere in ["caoutchouc", "plastique", "mousse (foam)"]:
        add_row("Moteurs & Roues", "MR", f"Roue {diam}mm ({matiere})", random.uniform(3, 12),
                f"Diamètre {diam}mm, matière {matiere}", f"Roue {diam}mm en {matiere} pour robot mobile.")

for item in ["Chenilles pour robot chenillé (paire)", "Encodeur rotatif KY-040", "Encodeur incrémental optique",
             "Moteur brushless + ESC 30A", "Moteur brushless + ESC 50A"]:
    add_row("Moteurs & Roues", "MR", item, random.uniform(6, 90), "Voir fiche technique", f"{item}.")

# ============================================================
# AFFICHEURS (code AF)
# ============================================================
for taille in ["0.91\"", "0.96\"", "1.3\"", "1.5\"", "2.42\""]:
    for couleur in ["monochrome blanc", "monochrome bleu", "bicolore jaune/bleu"]:
        for interface in ["I2C", "SPI"]:
            add_row("Afficheurs", "AF", f"Écran OLED {taille} {couleur} ({interface})", random.uniform(10, 45),
                    f"Résolution selon taille, interface {interface}", f"Écran OLED {taille}, {couleur}, interface {interface}.")

for fmt in ["16x2", "20x4", "16x1", "20x2"]:
    for interface in ["I2C (module ajouté)", "parallèle 4/8 bits"]:
        add_row("Afficheurs", "AF", f"Écran LCD {fmt} ({interface})", random.uniform(9, 22),
                f"Format {fmt} caractères, {interface}", f"Écran LCD alphanumérique {fmt}, {interface}.")

for taille in ["1.44\"", "1.8\"", "2.0\"", "2.2\"", "2.4\"", "2.8\"", "3.2\"", "3.5\""]:
    for tactile in ["tactile résistif", "sans tactile"]:
        add_row("Afficheurs", "AF", f"Écran TFT couleur {taille} ({tactile})", random.uniform(15, 70),
                f"Écran couleur {taille}, {tactile}", f"Écran TFT {taille}, {tactile}, compatible Arduino/ESP32.")

for digits in [1, 2, 4, 6, 8]:
    for couleur in ["rouge", "vert", "bleu", "jaune"]:
        add_row("Afficheurs", "AF", f"Afficheur 7 segments {digits} chiffre(s) ({couleur})", random.uniform(4, 15),
                f"{digits} chiffre(s), couleur {couleur}", f"Afficheur 7 segments {digits} chiffres, couleur {couleur}.")

for item in ["Matrice LED 8x8 monochrome", "Matrice LED 8x8 RGB", "Matrice LED 16x16 monochrome",
             "Écran e-paper 1.54\"", "Écran e-paper 2.13\"", "Écran e-paper 2.9\"", "Écran e-paper 4.2\""]:
    add_row("Afficheurs", "AF", item, random.uniform(15, 90), "Voir fiche technique", f"{item}.")

# ============================================================
# KITS & PROTOTYPAGE (code KP)
# ============================================================
for taille in [400, 830, 1660]:
    for couleur in ["blanche", "transparente", "verte"]:
        add_row("Kits & Prototypage", "KP", f"Breadboard {taille} points ({couleur})", random.uniform(5, 25),
                f"{taille} points de connexion", f"Plaque d'essai sans soudure {taille} points, {couleur}.")

for niveau in ["débutant", "intermédiaire", "avancé"]:
    for theme in ["Arduino", "ESP32/IoT", "Raspberry Pi", "Robotique", "Domotique"]:
        add_row("Kits & Prototypage", "KP", f"Kit de démarrage {theme} — niveau {niveau}", random.uniform(45, 250),
                f"Kit {niveau} orienté {theme}", f"Kit complet {niveau} pour démarrer un projet {theme}.")

for modele in ["Ender-3 V2", "Ender-3 S1", "Creality K1", "Prusa Mini+", "Anycubic Kobra 2", "Voxelab Aquila"]:
    add_row("Kits & Prototypage", "KP", f"Imprimante 3D {modele} (kit assemblage)", random.uniform(750, 2500),
            "Volume d'impression variable selon modèle", f"Imprimante 3D FDM {modele}.")

for matiere in ["PLA", "ABS", "PETG", "TPU (flexible)", "PLA+"]:
    for couleur in ["blanc", "noir", "rouge", "bleu", "vert", "jaune", "orange", "gris", "transparent",
                     "rose", "violet", "marron", "or", "argent", "phosphorescent", "bois (wood fill)",
                     "cuivre (métal fill)", "bleu ciel", "vert fluo", "noir mat"]:
        for poids in ["250g", "500g", "1kg"]:
            add_row("Kits & Prototypage", "KP", f"Filament {matiere} {couleur} ({poids})", random.uniform(28, 65),
                    f"Diamètre 1.75mm, {matiere}, {poids}", f"Bobine de filament d'impression 3D {matiere} {couleur}, {poids}.")

for item in ["Kit de soudure débutant complet", "Kit de soudure avancé (station incluse)",
             "Kit robotique éducatif niveau collège", "Kit robotique éducatif niveau lycée",
             "Kit capteurs IoT complet (10 capteurs)"]:
    add_row("Kits & Prototypage", "KP", item, random.uniform(50, 180), "Voir contenu détaillé", f"{item}.")

# ============================================================
# COMPOSANTS (code CO)
# ============================================================
e24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]
decades = [(1, "Ω"), (10, "Ω"), (100, "Ω"), (1000, "kΩ"), (10000, "kΩ"), (100000, "kΩ"), (1000000, "MΩ")]

def format_ohm(base, mult, unit):
    val = base * mult
    if unit == "kΩ":
        val = val / 1000
    elif unit == "MΩ":
        val = val / 1000000
    return f"{val:g}{unit}"

for base in e24:
    for mult, unit in decades:
        valeur_str = format_ohm(base, mult, unit)
        for puissance in ["1/8W", "1/4W", "1/2W", "1W"]:
            for tol in ["±1%", "±5%", "±10%"]:
                for package in ["traversant (THT)", "CMS 0805", "CMS 1206", "CMS 0603"]:
                    add_row("Composants", "CO", f"Résistance {valeur_str} {puissance} {tol} ({package})",
                            0.15 + puissance.count("/") * 0.05,
                            f"{valeur_str}, {puissance}, tolérance {tol}, {package}",
                            f"Résistance {valeur_str}, {puissance}, {tol}, boîtier {package}.",
                            dispo_weights=(85, 8, 4, 3))

for valeur in [1, 2.2, 4.7, 10, 22, 47, 100, 220, 470, 1000, 2200, 4700, 10000, 22000, 47000]:
    unit = "nF" if valeur >= 1 else "pF"
    for tension in ["16V", "25V", "50V", "100V", "250V"]:
        add_row("Composants", "CO", f"Condensateur céramique {valeur}{unit} {tension}", random.uniform(0.2, 1.5),
                f"{valeur}{unit}, {tension}, céramique multicouche", f"Condensateur céramique {valeur}{unit}, tension max {tension}.")

for valeur in [1, 2.2, 4.7, 10, 22, 33, 47, 100, 220, 330, 470, 680, 1000, 2200, 3300, 4700, 6800, 10000]:
    for tension in ["6.3V", "10V", "16V", "25V", "35V", "50V", "63V"]:
        add_row("Composants", "CO", f"Condensateur électrolytique {valeur}µF {tension}", random.uniform(0.3, 3.5),
                f"{valeur}µF, {tension}, électrolytique radial", f"Condensateur chimique {valeur}µF, tension max {tension}.")

for couleur in ["rouge", "vert", "bleu", "jaune", "blanc", "orange", "UV", "infrarouge", "RGB", "rose"]:
    for taille in ["3mm", "5mm", "8mm", "10mm"]:
        for type_ in ["diffusé", "clair haute luminosité"]:
            add_row("Composants", "CO", f"LED {couleur} {taille} ({type_})", random.uniform(0.15, 1.2),
                    f"{couleur}, {taille}, {type_}", f"LED {couleur} {taille}, finition {type_}.")

for valeur in ["1k", "5k", "10k", "20k", "50k", "100k", "250k", "470k", "1M"]:
    for type_ in ["linéaire", "logarithmique", "multitours (10 tours)"]:
        add_row("Composants", "CO", f"Potentiomètre {valeur}Ω ({type_})", random.uniform(1, 6),
                f"{valeur}Ω, {type_}", f"Potentiomètre {valeur}Ω, réponse {type_}.")

for ref, desc in [("1N4001", "diode redressement 1A"), ("1N4007", "diode redressement 1A 1000V"),
                   ("1N4148", "diode signal rapide"), ("1N5819", "diode Schottky"),
                   ("1N5399", "diode redressement 1.5A"), ("BAT85", "diode Schottky petit signal"),
                   ("Zener 3.3V", "diode zener régulation"), ("Zener 5.1V", "diode zener régulation"),
                   ("Zener 9.1V", "diode zener régulation"), ("Zener 12V", "diode zener régulation"),
                   ("Zener 15V", "diode zener régulation"), ("Pont de diodes 1A", "redressement pont complet"),
                   ("Pont de diodes 4A", "redressement pont complet"), ("LED laser 5mW", "module laser"),
                   ("Varistance MOV 275V", "protection surtension"), ("TVS diode ESD", "protection décharge électrostatique")]:
    add_row("Composants", "CO", f"Diode {ref}", random.uniform(0.3, 2.5), desc, f"{ref} — {desc}.")

for ref, desc in [("2N2222", "transistor NPN usage général"), ("2N3904", "transistor NPN"),
                   ("2N3906", "transistor PNP"), ("BC547", "transistor NPN"), ("BC557", "transistor PNP"),
                   ("BC337", "transistor NPN puissance moyenne"), ("TIP31", "transistor NPN puissance"),
                   ("TIP32", "transistor PNP puissance"), ("TIP120", "transistor Darlington NPN"),
                   ("IRF540N", "MOSFET canal N"), ("IRFZ44N", "MOSFET canal N"), ("IRF9540", "MOSFET canal P"),
                   ("2N7000", "MOSFET signal N"), ("MJE13005", "transistor NPN haute tension"),
                   ("D882", "transistor NPN audio"), ("A733", "transistor PNP audio")]:
    add_row("Composants", "CO", f"Transistor {ref}", random.uniform(0.4, 3.5), desc, f"{ref} — {desc}.")

for ref, desc in [("LM358", "double ampli-op"), ("LM324", "quadruple ampli-op"), ("TL071", "ampli-op faible bruit"),
                   ("NE5532", "double ampli-op audio"), ("LM741", "ampli-op classique"),
                   ("555", "timer classique"), ("556", "double timer"),
                   ("7805", "régulateur 5V"), ("7812", "régulateur 12V"), ("7809", "régulateur 9V"),
                   ("7912", "régulateur -12V"), ("LM317", "régulateur ajustable"), ("LM337", "régulateur négatif ajustable"),
                   ("74HC00", "quadruple NAND"), ("74HC04", "hexa inverseur"), ("74HC08", "quadruple AND"),
                   ("74HC32", "quadruple OR"), ("74HC595", "registre à décalage"), ("74HC165", "registre entrée parallèle"),
                   ("CD4017", "compteur décade"), ("CD4511", "décodeur BCD 7-segments"),
                   ("ATmega328P", "microcontrôleur AVR (nu)"), ("PCF8574", "extenseur GPIO I2C"),
                   ("MCP23017", "extenseur GPIO 16 bits I2C"), ("MAX232", "convertisseur niveau RS232"),
                   ("ULN2803", "réseau de transistors Darlington"), ("optocoupleur PC817", "isolation optique"),
                   ("MAX7219", "driver afficheur/matrice LED"), ("DS18B20", "capteur température numérique"),
                   ("AMS1117-3.3", "régulateur SMD 3.3V"), ("TP4056", "module charge lithium")]:
    add_row("Composants", "CO", f"Circuit intégré {ref}", random.uniform(1, 8), desc, f"{ref} — {desc}.")

for freq in ["4MHz", "8MHz", "11.0592MHz", "12MHz", "16MHz", "20MHz", "24MHz", "25MHz", "32.768kHz", "27MHz"]:
    add_row("Composants", "CO", f"Résonateur/Quartz {freq}", random.uniform(0.5, 2.5),
            f"Fréquence {freq}", f"Quartz/résonateur céramique {freq}.")

for item, prix in [("Bouton poussoir tactile 6x6mm", 0.3), ("Bouton poussoir tactile 12x12mm", 0.5),
                    ("Interrupteur à bascule (rocker)", 1.5), ("Interrupteur glissière SPDT", 1.2),
                    ("DIP switch 2 positions", 1.0), ("DIP switch 4 positions", 1.5),
                    ("DIP switch 8 positions", 2.5), ("Bouton arcade rouge", 3.5), ("Bouton arcade bleu", 3.5),
                    ("Bouton arcade vert", 3.5), ("Bouton arcade jaune", 3.5), ("Bouton arcade blanc", 3.5),
                    ("Bouton poussoir étanche 12mm", 2.8), ("Micro-switch fin de course", 1.8),
                    ("Bouton d'arrêt d'urgence", 12), ("Buzzer piezo passif", 1.5), ("Buzzer actif 5V", 2.0),
                    ("Haut-parleur 8Ω 0.5W", 4.5), ("Haut-parleur 8Ω 2W", 7.0), ("Vibreur moteur (coin vibrator)", 3.0)]:
    add_row("Composants", "CO", item, prix, "Voir fiche technique", f"{item}.")

# ============================================================
# INSTRUMENTS DE MESURE (code IM)
# ============================================================
for gamme in ["entrée de gamme", "milieu de gamme", "professionnelle"]:
    for fonction in ["basique", "True-RMS"]:
        add_row("Instruments de Mesure", "IM", f"Multimètre numérique ({gamme}, {fonction})", random.uniform(18, 140),
                f"Gamme {gamme}, mesure {fonction}", f"Multimètre {gamme}, fonction {fonction}.")

for bp in ["10MHz", "20MHz", "50MHz", "100MHz", "200MHz"]:
    for canaux in [1, 2, 4]:
        add_row("Instruments de Mesure", "IM", f"Oscilloscope numérique {bp} ({canaux} canaux)", random.uniform(90, 950),
                f"Bande passante {bp}, {canaux} canaux", f"Oscilloscope {bp}, {canaux} voies d'acquisition.")

for item, prix in [("Pince ampèremétrique 200A", 45), ("Pince ampèremétrique 600A", 65), ("Pince ampèremétrique 1000A", 95),
                    ("Générateur de fonctions 1MHz", 85), ("Générateur de fonctions 5MHz", 130),
                    ("Générateur de fonctions 10MHz", 180), ("LCR-mètre de poche", 55), ("LCR-mètre de table", 210),
                    ("Testeur de composants (transistor tester)", 35), ("Analyseur logique 8 canaux", 40),
                    ("Analyseur logique 16 canaux", 75), ("Thermomètre infrarouge", 28), ("Sonde de température K", 15),
                    ("Sonde oscilloscope x10", 25), ("Sonde oscilloscope différentielle", 90)]:
    add_row("Instruments de Mesure", "IM", item, prix, "Voir fiche technique", f"{item}.")

# ============================================================
# OUTILLAGE (code OU)
# ============================================================
for puissance in ["30W", "40W", "60W", "80W", "100W"]:
    for type_ in ["température fixe", "température réglable"]:
        add_row("Outillage", "OU", f"Fer à souder {puissance} ({type_})", random.uniform(15, 60),
                f"{puissance}, {type_}", f"Fer à souder électrique {puissance}, {type_}.")

for item, prix in [("Station de soudure air chaud + fer", 165), ("Station de soudure air chaud seule", 120),
                    ("Pince coupante précision", 8), ("Pince à dénuder professionnelle", 12),
                    ("Pince brucelles droite", 4), ("Pince brucelles courbée", 4.5), ("Pince multiprise", 15),
                    ("Kit tournevis précision 21 pièces", 22), ("Kit tournevis précision 32 pièces", 30),
                    ("Kit tournevis précision 68 pièces", 45), ("Troisième main avec loupe", 20),
                    ("Loupe frontale avec éclairage LED", 18), ("Loupe de table avec éclairage", 25),
                    ("Étain à souder 60/40 (100g)", 12), ("Étain à souder sans plomb (100g)", 16),
                    ("Flux de soudure (pot)", 6), ("Pompe à dessouder", 5), ("Tresse à dessouder", 3.5),
                    ("Tapis de soudure anti-statique", 20), ("Établi/plateau de travail électronique", 45),
                    ("Bracelet antistatique", 4), ("Pistolet à colle chaude", 15), ("Cutter de précision", 5),
                    ("Multimètre de poche basique", 12), ("Testeur de tension sans contact", 10)]:
    add_row("Outillage", "OU", item, prix, "Voir fiche technique", f"{item}.")

# ============================================================
# ALIMENTATION (code AL)
# ============================================================
for capacite in ["1200mAh", "2200mAh", "2600mAh", "3000mAh", "3500mAh", "3800mAh"]:
    for marque in ["générique", "protégée (avec circuit PCB)", "haute décharge (high-drain)"]:
        add_row("Alimentation", "AL", f"Batterie 18650 {capacite} ({marque})", random.uniform(8, 22),
                f"Li-ion 3.7V, {capacite}, {marque}", f"Batterie rechargeable 18650 {capacite}, version {marque}.")

for type_pile in ["AA", "AAA", "9V", "CR2032", "18650", "LiPo 3.7V 500mAh", "LiPo 3.7V 1000mAh", "LiPo 3.7V 2000mAh"]:
    for qty in ["pack de 4", "pack de 10", "pack de 20"]:
        add_row("Alimentation", "AL", f"Pile/Batterie {type_pile} ({qty})", random.uniform(4, 35),
                f"Type {type_pile}, {qty}", f"Piles/batteries {type_pile}, conditionnement {qty}.")

for item, prix in [("Panneau solaire 5V 0.5W", 10), ("Panneau solaire 5V 1W", 15), ("Panneau solaire 6V 2W", 22),
                    ("Panneau solaire 12V 5W", 45), ("Panneau solaire 12V 10W", 75), ("Panneau solaire 18V 20W", 130),
                    ("Chargeur batteries 18650 (2 slots)", 19), ("Chargeur batteries 18650 (4 slots)", 28),
                    ("Chargeur universel LiPo/Li-ion", 35), ("Module TP4056 (charge USB-C)", 3),
                    ("Module boost 5V (powerbank DIY)", 4), ("Powerbank DIY complet (boîtier + module)", 15),
                    ("Alimentation labo réglable 0-30V 5A", 195), ("Alimentation labo réglable 0-30V 10A", 320),
                    ("Bloc secteur 5V 2A", 12), ("Bloc secteur 9V 1A", 10), ("Bloc secteur 12V 2A", 15),
                    ("Bloc secteur 12V 5A", 25), ("Bloc secteur 24V 3A", 22), ("Support pile AA (x4) avec fil", 3),
                    ("Support pile 9V avec connecteur", 2), ("Support batterie 18650 (x1) avec fil", 2.5),
                    ("Support batterie 18650 (x2) avec fil", 4)]:
    add_row("Alimentation", "AL", item, prix, "Voir fiche technique", f"{item}.")

# ============================================================
# CONNECTIQUE (code CN)
# ============================================================
for type_ in ["Mâle-Mâle", "Mâle-Femelle", "Femelle-Femelle"]:
    for longueur in [5, 10, 15, 20, 25, 30, 40, 50, 60, 100]:
        for qty in [10, 20, 30, 40, 50, 65, 80, 100]:
            add_row("Connectique", "CN", f"Câbles Dupont {type_} {longueur}cm (lot de {qty})", random.uniform(2, 18),
                    f"{type_}, {longueur}cm, lot de {qty}", f"Câbles de prototypage Dupont {type_}, {longueur}cm.",
                    dispo_weights=(80, 10, 5, 5))

for pins in range(1, 41):
    for type_ in ["droit", "coudé 90°", "femelle empilable", "double rangée droite"]:
        for pitch in ["2.54mm", "2.0mm", "1.27mm"]:
            add_row("Connectique", "CN", f"Barrette {pins} broches ({type_}, pas {pitch})", random.uniform(0.5, 4),
                    f"{pins} broches, {type_}, pas {pitch}", f"Barrette de connecteurs {pins} broches, {type_}, pas {pitch}.",
                    dispo_weights=(82, 9, 5, 4))

for pins in range(2, 13):
    for genre in ["mâle", "femelle", "paire mâle-femelle"]:
        for serie in ["JST-XH", "JST-PH"]:
            add_row("Connectique", "CN", f"Connecteur {serie} {pins} broches ({genre})", random.uniform(0.8, 3.5),
                    f"{serie}, {pins} broches, {genre}", f"Connecteur {serie} {pins} broches, {genre}.")

for pins in range(2, 25):
    for pas in ["2.54mm", "3.5mm", "5.08mm", "7.5mm"]:
        add_row("Connectique", "CN", f"Bornier à vis {pins} positions (pas {pas})", random.uniform(1, 6),
                f"{pins} positions, pas {pas}", f"Bornier à vis {pins} positions, pas {pas}.")

for diam in [1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 40]:
    for couleur in ["noir", "rouge", "transparent", "multicolore (kit)", "bleu", "jaune"]:
        add_row("Connectique", "CN", f"Gaine thermorétractable Ø{diam}mm ({couleur}, 1m)", random.uniform(0.8, 5),
                f"Diamètre {diam}mm, {couleur}, ratio 2:1", f"Gaine thermorétractable Ø{diam}mm, couleur {couleur}.")

for conducteurs in [4, 6, 8, 10, 16, 20, 26, 34, 40, 50]:
    for longueur in ["1m", "2m", "5m"]:
        add_row("Connectique", "CN", f"Câble ruban {conducteurs} conducteurs ({longueur})", random.uniform(2, 15),
                f"{conducteurs} conducteurs, {longueur}", f"Câble plat ruban {conducteurs} conducteurs, {longueur}.")

for type_ in ["USB-A vers Micro-USB", "USB-A vers USB-C", "USB-A vers Mini-USB", "USB-C vers USB-C", "USB-A vers USB-A"]:
    for longueur in ["0.3m", "0.5m", "1m", "1.5m", "2m", "3m", "5m", "10m"]:
        add_row("Connectique", "CN", f"Câble {type_} ({longueur})", random.uniform(2, 12),
                f"{type_}, {longueur}", f"Câble {type_}, longueur {longueur}.")

for couleur in ["rouge", "noir", "jaune", "vert", "bleu", "blanc"]:
    for genre in ["mâle", "femelle"]:
        add_row("Connectique", "CN", f"Connecteur banane {couleur} ({genre})", random.uniform(0.8, 2.5),
                f"{couleur}, {genre}", f"Connecteur banane 4mm, {couleur}, {genre}.")

for item, prix in [("Fiche alimentation DC 5.5x2.1mm mâle", 1.2), ("Fiche alimentation DC 5.5x2.1mm femelle", 1.5),
                    ("Fiche alimentation DC 3.5x1.3mm mâle", 1.2), ("Fiche alimentation DC 2.5x0.7mm mâle", 1.2),
                    ("Connecteur batterie XT30 (paire)", 2.5), ("Connecteur batterie XT60 (paire)", 3.5),
                    ("Connecteur batterie XT90 (paire)", 5), ("Connecteur batterie Deans (paire)", 3),
                    ("Connecteur batterie JST-PH (paire)", 1.5), ("Connecteur servo Tamiya (paire)", 2),
                    ("Cosse électrique œillet (lot 50)", 4), ("Cosse électrique fourche (lot 50)", 4),
                    ("Cosse électrique droite (lot 50)", 4), ("Cosse électrique femelle (lot 50)", 4.5),
                    ("Domino électrique 12 positions", 2), ("Bloc de jonction rapide (lot 20)", 5)]:
    add_row("Connectique", "CN", item, prix, "Voir fiche technique", f"{item}.")

# ============================================================
# ÉCLAIRAGE LED (code EL)
# ============================================================
longueurs_ruban = ["0.5m", "1m", "1.5m", "2m", "2.5m", "3m", "4m", "5m", "6m", "8m", "10m", "15m"]

for longueur in longueurs_ruban:
    for densite in ["30 LED/m", "60 LED/m", "74 LED/m", "96 LED/m", "144 LED/m"]:
        for ip in ["IP20 (intérieur)", "IP65 (résistant éclaboussures)", "IP67 (étanche)"]:
            add_row("Éclairage LED", "EL", f"Ruban LED WS2812B adressable {longueur} ({densite}, {ip})", random.uniform(15, 120),
                    f"{longueur}, {densite}, {ip}, adressable individuellement", f"Ruban LED RGB adressable WS2812B, {longueur}, {densite}, {ip}.")

for longueur in longueurs_ruban:
    for densite in ["30 LED/m", "60 LED/m", "144 LED/m"]:
        add_row("Éclairage LED", "EL", f"Ruban LED SK6812 RGBW {longueur} ({densite})", random.uniform(18, 130),
                f"{longueur}, {densite}, RGBW adressable", f"Ruban LED RGBW adressable SK6812, {longueur}, {densite}.")
        add_row("Éclairage LED", "EL", f"Ruban LED RGB analogique {longueur} ({densite})", random.uniform(10, 90),
                f"{longueur}, {densite}, RGB non-adressable", f"Ruban LED RGB analogique, {longueur}, {densite}.")

for longueur in longueurs_ruban:
    for couleur in ["blanc chaud 3000K", "blanc neutre 4000K", "blanc froid 6000K", "rouge", "vert", "bleu", "jaune"]:
        for ip in ["IP20", "IP65"]:
            add_row("Éclairage LED", "EL", f"Ruban LED mono {couleur} {longueur} ({ip})", random.uniform(8, 70),
                    f"{longueur}, {couleur}, {ip}", f"Ruban LED monochrome {couleur}, {longueur}, {ip}.")

for longueur in ["1m", "2m", "3m", "5m", "8m"]:
    for couleur in ["blanc", "rouge", "vert", "bleu", "jaune", "rose", "violet", "orange"]:
        add_row("Éclairage LED", "EL", f"Néon flex LED {couleur} ({longueur})", random.uniform(12, 55),
                f"{longueur}, couleur {couleur}, flexible", f"Néon flexible à LED, couleur {couleur}, {longueur}.")

for item, prix in [("Contrôleur LED RGB (télécommande IR)", 8), ("Contrôleur LED RGB (Bluetooth app)", 15),
                    ("Contrôleur LED adressable (WLED compatible)", 22), ("Amplificateur signal RGB", 10),
                    ("Profilé aluminium pour ruban LED 1m", 6), ("Profilé aluminium pour ruban LED 2m", 11),
                    ("Diffuseur opale pour profilé LED", 3), ("Alimentation dédiée ruban LED 12V 5A", 20),
                    ("Alimentation dédiée ruban LED 12V 10A", 35), ("Connecteur rapide ruban LED (paire)", 1.5)]:
    add_row("Éclairage LED", "EL", item, prix, "Voir fiche technique", f"{item}.")

for longueur in longueurs_ruban:
    for temp in ["2700K", "3000K", "4000K", "6000K"]:
        add_row("Éclairage LED", "EL", f"Ruban LED COB haute densité {longueur} ({temp})", random.uniform(20, 140),
                f"{longueur}, densité continue (sans points visibles), {temp}", f"Ruban LED COB {longueur}, {temp}, éclairage homogène.")

for puissance in ["5W", "7W", "9W", "12W", "15W"]:
    for temp in ["blanc chaud 2700K", "blanc neutre 4000K", "blanc froid 6500K"]:
        add_row("Éclairage LED", "EL", f"Ampoule LED E27 {puissance} ({temp})", random.uniform(4, 14),
                f"Culot E27, {puissance}, {temp}", f"Ampoule LED E27 {puissance}, {temp}.")

for puissance in ["3W", "5W", "7W"]:
    for temp in ["blanc chaud", "blanc neutre", "blanc froid"]:
        add_row("Éclairage LED", "EL", f"Spot LED encastrable {puissance} ({temp})", random.uniform(6, 18),
                f"{puissance}, {temp}, encastrable", f"Spot LED encastrable {puissance}, {temp}.")


# ============================================================
# Écriture du CSV
# ============================================================
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["sku", "nom", "categorie", "prix_dt", "disponibilite", "caracteristiques", "description"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

print(f"✅ {len(rows)} produits générés dans {OUTPUT_PATH}")

# Répartition par catégorie
from collections import Counter
counts = Counter(r["categorie"] for r in rows)
for cat, n in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {n}")
