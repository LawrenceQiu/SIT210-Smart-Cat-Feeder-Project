#!/usr/bin/env python3
"""
feeder_rspi.py
--------------
Tkinter GUI that:
 - Reads RFID tags via PiicoDev
 - For an authorized tag, GETs weight from Arduino over HTTP
 - Dispenses food via PiicoDev Servo if weight < threshold
 - Manages authorized/unauthorized lists and logging of feed data
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import requests
from PiicoDev_RFID import PiicoDev_RFID
from PiicoDev_Servo import PiicoDev_Servo, PiicoDev_Servo_Driver
from PiicoDev_Unified import sleep_ms
import threading
import time
import json
import os
import csv
from datetime import datetime

# Configuration
ARDUINO_IP = "" #Enter Arduino IP here
ARDUINO_URL = f"http://{ARDUINO_IP}/weight"
WEIGHT_THRESHOLD = 20.0  # grams
TAG_FILE = "authorized_tags.json"
LOG_FILE = "feeding_log.csv"

# Load/Save Authorized Tags
def load_authorized_tags():
    if os.path.exists(TAG_FILE):
        try:
            with open(TAG_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_authorized_tags():
    with open(TAG_FILE, "w") as f:
        json.dump(authorized_tags, f, indent=2)

# CSV Logging
def log_dispense(tag, pet_name, grams):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, mode="a", newline="") as f:
        csv.writer(f).writerow([timestamp, tag, pet_name, grams])

def get_logs_for_tag(tag):
    entries = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 4 and row[1] == tag:
                    entries.append(row)
    return entries

# Initial Data
authorized_tags = load_authorized_tags()  # { tag: pet_name }
unauthorized_tags = []

# Hardware Setup
rfid = PiicoDev_RFID()
servo_driver = PiicoDev_Servo_Driver()
servo = PiicoDev_Servo(servo_driver, 1)
servo.angle = 10  # Closed

# GUI Setup
root = tk.Tk()
root.title("Smart Cat Feeder GUI")
root.geometry("500x600")

tag_status = tk.StringVar(value="Waiting for tag...")
weight_status = tk.StringVar(value="Current weight: -- g")

# Status Display
tk.Label(root, text="RFID Tag Status:", font=("Arial", 14)).pack(pady=10)
status_label = tk.Label(root, textvariable=tag_status, font=("Arial", 12))
status_label.pack(pady=5)

tk.Label(root, textvariable=weight_status, font=("Arial", 12, "italic")).pack(pady=5)

# Unauthorized List
tk.Label(root, text="Unauthorized Tags").pack()
unauth_listbox = tk.Listbox(root, height=5)
unauth_listbox.pack(fill=tk.X, padx=10)

# Authorized Pets List
tk.Label(root, text="Authorized Pets").pack(pady=(10, 0))
auth_listbox = tk.Listbox(root, height=5)
auth_listbox.pack(fill=tk.X, padx=10)

def refresh_auth_listbox():
    auth_listbox.delete(0, tk.END)
    for tag, name in authorized_tags.items():
        auth_listbox.insert(tk.END, f"{name} -> {tag}")

refresh_auth_listbox()

# Dispense Logic
def dispense_food(tag, pet_name):
    try:
        before = requests.get(ARDUINO_URL, timeout=2)
        weight_before = float(before.json().get("weight", 0.0))

        servo.angle = 60  # Open
        time.sleep(2)
        servo.angle = 10  # Close

        time.sleep(1)
        after = requests.get(ARDUINO_URL, timeout=2)
        weight_after = float(after.json().get("weight", 0.0))

        dispensed = max(0.0, weight_after - weight_before)
        log_dispense(tag or "manual", pet_name, f"{dispensed:.1f}")
        print(f"Dispensed: {dispensed:.1f} g")
    except Exception as e:
        print("Error in dispense_food:", e)

# RFID Loop
def rfid_loop():
    while True:
        if rfid.tagPresent():
            tag = rfid.readID()
            if tag:
                if tag in authorized_tags:
                    pet = authorized_tags[tag]
                    tag_status.set(f"[AUTHORIZED] {pet} ({tag})")
                    status_label.config(fg="green")

                    try:
                        resp = requests.get(ARDUINO_URL, timeout=2)
                        weight = float(resp.json().get("weight", 0.0))
                        print(f"Weight from Arduino: {weight:.2f} g")
                        if weight < WEIGHT_THRESHOLD:
                            threading.Thread(target=dispense_food, args=(tag, pet), daemon=True).start()
                        else:
                            print("Above threshold - no dispense")
                    except Exception as e:
                        print("HTTP error:", e)
                elif tag not in unauthorized_tags:
                    unauthorized_tags.append(tag)
                    unauth_listbox.insert(tk.END, tag)
                    tag_status.set(f"[UNAUTHORIZED] {tag}")
                    status_label.config(fg="red")
                else:
                    tag_status.set(f"[UNAUTHORIZED - Logged] {tag}")
                    status_label.config(fg="red")
        sleep_ms(200)  # Faster polling

# Live weight update
def live_weight_loop():
    while True:
        try:
            resp = requests.get(ARDUINO_URL, timeout=2)
            weight = float(resp.json().get("weight", 0.0))
            weight_status.set(f"Current weight: {weight:.1f} g")
        except:
            weight_status.set("Current weight: -- g")
        time.sleep(0.5)

threading.Thread(target=rfid_loop, daemon=True).start()
threading.Thread(target=live_weight_loop, daemon=True).start()

# Authorize Selected Tag
def authorize_selected_tag():
    sel = unauth_listbox.curselection()
    if not sel:
        messagebox.showwarning("No Selection", "Select a tag first.")
        return
    tag = unauth_listbox.get(sel[0])
    pet = simpledialog.askstring("Pet Name", f"Enter pet name for {tag}:")
    if pet:
        authorized_tags[tag] = pet
        save_authorized_tags()
        unauthorized_tags.remove(tag)
        unauth_listbox.delete(sel[0])
        refresh_auth_listbox()
        messagebox.showinfo("Authorized", f"{pet} authorized.")
    else:
        messagebox.showwarning("Cancelled", "No name - authorization cancelled.")

tk.Button(root, text="Authorize Selected Tag", command=authorize_selected_tag).pack(pady=10)

# Manual Dispense
def manual_dispense():
    threading.Thread(target=lambda: dispense_food(None, "Manual"), daemon=True).start()
    tag_status.set("[MANUAL] Dispense")
    status_label.config(fg="blue")

tk.Button(root, text="Manual Dispense", command=manual_dispense).pack(pady=5)

# View Log for Selected Pet
def view_log_for_selected_pet():
    sel = auth_listbox.curselection()
    if not sel:
        messagebox.showwarning("No Selection", "Select a pet first.")
        return
    entry = auth_listbox.get(sel[0])
    name, tag = [s.strip() for s in entry.split("->")]
    logs = get_logs_for_tag(tag)
    if not logs:
        messagebox.showinfo("No Logs", f"No RFID logs for {name}.")
        return

    win = tk.Toplevel(root)
    win.title(f"Log - {name}")
    tk.Label(win, text=f"Feeding Log for {name}", font=("Arial", 12, "bold")).pack(pady=5)
    lb = tk.Listbox(win, width=50)
    lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    for row in logs:
        timestamp, _, _, grams = row
        lb.insert(tk.END, f"{timestamp} - {grams} g")

tk.Button(root, text="View Log for Selected Pet", command=view_log_for_selected_pet).pack(pady=5)

# Start GUI
root.mainloop()

